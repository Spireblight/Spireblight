__all__ = ["Encounter", "EventEncounter"]

# TODO: Handle the website display part, figure out details of these classes later

class GameData:
    room_type = "<UNDEFINED>"

    def __init__(self):
        self._floor = None
        self._maxhp = None
        self._curhp = None
        self._gold = None

    @classmethod
    def from_parser(cls, parser, floor: int, *extra):
        data: dict = parser.data
        prefix = ""
        if "victory" not in data: # this is a save file
            prefix = "metric_"

        self = cls(*extra)
        self._floor = floor
        try:
            self._maxhp = data[prefix + "max_hp_per_floor"][floor]
        except IndexError:
            raise ValueError(f"we did not visit floor {floor}")
        self._curhp = data[prefix + "current_hp_per_floor"][floor]
        self._gold = data[prefix + "gold_per_floor"][floor]

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

def get_node(parser, node: str, floor: int) -> GameData:
    match node:
        case "M":
            return Encounter.from_parser(parser, floor)

class Encounter(GameData):
    """A data class for Spire encounters."""

    room_type = "combat"

    def __init__(self, damage: dict):
        super().__init__()
        self._damage = damage
        self._cards = None

        self._potion = None

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

        self = super().from_parser(damage, *extra)

        for cards in data[prefix + "card_choices"]:
            if cards["floor"] == floor:
                self._cards = cards

        for potion in data[prefix + "potions_obtained"]:
            if potion["floor"] == floor:
                self._potion = potion["key"]
                break

        return self

    @property
    def name(self) -> str:
        return self._damage["enemies"]

    @property
    def damage(self) -> int:
        return self._damage["damage"]

    @property
    def turns(self) -> int:
        return self._damage["turns"]

    @property
    def picked(self) -> str | None:
        if self._cards is None or self._cards["picked"] == "SKIP":
            return None
        return self._cards["picked"]

    @property
    def skipped(self) -> list[str]:
        ret = []
        if self._cards is not None:
            ret.extend(self._cards["skipped"])
        return ret

    @property
    def potion(self) -> str | None:
        return self._potion

class EventEncounter(Encounter):
    room_type = "combat (event)"

class Treasure(GameData):
    room_type = "treasure chest"



class EliteEncounter(Encounter):
    room_type = "elite"

class Merchant(GameData):
    room_type = "merchant"

    def __init__(self):
        pass
