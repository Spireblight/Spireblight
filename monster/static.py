# all static data fetched from:
# - https://github.com/brendanjhoffman/TrainStewardBot/tree/main (names, descriptions)
# - https://github.com/KittenAqua/TrainworksModdingTools/tree/master/TrainworksModdingTools/Constants (IDs)

from __future__ import annotations

from collections import defaultdict

import json
import os

# this is an iterable of 1-length str to remove from queries
_replace_str = " -'()."

__all__ = ["query", "get", "load"]

_internal_cache: dict[str, Base] = {}
_query_cache: dict[str, list[Base]] = defaultdict(list)

def sanitize(x: str) -> str:
    x = x.lower()
    for s in _replace_str:
        x = x.replace(s, "")
    return x

def query(name: str):
    name = sanitize(name)
    if name in _query_cache:
        ret = _query_cache[name].pop(0)
        # this makes sure to cycle through cards if there are multiple
        _query_cache[name].append(ret)
        return ret
    return None

def get(name: str) -> Base:
    if name in _internal_cache:
        return _internal_cache[name]

    return Unknown(name)

def get_safe(name: str) -> str:
    if name in _internal_cache:
        return _internal_cache[name].name
    return name

class Base:
    def __init__(self, data: dict):
        self.name: str = data["Name"]
        self.description = data["Description"]
        self.internal = data["ID"]

    @property
    def info(self):
        return f"{self.name}: {self.description}"

class Card(Base):
    def __init__(self, data: dict):
        super().__init__(data)
        self.clan = data["Clan"]
        self.type = data["Type"]
        self.rarity = data["Rarity"]
        self.cost = data["Cost"]
        self.capacity = data["CP"]
        self.attack = data["ATK"]
        self.health = data["HP"]

    @property
    def info(self) -> str:
        if self.capacity: # this is a unit
            return f"{self.name} ({self.rarity} {self.type} {self.clan}) [{self.capacity} pips] ({self.cost}) {self.attack}/{self.health} - {self.description}"
        return f"{self.name} ({self.rarity} {self.type} {self.clan}): {self.description}"

class Artifact(Base):
    def __init__(self, data: dict):
        super().__init__(data)
        self.clan = data["Clan/Type"] # TODO: separate the two
        self.source = data["Source"]
        self.dlc = data["DLC"]

    @property
    def info(self) -> str:
        clan = source = ""
        if self.clan:
            clan = f" ({self.clan})"
        if self.source:
            source = f" [from {self.source}]"
        return f"{self.name}{clan}{source}: {self.description}"

class Misc(Base):
    """For things like clan names."""

class Unknown(Base):
    def __init__(self, name: str):
        self.internal = name
        self.name = name
        self.description = f"Could not find description for {name!r} (this is a bug)"

def load():
    _internal_cache.clear()
    _query_cache.clear()
    for cls, file in ((Card, "cards"), (Artifact, "artifacts"), (Misc, "misc")):
        with open(os.path.join("monster", f"{file}.json")) as f:
            data = json.load(f)
            for d in data:
                value = cls(d)
                _internal_cache[value.internal] = value
                _query_cache[sanitize(value.name)].append(value)
