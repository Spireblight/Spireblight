# all static data fetched from:
# - https://github.com/brendanjhoffman/TrainStewardBot/tree/main (names, descriptions)
# - https://github.com/KittenAqua/TrainworksModdingTools/tree/master/TrainworksModdingTools/Constants (IDs)
# MT2 data from the modding discord (might become desynced of updates)
# huge thanks to PattyHoswell from the Shiny Shoe discord for sending me a bunch of JSONs

from __future__ import annotations

from collections import defaultdict

import json
import os

# this is an iterable of 1-length str to remove from queries
_replace_str = " -'()."

__all__ = ["query", "get", "load_mt1", "load_mt2"]

_internal_cache: dict[str, Base] = {}
_query_cache: dict[str, list[Base]] = defaultdict(list)
_mutators: dict[str, Mutator] = {}

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
        self.description = data.get("Description", "")
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

class Mutator(Base):
    def __init__(self, data: dict):
        super().__init__(data)
        _mutators[self.name] = self

class Challenge(Base):
    def __init__(self, data: dict):
        super().__init__(data)
        self._mutators = data["Mutators"]

    @property
    def mutators(self) -> list[Mutator]:
        return [_mutators[x] for x in self._mutators]

    @property
    def info(self) -> str:
        return f"{self.name} ({self.description}). Mutators: {', '.join(x.name for x in self.mutators)}"

class Misc(Base):
    """For things like clan names."""

class Unknown:
    def __init__(self, name: str):
        self.internal = name
        self.name = name
        self.description = f"Could not find description for {name!r} (this is a bug)"
        self.id = name
        self.lore = "Once upon a time, there was something I could not find."

_map1 = {
    "cards": Card,
    "artifacts": Artifact,
    "mutators": Mutator,
    "challenges": Challenge,
}

# TODO: Merge stuff that's in multiple places so we can combine the Unit and the Card part of them

class Base2:
    def __init__(self, data: dict):
        self.name: str = data.get("name", data.get("title", ""))
        self.description: str = data.get("description", data.get("raw", ""))
        self.internal: str = data.get("internal", "")
        self.id: str = data["id"]
        self.lore: str = data.get("lore", "")

    @property
    def info(self):
        return f"{self.__class__.__name__} {self.name}: {self.description}"

class Card2(Base2):
    def __init__(self, data: dict):
        super().__init__(data)
        self.clan: str = data["clan"]
        self.type: str = data["type"]
        self.rarity: str = data["rarity"]
        self.cost = int(data["cost"])
        self.unlock = int(data["unlock"])
        self.artist: str = data["artist"]
        self.has_ability: bool = data["ability"]
        self.initial_cooldown = int(data["init_cooldown"])
        self.ability_cooldown = int(data["ability_cooldown"])

    @property
    def info(self) -> str:
        return f"{self.name} ({self.rarity} {self.type} {self.clan}): {self.description}"

class Character(Base2):
    def __init__(self, data: dict):
        super().__init__(data)
        self.ability: str = data["ability"]
        self.attack = int(data["attack"])
        self.health = int(data["health"])
        self.grafted: str = data["grafted"]
        self.size = int(data["size"])

    @property
    def info(self) -> str:
        return f"{self.name} [{self.size} pips] {self.attack}/{self.health} - {self.description}"

class Clan(Base2):
    @property
    def info(self):
        return self.name

class Covenant(Base2):
    def __init__(self, data):
        super().__init__(data)
        self.level: int = data["level"]
        self.name = f"Covenant {self.level}"

    @property
    def info(self):
        return f"Covenant {self.level}: {self.description}"

class Enhancer(Base2):
    def __init__(self, data: dict):
        super().__init__(data)
        self.clan: str = data["clan"]
        self.rarity: str = data["rarity"]
        self.unlock = int(data["unlock"])

class Node(Base2):
    """Store map node information"""
    # this JSON is... a bit of a mess
    # some things are not exactly clear as to what is what
    # there's like 5 fields which are only used for 1-2 things each
    # and 2 which are completely unnecessary for us
    # but I don't wanna fuck around with regex to clear them atm

class Relic(Base2):
    def __init__(self, data):
        super().__init__(data)
        self.clan: str = data["clan"] # could be empty string
        self.unlock = int(data["unlock"])
        self.rarity: str = data["rarity"]
        self.story_event: bool = data["story_event"]
        self.dragons_hoard: bool = data["dragons_hoard"]
        self.boss_artifact: bool = data["boss_artifact"]

class Trial(Base2):
    """Store trial information."""
    # trials values are not 100% certain
    # aka the "Enemies heal for X" where X is guessed but not entirely known
    # this is why the descriptions are a bit... weird
    # to be able to identify them during runs, and thus fix

class Upgrade(Base2):
    def __init__(self, data):
        super().__init__(data)
        self.bonus_atk = int(data["bonus_atk_pwr"])
        self.bonus_hp = int(data["bonus_hp"])
        self.bonus_heal = int(data["bonus_heal"])
        self.bonus_size = int(data["bonus_size"])
        self.cost_reduction = int(data["cost_reduction"])
        self.x_cost_reduction = int(data["x_cost_reduction"])
        self.ability: str = data["ability"]
        self.unique: bool = data["unique"]
        self.clone_excluded: bool = data["clone_excluded"]
        self.do_not_replace_ability: bool = data["do_not_replace_ability"] # why it's phrased so ass-backwards is beyond me

class Misc2:
    def __init__(self, data):
        pass

_map2 = {
    "cards": Card2,
    "characters": Character,
    "classes": Clan,
    "covenants": Covenant,
    "enhancers": Enhancer,
    "nodes": Node,
    "relics": Relic,
    "trials": Trial,
    "upgrades": Upgrade,
}

def load_mt1():
    return
    _internal_cache.clear()
    _query_cache.clear()
    for file in os.listdir(os.path.join("monster", "_static", "mt1")):
        if not file.endswith(".json"):
            continue
        with open(os.path.join("monster", "_static", "mt1", file)) as f:
            data = json.load(f)
            for d in data:
                value = _map1.get(file[:-5], Misc)(d)
                _internal_cache[value.internal] = value
                _query_cache[sanitize(value.name)].append(value)

def load_mt2():
    # TODO: make clans and units as proper objects that others can use
    _internal_cache.clear()
    _query_cache.clear()
    for file in os.listdir(os.path.join("monster", "_static", "mt2")):
        if not file.endswith(".json"):
            continue
        with open(os.path.join("monster", "_static", "mt2", file)) as f:
            data = json.load(f)
            for d in data:
                value = _map2.get(file[:-5], Misc2)(d)
                _internal_cache[value.id] = value
                _query_cache[sanitize(value.name)].append(value)
