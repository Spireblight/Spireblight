from __future__ import annotations

from typing import Any, Generator

from nameinternal import get_relic, get_card, get_potion

__all__ = ["FileParser", "get_nodes", "get_node"]

# TODO: Handle the website display part, figure out details of these classes later

class NeowBonus:
    def __init__(self, parser: FileParser):
        self.parser = parser

    @property
    def mod_data(self) -> dict[str, Any] | None:
        if "basemod:mod_saves" in self.parser:
            return self.parser["basemod:mod_saves"].get("NeowBonusLog")
        return self.parser.get("neow_bonus_log")

    @property
    def current_hp(self) -> int:
        return self.get_hp()[0]

    @property
    def max_hp(self) -> int:
        return self.get_hp()[1]

    @property
    def gold(self) -> int:
        return self.get_gold()

    @property
    def floor(self) -> int:
        return 0

    @property
    def floor_time(self) -> int:
        return 0

    def get_hp(self) -> tuple[int, int]:
        """Return how much HP the run had before entering floor 1 in a (current, max) tuple."""
        if self.parser.character is None:
            return 0, 0

        match self.parser.character:
            case "Ironclad":
                base = 80
            case "Silent":
                base = 70
            case "Defect":
                base = 75
            case "Watcher":
                base = 72
            case a:
                raise ValueError(f"I don't know how to handle {a}")

        if self.parser["ascension_level"] >= 14: # lower max HP
            base -= 4
            if self.parser.character == "Ironclad":
                base -= 1 # 5 total

        bonus = base // 10

        cur = base

        if self.parser["ascension_level"] >= 6: # take damage
            cur -= (cur // 10)

        if self.mod_data is not None:
            cur -= self.mod_data["damageTaken"]
            cur += self.mod_data["maxHpGained"]
            base -= self.mod_data["maxHpLost"]
            base += self.mod_data["maxHpGained"]
            return (cur, base)

        match self.parser["neow_cost"]:
            case "TEN_PERCENT_HP_LOSS": # actually hardcoded
                base -= bonus
                if cur > base:
                    cur = base
            case "PERCENT_DAMAGE":
                cur -= (cur // 10) * 3

        match self.parser["neow_bonus"]:
            case "TEN_PERCENT_HP_BONUS":
                base += bonus
                cur += bonus
            case "TWENTY_PERCENT_HP_BONUS":
                base += (bonus * 2)
                cur += (bonus * 2)

        return (cur, base)

    def get_gold(self) -> int:
        base = 99
        if self.mod_data is not None:
            base += (self.mod_data["goldGained"] - self.mod_data["goldLost"])
            if "Old Coin" in self.mod_data["relicsObtained"]:
                base += 300
            return base

        if self.parser["neow_cost"] == "NO_GOLD":
            base = 0

        match self.parser["neow_bonus"]:
            case "HUNDRED_GOLD":
                base += 100
            case "TWO_FIFTY_GOLD":
                base += 250
            case "ONE_RARE_RELIC":
                if self.parser["relics"][1] == "Old Coin": # this can break if N'loth is involved
                    base += 300

        return base

    # options 1 & 2

    def bonus_THREE_CARDS(self):
        prefix = self.parser.prefix
        for cards in self.parser[prefix + "card_choices"]:
            if cards["floor"] == 0:
                if cards["picked"] != "SKIP":
                    return f"picked {get_card(cards['picked'])} over {' and '.join(get_card(x) for x in cards['not_picked'])}"
                return f"were offered {', '.join(get_card(x) for x in cards['not_picked'])} but skipped them all"

        raise ValueError("That is not the right bonus??")

    bonus_RANDOM_COLORLESS = bonus_THREE_CARDS

    def bonus_RANDOM_COMMON_RELIC(self):
        if self.mod_data is not None:
            return f"picked a random Common relic, and got {get_relic(self.mod_data['relicsObtained'][0])}"
        return "picked a random Common relic"

    def bonus_REMOVE_CARD(self):
        if self.mod_data is not None:
            return f"removed {get_card(self.mod_data['cardsRemoved'][0])}"
        return "removed a card"

    def bonus_TRANSFORM_CARD(self):
        if self.mod_data is not None:
            return f"transformed {get_card(self.mod_data['cardsTransformed'][0])} into {get_card(self.mod_data['cardsObtained'][0])}"
        return "transformed a card"

    def bonus_UPGRADE_CARD(self):
        if self.mod_data is not None:
            return f"upgraded {get_card(self.mod_data['cardsUpgraded'][0])}"
        return "upgraded a card"

    def bonus_THREE_ENEMY_KILL(self):
        return "got Neow's Lament to get three fights with enemies having 1 HP"

    def bonus_THREE_SMALL_POTIONS(self):
        potions = []
        skipped = []
        prefix = self.parser.prefix
        for potion in self.parser[prefix + "potions_obtained"]:
            if potion["floor"] == 0:
                potions.append(get_potion(potion["key"]))
        if self.mod_data is not None:
            if "basemod:mod_saves" in self.parser:
                s = self.parser["basemod:mod_saves"]["RewardsSkippedLog"]
            else:
                s = self.parser["rewards_skipped"]
            for skip in s:
                if skip["floor"] == 0:
                    skipped.extend(get_potion(x) for x in skip["potions"])
        if skipped:
            return f"got {' and '.join(potions)}, and skipped {' and '.join(skipped)}"
        return f"got {' and '.join(potions)}"

    def bonus_TEN_PERCENT_HP_BONUS(self):
        if self.mod_data is not None:
            return f"gained {self.mod_data['maxHpGained']} Max HP"
        return "gained 10% Max HP"

    def bonus_ONE_RANDOM_RARE_CARD(self):
        if self.mod_data is not None:
            return f"picked a random Rare card, and got {get_card(self.mod_data['cardsObtained'][0])}"
        return "picked a random Rare card"

    def bonus_HUNDRED_GOLD(self):
        return "got 100 gold"

    # option 3

    def bonus_TWO_FIFTY_GOLD(self):
        return "got 250 gold"

    def bonus_TWENTY_PERCENT_HP_BONUS(self):
        if self.mod_data is not None:
            return f"gained {self.mod_data['maxHpGained']} Max HP"
        return "gained 20% Max HP"

    bonus_RANDOM_COLORLESS_2 = bonus_THREE_CARDS
    bonus_THREE_RARE_CARDS = bonus_THREE_CARDS

    def bonus_REMOVE_TWO(self):
        if self.mod_data is not None:
            return f"removed {' and '.join(get_card(x) for x in self.mod_data['cardsRemoved'])}"
        return "removed two cards"

    def bonus_TRANSFORM_TWO_CARDS(self):
        if self.mod_data is not None:
            return f"transformed {' and '.join(get_card(x) for x in self.mod_data['cardsTransformed'])} into {' and '.join(get_card(x) for x in self.mod_data['cardsObtained'])}"
        return "transformed two cards"

    def bonus_ONE_RARE_RELIC(self):
        if self.mod_data is not None:
            return f"picked a random Rare relic and got {get_relic(self.mod_data['relicsObtained'][0])}"
        return "obtained a random Rare relic"

    # option 4

    def bonus_BOSS_RELIC(self):
        if self.mod_data is not None:
            return f"swapped our starter relic for {get_relic(self.mod_data['relicsObtained'][0])}"
        return f"swapped our starter relic for {get_relic(self.parser['relics'][0])}" # N'loth can mess with this

    # costs for option 3

    def cost_CURSE(self):
        if self.mod_data is not None:
            return f"got cursed with {get_card(self.mod_data['cardsObtained'][0])}"
        return "got a random curse"

    def cost_NO_GOLD(self):
        return "lost all gold"

    def cost_TEN_PERCENT_HP_LOSS(self):
        if self.mod_data is not None:
            return f"lost {self.mod_data['maxHpLost']} Max HP"
        return "lost 10% Max HP"

    def cost_PERCENT_DAMAGE(self):
        if self.mod_data is not None:
            return f"took {self.mod_data['damageTaken']} damage"
        return "took damage (current HP / 10, rounded down, * 3)"

    def as_str(self) -> str:
        neg = getattr(self, f"cost_{self.parser['neow_cost']}", None)
        pos = getattr(self, f"bonus_{self.parser['neow_bonus']}")

        if neg is None:
            msg = f"We {pos()}."
        else:
            msg = f"We {neg()}, and then {pos()}."

        return msg

    def card_delta(self) -> int:
        num = 10
        if self.parser.character == "Silent":
            num += 2

        if self.parser["ascension_level"] >= 10:
            num += 1

        prefix = self.parser.prefix
        for cards in self.parser[prefix + "card_choices"]:
            if cards["floor"] == 0:
                if cards["picked"] != "SKIP":
                    num += 1

        if self.parser["neow_cost"] == "CURSE":
            num += 1

        match self.parser["neow_bonus"]:
            case "REMOVE_CARD":
                num -= 1
            case "REMOVE_TWO":
                num -= 2
            case "ONE_RANDOM_RARE_CARD":
                num += 1

        return num

    def relic_delta(self) -> int:
        num = 1
        if self.parser["neow_bonus"] in ("THREE_ENEMY_KILL", "ONE_RARE_RELIC", "RANDOM_COMMON_RELIC"):
            num += 1
        return num

    def potion_delta(self) -> int:
        num = 0
        prefix = self.parser.prefix
        for potion in self.parser[prefix + "potions_obtained"]:
            if potion["floor"] == 0:
                num += 1
        return num

    @property
    def card_count(self) -> int:
        return self.card_delta()

    @property
    def relic_count(self) -> int:
        return self.relic_delta()

    @property
    def potion_count(self) -> int:
        return self.potion_delta()

_chars = {"THE_SILENT": "Silent"}

class FileParser: # TODO: relics hover
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.neow_bonus = NeowBonus(self)
        self._cache = {}
        self._pathed = False
        self._character: str | None = None

    def __getitem__(self, item: str) -> Any:
        return self.data[item]

    def __contains__(self, item: str) -> bool:
        return item in self.data

    def get(self, item: str, default=None):
        return self.data.get(item, default)

    @property
    def prefix(self) -> str:
        return ""

    @property
    def character(self) -> str | None:
        if self._character is None:
            return None

        c = _chars.get(self._character)
        if c is None:
            c = self._character.title()
        return c

    @property
    def seed(self) -> int:
        if "seed" not in self._cache:
            c = "0123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"

            try:
                seed = int(self["seed"]) # might be stored as a str
            except KeyError:
                seed = int(self["seed_played"])

            # this is a bit weird, but lets us convert a negative number, if any, into a positive one
            num = int.from_bytes(seed.to_bytes(20, "big", signed=True).strip(b"\xff"), "big")
            s = []

            while num:
                num, i = divmod(num, 35)
                s.append(c[i])

            s.reverse() # everything's backwards, for some reason... but this works

            self._cache["seed"] = "".join(s)

        return self._cache["seed"]

    @property
    def path(self) -> Generator[NodeData, None, None]:
        """Return the run's path. This is cached."""
        if not self._pathed:
            if "path" in self._cache:
                raise RuntimeError("Called RunParser.path while it's generating")
            self._cache["path"] = []
            if "basemod:mod_saves" in self:
                floor_time = self["basemod:mod_saves"].get("FloorExitPlaytimeLog", ())
            else:
                floor_time = self.get("floor_exit_playtime", ())
            prev = 0
            card_count = self.neow_bonus.card_delta()
            relic_count = self.neow_bonus.relic_delta()
            potion_count = self.neow_bonus.potion_delta()
            for node, cached in get_nodes(self, self._cache.pop("old_path", None)):
                try:
                    t = floor_time[node.floor - 1]
                except IndexError:
                    t = 0
                if cached: # don't recompute the deltas -- just grab their cached counts
                    card_count = node.card_count
                    relic_count = node.relic_count
                    potion_count = node.potion_count
                else:
                    card_count += node.card_delta
                    node._card_count = card_count
                    relic_count += node.relic_delta
                    node._relic_count = relic_count
                    potion_count += node.potion_delta
                    node._potion_count = potion_count
                    node._floor_time = t - prev
                prev = t
                self._cache["path"].append(node)
                yield node
            self._pathed = True
            return

        yield from self._cache["path"] # generator so that it's a consistent type

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
        self._floor_time = None
        self._card_count = None
        self._relic_count = None
        self._potion_count = None
        self._cards = []
        self._relics = []
        self._potions = []
        self._usedpotions = []
        self._discarded = []
        self._cache = {}

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        """Create a NodeData instance from a parser and floor number.

        This is the recommended way to create NodeData instances. All
        subclasses should call it to create a new instance. Extra arguments
        will be passed to `__init__` for instance creation."""

        prefix = parser.prefix

        self = cls(*extra)
        self._floor = floor
        try:
            self._maxhp = parser[prefix + "max_hp_per_floor"][floor - 1]
            self._curhp = parser[prefix + "current_hp_per_floor"][floor - 1]
            self._gold = parser[prefix + "gold_per_floor"][floor - 1]
            if "potion_use_per_floor" in parser: # run file
                self._usedpotions.extend(get_potion(x) for x in parser["potion_use_per_floor"][floor - 1])
            elif "PotionUseLog" in parser.get("basemod:mod_saves", ()): # savefile
                self._usedpotions.extend(get_potion(x) for x in parser["PotionUseLog"][floor - 1])
        except IndexError:
            self._maxhp = parser[prefix + "max_hp_per_floor"][floor - 2]
            self._curhp = parser[prefix + "current_hp_per_floor"][floor - 2]
            self._gold = parser[prefix + "gold_per_floor"][floor - 2]

        try:
            self._discarded.extend(parser.get("potion_discard_per_floor", ())[floor - 1])
        except IndexError:
            pass

        for cards in parser[prefix + "card_choices"]:
            if cards["floor"] == floor:
                self._cards.append(cards)

        for relic in parser[prefix + "relics_obtained"]:
            if relic["floor"] == floor:
                self._relics.append(get_relic(relic["key"]))

        for potion in parser[prefix + "potions_obtained"]:
            if potion["floor"] == floor:
                self._potions.append(get_potion(potion["key"]))

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
            text.extend(f"- {x}" for x in self.relics)

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
                ret.append(get_card(cards["picked"]))
        return ret

    @property
    def skipped(self) -> list[str]:
        ret = []
        for cards in self._cards:
            ret.extend(get_card(x) for x in cards["not_picked"])
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

    @property
    def floor_time(self) -> int:
        if self._floor_time is None:
            return 0
        return self._floor_time

    @property
    def card_delta(self) -> int:
        return len(self.picked)

    @property
    def relic_delta(self) -> int:
        return len(self.relics)

    @property
    def potion_delta(self) -> int:
        return len(self.potions) - len(self.used_potions) - len(self._discarded)

    @property
    def card_count(self) -> int:
        if self._card_count is None:
            return 0
        return self._card_count

    @property
    def relic_count(self) -> int:
        if self._relic_count is None:
            return 1
        return self._relic_count

    @property
    def potion_count(self) -> int:
        if self._potion_count is None:
            return 0
        return self._potion_count

def get_node(parser: FileParser, floor: int) -> NodeData:
    for node, cached in get_nodes(parser, None):
        if node.floor == floor:
            return node
    raise IndexError(f"We did not reach floor {floor}")

def get_nodes(parser: FileParser, maybe_cached: list[NodeData] | None) -> Generator[tuple[NodeData, bool], None, None]:
    prefix = parser.prefix
    on_map = iter(parser[prefix + "path_taken"])
    # maybe_cached will not be None if this is a savefile we're iterating through
    # which means we already know previous floors, so just use that.
    # to be safe, regenerate the last floor, since it might have changed
    # (e.g. the last time we saw it, we were in-combat, and now we're out of it)
    # this is also used for run files for which we had the savefile
    if maybe_cached is not None:
        maybe_cached.pop()
    for floor, actual in enumerate(parser[prefix + "path_per_floor"], 1):
        if maybe_cached:
            maybe_node = maybe_cached.pop(0)
            if floor == maybe_node.floor: # if it's not, then something's wrong. just regen it
                yield maybe_node, True
                continue

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

        yield cls.from_parser(parser, floor), False

class EncounterBase(NodeData):
    """A base data class for Spire node encounters."""

    def __init__(self, damage: dict):
        super().__init__()
        self._damage = damage

    @classmethod
    def from_parser(cls, parser, floor: int, *extra):
        prefix = parser.prefix
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
        self._bluekey = has_blue_key
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
        return super().from_parser(parser, floor, has_blue_key, get_relic(relic), *extra)

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

class Event(NodeData): # TODO: cards, relics, and potions obtained, delta might not get updated
    room_type = "Unknown"
    map_icon = "event.png"

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        return super().from_parser(parser, floor, *extra)

class Merchant(NodeData):
    room_type = "Merchant"
    map_icon = "shop.png"

    def __init__(self, bought: dict[str, list[str]], purged: str | None, contents: dict[str, list[str]] | None):
        super().__init__()
        self._bought = bought
        self._purged = purged
        self._contents = contents

    def _description(self, to_append: dict[int, list[str]]) -> str:
        if self.purged:
            if 5 not in to_append:
                to_append[5] = []
            to_append[5].append(f"* Removed {self.purged}")
        if self.contents:
            if 6 not in to_append:
                to_append[6] = []
            to_append[6].append("Skipped:")
            if self.contents["relics"]:
                to_append[6].append("* Relics")
                to_append[6].extend(f"  - {x}" for x in self.contents["relics"])
            if self.contents["cards"]:
                to_append[6].append("* Cards")
                to_append[6].extend(f"  - {x}" for x in self.contents["cards"])
            if self.contents["potions"]:
                to_append[6].append("* Potions")
                to_append[6].extend(f"  - {x}" for x in self.contents["potions"])
        return super()._description(to_append)

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        bought = {"cards": [], "relics": [], "potions": []}
        purged = None
        contents = None
        for i, purchased in enumerate(parser[parser.prefix + "item_purchase_floors"]):
            if purchased == floor:
                value = parser[parser.prefix + "items_purchased"][i]
                card = get_card(value, None)
                relic = get_relic(value, None)
                potion = get_potion(value, None)
                if card is not None:
                    bought["cards"].append(card)
                elif relic is not None:
                    bought["relics"].append(relic)
                elif potion is not None:
                    bought["potions"].append(potion)

        try:
            index = parser[parser.prefix + "items_purged_floors"].index(floor)
        except ValueError:
            pass
        else:
            purged = get_card(parser[parser.prefix + "items_purged"][index])

        d = ()
        if "shop_contents" in parser:
            d = parser["shop_contents"]
        elif "basemod:mod_saves" in parser:
            d = parser["basemod:mod_saves"].get("ShopContentsLog", ())
        if d:
            contents = {"relics": [], "cards": [], "potions": []}
        for data in d:
            if data["floor"] == floor:
                for relic in data["relics"]:
                    contents["relics"].append(get_relic(relic))
                for card in data["cards"]:
                    contents["cards"].append(get_card(card))
                for potion in data["potions"]:
                    contents["potions"].append(get_potion(potion))

        return super().from_parser(parser, floor, bought, purged, contents, *extra)

    @property
    def picked(self) -> list[str]:
        return super().picked + self.bought["cards"]

    @property
    def relics(self) -> list[str]:
        return super().relics + self.bought["relics"]

    @property
    def potions(self) -> list[str]:
        return super().potions + self.bought["potions"]

    @property
    def bought(self) -> dict[str, list[str]]:
        return self._bought

    @property
    def purged(self) -> str | None:
        return self._purged

    @property
    def contents(self) -> dict[str, list[str]] | None:
        return self._contents

    @property
    def card_delta(self) -> int:
        return super().card_delta - (self.purged is not None)

class EventMerchant(Merchant):
    room_type = "Unknown (Merchant)"
    map_icon = "event_shop.png"

class Campfire(NodeData):
    room_type = "Rest Site"
    map_icon = "rest.png"

    def __init__(self, key: str, data: str | None):
        super().__init__()
        self._key = key
        self._data = data

    def _description(self, to_append: dict[int, list[str]]) -> str:
        if 4 not in to_append:
            to_append[4] = []
        to_append[4].append(self.action)
        return super()._description(to_append)

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        key = None
        data = None
        for rest in parser[parser.prefix + "campfire_choices"]:
            if rest["floor"] == floor:
                key = rest["key"]
                data = rest.get("data")
        return super().from_parser(parser, floor, key, data, *extra)

    @property
    def action(self) -> str:
        match self._key:
            case "REST":
                return "Rested"
            case "RECALL":
                return "Got the Ruby key"
            case "SMITH":
                return f"Upgraded {get_card(self._data)}"
            case "LIFT":
                return f"Lifted for additional strength (Total: {self._data})"
            case "DIG":
                return "Dug!"
            case "PURGE":
                return f"Toked {get_card(self._data)}"
            case a:
                return f"Did {a!r} with {self._data!r}, but I'm not sure what this means"

class Boss(EncounterBase):
    room_type = "Boss"
    map_icon = "boss_node.png"

class BossChest(NodeData): # TODO: Boss relics obtained and skipped
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

    def __init__(self, score: int | None, data: list[str]):
        self._score = score
        self._data = data
        super().__init__()

    def _description(self, to_append: dict[int, list[str]]) -> str:
        if self.score:
            if 6 not in to_append:
                to_append[6] = []
            to_append[6].extend(self.score_breakdown)
            to_append[6].append(f"Score: {self.score}")
        return super()._description(to_append)

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        score = parser.get("score", 0)
        breakdown = parser.get("score_breakdown", [])
        return super().from_parser(parser, floor, score, breakdown, *extra)

    @property
    def score(self) -> int:
        return self._score

    @property
    def score_breakdown(self) -> list[str]:
        return self._data
