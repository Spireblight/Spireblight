from typing import Generator

__all__ = ["get_nodes", "get_node", "get_character"]

# TODO: Handle the website display part, figure out details of these classes later

_chars = {"THE_SILENT": "Silent"}

def get_character(x):
    if "character_chosen" in x.data:
        c = _chars.get(x.data["character_chosen"])
        if c is None:
            return x.data["character_chosen"].title()

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

    def __init__(self):
        if self.room_type == NodeData.room_type or self.map_icon == NodeData.map_icon:
            raise ValueError(f"Cannot create NodeData subclass {self.__class__.__name__!r}")
        self._floor = None
        self._maxhp = None
        self._curhp = None
        self._gold = None
        self._cards = []
        self._relics = []
        self._potions = []

    @classmethod
    def from_parser(cls, parser, floor: int, *extra):
        """Create a NodeData instance from a parser and floor number.

        This is the recommended way to create NodeData instances. All
        subclasses should call it to create a new instance. Extra arguments
        will be passed to `__init__` for instance creation."""

        data: dict = parser.data
        prefix = ""
        if "victory" not in data: # this is a save file
            prefix = "metric_"

        self = cls(*extra)
        self._floor = floor
        self._maxhp = data[prefix + "max_hp_per_floor"][floor - 1]
        self._curhp = data[prefix + "current_hp_per_floor"][floor - 1]
        self._gold = data[prefix + "gold_per_floor"][floor - 1]

        for cards in data[prefix + "card_choices"]:
            if cards["floor"] == floor:
                self._cards.append(cards)

        for relic in data[prefix + "relics_obtained"]:
            if relic["floor"] == floor:
                self._relics.append(relic["key"])

        for potion in data[prefix + "potions_obtained"]:
            if potion["floor"] == floor:
                self._potions.append(potion["key"])

        return self

    def description(self, to_append: dict[int, list[str]] = None) -> str:
        text = []
        if to_append is None:
            to_append = {}
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
            text.extend(self.potions)

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

def get_node(parser, floor: int) -> NodeData:
    for node in get_nodes(parser):
        if node.floor == floor:
            return node
    raise IndexError(f"We did not reach floor {floor}")

def get_nodes(parser) -> Generator[NodeData, None, None]:
    prefix = ""
    if "victory" not in parser.data:
        prefix = "metric_"
    on_map = iter(parser.data[prefix + "path_taken"])
    for floor, actual in enumerate(parser.data[prefix + "path_per_floor"], 1):
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
                cls = BossChest
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
        data: dict = parser.data
        prefix = ""
        if "victory" not in data: # this is a save file
            prefix = "metric_"

        for damage in data[prefix + "damage_taken"]:
            if damage["floor"] == floor:
                break
        else:
            raise ValueError(f"no fight happened on floor {floor}")

        return super().from_parser(parser, floor, damage, *extra)

    def description(self, to_append: dict[int, list[str]] = None) -> str:
        if to_append is None:
            to_append = {}
        if 3 not in to_append:
            to_append[3] = []
        to_append[3].append(f"{self.damage} damage")
        to_append[3].append(f"{self.turns} turns")
        return super().description(to_append)

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

    def description(self, to_append: dict[int, list[str]] = None) -> str:
        if to_append is None:
            to_append = {}
        if self.blue_key:
            if 5 not in to_append:
                to_append[5] = []
            to_append[5].append(f"Skipped {self.key_relic} for the Sapphire key.")
        return super().description(to_append)

    @classmethod
    def from_parser(cls, parser, floor: int, *extra):
        has_blue_key = False
        relic = ""
        d = parser.data.get("basemod:mod_saves", ())
        if "BlueKeyRelicSkippedLog" in d: # XXX: check how savefiles do it
            if d["BlueKeyRelicSkippedLog"]["floor"] == floor:
                relic = d["BlueKeyRelicSkippedLog"]["relicID"]
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
