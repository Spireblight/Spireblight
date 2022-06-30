from typing import Generator

__all__ = ["get_nodes", "get_node"]

# TODO: Handle the website display part, figure out details of these classes later

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
            ret.extend(cards["skipped"])
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
    room_type = "combat"
    map_icon = "fight_normal.png"

class EventEncounter(EncounterBase):
    room_type = "combat (event)"
    map_icon = "event_fight.png"

class Treasure(NodeData):
    room_type = "treasure chest"
    map_icon = "treasure_chest.png"

class EventTreasure(Treasure):
    room_type = "treasure chest (event)"
    map_icon = "event_chest.png"

class EliteEncounter(EncounterBase):
    room_type = "elite"
    map_icon = "fight_elite.png"

class EventElite(EliteEncounter):
    room_type = "elite (event)"
    map_icon = "event.png"

class Event(NodeData):
    room_type = "event"
    map_icon = "event.png"

class Merchant(NodeData):
    room_type = "merchant"
    map_icon = "shop.png"

class EventMerchant(Merchant):
    room_type = "merchant (event)"
    map_icon = "event_shop.png"

class Campfire(NodeData):
    room_type = "rest site"
    map_icon = "rest.png"

class Boss(EncounterBase):
    room_type = "boss"
    map_icon = "boss.png"

class BossChest(NodeData):
    room_type = "boss chest"
    map_icon = "boss_chest.png"
