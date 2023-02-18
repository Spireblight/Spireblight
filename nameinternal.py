from __future__ import annotations

from collections import defaultdict
from functools import total_ordering
from aiohttp import ClientSession

import json
import os

from configuration import config
from events import add_listener

__all__ = [
    "get", "get_card",
    "get_relic_stats",
    "get_event",
    "query", "get_run_mod",
]

_cache: dict[str, dict[str, str]] = {}
_internal_cache: dict[str, Base] = {}
_query_cache: dict[str, list[Base]] = defaultdict(list)

def query(name: str, type: str | None = None):
    name = name.lower().replace(" ", "").replace("-", "").replace("'", "").replace("(", "").replace(")", "")
    if name in _query_cache:
        return _query_cache[name][0] # FIX THIS
    return None

def get(name: str) -> Base:
    if name in _internal_cache:
        return _internal_cache[name]

    raise ValueError(f"Could not find item {name}")

def get_card(card: str) -> str:
    name, _, upgrades = card.partition("+")
    inst = get(name)
    match upgrades:
        case "":
            return inst.name
        case "1":
            return f"{inst.name}+"
        case a:
            return f"{inst.name}+{a}"

@total_ordering
class Base:
    cls_name = ""
    def __init__(self, data: dict[str, str]):
        assert self.cls_name, "Cannot instantiate Base"
        self.internal = data.get("id", data["name"])
        self.name = data["name"]
        self.description = data["description"]
        self.mod = data.get("mod")

    @property
    def info(self) -> str:
        return f"{self.name}: {self.description}"

    def __hash__(self) -> int:
        return hash(self.internal)

    def __eq__(self, other):
        # technically, this could be checking against just Base
        # but we don't want to accidentally compare cards and relics
        # so it's disallowed here and will throw an error instead
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.name == other.name

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.name < other.name

class Card(Base):
    cls_name = "card"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.color: str = data["color"]
        self.rarity: str = data["rarity"]
        self.type: str = data["type"]
        self.cost: str | None = data["cost"] or None
        self.pack: str | None = data.get("pack")

    @property
    def info(self) -> str:
        mod = ""
        if self.pack:
            mod = f"(Packmaster: {self.pack})"
        elif self.mod != "Slay the Spire":
            mod = f"(Mod: {self.mod})"
        return f"{self.name} - [{self.cost}] {self.color} {self.rarity} {self.type}: {self.description} {mod}"

class Relic(Base):
    cls_name = "relic"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.pool: str | None = data.get("pool")
        self.tier: str = data["tier"]
        self.flavour_text: str = data["flavorText"]

    @property
    def info(self) -> str:
        mod = ""
        if self.mod != "Slay the Spire":
            mod = f"(Mod: {self.mod})"
        pool = " "
        if self.pool:
            pool = f" ({self.pool})"
        return f"{self.name} - {self.tier}{pool}: {self.description} {mod}"

class Potion(Base):
    cls_name = "potion"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.rarity: str = data["rarity"]
        self.color: str = data.get("color")

    @property
    def info(self) -> str:
        mod = ""
        if self.mod != "Slay the Spire":
            mod = f"(Mod: {self.mod})"
        color = ""
        if self.color:
            color = f" ({self.color})"
        return f"{self.name} - {self.rarity}{color}: {self.description} {mod}"

class Keyword(Base):
    cls_name = "keyword"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.names: list[str] = data.get("names", [])

class ScoreBonus(Base):
    cls_name = "score_bonus"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.format_string: str = data.get("format_string", self.name)

_str_to_cls: dict[str, Base] = {
    "cards": Card,
    "relics": Relic,
    "potions": Potion,
    "keywords": Keyword,
    "score_bonuses": ScoreBonus,
}

def _get_name(x: str, d: str, default: str) -> str:
    return _cache[d].get(x, {}).get("NAME", default)

def get_event(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Event {name}>"
    return _get_name(name, "events", default)

def get_relic_stats(name: str) -> list[str]:
    return _cache["relic_stats"][name]["TEXT"]

def get_run_mod(name: str) -> str:
    return f'{_cache["run_mods"][name]["NAME"]} - {_cache["run_mods"][name]["DESCRIPTION"]}'

@add_listener("setup_init")
async def load():
    _cache.clear()
    session = ClientSession()
    for mod in config.spire.enabled_mods:
        data = None
        async with session.get(f"https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/{mod}/data.json") as resp:
            if resp.ok:
                decoded = await resp.text()
                data = json.loads(decoded)
        if data is None:
            raise ValueError(f"Mod {mod} could not be found.")

        for cat, maps in data.items():
            if cat in _str_to_cls:
                for mapping in maps:
                    inst: Base = _str_to_cls[cat](mapping)
                    _internal_cache[inst.internal] = inst
                    _query_cache[inst.name.lower().replace(" ", "").replace("-", "").replace("'", "").replace("(", "").replace(")", "")].append(inst)

    with open("score_bonuses.json") as f:
        j = json.load(f)
        for x in j["score_bonuses"]:
            inst = ScoreBonus(x)
            _internal_cache[inst.internal] = inst
            _query_cache[inst.name.lower().replace(" ", "").replace("-", "").replace("'", "")].append(inst)

    for file in os.listdir("eng"):
        name = file[:-5]
        if not name.startswith("_"):
            with open(os.path.join("eng", file)) as f:
                _cache[name] = json.load(f)
