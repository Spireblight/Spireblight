from typing import Generator

import aiohttp_jinja2
import struct
import json
import os

from aiohttp.web import Request, Response, HTTPServiceUnavailable, HTTPForbidden, FileField

from src.monster.replay import parse
from src.monster.static import get, get_safe, get_champion, Challenge, Mutator, Artifact, Character, Mutator2, Soul, Trial, Clan, Node
from src.webpage import router
from src.utils import get_req_data, getfile, catch_error

from src.typehints import ContextType

from src.config import config

_fights = ( # lines with UNSORTED have not been confirmed
    (   # Ring 1 fight
        "Dominion's Preservation", # UNSORTED
        "Forsaken Few", # UNSORTED
        "Heavenly Toll",
    ),
    (   # Ring 2 fight
        "Knights of Entropy",
        "Flagellant's March", # UNSORTED
        "March of the Supplicants", # UNSORTED
        "Quicksilver Cherubs", # UNSORTED
    ),
    (   # First flying boss
        "Fleshweaver (Corrupted Mass)", # UNSORTED but almost guaranteed to be correct
        "Fleshweaver (More Mass)",
        "Fleshweaver (Spiked Mass)",
        "Arkion, Scion of Savagery (Furious Frenzy)", # UNSORTED
        "Arkion, Scion of Savagery (Hard Headed)", # UNSORTED
        "Arkion, Scion of Savagery (Pyre Hunter)", # UNSORTED
    ),
    (   # Ring 4 fight
        "Dire Defenses", # UNSORTED
        "Penance Seekers", # UNSORTED
        "Savagery's Hunters", # UNSORTED
        "Hordes of Heaven",
    ),
    (   # Ring 5 fight
        "Corrupted Crusade", # UNSORTED
        "Relentless Zealots", # UNSORTED
        "Undying Minions", # UNSORTED
        "Unholy Alliances", # UNSORTED
    ),
    (   # Second flying boss
        "Cael, Lord of the Cherubs (Holy Feed)", # UNSORTED
        "Cael, Lord of the Cherubs (Nourishing Feed)", # UNSORTED
        "Cael, Lord of the Cherubs (Vampiric Feed)", # UNSORTED
        "Stryx/Hallow (Bloody Harvest)", # UNSORTED
        "Stryx/Hallow (Doombringers)", # UNSORTED
        "Stryx/Hallow (Inevitability)", # UNSORTED
    ),
    (   # Ring 7 fight
        "Dominion's Disdain", # UNSORTED
        "Purified Hordes", # UNSORTED
        "Savagery's Final Assault", # UNSORTED
    ),
    (   # Third flying boss
        "Seraph Aeternus: The Savage (Champion of Savagery)", # UNSORTED
        "Seraph Aeternus: The Dominant (Chosen of Dominion)", # UNSORTED
        "Seraph Aeternus: The Entropic (Harbinger of Entropy)", # UNSORTED
    ),
    (   # Titans fight
        "Clash with the Titans", # do NOT remove this singular comma
    ),
)

def parse_value(v: list[int], *, little_endian=True) -> int:
    """Parse and unpack the various structs used for gold and other values."""
    assert len(v) % 8 == 0, "can only unpack multiples of 8"
    val = bytes(v)
    fs = "<" if little_endian else ">"
    fs += "d" * (len(v) // 8) # one double per 8 bytes
    unpacked = struct.unpack(fs, val)
    return int(sum(unpacked))

class MonsterSave:
    def __init__(self, file: str):
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
        names = []
        for ring in self.rings:
            names.extend(ring.get_names())
        return names

    @property
    def rings(self):
        snapshots = len(self._data["goldOverTime"])
        furthest, in_fight = snapshots // 2, bool(snapshots % 2)
        assert furthest == self._data["runState"]["numBattlesCompleted"], "battle count data mismatch"
        for i, data in enumerate(self._data["runState"]["nodes"]):
            battle = None
            if i < furthest:
                battle = self._data["completedBattles"][i]
            yield Ring(i, furthest, in_fight, data, battle)

    @property
    def gold(self) -> int:
        """The current count of gold. Ignores in-fight gains."""
        return self._asint("gold")

    @property
    def gold_graph(self) -> list[int]:
        """The gold count at specific snapshots during the run."""
        return self._data["goldOverTime"]

    @property
    def dragons_hoard(self) -> int:
        """The current count of Dragon's Hoard."""
        return self._asint("dragonsHoard")

    @property
    def dragons_hoard_cap(self) -> int:
        """The current limit of Dragon's Hoard we can hold."""
        return self._asint("dragonsHoardCap")

    @property
    def use_dragons_hoard(self) -> bool:
        return "Pyreborne" in (self.main_class, self.sub_class)

    @property
    def forge_points(self) -> int:
        """The current count of Forge Points being held."""
        return self._asint("forgePoints")

    @property
    def use_forge_points(self) -> bool:
        return "Railforged" in (self.main_class, self.sub_class)

    @property
    def pyre_hp(self) -> int:
        """The current Pyre HP."""
        return self._asint("towerHP")

    @property
    def pyre_hp_graph(self) -> list[int]:
        """The Pyre HP at specific snapshots during the run."""
        return self._data["towerHPOverTime"]

    @property
    def pyre_max_hp(self) -> int:
        """The Pyre Max HP."""
        return self._asint("maxTowerHP")

    @property
    def pyre_max_hp_graph(self) -> list[int]:
        """The Pyre Max HP at specific snapshots during the run."""
        return self._data["towerMaxHPOverTime"]

    @property
    def in_game(self) -> bool:
        # XXX: there might be a few more pieces to check
        return self._data and self.main_class

    @property
    def champion(self):
        return get_champion(self.main_class, self.main_exiled)

    def get_clan_image(self, *, is_main: bool) -> str:
        """Generate an SVG with the clan with or without exiled symbol.

        :param is_main: Whether this is the main clan we want.
        :type is_main: bool
        :return: A full SVG matching the clan.
        :rtype: str
        """

        key = ("subclassInfo", "mainClassInfo")[is_main]
        clan: Clan = get(self._data["startingConditions"][key]["classId"])
        exiled = ""
        if self._data["startingConditions"][key]["championIndex"] == 1: # exiled
            exiled = f'<image width="16" height="16" xlink:href="{config.server.url}/static/mt2/clan/Exiled.png" x="40" y="96"></image>'
        name = clan.name
        if exiled:
            name = f"{name} (Exiled)"
        return (
            f'<svg width="96" height="112"><title>{name}</title>'
            f'<image width="96" height="96" xlink:href="{config.server.url}{clan.image}"></image>{exiled}</svg>'
        )

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
    def main_clan_icon(self) -> str:
        return self.get_clan_image(is_main=True)

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
    def sub_clan_icon(self) -> str:
        return self.get_clan_image(is_main=False)

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

class Ring:
    """Store information for one ring."""

    def __init__(self, ring: int, farthest: int, in_fight: bool, data: dict, battle: dict | None):
        self.ring = ring # 0-indexed
        self.farthest = farthest
        self.in_fight = in_fight
        self._data = data
        self._battle = battle

    def _get_boss(self, *, allow_future: bool = False) -> Character | None:
        if not allow_future and not self._battle:
            return None
        if not self._data["bossId"]: # flying boss
            return None # need to use scenarioIndex or whatever
        return get(self._data["bossId"])

    @property
    def boss(self):
        """Get the ring's boss. Does not display major (flying) bosses."""
        return self._get_boss()

    @property
    def align(self) -> bool:
        return self.ring % 2 and "right" or "left"

    def get_nodes(self):
        """Get the nodes on left, center, and right respectively."""
        shared: set[tuple[Node, str]] = set()
        left_nodes: list[tuple[Node, str]] = []
        right_nodes: list[tuple[Node, str]] = []
        ss = "active"
        match self._data["chosenBranch"]:
            case 0:
                ls = "active"
                rs = "inactive"
            case 1:
                ls = "inactive"
                rs = "active"
            case -1:
                ls = rs = ss = "frozen"

        unparsed = self._data["mapNodes"]
        if len(unparsed) == 1: # either very first or very last ring
            side = unparsed[0]
            if side["_nodes"]: # we have any nodes at all
                for x in side["_nodes"]:
                    node: Node = get(x)
                    if node.name:
                        shared.add((node, ss))

        else:
            left, right = unparsed
            for side, lst, sub in ((left, left_nodes, ls), (right, right_nodes, rs)):
                for key in ("_nodes", "_randomizedNodes"):
                    for x in side[key]:
                        node: Node = get(x)
                        if node.name: # some are empty
                            lst.append((node, sub))

            # handle shared nodes
            shared_node = {x[0] for x in left_nodes} & {x[0] for x in right_nodes}
            if shared_node: # there will only be 0 or 1 items
                for x in shared_node:
                    shared.add((x, ss))
                left_nodes = [x for x in left_nodes if x[0] not in shared_node]
                right_nodes = [x for x in right_nodes if x[0] not in shared_node]

        return left_nodes, shared, right_nodes

    def get_names(self):
        """Return names for the before and after."""
        if self.ring == 8: # Titans
            return ["Before the Titans"]
        fight_name: str = _fights[self.ring][self._data["scenarioIndex"]]
        if (b := self._get_boss(allow_future=True)) is None: # flying boss
            boss = fight_name
        else:
            boss = b.name
        match self.ring:
            case 0:
                word = "first fight"
            case 1:
                word = "second fight"
            case 3:
                word = "fourth fight"
            case 4:
                word = "fifth fight"
            case 6:
                word = "seventh fight"
            case 2 | 5 | 7:
                word = boss # handled below
            case a:
                raise ValueError(f"Ring #{a} makes no sense")
        if fight_name == boss: # flying bosses are always known
            name = fight_name.partition(" (")[0]
            if self._data["titanTrialEnabled"]:
                fight_name = fight_name[:-1] + " II)"
            return f"Before {name}", f"After beating {fight_name}"
        if self.in_fight and self.ring == self.farthest: # we're in the fight and it has begun
            return f"Before {fight_name}", f"After {word}"
        if self.ring < self.farthest:
            return f"Before {fight_name}", f"After beating {boss}"
        return f"Before {word}", f"After {word}"

    def _get_trial(self, *, allow_future: bool = False, taken_only: bool = True) -> Trial | None:
        if not allow_future and not self._battle:
            return None
        tinfo = self._data["trialInfo"]
        if taken_only and not tinfo["trialEnabled"]:
            return None
        if not tinfo["trialDataId"]:
            return None
        return get(tinfo["trialDataId"])

    @property
    def trial(self) -> Trial | None:
        """Get the ring's trial, if it was taken."""
        return self._get_trial()

    @property
    def is_titan_trial(self) -> bool:
        return self._data["titanTrialEnabled"]

class Metasave:
    def __init__(self, filename: str):
        data = None
        try:
            with getfile(filename, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self._data = data

    def update_data(self, data: dict):
        self._data = data

    @property
    def max_covenant(self) -> int:
        return self._data["maxAscensionLevel"]

_savefile = MonsterSave("monster-train-save.json")
_save2 = MonsterSave("monster-train-2-save.json")

_meta1 = Metasave("monster-train-meta.json")
_meta2 = Metasave("monster-train-2-meta.json")

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

@router.post("/sync/monster-train/meta")
@catch_error
async def receive_meta_data(req: Request): # we store the data, but nothing uses it yet
    meta, game_version = await get_req_data(req, "meta", "game_version")
    data = json.loads(meta)
    if game_version == "1":
        savefile = _meta1
        filename = "monster-train-meta.json"
    elif game_version == "2":
        savefile = _meta2
        filename = "monster-train-2-meta.json"
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
    #save = await get_savefile()
    save = _save2 # temporary fix
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
