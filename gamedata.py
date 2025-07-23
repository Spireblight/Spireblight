from __future__ import annotations

from typing import Any, Generator, Iterable, NamedTuple, Optional, TYPE_CHECKING

import urllib.parse
import collections
import datetime
import math
import io

from abc import ABC, abstractmethod

from aiohttp.web import Request, Response, HTTPForbidden, HTTPNotImplemented, HTTPNotFound

from typehints import *
from utils import format_for_slaytabase

try:
    from matplotlib import pyplot as plt
except ModuleNotFoundError:
    plt = None

try:
    from mpld3 import fig_to_html
except ModuleNotFoundError:
    fig_to_html = None

from nameinternal import get_event, get_relic_stats, get_run_mod, get, get_card, Card, SingleCard, Relic, Potion
from sts_profile import Profile
from logger import logger

from configuration import config

if TYPE_CHECKING:
    from runs import StreakInfo

__all__ = ["FileParser"]

# XXX Make sure to remove private member access from outside the class
# search for #PRIV# in this file for places that need modified
# put all of damage_taken, max_hp_{gained,lost} on the base class

class BaseNode(ABC):
    """This the common base class for all path nodes, including Neow.

    This provides basic utility functions that subclasses may use.

    This also has abstract methods and properties that need to be overridden.

    Subclasses can - and should - implement their own 'get_description' method.
    This takes one argument, type 'collections.defaultdict[int, list[str]]',
    and should modify that mapping in-place. Returning any non-None value will
    raise an error. The method should **NOT** attempt to call the superclass
    version of it with super(). BaseNode's 'description' method walks through
    the entire superclass tree, including third-party classes, in Method
    Resolution Order, and calls each existing 'get_description' method in each
    class. Failure to implement this method in a direct subclass will raise an
    error, though additional classes in the MRO without one will pass silently.

    Built-in index keys all use even numbers. Result will be joined together
    with newlines, and returned in ascending order. Custom code should only add
    data to odd indices. Ranges are provided here; refer to the relevant
    subclass for details. Calling order between various methods is not
    guaranteed - appending to a key already used may have unexpected results.

    0     - Basic stuff; only for things that all nodes share
    2     - Event-specific combat setup
    4     - Combat results (damage taken, turns elapsed, etc.)
    6     - Unique values (key obtained, campfire option, etc.)
    8     - Neow bonus
    10-20 - Potion usage data
    30-36 - Relic obtention data
    40-62 - Event results
    70-78 - Shop contents
    100+  - Special stuff; reserved for bugged or modded content

    """

    room_type = ""
    end_of_act = False

    # the following are handled differently in each branch
    # as such, we only tell the type checkers what they are
    # if a subclass does not implement these, it is a bug

    current_hp: int
    max_hp: int
    gold: int

    floor: int

    card_count: int
    relic_count: int
    potion_count: int
    fights_count: int
    turns_count: int

    def __init__(self, parser: FileParser, *extra):
        super().__init__(*extra)
        self.parser = parser
        self.floor_time: int = 0

    @property
    def potions(self) -> list[Potion]:
        """Return a read-only list of potions obtained on this node."""
        return self.parser.potions[self.floor]

    @property
    def picked(self) -> list[SingleCard]:
        """Return the cards picked this floor."""
        ret = []
        for card in self.parser.card_choices[0][self.floor]:
            ret.append(card)
        return ret

    @property
    def skipped(self) -> list[SingleCard]:
        """Return the cards skipped this floor."""
        ret = []
        for card in self.parser.card_choices[1][self.floor]:
            ret.append(card)
        return ret

    @property
    def cards_obtained(self) -> list[SingleCard]:
        """Return the cards obtained outside of a card reward this floor."""
        return []

    @property
    def cards_removed(self) -> list[SingleCard]:
        """Return the cards that were removed this floor."""
        return []

    @property
    def cards_transformed(self) -> list[SingleCard]:
        """Return the cards that were transformed away this floor."""
        return []

    @property
    def cards_upgraded(self) -> list[SingleCard]:
        """Return the cards that were upgraded this floor, before the upgrade."""
        return []

    @property
    def relics(self) -> list[Relic]:
        """Return the relics obtained this floor."""
        return self.parser.relics_obtained[self.floor]

    @property
    def relics_lost(self) -> list[Relic]:
        """Return the relics lost this floor."""
        return []

    @property
    def used_potions(self) -> list[Potion]:
        """Return which potions were used on this floor."""
        return self.parser.potions_use[self.floor]

    @property
    def potions_from_alchemize(self) -> list[Potion]:
        """Return the potions obtained through Alchemize on this floor."""
        return self.parser.potions_alchemize[self.floor]

    @property
    def potions_from_entropic(self) -> list[Potion]:
        """Return the potions obtained through Entropic Brew on this floor."""
        return self.parser.potions_entropic[self.floor]

    @property
    def discarded_potions(self) -> list[Potion]:
        """Return potions which were mercilessly discarded on this floor."""
        return self.parser.potions_discarded[self.floor]

    @property
    def all_potions_received(self) -> list[Potion]:
        """Return all potions which were received on this floor."""
        return self.potions + self.potions_from_alchemize + self.potions_from_entropic

    @property
    def all_potions_dropped(self) -> list[Potion]:
        """Return all potions which were used or discarded this floor."""
        return self.used_potions + self.discarded_potions

    @property
    def skipped_relics(self) -> list[Relic]:
        """Return a list of relics that were offered but skipped here."""
        return self.parser.skipped_rewards[0][self.floor]

    @property
    def skipped_potions(self) -> list[Potion]:
        """Return a list of potions that were offered but skipped here."""
        return self.parser.skipped_rewards[1][self.floor]

    @property
    def name(self) -> str:
        """Return the name to display for the node."""
        return ""

    def card_delta(self) -> int:
        """How many cards were added or removed on this floor."""
        return len(self.picked) + len(self.cards_obtained) - len(self.cards_removed) - len(self.cards_transformed)

    def relic_delta(self) -> int:
        """How many relics were gained or lost on this floor."""
        return len(self.relics) - len(self.relics_lost)

    def potion_delta(self) -> int:
        """How many potions were obtained, used, or discarded on this floor."""
        return len(self.all_potions_received) - len(self.all_potions_dropped)

    def fights_delta(self) -> int:
        """How many fights were fought on this floor."""
        return 0

    def turns_delta(self) -> int:
        """How many turns were spent on this floor."""
        return 0

    def description(self) -> str:
        """Return a newline-separated description for the current node.

        Refer to BaseNode's docstring for implementation details."""

        # TODO: Move away from numbers and use Enums

        to_append = collections.defaultdict(list)
        done = []
        for cls in type(self).__mro__:
            try:
                fn = cls.get_description
            except AttributeError:
                continue # support multi-classing if you're Emily Axford
            if fn in done:
                continue
            if fn(self, to_append) is not None: # returned something
                raise RuntimeError(f"'{cls.__name__}.get_description()' returned a non-None value.")
            done.append(fn)
            if not to_append:
                continue
            try:
                if (n := min(to_append)) < 0:
                    raise ValueError(f"Class {cls.__name__!r} used negative index {n} (positive values only)")
            except TypeError as e:
                raise TypeError(f"Class {cls.__name__!r} did not use a number-like type") from e

        final = []
        desc = list(to_append.items())
        desc.sort(key=lambda x: x[0])
        for i, text in desc:
            final.extend(text)

        return "\n".join(final)

    def escaped_description(self) -> str:
        return self.description().replace("\n", "<br>").replace("'", "\\'")

    # Every subclass must implement this method, and NOT call this one

    def get_description(self, to_append: dict[int, list[str]]):
        """Add each individual node's description, as needed."""
        if self.room_type:
            to_append[0].append(f"{self.room_type}")
        to_append[0].append(f"{self.current_hp}/{self.max_hp} - {self.gold} gold")

        if self.name:
            to_append[0].append(self.name)

class NeowBonus(BaseNode):

    all_bonuses = {
        "THREE_CARDS": "Choose one of three cards to obtain.",
        "RANDOM_COLORLESS": "Choose an uncommon Colorless card to obtain.",
        "RANDOM_COMMON_RELIC": "Obtain a random common relic.",
        "REMOVE_CARD": "Remove a card.",
        "TRANSFORM_CARD": "Transform a card.",
        "UPGRADE_CARD": "Upgrade a card.",
        "THREE_ENEMY_KILL": "Enemies in the first three combats have 1 HP.",
        "THREE_SMALL_POTIONS": "Gain 3 random potions.",
        "TEN_PERCENT_HP_BONUS": "Gain 10% Max HP.",
        "ONE_RANDOM_RARE_CARD": "Gain a random Rare card.",
        "HUNDRED_GOLD": "Gain 100 gold.",

        "TWO_FIFTY_GOLD": "Gain 250 gold.",
        "TWENTY_PERCENT_HP_BONUS": "Gain 20% Max HP.",
        "RANDOM_COLORLESS_2": "Choose a Rare colorless card to obtain.",
        "THREE_RARE_CARDS": "Choose a Rare card to obtain.",
        "REMOVE_TWO": "Remove two cards.",
        "TRANSFORM_TWO_CARDS": "Transform two cards.",
        "ONE_RARE_RELIC": "Obtain a random Rare relic.",

        "BOSS_RELIC": "Lose your starter relic. Obtain a random Boss relic.",

        # more Neow

        "CHOOSE_OTHER_CHAR_RANDOM_COMMON_CARD": "Choose a common card from another character to obtain.",
        "CHOOSE_OTHER_CHAR_RANDOM_UNCOMMON_CARD": "Choose an uncommon card from another character to obtain.",
        "CHOOSE_OTHER_CHAR_RANDOM_RARE_CARD": "Choose a rare card from another character to obtain.",
        "GAIN_RANDOM_SHOP_RELIC": "Obtain a random Shop relic.",
        "GAIN_POTION_SLOT": "Gain a potion slot.",
        "GAIN_TWO_POTION_SLOTS": "Gain two potions slots.",
        "GAIN_TWO_RANDOM_COMMON_RELICS": "Gain two random common relics.",
        "GAIN_UNCOMMON_RELIC": "Obtain a random uncommon relic.",
        "THREE_BIG_POTIONS": "Obtain three random potions.",

        "SWAP_MEMBERSHIP_COURIER": "Take a small loan... of a million gold.",
    }

    all_costs = {
        "CURSE": "Gain a curse.",
        "NO_GOLD": "Lose all gold.",
        "TEN_PERCENT_HP_LOSS": "Lose 10% Max HP.",
        "PERCENT_DAMAGE": "Take damage.",
        "TWO_STARTER_CARDS": "Add two starter cards.",
        "ONE_STARTER_CARD": "Add a starter card.",
    }

    floor = 0

    @property
    def name(self) -> str:
        return "Neow bonus"

    @property
    def choice_made(self) -> bool:
        return bool(self.parser._neow_picked[0])

    @property
    def boon_picked(self) -> str:
        bonus, cost = self.parser._neow_picked
        if cost == "NONE":
            return self.all_bonuses.get(bonus, bonus)
        return f"{self.all_costs.get(cost, cost)} {self.all_bonuses.get(bonus, bonus)}"

    @property
    def boons_skipped(self) -> Generator[str, None, None]:
        data, bonuses, costs = self.parser._neow_data

        if not bonuses or not costs:
            yield "<Could not fetch data>"
            return

        for c, b in zip(costs, bonuses, strict=True):
            if c == "NONE":
                yield self.all_bonuses.get(b, b)
            else:
                yield f"{self.all_costs.get(c, c)} {self.all_bonuses.get(b, b)}"

    @property
    def cards_obtained(self) -> list[SingleCard]:
        ret = super().cards_obtained
        for card in self.parser._neow_data[0].get("cardsObtained", []):
            ret.append(get_card(card))
        return ret

    @property
    def cards_removed(self) -> list[SingleCard]:
        ret = super().cards_removed
        for card in self.parser._neow_data[0].get("cardsRemoved", []):
            ret.append(get_card(card))
        return ret

    @property
    def cards_transformed(self) -> list[SingleCard]:
        ret = super().cards_transformed
        for card in self.parser._neow_data[0].get("cardsTransformed", []):
            ret.append(get_card(card))
        return ret

    @property
    def cards_upgraded(self) -> list[SingleCard]:
        ret = super().cards_upgraded
        for card in self.parser._neow_data[0].get("cardsUpgraded", []):
            ret.append(get_card(card))
        return ret

    @property
    def relics(self) -> list[Relic]:
        ret = super().relics
        for x in self.parser._neow_data[0].get('relicsObtained', ()):
            ret.append(get(x))
        return ret

    @property
    def damage_taken(self) -> int:
        return self.parser._neow_data[0].get("damageTaken", 0)

    @property
    def max_hp_gained(self) -> int:
        return self.parser._neow_data[0].get("maxHpGained", 0)

    @property
    def max_hp_lost(self) -> int:
        return self.parser._neow_data[0].get("maxHpLost", 0)

    def _get_hp(self) -> tuple[int, int]:
        """Return how much HP the run had before entering floor 1 in a (current, max) tuple."""
        if self.parser.character is None:
            return 0, 0

        match self.parser.character:
            case "Snecko":
                base = 85
            case "Ironclad" | "Guardian" | "Champ":
                base = 80
            case "Defect" | "Hermit" | "Blade Gunner" | "Packmaster":
                base = 75
            case "Watcher":
                base = 72
            case "Silent" | "Bronze Automaton":
                base = 70
            case "Hexaghost":
                base = 66
            case "Slime Boss" | "Collector":
                base = 65
            case "Gremlin Gang":
                base = 16
            case a:
                raise ValueError(f"I don't know how to handle {a}")

        if self.parser.ascension_level >= 14: # lower max HP
            base -= math.floor(base/16)

        bonus = base // 10

        cur = base

        if self.parser.ascension_level >= 6: # take damage
            cur -= math.ceil(cur / 10)

        if self.parser._neow_data[0]:
            cur -= self.damage_taken
            cur += self.max_hp_gained
            base -= self.max_hp_lost
            base += self.max_hp_gained
            return (cur, base)

        match self.parser._neow_picked[1]:
            case "TEN_PERCENT_HP_LOSS":
                base -= bonus
                if cur > base:
                    cur = base
            case "PERCENT_DAMAGE":
                cur -= (cur // 10) * 3

        match self.parser._neow_picked[0]:
            case "TEN_PERCENT_HP_BONUS":
                base += bonus
                cur += bonus
            case "TWENTY_PERCENT_HP_BONUS":
                base += (bonus * 2)
                cur += (bonus * 2)

        return (cur, base)

    @property
    def current_hp(self) -> int:
        """Return our current HP after the Neow bonus."""
        return self._get_hp()[0]

    @property
    def max_hp(self) -> int:
        """Return our max HP after the Neow bonus."""
        return self._get_hp()[1]

    @property
    def gold(self) -> int:
        """Return how much gold we have after the Neow bonus."""
        base = 99
        if (d := self.parser._neow_data[0]):
            base += (d["goldGained"] - d["goldLost"])
            if "Old Coin" in d["relicsObtained"]:
                base += 300
            return base

        if self.parser._neow_picked[1] == "NO_GOLD":
            base = 0

        match self.parser._neow_picked[0]:
            case "HUNDRED_GOLD":
                base += 100
            case "TWO_FIFTY_GOLD":
                base += 250
            case "ONE_RARE_RELIC":
                if self.parser.relics_bare[0].name == "Old Coin": # this can break if N'loth is involved
                    base += 300

        return base

    def get_cards(self) -> list[SingleCard]:
        cards = []
        if self.parser.ascension_level >= 10:
            cards.append("AscendersBane")

        match self.parser.character:
            case "Ironclad":
                cards.extend(("Strike_R",) * 5)
                cards.extend(("Defend_R",) * 4)
                cards.append("Bash")
            case "Silent":
                cards.extend(("Strike_G",) * 5)
                cards.extend(("Defend_G",) * 5)
                cards.append("Neutralize")
                cards.append("Survivor")
            case "Defect":
                cards.extend(("Strike_B",) * 4)
                cards.extend(("Defend_B",) * 4)
                cards.append("Zap")
                cards.append("Dualcast")
            case "Watcher":
                cards.extend(("Strike_P",) * 4)
                cards.extend(("Defend_P",) * 4)
                cards.append("Vigilance")
                cards.append("Eruption")
            case a:
                raise ValueError(f"I don't know how to handle {a!r}")

        cards = [get_card(x) for x in cards]

        for x in self.cards_transformed + self.cards_removed:
            cards.remove(x)
        for x in self.cards_obtained:
            cards.append(x)
        for x in self.cards_upgraded:
            index = cards.index(x)
            cards[index].upgrades += 1

        cards.extend(self.picked)

        return cards

    # options 1 & 2

    def bonus_THREE_CARDS(self):
        if self.picked:
            return f"picked {self.picked[0]} over {' and '.join(x.name for x in self.skipped)}"
        if self.skipped:
            return f"were offered {', '.join(x.name for x in self.skipped)} but skipped them all"

        raise ValueError("That is not the right bonus??")

    bonus_RANDOM_COLORLESS = bonus_THREE_CARDS

    def bonus_RANDOM_COMMON_RELIC(self):
        if self.relics:
            return f"got {self.relics[0]}"
        return "picked a random Common relic"

    def bonus_REMOVE_CARD(self):
        if self.cards_removed:
            return f"removed {self.cards_removed[0]}"
        return "removed a card"

    def bonus_TRANSFORM_CARD(self):
        if self.cards_transformed:
            return f"transformed {self.cards_transformed[0]} into {self.cards_obtained[0]}"
        return "transformed a card"

    def bonus_UPGRADE_CARD(self):
        if self.cards_upgraded:
            return f"upgraded {self.cards_upgraded[0]}"
        return "upgraded a card"

    def bonus_THREE_ENEMY_KILL(self):
        return "got Neow's Lament to get three fights with enemies having 1 HP"

    def bonus_THREE_SMALL_POTIONS(self):
        if self.skipped_potions:
            if not self.potions:
                return f"were offered {' and '.join(x.name for x in self.skipped_potions)} and skipped all of them... for some reason"
            return f"got {' and '.join(x.name for x in self.potions)}, and skipped {' and '.join(x.name for x in self.skipped_potions)}"
        return f"got {' and '.join(x.name for x in self.potions)}"

    def bonus_TEN_PERCENT_HP_BONUS(self):
        if self.max_hp_gained:
            return f"gained {self.max_hp_gained} Max HP"
        return "gained 10% Max HP"

    def bonus_ONE_RANDOM_RARE_CARD(self):
        if self.cards_obtained:
            return f"picked a random Rare card, and got {self.cards_obtained[0]}"
        return "picked a random Rare card"

    # option 3

    def bonus_TWO_FIFTY_GOLD(self):
        return "got 250 gold"

    def bonus_TWENTY_PERCENT_HP_BONUS(self):
        if self.max_hp_gained:
            return f"gained {self.max_hp_gained} Max HP"
        return "gained 20% Max HP"

    bonus_RANDOM_COLORLESS_2 = bonus_THREE_CARDS
    bonus_THREE_RARE_CARDS = bonus_THREE_CARDS

    def bonus_REMOVE_TWO(self):
        if self.cards_removed:
            return f"removed {' and '.join(x.name for x in self.cards_removed)}"
        return "removed two cards"

    def bonus_TRANSFORM_TWO_CARDS(self):
        if self.cards_transformed:
            # in case the cost is "gain a curse", the curse will be the first item. this guarantees we only get the last two cards
            return f"transformed {' and '.join(x.name for x in self.cards_transformed)} into {' and '.join(x.name for x in self.cards_obtained[-2:])}"
        return "transformed two cards"

    def bonus_ONE_RARE_RELIC(self):
        if self.relics:
            return f"picked a random Rare relic and got {self.relics[0]}"
        return "obtained a random Rare relic"

    # option 4

    def bonus_BOSS_RELIC(self):
        if self.relics:
            return f"swapped our starter relic for {self.relics[0]}"
        return f"swapped our starter relic for {self.parser.relics_bare[0]}" # N'loth can mess with this

    # more Neow mod

    bonus_CHOOSE_OTHER_CHAR_RANDOM_COMMON_CARD = bonus_THREE_CARDS
    bonus_CHOOSE_OTHER_CHAR_RANDOM_UNCOMMON_CARD = bonus_THREE_CARDS
    bonus_CHOOSE_OTHER_CHAR_RANDOM_RARE_CARD = bonus_THREE_CARDS

    # costs for option 3

    def cost_CURSE(self):
        if self.cards_obtained:
            return f"got cursed with {self.cards_obtained[0]}"
        return "got a random curse"

    def cost_NO_GOLD(self):
        return "lost all gold"

    def cost_TEN_PERCENT_HP_LOSS(self):
        if self.max_hp_lost:
            return f"lost {self.max_hp_lost} Max HP"
        return "lost 10% Max HP"

    def cost_PERCENT_DAMAGE(self):
        if self.damage_taken:
            return f"took {self.damage_taken} damage"
        return "took damage (current HP / 10, rounded down, * 3)"

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[8].append(self.as_str())

    def as_str(self) -> str:
        bonus, cost = self.parser._neow_picked
        neg = getattr(self, f"cost_{cost}", None)
        try:
            pos = getattr(self, f"bonus_{bonus}")
        except AttributeError:
            return "<No option picked/option unknown>"

        try:
            if neg is None:
                msg = f"We {pos()}."
            else:
                msg = f"We {neg()}, and then {pos()}."
        except ValueError:
            msg = "<Unknown option>"

        return msg

    @property
    def has_info(self) -> bool:
        return hasattr(self, f"bonus_{self.parser._neow_picked[0]}")

    @property
    def cards(self) -> list[CardData]:
        try:
            l = self.get_cards()
            return [CardData(x, l) for x in l]
        except ValueError:
            return []

    def card_delta(self) -> int:
        num = super().card_delta() + 10
        if self.parser.character == "Silent":
            num += 2

        if self.parser.ascension_level >= 10:
            num += 1

        bonus, cost = self.parser._neow_picked

        if cost == "CURSE":
            num += 1

        match bonus:
            case "REMOVE_CARD":
                num -= 1
            case "REMOVE_TWO":
                num -= 2
            case "ONE_RANDOM_RARE_CARD":
                num += 1

        return num

    def relic_delta(self) -> int: # does not handle calling bell
        num = 1
        if self.parser._neow_picked[0] in ("THREE_ENEMY_KILL", "ONE_RARE_RELIC", "RANDOM_COMMON_RELIC"):
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

    @property
    def fights_count(self) -> int:
        return 0

    @property
    def turns_count(self) -> int:
        return 0

_chars = {
    "SLIMEBOUND": "Slime Boss",
    "GREMLIN": "Gremlin Gang",
    "THE_SPIRIT": "Hexaghost",
    "THE_AUTOMATON": "Bronze Automaton",
}

_enemies = { # Downfall bosses
    "IC_STATUS_ARCHETYPE": "Status Ironclad",
    "SI_POISON_ARCHETYPE": "Poison Silent",
    "DF_ARCHETYPE_STREAMLINE": "0-cost Defect",
    "WA_ARCHETYPE_RETAIN": "Retain Watcher",
    "HERMIT_SHARPSHOOTER_ARCHETYPE": "Deadeye Hermit",

    "IC_MUSHROOM_ARCHETYPE": "Reaper Ironclad",
    "SI_MIRROR_ARCHETYPE": "After Image Silent",
    "DF_ARCHETYPE_CLAW": "Claw Defect",
    "WA_ARCHETYPE_CALM": "Blasphemy Watcher",
    "HERMIT_WHEEL_ARCHETYPE": "Rotating Cards Hermit",

    "IC_BLOCK_ARCHETYPE": "Barricade Ironclad",
    "SI_SHIV_ARCHETYPE": "Shiv Silent",
    "DF_ARCHETYPE_ORBS": "Orb Defect",
    "WA_ARCHETYPE_DIVINITY": "Mantra Watcher",
    "HERMIT_DOOMSDAY_ARCHETYPE": "Doomsday Hermit",

    "downfall:NeowBoss": "The heroes, Returned",
    "downfall:NeowBossFinal": "Neow, Goddess of Life",
}

class ShopContents:
    """Contains one floor's shop contents.

    This can be used either for contents or purchases."""

    def __init__(self):
        self.cards: list[SingleCard] = []
        self.relics: list[Relic] = []
        self.potions: list[Potion] = []

    def add_card(self, card: str):
        """Add a card to this floor's contents."""
        self.cards.append(get_card(card))

    def add_relic(self, relic: str):
        """Add a relic to this floor's contents."""
        self.relics.append(get(relic))

    def add_potion(self, potion: str):
        """Add a potion to this floor's contents."""
        self.potions.append(get(potion))


class FileParser(ABC):
    _variables_map = {
        "current_hp": "Current HP",
        "max_hp": "Max HP",
        "gold": "Gold",
        "floor_time": "Time spent in the floor (seconds)",
        "card_count": "Cards in the deck",
        "relic_count": "Relics",
        "potion_count": "Potions",
    }

    _graph_types = {
        "embed": "text/html",
        "image": "image/png",
    }

    _potion_mapping = {
        "use": ("PotionUseLog", "potion_use_per_floor"),
        "alchemize": ("potionsObtainedAlchemizeLog", "potions_obtained_alchemize"),
        "entropic": ("potionsObtainedEntropicBrewLog", "potions_obtained_entropic_brew"),
        "discarded": ("PotionDiscardLog", "potion_discard_per_floor"),
    }

    prefix = ""
    done = False

    def __init__(self, data: dict[str, Any]):
        self._data = data
        self.neow_bonus = NeowBonus(self)
        self._cache: dict[str, Any] = {"self": self} # this lets us do on-the-fly debugging
        self._character: str | None = None
        self._graph_cache: dict[tuple[str, str, tuple, str | None, str | None], str | bytes] = {}

    def __str__(self):
        return f"{self.__class__.__name__}<{self.timestamp}>"

    def get_boss_chest(self) -> dict[str, str | list[str]]:
        if "boss_chest_iter" not in self._cache:
            self._cache["boss_chest_iter"] = iter(self._data[self.prefix + "boss_relics"])

        try: # with a savefile, it's possible to try to get the same floor twice, which will the last one
            return next(self._cache["boss_chest_iter"]) # type: ignore
        except StopIteration:
            return self._data[self.prefix + "boss_relics"][-1]

    def graph(self, req: Request) -> Response:
        if "view" not in req.query or "type" not in req.query:
            raise HTTPForbidden(reason="Needs 'view' and 'type' params")
        if req.query["type"] not in self._graph_types:
            raise HTTPNotImplemented(reason=f"Display type {req.query['type']} is undefined")

        graph_type = req.match_info["type"]
        display_type = req.query["type"]
        items = req.query["view"].split(",")
        label = req.query.get("label")
        title = req.query.get("title")

        to_cache = (graph_type, display_type, tuple(items), label, title)

        if to_cache not in self._graph_cache:
            try:
                self._graph_cache[to_cache] = self._generate_graph(graph_type, display_type, items, label, title, allow_private=False)
            except ValueError as e:
                raise HTTPForbidden(reason=e.args[0])
            except TypeError:
                raise HTTPNotFound()

        return Response(body=self._graph_cache[to_cache], content_type=self._graph_types[display_type])

    def bar(self, dtype: str, items: Iterable[str], label: str | None = None, title: str | None = None, *, allow_private: bool = False) -> str | bytes:
        if dtype not in self._graph_types:
            raise ValueError(f"Display type {dtype} is undefined")
        to_cache = ("bar", dtype, tuple(items), label, title)
        if to_cache not in self._graph_cache:
            self._graph_cache[to_cache] = self._generate_graph("bar", dtype, items, label, title, allow_private=allow_private)
        return self._graph_cache[to_cache]

    def _generate_graph(self, graph_type: str, display_type: str, items: Iterable[str], ylabel: str | None, title: str | None, *, allow_private: bool) -> str | bytes:
        if plt is None:
            raise ValueError("matplotlib is not installed, graphs cannot be used")

        totals: dict[str, list[int]] = {}
        ends = []
        floors = []
        for arg in items:
            if arg.startswith("_") and not allow_private:
                raise ValueError(f"Cannot access private attribute {arg}.")
            totals[arg] = []
            if arg not in self._variables_map:
                logger.warning(f"Graph parameter {arg!r} may not be properly handled.")

        for name, d in totals.items():
            val = getattr(self.neow_bonus, name, None)
            if val is not None:
                if not floors:
                    floors.append(0)
                d.append(val)

        for node in self.path:
            floors.append(node.floor)
            if node.end_of_act:
                ends.append(node.floor)
            for name, d in totals.items():
                val = getattr(node, name, 0)
                if callable(val):
                    try:
                        val = val()
                    except TypeError:
                        raise ValueError(f"Cannot call function {name!r} that requires parameters.")
                try:
                    val + 0
                except TypeError:
                    raise ValueError(f"Cannot use non-integer {name!r} for graphs.")
                else:
                    d.append(val)

        fig, ax = plt.subplots()
        match graph_type:
            case "plot":
                func = ax.plot
            case "scatter":
                func = ax.scatter
            case "bar":
                func = ax.bar
            case "stem":
                func = ax.stem
            case a:
                raise TypeError(f"Could not understand graph type {a}")

        if display_type != "embed":
            for num in ends:
                plt.axvline(num, color="black", linestyle="dashed")

        for name, d in totals.items():
            func(floors, d, label=self._variables_map.get(name, name))
        ax.legend()

        plt.xlabel("Floor")
        if ylabel is not None:
            plt.ylabel(ylabel)
        elif len(totals) == 1:
            label = tuple(totals)[0]
            plt.ylabel(self._variables_map.get(label, label))
        plt.xlim(left=0)
        plt.ylim(bottom=0)
        if title is not None: # doesn't appear to work with mpld3
            plt.suptitle(title)

        match display_type:
            case "embed":
                if fig_to_html is None:
                    raise ValueError("mpld3 isn't installed, cannot embed graphs. Use 'image' display type")
                value: str = fig_to_html(fig)
                plt.close(fig)
                return value

            case "image":
                with io.BytesIO() as file:
                    plt.savefig(file, format="png", transparent=True)
                    plt.close(fig)
                    return file.getvalue()

    @property
    @abstractmethod
    def floor(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def timestamp(self) -> datetime.datetime:
        raise NotImplementedError

    @property
    @abstractmethod
    def timedelta(self) -> datetime.timedelta:
        raise NotImplementedError

    @property
    @abstractmethod
    def profile(self) -> Profile:
        raise NotImplementedError

    @property
    @abstractmethod
    def character_streak(self) -> StreakInfo:
        raise NotImplementedError

    @property
    @abstractmethod
    def rotating_streak(self) -> StreakInfo:
        raise NotImplementedError

    @property
    @abstractmethod
    def _neow_data(self) -> tuple[dict[str, list[str] | int], list[str], list[str]]:
        """Return the Neow Bonus data. For internal use only."""
        raise NotImplementedError

    @property
    def _neow_picked(self) -> tuple[str, str]:
        """Return the Neow bonus and cost picked. For internal use only."""
        return (self._data["neow_bonus"], self._data["neow_cost"])

    @property
    def display_name(self) -> str:
        return ""

    @property
    def skipped_rewards(self) -> tuple[RelicRewards, PotionRewards]:
        rels = collections.defaultdict(list)
        pots = collections.defaultdict(list)
        if self.prefix == "metric_": # savefile
            skipped = self._data["basemod:mod_saves"].get("RewardsSkippedLog")
        else:
            skipped = self._data.get("rewards_skipped")

        if skipped:
            for choice in skipped:
                if (r := choice["relics"]):
                    rels[choice["floor"]].extend(get(x) for x in r)
                if (p := choice["potions"]):
                    pots[choice["floor"]].extend(get(x) for x in p)

        return rels, pots

    @property
    def character(self) -> str | None:
        if self._character is None:
            return None

        c = _chars.get(self._character)
        if c is None:
            c = self._character.replace("_", " ").title()
        if c.startswith("The "): # just fix it after the fact
            c = c[4:]
        return c

    @property
    def modded(self) -> bool:
        return self.character not in ("Ironclad", "Silent", "Defect", "Watcher")

    @property
    def current_hp_counts(self) -> list[int]:
        return [self.neow_bonus.current_hp] + self._data[self.prefix + "current_hp_per_floor"]

    @property
    def max_hp_counts(self) -> list[int]:
        return [self.neow_bonus.max_hp] + self._data[self.prefix + "max_hp_per_floor"]

    @property
    def gold_counts(self) -> list[int]:
        return [self.neow_bonus.gold] + self._data[self.prefix + "gold_per_floor"]

    @property
    def potions(self) -> PotionRewards:
        res = collections.defaultdict(list)
        for d in self._data[self.prefix + "potions_obtained"]:
            res[d["floor"]].append(get(d["key"]))

        return res

    def _handle_potions(self, key: str) -> PotionsListing:
        final = [[]] # empty list for Neow
        if key not in self._potion_mapping:
            raise ValueError(f"Key {key} is not a valid potion action.")
        mapping = self._data
        idx = 1
        if self.prefix == "metric_": # savefile
            mapping = mapping["basemod:mod_saves"]
            idx = 0
        mapkey = self._potion_mapping[key][idx]
        # this needs RHP, so it might not be present
        # but we want a list anyway, which is why we iterate like this
        for i in range(self.floor):
            potions = []
            try:
                # it's possible the key doesn't exist, but we don't want it to error
                for x in mapping[mapkey][i]:
                    potions.append(get(x))
            except (KeyError, IndexError):
                # Either we don't have RHP, or the floor isn't stored somehow
                pass

            final.append(potions)

        return final

    @property
    def potions_use(self) -> PotionsListing:
        return self._handle_potions("use")

    @property
    def potions_alchemize(self) -> PotionsListing:
        return self._handle_potions("alchemize")

    @property
    def potions_entropic(self) -> PotionsListing:
        return self._handle_potions("entropic")

    @property
    def potions_discarded(self) -> PotionsListing:
        return self._handle_potions("discarded")

    @property
    def boss_relics(self) -> list[BossRelicChoice]:
        rels: list[dict] = self._data[f"{self.prefix}boss_relics"]
        ret = []
        for choices in rels:
            picked = None
            if "picked" in choices:
                picked = get(choices["picked"])
            skipped = tuple(get(x) for x in choices["not_picked"])
            ret.append( (picked, skipped) )

        return ret

    @property
    def ascension_level(self) -> int:
        return self._data["ascension_level"]

    @property
    def playtime(self) -> int:
        return self._data[self.prefix + "playtime"]

    @property
    @abstractmethod
    def keys(self) -> KeysObtained:
        raise NotImplementedError

    @property
    def card_choices(self) -> tuple[CardRewards, CardRewards]:
        picked = collections.defaultdict(list)
        skipped = collections.defaultdict(list)
        for d in self._data[self.prefix + "card_choices"]:
            if (c := d["picked"]) != "SKIP":
                picked[d["floor"]].append(get_card(c))
            for card in d["not_picked"]:
                skipped[d["floor"]].append(get_card(card))

        return picked, skipped

    @property
    @abstractmethod #PRIV# why is this like that
    def _master_deck(self) -> list[str]:
        raise NotImplementedError

    def get_cards(self) -> Generator[CardData, None, None]:
        master_deck = self._master_deck
        for card in set(master_deck):
            yield CardData(card, master_deck)

    def get_meta_scaling_cards(self) -> list[tuple[str, int]]:
        return []

    @property
    def cards(self) -> Generator[str, None, None]:
        for card in self.get_cards():
            yield from card.as_cards()

    def get_purchases(self) -> collections.defaultdict[int, ShopContents]:
        """Return a mapping of purchases for a given floor."""
        bought: collections.defaultdict[int, ShopContents] = collections.defaultdict(ShopContents)
        for i, purchased in enumerate(self._data[self.prefix + "item_purchase_floors"]):
            value = self._data[self.prefix + "items_purchased"][i]
            name, _, upgrades = value.partition("+")
            item = get(name)
            match item.cls_name:
                case "card":
                    bought[purchased].add_card(value)
                case "relic":
                    bought[purchased].add_relic(value)
                case "potion":
                    bought[purchased].add_potion(value)

        return bought

    def get_shop_contents(self) -> collections.defaultdict[int, ShopContents]:
        d = ()
        if "shop_contents" in self._data:
            d = self._data["shop_contents"]
        elif "basemod:mod_saves" in self._data:
            d = self._data["basemod:mod_saves"].get("ShopContentsLog", ())

        results = collections.defaultdict(ShopContents)
        for data in d:
            results[data["floor"]] = contents = ShopContents()
            for relic in data["relics"]:
                contents.add_relic(relic)
            for card in data["cards"]:
                contents.add_card(card)
            for potion in data["potions"]:
                contents.add_potion(potion)

        return results

    @property
    def _removals(self) -> list[tuple[str, int]]:
        event_removals = []
        for event in self._data[self.prefix + "event_choices"]:
            for removed in event.get("cards_removed", []):
                event_removals.append((removed, event["floor"]))

        store_removals = zip(self._data.get(self.prefix + "items_purged", []), self._data.get(self.prefix + "items_purged_floors", []))

        # missing Empty Cage
        all_removals = []
        for card in self.neow_bonus.cards_removed:
            all_removals.append((card.name, 0))
        all_removals.extend(event_removals)
        all_removals.extend(store_removals)
        return all_removals

    def get_removals(self) -> Generator[CardData, None, None]:
        removals = [x[0] for x in self._removals]
        for card in set(removals): # remove duplicates
            yield CardData(card, removals)

    @property
    def has_removals(self) -> bool:
        return bool(self._removals)

    @property
    def removals(self) -> Generator[ItemFloor, None, None]:
        for card, floor in self._removals:
            cdata = CardData(card, [])
            yield (cdata.name, floor)

    def master_deck_as_html(self):
        return self._cards_as_html(self.get_cards())

    def removals_as_html(self):
        return self._cards_as_html(self.get_removals())

    def _cards_as_html(self, cards: Iterable[CardData]) -> Generator[str, None, None]:
        text = (
            '<a class="card"{color} href="https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/{mod}/cards/{card_url}.png" target="_blank">'
            '<svg width="32" height="32">'
            '<image width="32" height="32" xlink:href="{website}/static/card/Back_{card.color}.png"></image>'
            '<image width="32" height="32" xlink:href="{website}/static/card/Desc_{card.color}.png"></image>'
            '<image width="32" height="32" xlink:href="{website}/static/card/Type_{card.type_safe}.png"></image>'
            '<image width="32" height="32" xlink:href="{website}/static/card/Banner_{banner}.png"></image>'
            '</svg><span>{card.display_name}</span></a>'
        )

        def new_color() -> dict[str | None, list[CardData]]:
            return {"Rare": [], "Uncommon": [], "Common": [], None: []}

        order = ["Red", "Green", "Blue", "Purple", "Colorless", "Curse"]
        content = collections.defaultdict(new_color)
        for card in cards:
            if card.color not in order:
                order.insert(0, card.color)
            content[card.color][card.rarity_safe].append(card)

        final = []

        for color in order:
            for rarity, all_cards in content[color].items():
                all_cards.sort(key=lambda x: f"{x.name}{x.upgrades}")
                for card in all_cards:
                    format_map = {
                        "color": ' style="color:#a0ffaa"' if card.upgrades else "", # make it green when upgraded
                        "website": config.server.url,
                        "banner": rarity or "Common",
                        "mod": urllib.parse.quote(card.card.mod or "Slay the Spire").lower(),
                        "card_url": format_for_slaytabase(card.card.internal),
                        "card": card,
                    }
                    final.append(text.format_map(format_map))

        step, rem = divmod(len(final), 3)
        end = []
        while rem:
            end.append(final.pop(step*rem))
            rem -= 1
        end.reverse()
        for i in range(step):
            yield from final[i::step]
        yield from end

    @property
    def relics(self) -> list[RelicData]:
        if "relics" not in self._cache:
            self._cache["relics"] = []
            for relic in self._data["relics"]:
                value = RelicData(self, relic)
                self._cache["relics"].append(value)

        return list(self._cache["relics"])

    @property
    def relics_bare(self) -> list[Relic]:
        # could be a generator, but we want easy contain check
        return [x.relic for x in self.relics]

    @property
    def relics_obtained(self) -> RelicRewards:
        res = collections.defaultdict(list)
        for relic in self._data[self.prefix + "relics_obtained"]:
            res[relic["floor"]].append(get(relic["key"]))

        return res

    @property
    def seed(self) -> str:
        c = "0123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"

        try:
            seed = int(self._data["seed"]) # might be stored as a str
        except KeyError:
            seed = int(self._data["seed_played"])

        # this is a bit weird, but lets us convert a negative number, if any, into a positive one
        num = int.from_bytes(seed.to_bytes(20, "big", signed=True).lstrip(b"\xff"), "big")
        s = []

        while num:
            num, i = divmod(num, 35)
            s.append(c[i])

        s.reverse() # everything's backwards, for some reason... but this works

        return "".join(s)

    @property
    def is_seeded(self) -> bool:
        if "seed_set" in self._data:
            return self._data["seed_set"]
        return self._data["chose_seed"]

    @property
    def path(self) -> list[NodeData]:
        """Return the run's path. This is cached."""
        if "path" not in self._cache:
            self._cache["path"] = []
            floor_time: tuple[int, ...]
            if "basemod:mod_saves" in self._data:
                floor_time = self._data["basemod:mod_saves"].get("FloorExitPlaytimeLog", ())
            else:
                floor_time = self._data.get("floor_exit_playtime", ())
            prev = 0
            card_count = self.neow_bonus.card_delta()
            relic_count = self.neow_bonus.relic_delta()
            potion_count = self.neow_bonus.potion_delta()
            fights_count = self.neow_bonus.fights_delta()
            turns_count = self.neow_bonus.turns_delta()
            for node, cached in _get_nodes(self, self._cache.pop("old_path", None)):
                try:
                    t = floor_time[node.floor - 1]
                except IndexError:
                    t = 0
                if cached: # don't recompute the deltas -- just grab their cached counts
                    card_count = node.card_count
                    relic_count = node.relic_count
                    potion_count = node.potion_count
                    fights_count = node.fights_count
                    turns_count = node.turns_count
                else:
                    card_count += node.card_delta()
                    node.card_count = card_count
                    relic_count += node.relic_delta()
                    node.relic_count = relic_count
                    potion_count += node.potion_delta()
                    node.potion_count = potion_count
                    fights_count += node.fights_delta()
                    node.fights_count = fights_count
                    turns_count += node.turns_delta()
                    node.turns_count = turns_count
                    node.floor_time = t - prev
                prev = t
                self._cache["path"].append(node)

        return list(self._cache["path"])

    @property
    def modifiers(self) -> list[str]:
        return self._data.get("daily_mods", [])

    @property
    def modifiers_with_desc(self) -> list[str]:
        if self.modifiers:
            modifiers_with_desc = [get_run_mod(mod) for mod in self.modifiers]
            return modifiers_with_desc
        return []

    @property
    @abstractmethod
    def score(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def score_breakdown(self) -> list[str]:
        raise NotImplementedError

    def get_floor(self, floor: int) -> BaseNode | None:
        if floor == 0:
            return self.neow_bonus
        for node in self.path:
            if node.floor == floor:
                return node
        return None

def _get_nodes(parser: FileParser, maybe_cached: list[NodeData] | None) -> Generator[tuple[NodeData, bool], None, None]: #PRIV#
    """Get the map nodes. This should only ever be called from 'FileParser.path' to get the cache."""
    prefix = parser.prefix
    on_map = parser._data[prefix + "path_taken"]
    # maybe_cached will not be None if this is a savefile we're iterating through
    # which means we already know previous floors, so just use that.
    # to be safe, regenerate the last floor, since it might have changed
    # (e.g. the last time we saw it, we were in-combat, and now we're out of it)
    # this is also used for run files for which we had the savefile
    if maybe_cached:
        maybe_cached.pop()
    nodes = []
    error = False
    taken_len = len(parser._data[prefix + "path_taken"])
    actual_len = len([x for x in parser._data[prefix + "path_per_floor"] if x is not None])
    last_changed = 0
    offset = 1
    for floor, actual in enumerate(parser._data[prefix + "path_per_floor"], 1):
        iterate = True
        # Slay the Streamer boss pick
        if actual_len > taken_len and actual == "T" and floor == last_changed + 10:
            taken_len += 1 # keep track
            offset += 1
            iterate = False
        # make sure we step through the iterator even if it's cached
        node = [actual, None]
        if iterate and node[0] is not None:
            node[1] = on_map[floor-offset]
        elif iterate:
            offset += 1

        nodes.append(node)

        if maybe_cached:
            maybe_node = maybe_cached.pop(0)
            if floor == maybe_node.floor: # if it's not, then something's wrong. just regen it
                yield maybe_node, True
                continue

        if not iterate:
            continue

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
                cls = event_node # not actually a NodeData subclass, but it returns one
            case ("R", "R"):
                cls = Campfire
            case ("B", "BOSS"):
                cls = Boss
            case ("C", "C"):
                cls = Courier
            case ("-", "-"):
                cls = Empty
            case ("P", "P"):
                cls = SWF
            case (None, None):
                if floor < 50: # kind of a hack for the first two acts
                    cls = BossChest
                elif len(parser._data[prefix + "max_hp_per_floor"]) < floor:
                    cls = Victory
                else:
                    cls = Act4Transition
            case (a, b):
                logger.warning(f"Error: the combination of map node {b!r} and content {a!r} is undefined (run: {getattr(parser, 'name', 'savefile')})")
                error = True
                continue

        if cls.end_of_act:
            last_changed = floor

        try:
            value: NodeData = cls(parser, floor)
        except ValueError: # this can happen for savefiles if we're on the latest floor
            if taken_len == floor:
                continue # we're on the last floor
            raise
        else:
            yield value, False

    if error:
        logger.error("\n".join(f"Actual: {str(x):<4} | Map: {y}" for x, y in nodes))

class KeysObtained:
    """Contain information about the obtained keys."""

    def __init__(self):
        self.ruby_key_obtained = False
        self.ruby_key_floor = 0
        self.emerald_key_obtained = False
        self.emerald_key_floor = 0
        self.sapphire_key_obtained = False
        self.sapphire_key_floor = 0

    def as_list(self):
        return [
            ("Emerald Key", self.emerald_key_obtained, self.emerald_key_floor),
            ("Ruby Key", self.ruby_key_obtained, self.ruby_key_floor),
            ("Sapphire Key", self.sapphire_key_obtained, self.sapphire_key_floor),
        ]

class RelicData:
    """Contain information for Spire relics."""

    def __init__(self, parser: FileParser, relic: str):
        self.parser = parser
        self.relic: Relic = get(relic)
        self._description = None

    def __str__(self) -> str:
        return self.relic.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.parser}, {self.relic.name})"

    def description(self) -> str:
        if self._description is None:
            desc = []
            obtained: BaseNode = self.parser.neow_bonus
            node = None
            for node in self.parser.path:
                if self.relic in node.relics:
                    obtained = node
            desc.append(f"Obtained on floor {obtained.floor}")
            if node is not None:
                desc.extend(self.get_details(obtained, node)) # node will be the last node
            self._description = "\n".join(desc)
        return self._description

    def escaped_description(self) -> str:
        return self.description().replace("\n", "<br>").replace("'", "\\'")

    def get_stats(self) -> int | float | str | list[str] | None: #PRIV#
        if "basemod:mod_saves" in self.parser._data:
            return self.parser._data["basemod:mod_saves"].get(f"stats_{self.relic.internal}")
        if "relic_stats" in self.parser._data:
            return self.parser._data["relic_stats"].get(self.relic.internal)

    def get_details(self, obtained: NodeData, last: NodeData) -> list[str]:
        desc = []
        try:
            text = get_relic_stats(self.relic.internal) # FIXME
        except KeyError: # no stats for these
            return []
        stats = self.get_stats()
        if stats is None:
            return []

        per_turn = True

        if self.relic.name == "White Beast Statue":
            # if this is a savefile, only the last number matters. run files should be unaffected
            stats = [stats[-1]]
        elif self.relic.name == "Snecko Eye":
            # special handling for this
            per_turn = False
            if (c := sum(stats[:-1])) > 0:
                stats[-1] = stats[-1] / c

        if isinstance(stats, int):
            desc.append(text[0] + str(stats))
            desc.extend(text[1:])
        elif isinstance(stats, float): # only Frozen Eye
            minutes, seconds = divmod(stats, 60)
            if minutes:
                desc.append(f"{text[0]}{minutes:.0f}m {seconds:.2f}s")
            else:
                desc.append(f"{text[0]}{seconds:.2f}s")
        elif isinstance(stats, str): # bottles
            desc.append(text[0] + get(stats).name)
        elif isinstance(stats, list):
            if not stats: # e.g. Whetstone upgrading nothing
                desc.append(f"{text[0]}<nothing>")
            elif isinstance(stats[0], str):
                stats = [get(x).name for x in stats]
                desc.append(f"{text[0]}\n- "+ "\n- ".join(stats))
            else:
                text_iter = iter(text)
                for stat in stats:
                    stat_str = str(stat)
                    if isinstance(stat, float):
                        stat_str = f"{stat:.2f}"
                    desc.append(next(text_iter) + stat_str)
                    if per_turn:
                        num = stat / max((last.turns_count - obtained.turns_count), 1)
                        desc.append(f"Per turn: {num:.2f}")
                        num = stat / max((last.fights_count - obtained.fights_count), 1)
                        desc.append(f"Per combat: {num:.2f}")
        else:
            desc.append(f"Unable to parse stats for {self.name}")

        return desc

    @property
    def mod(self) -> str:
        if not self.relic.mod:
            return "Slay the Spire"
        return self.relic.mod

    @property
    def image(self) -> str:
        name = self.relic.internal
        if ":" in name:
            name = name[name.index(":")+1:]
        return f"{format_for_slaytabase(name)}.png"

    @property
    def name(self) -> str:
        return self.relic.name

class CardData: # TODO: metadata + scaling cards (for savefile)
    def __init__(self, card: str | SingleCard, cards_list: Iterable[str], meta: int = 0):
        self.orig = card
        if isinstance(card, str):
            card = get_card(card)
        self._cards_list = list(cards_list)
        self.single = card
        self.card: Card = card.card
        self.meta = meta
        self.upgrades = card.upgrades

    def as_cards(self):
        for i in range(self.count):
            yield self.name

    @property
    def color(self) -> str:
        return self.card.color

    @property
    def type(self) -> str:
        return self.card.type

    @property
    def type_safe(self) -> str:
        if self.type not in ("Attack", "Skill", "Power"):
            return "Skill"
        return self.type

    @property
    def rarity(self) -> str:
        return self.card.rarity

    @property
    def rarity_safe(self) -> str | None:
        if self.rarity not in ("Rare", "Uncommon", "Common"):
            return None
        return self.rarity

    @property
    def count(self) -> int:
        if self._cards_list:
            return self._cards_list.count(self.orig)
        return 1 # support standalone card stuff

    @property
    def name(self) -> str:
        match self.upgrades:
            case 0:
                return self.card.name
            case 1:
                return f"{self.card.name}+"
            case a:
                return f"{self.card.name}+{a}"

    @property
    def display_name(self) -> str:
        if self.count > 1:
            return f"{self.count}x {self.name}"
        return self.name

class NodeData(BaseNode):
    """Contain relevant information for Spire nodes.

    Subclasses should define the following class variables:
    - room_type :: a human-readable name for the node
    - map_icon  :: the filename for the icon in the icons/ folder

    To instantiate a subclass, call the class with a FileParser instance
    (either RunParser or Savefile) and the floor number.

    To change behaviour, you need to subclass the relevant subclass and alter
    the behaviour there. Some features rely on objects being instances of
    specific NodeData subclasses (e.g. Treasure) and will fail otherwise.
    There is no mechanism currently for overriding which subclasses are
    returned by the node path parser.

    """

    map_icon = ""

    def __init__(self, parser: FileParser, floor: int, *extra): # TODO: Keep track of the deck per node
        """Create a NodeData instance from a parser and floor number."""
        if not (self.room_type and self.map_icon):
            raise ValueError(f"Cannot create NodeData subclass {self.__class__.__name__!r}")
        super().__init__(parser, *extra)
        self.floor = floor
        if not self._set_hp_gold(floor):
            # in case our current floor doesn't have data, get previous floor
            # this can happen with the post-Heart victory screen
            # and also maybe during an ongoing run while getting the current node
            # if this assignment fails too, just let it
            self._set_hp_gold(floor - 1)

        self._cache = {}

    def _set_hp_gold(self, floor: int) -> bool:
        """Set the gold as well as current and max HP for this node.
        
        Return True if assignment succeeded, False otherwise."""

        try:
            # delay assignment in case a later one fails
            # we don't want some of them to be assigned and others not
            cur_hp = self.parser.current_hp_counts[floor]
            max_hp = self.parser.max_hp_counts[floor]
            gold = self.parser.gold_counts[floor]
        except IndexError:
            return False

        self.current_hp = cur_hp
        self.max_hp = max_hp
        self.gold = gold
        return True

    def description(self) -> str:
        if "description" not in self._cache:
            self._cache["description"] = super().description()
        return self._cache["description"]

    def get_description(self, to_append: dict[int, list[str]]):
        if self.potions:
            to_append[10].append("Potions obtained:")
            to_append[10].extend(f"- {x.name}" for x in self.potions)

        if self.used_potions:
            to_append[12].append("Potions used:")
            to_append[12].extend(f"- {x.name}" for x in self.used_potions)

        if self.potions_from_alchemize:
            to_append[14].append("Potions obtained from Alchemize:")
            to_append[14].extend(f"- {x.name}" for x in self.potions_from_alchemize)

        if self.potions_from_entropic:
            to_append[16].append("Potions obtained from Entropic Brew:")
            to_append[16].extend(f"- {x.name}" for x in self.potions_from_entropic)

        if self.discarded_potions:
            to_append[18].append("Potions discarded:")
            to_append[18].extend(f"- {x.name}" for x in self.discarded_potions)

        if self.skipped_potions:
            to_append[20].append("Potions skipped:")
            to_append[20].extend(f"- {x.name}" for x in self.skipped_potions)

        if self.relics:
            to_append[30].append("Relics obtained:")
            to_append[30].extend(f"- {x.name}" for x in self.relics)

        if self.skipped_relics:
            to_append[32].append("Relics skipped:")
            to_append[32].extend(f"- {x.name}" for x in self.skipped_relics)

        if self.picked:
            to_append[34].append("Picked:")
            to_append[34].extend(f"- {x}" for x in self.picked)

        if self.skipped:
            to_append[36].append("Skipped:")
            to_append[36].extend(f"- {x}" for x in self.skipped)

class EncounterBase(NodeData):
    """A base data class for Spire node encounters."""

    def __init__(self, parser: FileParser, floor: int, *extra):
        super().__init__(parser, floor, *extra)
        for damage in parser._data[parser.prefix + "damage_taken"]: #PRIV#
            if damage["floor"] == floor:
                break
        else:
            raise ValueError("no fight result yet")
        self._damage = damage

    def get_description(self, to_append: dict[int, list[str]]):
        if self.name != self.fought:
            to_append[4].append(f"Fought {self.fought}")
        to_append[4].append(f"{self.damage} damage")
        to_append[4].append(f"{self.turns} turns")

    def fights_delta(self) -> int:
        return 1

    def turns_delta(self) -> int:
        return self.turns

    @property
    def name(self) -> str:
        enemies = self._damage["enemies"]
        return _enemies.get(enemies, enemies)

    @property
    def fought(self) -> str:
        fought = self._damage["enemies"]
        return _enemies.get(fought, fought)

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

    def __init__(self,  parser: FileParser, floor: int, *extra):
        super().__init__(parser, floor, *extra)
        self.key_relic = self._get_relic()
        self.blue_key = (self.key_relic is not None)

    def _get_relic(self) -> Optional[Relic]: #PRIV#
        d = self.parser._data.get("basemod:mod_saves", ())
        if "BlueKeyRelicSkippedLog" in d:
            if d["BlueKeyRelicSkippedLog"]["floor"] == self.floor:
                return get(d["BlueKeyRelicSkippedLog"]["relicID"])
        elif "blue_key_relic_skipped_log" in self.parser._data:
            if self.parser._data["blue_key_relic_skipped_log"]["floor"] == self.floor:
                return get(self.parser._data["blue_key_relic_skipped_log"]["relicID"])

    def get_description(self, to_append: dict[int, list[str]]):
        if self.blue_key:
            to_append[6].append(f"Skipped {self.key_relic} for the Sapphire key")

class EventTreasure(Treasure):
    room_type = "Unknown (Treasure)"
    map_icon = "event_chest.png"

class EliteEncounter(EncounterBase):
    room_type = "Elite"
    map_icon = "fight_elite.png"

    def __init__(self, parser: FileParser, floor: int, *extra):
        super().__init__(parser, floor, *extra)
        if "basemod:mod_saves" in parser._data:
            key_floor = parser._data["basemod:mod_saves"].get("greenKeyTakenLog")
        else:
            key_floor = parser._data.get("green_key_taken_log")
        self.has_key = (key_floor is not None and int(key_floor) == floor)

    def get_description(self, to_append: dict[int, list[str]]):
        if self.has_key:
            to_append[6].append("Got the Emerald Key")

class EventElite(EliteEncounter):
    room_type = "Unknown (Elite)"
    map_icon = "event.png"

def event_node(parser: FileParser, floor: int, *extra) -> BaseNode:
    events = []
    for event in parser._data[parser.prefix + "event_choices"]: #PRIV#
        if event["floor"] == floor:
            events.append(event)
    if not events:
        return EmptyEvent(parser, floor, *extra)
    if events[0]["event_name"] == "Colosseum":
        return Colosseum(parser, floor, events, *extra)
    if len(events) != 1:
        for a in events:
            for b in events:
                if a != b: # I'm not quite sure how this happens, but sometimes an event will be in twice?
                    return AmbiguousEvent(parser, floor, events, *extra)
    event = events[0]
    for dmg in parser._data[parser.prefix + "damage_taken"]:
        if dmg["floor"] == floor: # not passing dmg in, as EncounterBase fills it in
            return EventFight(parser, floor, event, *extra)
    return Event(parser, floor, event, *extra)

event_node.end_of_act = False

class EmptyEvent(NodeData):
    room_type = "Unknown (Bugged)"
    map_icon = "event.png"

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[100].append(
            "Something happened here, but I'm not sure what...\n"
            "This is a bug with a mod. Please report this to the mod creators:\n"
            "'Missing event data in JSON'\n"
            "(Provide the event name if you can find it)"
        )

class AmbiguousEvent(NodeData):
    room_type = "Unknown (Ambiguous)"
    map_icon = "event.png"

    def __init__(self, parser: FileParser, floor: int, events: list[dict[str, Any]], *extra):
        super().__init__(parser, floor, *extra)
        self._events = events

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[100].append(
            "This event is ambiguous; multiple events map to it:\n" +
            ", ".join(x["event_name"] for x in self._events) + " -\n" +
            "This is a bug with a mod. Please report this to the mod creators."
        )

class Event(NodeData):
    room_type = "Unknown"
    map_icon = "event.png"

    def __init__(self, parser: FileParser, floor: int, event: dict[str, Any], *extra):
        super().__init__(parser, floor, *extra)
        self._event = event

    def get_description(self, to_append: dict[int, list[str]]):
        i = 40
        if type(self) is EventFight:
            i = 2
        to_append[i].append(f"Option taken:\n- {self.choice}")
        i = 42   #       42               44              46               48           50             52
        for x in ("damage_healed", "damage_taken", "max_hp_gained", "max_hp_lost", "gold_gained", "gold_lost"):
            i += 2
            val = getattr(self, x)
            if val:
                name = x.replace("_", " ").capitalize().replace("hp", "HP")
                to_append[i].append(f"{name}: {val}")

        #               54                   56                58               60                 62
        for x in ("cards_transformed", "cards_obtained", "cards_removed", "cards_upgraded", "relics_lost"):
            i += 2
            val = getattr(self, x)
            if val:
                name = x.replace("_", " ").capitalize()
                to_append[i].append(f"{name}:")
                to_append[i].extend(f"- {card}" for card in val)

    def potion_delta(self) -> int:
        value = super().potion_delta()
        if self._event["event_name"] == "WeMeetAgain" and self.choice == "Gave Potion":
            value -= 1
        return value

    @property
    def name(self) -> str:
        return get_event(self._event["event_name"])

    @property
    def choice(self) -> str:
        return self._event["player_choice"]

    @property
    def damage_healed(self) -> int:
        return self._event["damage_healed"]

    @property
    def damage_taken(self) -> int:
        return self._event["damage_taken"]

    @property
    def max_hp_gained(self) -> int:
        return self._event["max_hp_gain"]

    @property
    def max_hp_lost(self) -> int:
        return self._event["max_hp_loss"]

    @property
    def gold_gained(self) -> int:
        return self._event["gold_gain"]

    @property
    def gold_lost(self) -> int:
        return self._event["gold_loss"]

    @property
    def cards_transformed(self) -> list[SingleCard]:
        l = super().cards_transformed
        for x in self._event.get("cards_transformed", ()):
            l.append(get_card(x))
        return l

    @property
    def cards_obtained(self) -> list[SingleCard]:
        l = super().cards_obtained
        for x in self._event.get("cards_obtained", ()):
            l.append(get_card(x))
        return l

    @property
    def cards_removed(self) -> list[SingleCard]:
        l = super().cards_removed
        for x in self._event.get("cards_removed", ()):
            l.append(get_card(x))
        return l

    @property
    def cards_upgraded(self) -> list[SingleCard]:
        l = super().cards_upgraded
        for x in self._event.get("cards_upgraded", ()):
            l.append(get_card(x))
        return l

    @property
    def relics(self) -> list[Relic]:
        l = super().relics
        for x in self._event.get("relics_obtained", ()):
            l.append(get(x))
        return l

    @property
    def relics_lost(self) -> list[Relic]:
        l = super().relics_lost
        for x in self._event.get("relics_lost", ()):
            l.append(get(x))
        return l

class EventFight(Event, EncounterBase):
    """This is a subclass for fights that happen in events.

    This works for Dead Adventurer, Masked Bandits, etc.
    This does *not* work for the Colosseum fight (use Colosseum instead)

    """

class Colosseum(Event):
    def __init__(self, parser: FileParser, floor: int, events: list[dict[str, Any]], *extra):
        event = {
            "damage_healed": 0,
            "gold_gain": 0,
            "player_choice": "Fought Taskmaster + Nob",
            "damage_taken": 0,
            "max_hp_gain": 0,
            "max_hp_loss": 0,
            "event_name": "Colosseum",
            "gold_loss": 0,
        }
        if len(events) == 1:
            event["player_choice"] = "Escaped"
        super().__init__(parser, floor, event, *extra)
        dmg = []
        for damage in parser._data[parser.prefix + "damage_taken"]:
            if damage["floor"] == floor:
                dmg.append(damage)
        self._damages = dmg

    def get_description(self, to_append: dict[int, list[str]]):
        for i, dmg in enumerate(self._damages, 1):
            to_append[4].append(f"Fight {i} ({dmg['enemies']}):")
            to_append[4].append(f"{dmg['damage']} damage")
            to_append[4].append(f"{dmg['turns']} turns")

    @property
    def damage(self) -> int:
        return sum(d["damage"] for d in self._damages)

    def fights_delta(self) -> int:
        return len(self._damages)

    def turns_delta(self) -> int:
        return sum(d["turns"] for d in self._damages)

class Merchant(NodeData):
    room_type = "Merchant"
    map_icon = "shop.png"

    def __init__(self, parser: FileParser, floor: int, *extra):
        super().__init__(parser, floor, *extra)
        self.contents = parser.get_shop_contents()[floor]
        self.bought = parser.get_purchases()[floor]
        self.purged = []
        for card, floor in self.parser.removals:
            if floor == self.floor:
                self.purged.append(card)

    def get_description(self, to_append: dict[int, list[str]]):
        if self.purged:
            to_append[70].append(f"* Removed {', '.join(self.purged)}")
        if self.contents:
            to_append[72].append("Skipped:")
            if self.contents.relics:
                to_append[74].append("* Relics")
                to_append[74].extend(f"  - {x.name}" for x in self.contents.relics)
            if self.contents.cards:
                to_append[76].append("* Cards")
                to_append[76].extend(f"  - {x}" for x in self.contents.cards)
            if self.contents.potions:
                to_append[78].append("* Potions")
                to_append[78].extend(f"  - {x.name}" for x in self.contents.potions)

    @property
    def picked(self) -> list[str]:
        return super().picked + self.bought.cards

    @property
    def relics(self) -> list[Relic]:
        return super().relics + self.bought.relics

    @property
    def potions(self) -> list[Potion]:
        return super().potions + self.bought.potions

    def card_delta(self) -> int:
        return super().card_delta() - len(self.purged)

class EventMerchant(Merchant):
    room_type = "Unknown (Merchant)"
    map_icon = "event_shop.png"

class Courier(NodeData):
    room_type = "Courier (Spire with Friends)"
    map_icon = "event.png"

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[99].append("This is a Courier node. I don't know how to deal with it.")

class Empty(NodeData):
    room_type = "Empty (Spire with Friends)"
    map_icon = "event.png"

    def get_description(self, to_append: dict[int, list[str]]) :
        to_append[99].append("This is an empty node. Nothing happened here.")

class SWF(NodeData):
    room_type = "Unknown Node (Spire with Friends)"
    map_icon = "event.png"

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[99].append("This is some Spire with Friends stuff. I don't know how to deal with it.")

class Campfire(NodeData):
    room_type = "Rest Site"
    map_icon = "rest.png"

    def __init__(self, parser: FileParser, floor: int, *extra):
        super().__init__(parser, floor, *extra)
        self._key = None
        self._data = None
        for rest in parser._data[parser.prefix + "campfire_choices"]:
            if rest["floor"] == floor:
                self._key = rest["key"]
                self._data = rest.get("data")

    def get_description(self, to_append: dict[int, list[str]]) -> str:
        to_append[6].append(self.action)

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

class BossChest(NodeData):
    room_type = "Boss Chest"
    map_icon = "boss_chest.png"
    end_of_act = True

    def __init__(self, parser: FileParser, floor: int, *extra):
        super().__init__(parser, floor, *extra)
        boss_relics = parser.get_boss_chest()
        picked = None
        skipped = []
        if boss_relics.get("picked", "SKIP") != "SKIP":
            picked = get(boss_relics["picked"])
        for relic in boss_relics["not_picked"]:
            skipped.append(get(relic))

        self._picked = picked
        self._skipped = skipped

    @property
    def relics(self) -> list[Relic]:
        if self._picked:
            return [self._picked]
        return []

    @property
    def skipped_relics(self) -> list[Relic]:
        return self._skipped

class Act4Transition(NodeData):
    room_type = "Transition into Act 4"
    map_icon = "event.png"
    end_of_act = True

class Victory(NodeData):
    room_type = "Victory!"
    map_icon = "event.png"

    def __init__(self, parser: FileParser, floor: int, *extra):
        super().__init__(parser, floor, *extra)
        self._score = parser._data.get("score", 0)
        self._data = parser._data.get("score_breakdown", [])

    def get_description(self, to_append: dict[int, list[str]]):
        if self.score:
            to_append[6].extend(self.score_breakdown)
            to_append[6].append(f"Score: {self.score}")

    @property
    def score(self) -> int:
        return self._score

    @property
    def score_breakdown(self) -> list[str]:
        return self._data

class BottleRelic(NamedTuple):
    bottle_id: str
    card: str
