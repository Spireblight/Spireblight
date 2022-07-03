from __future__ import annotations

from typing import Any, Generator

__all__ = ["FileParser", "get_nodes", "get_node", "get_character", "get_seed"]

# TODO: Handle the website display part, figure out details of these classes later

class FileParser:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self._cache = {}
        self._pathed = False

    def __getitem__(self, item: str) -> Any:
        return self.data[item]

    def __contains__(self, item: str) -> bool:
        return item in self.data

    def get(self, item: str, default=None):
        return self.data.get(item, default)

    @property
    def seed(self) -> int:
        if "seed" not in self._cache:
            self._cache["seed"] = get_seed(self)
        return self._cache["seed"]

    @property
    def path(self) -> Generator[NodeData, None, None]:
        """Return the run's path. This is cached."""
        if not self._pathed:
            if "path" in self._cache:
                raise RuntimeError("Called RunParser.path while it's generating")
            self._cache["path"] = []
            for node in get_nodes(self):
                self._cache["path"].append(node)
                yield node
            self._pathed = True
            return

        yield from self._cache["path"] # generator so that it's a consistent type

def get_seed(parser: FileParser):
    c = "0123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"

    try:
        seed = int(parser["seed"]) # might be stored as a str
    except KeyError:
        seed = int(parser["seed_played"])

    # this is a bit weird, but lets us convert a negative number, if any, into a positive one
    num = int.from_bytes(seed.to_bytes(20, "big", signed=True).strip(b"\xff"), "big")
    s = []

    while num:
        num, i = divmod(num, 35)
        s.append(c[i])

    s.reverse() # everything's backwards, for some reason... but this works

    return "".join(s)

_chars = {"THE_SILENT": "Silent"}

def get_character(x: FileParser):
    if "character_chosen" in x:
        c = _chars.get(x["character_chosen"])
        if c is None:
            c = x["character_chosen"].title()
        return c

    raise ValueError

class NodeData:
    """Contain relevant information for Spire nodes.

    Subclasses should define the following class variables:
    - room_type :: a human-readable name for the node
    - map_icon  :: the filename for the icon in the icons/ folder

    The recommended creation mechanism for NodeData classes is to call
    the class method `from_parser` with either a Run History parser or a
    Savefile parser, and the floor number."""

    room_type = "<UNDEFINED>"
    map_icon = "<UNDEFINED>"
    end_of_act = False

    def __init__(self): # TODO: Keep track of the deck per node
        if self.room_type == NodeData.room_type or self.map_icon == NodeData.map_icon:
            raise ValueError(f"Cannot create NodeData subclass {self.__class__.__name__!r}")
        self._floor = None
        self._maxhp = None
        self._curhp = None
        self._gold = None
        self._cards = []
        self._relics = []
        self._potions = []
        self._usedpotions = []
        self._cache = {}

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        """Create a NodeData instance from a parser and floor number.

        This is the recommended way to create NodeData instances. All
        subclasses should call it to create a new instance. Extra arguments
        will be passed to `__init__` for instance creation."""

        prefix = ""
        if "victory" not in parser: # this is a save file
            prefix = "metric_"

        self = cls(*extra)
        self._floor = floor
        try:
            self._maxhp = parser[prefix + "max_hp_per_floor"][floor - 1]
            self._curhp = parser[prefix + "current_hp_per_floor"][floor - 1]
            self._gold = parser[prefix + "gold_per_floor"][floor - 1]
            if "potion_use_per_floor" in parser: # run file
                self._usedpotions.extend(parser["potion_use_per_floor"][floor - 1])
            elif "PotionUseLog" in parser: # savefile
                self._usedpotions.extend(parser["PotionUseLog"][floor - 1])
        except IndexError:
            self._maxhp = parser[prefix + "max_hp_per_floor"][floor - 2]
            self._curhp = parser[prefix + "current_hp_per_floor"][floor - 2]
            self._gold = parser[prefix + "gold_per_floor"][floor - 2]

        for cards in parser[prefix + "card_choices"]:
            if cards["floor"] == floor:
                self._cards.append(cards)

        for relic in parser[prefix + "relics_obtained"]:
            if relic["floor"] == floor:
                self._relics.append(relic["key"])

        for potion in parser[prefix + "potions_obtained"]:
            if potion["floor"] == floor:
                self._potions.append(potion["key"])

        return self

    def description(self) -> str:
        if "description" not in self._cache:
            self._cache["description"] = self._description({})
        return self._cache["description"]

    def _description(self, to_append: dict[int, list[str]]) -> str:
        text = [f"Floor {self.floor}"]
        text.extend(to_append.get(0, ()))
        text.append(f"{self.room_type}")

        text.extend(to_append.get(1, ()))
        text.append(f"{self.current_hp}/{self.max_hp} - {self.gold} gold")

        text.extend(to_append.get(2, ()))
        if self.name:
            text.append(self.name)

        text.extend(to_append.get(3, ()))
        if self.potions:
            text.append("Potions obtained:")
            text.extend(f"- {x}" for x in self.potions)

        if self.used_potions:
            text.append("Potions used:")
            text.extend(f"- {x}" for x in self.used_potions)

        text.extend(to_append.get(4, ()))
        if self.relics:
            text.append("Relics obtained:")
            text.extend(self.relics)

        text.extend(to_append.get(5, ()))
        if self.picked:
            text.append("Picked:")
            text.extend(f"- {x}" for x in self.picked)

        if self.skipped:
            text.append("Skipped:")
            text.extend(f"- {x}" for x in self.skipped)

        text.extend(to_append.get(6, ()))

        return "\n".join(text)

    @property
    def name(self) -> str:
        return ""

    @property
    def floor(self) -> int:
        if self._floor is None:
            return 0
        return self._floor

    @property
    def max_hp(self) -> int:
        if self._maxhp is None:
            return 1
        return self._maxhp

    @property
    def current_hp(self) -> int:
        if self._curhp is None:
            return 0
        return self._curhp

    @property
    def gold(self) -> int:
        if self._gold is None:
            return 0
        return self._gold

    @property
    def picked(self) -> list[str]:
        ret = []
        for cards in self._cards:
            if cards["picked"] != "SKIP":
                ret.append(cards["picked"])
        return ret

    @property
    def skipped(self) -> list[str]:
        ret = []
        for cards in self._cards:
            ret.extend(cards["not_picked"])
        return ret

    @property
    def relics(self) -> list[str]:
        return self._relics

    @property
    def potions(self) -> list[str]:
        return self._potions

    @property
    def used_potions(self) -> list[str]:
        return self._usedpotions

def get_node(parser: FileParser, floor: int) -> NodeData:
    for node in get_nodes(parser):
        if node.floor == floor:
            return node
    raise IndexError(f"We did not reach floor {floor}")

def get_nodes(parser: FileParser) -> Generator[NodeData, None, None]:
    prefix = ""
    if "victory" not in parser:
        prefix = "metric_"
    on_map = iter(parser[prefix + "path_taken"])
    for floor, actual in enumerate(parser[prefix + "path_per_floor"], 1):
        node = [actual, None]
        if node[0] is not None:
            node[1] = next(on_map)

        match node:
            case ("M", "M"):
                cls = NormalEncounter
            case ("M", "?"):
                cls = EventEncounter
            case ("E", "E"):
                cls = EliteEncounter
            case ("E", "?"): # only happens if the Deadly Events modifier is on
                cls = EventElite
            case ("$", "$"):
                cls = Merchant
            case ("$", "?"):
                cls = EventMerchant
            case ("T", "T"):
                cls = Treasure
            case ("T", "?"):
                cls = EventTreasure
            case ("?", "?"):
                cls = Event
            case ("R", "R"):
                cls = Campfire
            case ("B", "BOSS"):
                cls = Boss
            case (None, None):
                if floor < 50: # kind of a hack for the first two acts
                    cls = BossChest
                elif len(parser[prefix + "max_hp_per_floor"]) < floor:
                    cls = Victory
                else:
                    cls = Act4Transition
            case (a, b):
                raise ValueError(f"Error: the combination of map node {b!r} and content {a!r} is undefined")

        yield cls.from_parser(parser, floor)

class EncounterBase(NodeData):
    """A base data class for Spire node encounters."""

    def __init__(self, damage: dict):
        super().__init__()
        self._damage = damage

    @classmethod
    def from_parser(cls, parser, floor: int, *extra):
        prefix = ""
        if "victory" not in parser: # this is a save file
            prefix = "metric_"

        for damage in parser[prefix + "damage_taken"]:
            if damage["floor"] == floor:
                break
        else:
            raise ValueError(f"no fight happened on floor {floor}")

        return super().from_parser(parser, floor, damage, *extra)

    def _description(self, to_append: dict[int, list[str]]) -> str:
        if 3 not in to_append:
            to_append[3] = []
        to_append[3].append(f"{self.damage} damage")
        to_append[3].append(f"{self.turns} turns")
        return super()._description(to_append)

    @property
    def name(self) -> str:
        return self._damage["enemies"]

    @property
    def damage(self) -> int:
        return int(self._damage["damage"])

    @property
    def turns(self) -> int:
        return int(self._damage["turns"])

class NormalEncounter(EncounterBase):
    room_type = "Enemy"
    map_icon = "fight_normal.png"

class EventEncounter(EncounterBase):
    room_type = "Unknown (Enemy)"
    map_icon = "event_fight.png"

class Treasure(NodeData):
    room_type = "Treasure"
    map_icon = "treasure_chest.png"

    def __init__(self, has_blue_key: bool, relic: str):
        super().__init__()
        self._bluekey = False
        self._key_relic = relic

    def _description(self, to_append: dict[int, list[str]]) -> str:
        if self.blue_key:
            if 5 not in to_append:
                to_append[5] = []
            to_append[5].append(f"Skipped {self.key_relic} for the Sapphire key.")
        return super()._description(to_append)

    @classmethod
    def from_parser(cls, parser, floor: int, *extra):
        has_blue_key = False
        relic = ""
        d = parser.get("basemod:mod_saves", ())
        if "BlueKeyRelicSkippedLog" in d:
            if d["BlueKeyRelicSkippedLog"]["floor"] == floor:
                relic = d["BlueKeyRelicSkippedLog"]["relicID"]
                has_blue_key = True
        elif "blue_key_relic_skipped_log" in parser:
            if parser["blue_key_relic_skipped_log"]["floor"] == floor:
                relic = parser["blue_key_relic_skipped_log"]["relicID"]
                has_blue_key = True
        return super().from_parser(parser, floor, has_blue_key, relic, *extra)

    @property
    def blue_key(self) -> bool:
        return self._bluekey

    @property
    def key_relic(self) -> str | None:
        if not self.blue_key:
            return None
        return self._key_relic

class EventTreasure(Treasure):
    room_type = "Unknown (Treasure)"
    map_icon = "event_chest.png"

class EliteEncounter(EncounterBase):
    room_type = "Elite"
    map_icon = "fight_elite.png"

class EventElite(EliteEncounter):
    room_type = "Unknown (Elite)"
    map_icon = "event.png"

class Event(NodeData):
    room_type = "Unknown"
    map_icon = "event.png"

class Merchant(NodeData):
    room_type = "Merchant"
    map_icon = "shop.png"

class EventMerchant(Merchant):
    room_type = "Unknown (Merchant)"
    map_icon = "event_shop.png"

class Campfire(NodeData):
    room_type = "Rest"
    map_icon = "rest.png"

class Boss(EncounterBase):
    room_type = "Boss"
    map_icon = "boss_node.png"

class BossChest(NodeData):
    room_type = "Boss Chest"
    map_icon = "boss_chest.png"
    end_of_act = True

class Act4Transition(NodeData):
    room_type = "Transition into Act 4"
    map_icon = "event.png"
    end_of_act = True

class Victory(NodeData):
    room_type = "Victory!"
    map_icon = "event.png"
