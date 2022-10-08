from __future__ import annotations

from collections import defaultdict

import json
import os
from typing import Any

from events import add_listener

__all__ = [
    "get_relic", "get_relic_stats",
    "get_card", "get_card_metadata",
    "get_potion", "get_event",
    "query", "get_run_mod",
    "get_score_bonus"
]

_cache: dict[str, dict[str, str]] = {}
_full_data: dict[str, dict[str, list[dict[str, str]]]] = {}
_internal_cache: dict[str, Base] = {}
_query_cache: dict[str, list[Base]] = defaultdict(list)

def query(name: str, type: str | None = None):
    name = name.lower().replace(" ", "").replace("-", "").replace("'", "")
    if name in _query_cache:
        return _query_cache[name][0] # FIX THIS
    return None

class Base:
    cls_name = ""
    def __init__(self, data: dict[str, str]):
        self.internal = data.get("internal", data["name"])
        self.name = data["name"]
        self.description = data["description"]
        self.mod = data.get("mod")

class Card(Base):
    cls_name = "card"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.color: str = data["color"]
        self.rarity: str = data["rarity"]
        self.type: str = data["type"]
        self.cost: str | None = data["cost"] or None

class Relic(Base):
    cls_name = "relic"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.pool: str | None = data.get("pool")
        self.tier: str = data["tier"]
        self.flavour_text: str = data["flavorText"]

_str_to_cls: dict[str, Base] = {
    "cards": Card,
    "relics": Relic,
}

def _get_name(x: str, d: str, default: str) -> str:
    return _cache[d].get(x, {}).get("NAME", default)

def get_relic(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Relic {name}>"
    return _get_name(name, "relics", default)

def get_card(name: str, default: str | None = None) -> str:
    if name == "Singing Bowl":
        return "Gain +2 Max HP"
    if default is None:
        default = f"<Unknown Card {name}>"
    name, plus, upgrades = name.partition("+")
    val = _get_name(name, "cards", default)
    if upgrades not in ("1", ""): # Searing Blow
        return f"{val}+{upgrades}"
    return f"{val}{plus}"

def get_card_metadata(name: str) -> dict[str, str]:
    return _cache["cards"][name.partition("+")[0]]

def get_potion(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Potion {name}>"
    return _get_name(name, "potions", default)

def get_event(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Event {name}>"
    return _get_name(name, "events", default)

def get_relic_stats(name: str) -> list[str]:
    return _cache["relic_stats"][name]["TEXT"]

def get_run_mod(name: str) -> str:
    return f'{_cache["run_mods"][name]["NAME"]} - {_cache["run_mods"][name]["DESCRIPTION"]}'

def get_score_bonus(name: str) -> dict[str, str]:
    return _cache["score_bonuses"][name]

@add_listener("setup_init")
async def load():
    _cache.clear()
    _full_data.clear()
    with open("full_data.json") as f:
        _full_data.update(json.load(f))
    for cat, maps in _full_data.items():
        if cat in _str_to_cls:
            for mapping in maps:
                inst: Base = _str_to_cls[cat](mapping)
                _internal_cache[inst.internal] = inst
                _query_cache[inst.name.lower().replace(" ", "").replace("-", "").replace("'", "")].append(inst)

    for file in os.listdir("eng"):
        name = file[:-5]
        if not name.startswith("_"):
            with open(os.path.join("eng", file)) as f:
                _cache[name] = json.load(f)
