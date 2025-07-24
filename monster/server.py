from typing import Generator

import json
import os

from aiohttp.web import Request, Response, HTTPServiceUnavailable, FileField

from monster.static import get, get_safe, Challenge, Mutator, Artifact, Character
from src.webpage import router
from src.utils import get_req_data

from src.typehints import ContextType

from src.configuration import config

class MonsterSave:
    def __init__(self, file):
        data = None
        try:
            with open(os.path.join("data", file), "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self._data = data

    def update_data(self, data: dict):
        self._data = data

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
    def sub_class(self) -> str:
        sub = self._data["startingConditions"]["subclassInfo"]
        if "className" in sub:
            return _get_sanitized(sub["className"])
        return _get_sanitized(sub["classId"])

    @property
    def sub_exiled(self) -> bool:
        return bool(self._data["startingConditions"]["subclassInfo"]["championIndex"])

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
    def mutators(self) -> list[Mutator]:
        return [get(x) for x in self._data["startingConditions"]["mutators"]]

_savefile = MonsterSave("monster-train-save.json")
_save2 = MonsterSave("monster-train-2-save.json")

async def get_savefile(ctx: ContextType | None = None) -> MonsterSave:
    if (_savefile._data is not None and (_savefile.main_class and _savefile.sub_class)):
        return _savefile

    if (_save2._data is not None and (_save2.main_class and _save2.sub_class)):
        return _save2

    if ctx is not None:
        await ctx.reply("Not in a run.")


@router.post("/sync/monster")
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

@router.post("/sync/monster-2")
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
