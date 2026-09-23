# all static data fetched from:
# - https://github.com/brendanjhoffman/TrainStewardBot/tree/main (names, descriptions)
# - https://github.com/KittenAqua/TrainworksModdingTools/tree/master/TrainworksModdingTools/Constants (IDs)
# MT2 data from the modding discord (might become desynced of updates)
# huge thanks to PattyHoswell from the Shiny Shoe discord for sending me a bunch of JSONs

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import json
import os

# this is an iterable of 1-length str to remove from queries
_replace_str = " -'()."

__all__ = ["query", "get", "load_mt1", "load_mt2"]

_id_cache: dict[str, Base | Base2] = {}
_internal_cache: dict[str, Base | Base2] = {}
_query_cache: dict[str, list[Base | Base2]] = defaultdict(list)
_mutators: dict[str, Mutator] = {}
_autoreplace: dict[str, str] = {} # mapping of name: uri (relative to /static/mt2/)

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
    """Get the class for the given data. Matches either internal name or ID."""
    if name in _internal_cache:
        return _internal_cache[name]
    if name in _id_cache:
        return _id_cache[name]

    return Unknown(name)

def get_safe(name: str) -> str:
    """Get the name matching the ID or internal name, or the input back if none found."""
    if name in _internal_cache:
        return _internal_cache[name].name
    if name in _id_cache:
        return _id_cache[name].name
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
        self._description: str = data.get("description", data.get("raw", ""))
        self.internal: str = data.get("internal", "")
        self.id: str = data.get("id")
        self.lore: str = data.get("lore", "")
        self.is_hidden: bool = data.get("hidden", False)
        self.dlc: str | None = data.get("dlc")

    @property
    def info(self):
        return f"{self.__class__.__name__} {self.name}: {self.description}"

    @property
    def description(self) -> str:
        if self.name in _descriptions:
            return _descriptions[self.name]
        return self._description

    def escaped_description(self) -> str:
        desc = self.description.replace("\n", "<br>").replace("'", "\\'")
        for name, uri in _autoreplace.items(): # XXX restrict image size?
            desc = desc.replace(f"[{name}]", f'<img src="/static/mt2/{uri}" alt="{self.name}">')
        return desc

class Card2(Base2):
    def __init__(self, data: dict):
        super().__init__(data)
        self.clan: str = data["clan"]
        self.type: str = data["card_type"]
        self.rarity: str = data["rarity"]
        self.cost: int = data["cost"] # X-cost cards are marked as 0
        self.unlock: int = data["unlock_level"]
        self.artist: str = data["artist"]
        self.has_ability: bool = data["unit_ability"]
        self.initial_cooldown: int = data["initial_cooldown"]
        self.ability_cooldown: int = data["ability_cooldown"]

    @property
    def info(self) -> str:
        return f"{self.name} ({self.rarity} {self.type} {self.clan}): {self.description}"

class Character(Base2):
    def __init__(self, data: dict):
        super().__init__(data)
        self.ability: str = data["ability"]
        self.attack: int = data["attack"]
        self.health: int = data["health"]
        self.grafted: str = data["grafted_equipment"]
        self.size: int = data["size"]
        self.artist: str = data["artist"]
        self.gender: str = data["gender"] # why is that a field

    @property
    def info(self) -> str:
        return f"{self.name} [{self.size} pips] {self.attack}/{self.health} - {self.description}"

    @property
    def upgrades(self) -> UpgradePath | None:
        if self.internal not in _upgrades:
            return None
        return _upgrades[self.internal]

class Clan(Base2):
    """Store data for clans.
    
    We also added "Clanless" to the list for easier access."""

    @property
    def info(self):
        return self.name

    @property
    def image(self) -> str:
        """The clan icon link."""
        return f"/static/mt2/clan/{self.internal}.png"

class Covenant(Base2):
    def __init__(self, data):
        super().__init__(data)
        self.level: int = data["level"]
        self.name = str(self.level) # description works out!

class Enhancer(Base2):
    def __init__(self, data: dict):
        super().__init__(data)
        self.clan: str = data["clan"]
        self.rarity: str = data["rarity"]
        self.unlock: int = data["unlock_level"]

class Event(Base2):
    def __init__(self, data):
        super().__init__(data)
        self.name = data["storyId"] # this is temporary, need to fix

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
        self.unlock: int = data["unlock_level"]
        self.rarity: str = data["rarity"]
        self.story_event: bool = data["is_story_event"]
        self.dragons_hoard: bool = data["is_dragons_hoard"]
        self.boss_artifact: bool = data["is_boss_artifact"]

class Trial(Base2):
    """Store trial information."""
    def __init__(self, data):
        super().__init__(data)
        self.trial = data["trial"] # this is like a status effect
        self.rewards = data["rewards"]

class Upgrade(Base2):
    """Store upgrade information."""
    def __init__(self, data):
        super().__init__(data)
        self.bonus_atk: int = data["bonus_atk_pwr"]
        self.bonus_hp: int = data["bonus_hp"]
        self.bonus_heal: int = data["bonus_heal"]
        self.bonus_size: int = data["bonus_size"]
        self.cost_reduction: int = data["cost_reduction"]
        self.x_cost_reduction: int = data["x_cost_reduction"]
        self.ability: str = data["ability"]
        self.unique: bool = data["unique"]
        self.clone_excluded: bool = data["clone_excluded"]
        self.do_not_replace_ability: bool = data["do_not_replace_ability"] # why it's phrased so ass-backwards is beyond me
        self.rarity: bool = data["rarity"] # why is this even a bool
        self.blocks_ability: bool = data["blocks_ability"]

    @property
    def image(self) -> str:
        """The image for the upgrade."""
        # we use internal instead of name for two reasons:
        # - we don't have to account for weird characters like -' or spaces
        # - if anything gets renamed in-game, nothing here breaks
        name, _, ss_name = self.internal.partition("_")
        if name == "SoulSavior":
            name = ss_name # the slab version just has a prefix here
        elif ss_name: # something else has an underscore?
            name = self.internal
        if name == "AddDamageShield":
            name = "AddDamageShield3" # Soul Savior compat
        return f"/static/mt2/upgrades/{name}.png"

class Status(Base2):
    """Store status information."""
    def __init__(self, data):
        super().__init__(data)
        self.card_tooltip: str = data["card_tooltip"]
        self.character_tooltip: str = data["character_tooltip"]
        self.notification: str = data["notification"]
        self.status_class: str = data["status_class"]

    @property
    def image(self) -> str:
        """Get the image link for the status."""
        name = self.internal
        if name == "soul":
            name = "captured_soul"
        return f"/static/mt2/status/{name}.png"

class Soul(Base2):
    """Store soul (from Soul Savior) information."""
    def __init__(self, data):
        super().__init__(data)
        self.clan: str = data["clan"]
        self.unlock_level: int = data["unlock_level"]
        self.rarity: str = data["rarity"]
        self.is_dlc: bool = data["is_dlc"]
        self.draft_min_distance: int = data["draft_min_distance"]
        self.draft_max_distance: int = data["draft_max_distance"]

class Sin(Base2):
    """Store sin information from fight trials."""

class Mutator(Base2):
    """Contain mutators for Daily and Challenge modes."""
    def __init__(self, data):
        super().__init__(data)
        self.boon_value: int = data["boon_value"]
        self.tags: str = data["tags"]
        self.soul_savior_only: bool = data["soul_savior_only"]
        self.daily_disabled: bool = data["daily_disabled"]

class EndlessMutator(Base2):
    """Contain mutators for Endless mode."""

class Reward(Base2):
    """Store some kind of reward information?"""
    def __init__(self, data):
        super().__init__(data)
        self.trial_modifiers = data["trial_modifiers"]

_upgrades: dict[str, UpgradePath] = {}

class UpgradePath:
    """Store all the Champion upgrade paths.
    
    The JSON file had to be manually edited from data in both characters.json and upgrades.json
    
    This *will* need manual intervention if and when new classes get added, or the upgrade paths modified."""

    def __init__(self, data: dict[str, list[dict]]):
        self._champion = data["champion"]
        _upgrades[self._champion] = self
        self._upgrades = data["upgrades"]
        self.names = [x["name"] for x in self._upgrades]

    @property
    def champion(self):
        """Which champion the upgrades belong to."""
        return _internal_cache[self._champion]

    def get_upgrade(self, *, name: str | None = None, index: int | None = None):
        """Get the matching upgrade or upgrade path.

        :param name: The name of the upgrade, defaults to None
        :type name: str | None, optional
        :param index: Which upgrade level to get, defaults to None. Has no effect if :param name: is None.
        :type index: int | None, optional
        :returns: The specific upgrade, a list of the three matching upgrades, or all if not specified.
        :rtype: dict[str, list[Upgrade]] | list[Upgrade] | Upgrade
        """
        if name is None:
            final = {}
            for path in self._upgrades:
                ups = []
                for d in path["upgrades"]:
                    ups.append(_id_cache[d["id"]])
                final[path["name"]] = ups
            return final

        name = name.casefold()
        for path in self._upgrades:
            if path["name"] != name:
                continue
            if index is not None:
                return _id_cache[path["upgrades"][index]["id"]]
            return [_id_cache[x["id"]] for x in path["upgrades"]]

        raise ValueError(f"No upgrade called {name} exists.")

_descriptions = {}

def card_description(data: dict[str, str]):
    _descriptions[data["name"]] = data["description"]

class Misc2(Base2):
    """Store information for unknown data."""

_map2 = {
    "cards": Card2,
    "characters": Character,
    "classes": Clan,
    "covenants": Covenant,
    "enhancers": Enhancer,
    "events": Event,
    "nodes": Node,
    "relics": Relic,
    "trials": Trial,
    "upgrades": Upgrade,
    "status": Status,
    "souls": Soul,
    "sins": Sin,
    "mutators": Mutator,
    "endless_mutators": EndlessMutator,
    "rewards": Reward,
    "upgrade_paths": UpgradePath,
    "card_text": card_description,
}

def load_mt1():
    return
    _id_cache.clear()
    _query_cache.clear()
    for file in os.listdir(os.path.join("argo", "mt1")):
        if not file.endswith(".json"):
            continue
        with open(os.path.join("argo", "mt1", file)) as f:
            data = json.load(f)
            for d in data:
                value = _map1.get(file[:-5], Misc)(d)
                _id_cache[value.internal] = value
                _query_cache[sanitize(value.name)].append(value)

def load_mt2():
    # TODO: make clans and units as proper objects that others can use
    _id_cache.clear()
    _internal_cache.clear()
    _query_cache.clear()
    base = Path(".")
    for file in (base / "argo" / "mt2").iterdir():
        if not file.name.endswith(".json"):
            continue
        with file.open() as f:
            data = json.load(f)
            for d in data:
                value = _map2.get(file.name.partition(".")[0], Misc2)(d)
                if not isinstance(value, Base2):
                    continue
                if value.id: # temporary fix while some units have a blank ID
                    _id_cache[value.id] = value
                _internal_cache[value.internal] = value
                _query_cache[sanitize(value.name)].append(value)

    for img in (base / "static" / "mt2").iterdir():
        if img.name.endswith(".png"):
            _autoreplace[img.name.partition(".")[0]] = img.name
        elif img.is_dir():
            for img2 in img.iterdir():
                if img2.name.endswith(".png"):
                    _autoreplace[img2.name.partition(".")[0]] = f"{img.name}/{img2.name}"
