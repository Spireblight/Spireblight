from typing import Generator

import aiohttp_jinja2
import struct
import json
import os

from aiohttp.web import Request, Response, HTTPServiceUnavailable, HTTPForbidden, FileField

from src.monster.replay import parse
from src.monster.static import get, get_safe, get_champion, Challenge, Mutator, Artifact, Character, Mutator2, Soul
from src.webpage import router
from src.utils import get_req_data, getfile, catch_error

from src.typehints import ContextType

from src.config import config

def parse_value(v: list[int], *, little_endian=True) -> int:
    """Parse and unpack the various structs used for gold and other values."""
    assert len(v) % 8 == 0, "can only unpack multiples of 8"
    val = bytes(v)
    fs = "<" if little_endian else ">"
    fs += "d" * len(v) // 8 # one double per 8 bytes
    unpacked = struct.unpack(fs, val)
    return int(sum(unpacked))

class MonsterSave:
    def __init__(self, file):
        data = None
        try:
            with getfile(file, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self._data = data

    def update_data(self, data: dict):
        self._data = data

    def _asint(self, key: str) -> int:
        return parse_value(self._data[key]["_values"])

    def get_fight_names(self) -> list[str]:
        """Get the list of run snapshots for "over time" stats."""
        return [] # TODO

    @property
    def current_gold(self) -> int:
        """The current count of gold. Ignores in-fight gains."""
        # TODO: we have a "goldOverTime" array which may be useful for... something
        return self._asint("gold")

    @property
    def dragons_hoard(self) -> int:
        """The current count of Dragon's Hoard."""
        return self._asint("dragonsHoard")

    @property
    def dragons_hoard_cap(self) -> int:
        """The current limit of Dragon's Hoard we can hold."""
        return self._asint("dragonsHoardCap")

    @property
    def forge_points(self) -> int:
        """The current count of Forge Points being held."""
        return self._asint("forgePoints")

    @property
    def pyre_hp(self) -> int:
        """The current Pyre HP."""
        return self._asint("towerHP")

    @property
    def pyre_max_hp(self) -> int:
        """The Pyre Max HP."""
        return self._asint("maxTowerHP")

    @property
    def in_game(self) -> bool:
        # XXX: there might be a few more pieces to check
        return not self._data

    @property
    def champion(self):
        return get_champion(self.main_class, self.main_exiled)

    @property
    def main_class(self) -> str:
        main = self._data["startingConditions"]["mainClassInfo"]
        if "className" in main:
            return _get_sanitized(main["className"])
        return _get_sanitized(main["classId"])

    @property
    def main_exiled(self) -> bool:
        return bool(self._data["startingConditions"]["mainClassInfo"]["championIndex"])

    @property
    def main_clan(self) -> str:
        if self.main_exiled:
            return f"{self.main_class} (Exiled)"
        return self.main_class

    @property
    def sub_class(self) -> str:
        sub = self._data["startingConditions"]["subclassInfo"]
        if "className" in sub:
            return _get_sanitized(sub["className"])
        return _get_sanitized(sub["classId"])

    @property
    def sub_exiled(self) -> bool:
        return bool(self._data["startingConditions"]["subclassInfo"]["championIndex"])

    @property
    def sub_clan(self) -> str:
        if self.sub_exiled:
            return f"{self.sub_class} (Exiled)"
        return self.sub_class

    @property
    def artifacts(self) -> Generator[Artifact, None, None]:
        for art in self._data["blessings"]:
            yield get(art["relicDataID"])

    @property
    def challenge(self) -> Challenge | None:
        ch = self._data["startingConditions"]["spChallengeId"]
        if ch:
            return get(ch)

    @property
    def covenant_level(self) -> int:
        return self._data["startingConditions"]["ascensionLevel"]

    @property
    def pyre(self) -> Character:
        return get(self._data["startingConditions"]["pyreCharacterId"])

    @property
    def mutators(self) -> list[Mutator | Mutator2]:
        return [get(x) for x in self._data["startingConditions"]["mutators"]]

    @property
    def souls(self) -> list[Soul]:
        return [get(x) for x in self._data["startingConditions"]["souls"]]

    @property
    def actions(self) -> list[str]:
        return [parse(x) for x in self._data["replayData"]["replayEntries"]]

_savefile = MonsterSave("monster-train-save.json")
_save2 = MonsterSave("monster-train-2-save.json")

async def get_savefile(ctx: ContextType | None = None) -> MonsterSave:
    if (_save2._data is not None and (_save2.main_class and _save2.sub_class)):
        return _save2

    if (_savefile._data is not None and (_savefile.main_class and _savefile.sub_class)):
        return _savefile

    if ctx is not None:
        await ctx.reply("Not in a run.")

@router.get("/mt2/current")
@catch_error
@aiohttp_jinja2.template("mt2_current.jinja2")
async def current_mt2(req: Request):
    context = {
        "save": _save2,
    }

    return context

@router.post("/sync/monster-train/save")
@catch_error
async def receive_save_data(req: Request):
    save, game_version = await get_req_data(req, "save", "game_version")
    data = json.loads(save)
    if game_version == "1":
        savefile = _savefile
        filename = "monster-train-save.json"
    elif game_version == "2":
        savefile = _save2
        filename = "monster-train-2-save.json"
    else:
        raise HTTPForbidden(reason="game_version can only be 1 or 2")

    savefile.update_data(data)

    with getfile(filename, "w") as f:
        json.dump(data, f, indent=config.server.json_indent)

    return Response()

# TODO: implement MT run sending and parsing

#@router.post("/sync/monster")
async def get_data(req: Request):
    save = (await get_req_data(req, "save"))[0]
    data = json.loads(save)
    _savefile.update_data(data)
    with open(os.path.join("data", "monster-train-save.json"), "w") as f:
        json.dump(data, f, indent=config.server.json_indent)

    # handle database stuff
    post = await req.post()

    def write_db(name: str):
        value = post[name]
        if isinstance(value, FileField):
            value = value.file.read()
        with open(os.path.join("data", f"mt-runs-{name}.sqlite3"), "wb") as f:
            f.write(value)

    for k in post:
        if k == "main" or k.isdigit() or k.endswith(".db"):
            write_db(k)

    return Response()

#@router.post("/sync/monster-2")
async def get_data(req: Request):
    save = (await get_req_data(req, "save"))[0]
    data = json.loads(save)
    _save2.update_data(data)
    with open(os.path.join("data", "monster-train-2-save.json"), "w") as f:
        json.dump(data, f, indent=config.server.json_indent)

    # handle database stuff
    post = await req.post()

    def write_db(name: str):
        value = post[name]
        if isinstance(value, FileField):
            value = value.file.read()
        with open(os.path.join("data", f"mt2-runs-{name}.sqlite3"), "wb") as f:
            f.write(value)

    for k in post:
        if k == "main" or k.isdigit() or k.endswith(".db"):
            write_db(k)

    return Response()

@router.get("/mt/debug")
async def mt_current(req: Request):
    save = await get_savefile()
    if save is None:
        raise HTTPServiceUnavailable(reason="No savefile present on server")
    data = save._data
    if "raw" not in req.query:
        data = _get_sanitized(data)
    return Response(text=json.dumps(data, indent=4), content_type="application/json")

def _get_sanitized(x):
    match x:
        case str():
            return get_safe(x)
        case list():
            return [_get_sanitized(a) for a in x]
        case dict():
            return {k: _get_sanitized(v) for k,v in x.items()}
        case _:
            return x
