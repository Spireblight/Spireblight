from __future__ import annotations

from typing import Any, Generator, Iterable, NamedTuple, TYPE_CHECKING

import urllib.parse
import collections
import datetime
import math
import io

from abc import ABC, abstractmethod

from aiohttp.web import Request, Response, HTTPForbidden, HTTPNotImplemented, HTTPNotFound

from utils import format_for_slaytabase

try:
    from matplotlib import pyplot as plt
except ModuleNotFoundError:
    plt = None

try:
    from mpld3 import fig_to_html
except ModuleNotFoundError:
    fig_to_html = None

from nameinternal import get_event, get_relic_stats, get_run_mod, get, get_card, Card, Relic, Potion
from sts_profile import Profile
from logger import logger

from configuration import config

if TYPE_CHECKING:
    from runs import StreakInfo

__all__ = ["FileParser"]

class NeowBonus:

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

    def __init__(self, parser: FileParser):
        self.parser = parser

    @property
    def mod_data(self) -> dict[str, Any] | None:
        if "basemod:mod_saves" in self.parser._data:
            return self.parser._data["basemod:mod_saves"].get("NeowBonusLog")
        return self.parser._data.get("neow_bonus_log")

    @property
    def picked(self) -> str:
        cost = self.parser._data["neow_cost"]
        bonus = self.parser._data["neow_bonus"]
        if cost == "NONE":
            return self.all_bonuses.get(bonus, bonus)
        return f"{self.all_costs.get(cost, cost)} {self.all_bonuses.get(bonus, bonus)}"

    @property
    def skipped(self) -> Generator[str, None, None]:
        if "basemod:mod_saves" in self.parser._data:
            bonuses = self.parser._data["basemod:mod_saves"].get("NeowBonusesSkippedLog")
            costs = self.parser._data["basemod:mod_saves"].get("NeowCostsSkippedLog")
        else:
            bonuses = self.parser._data.get("neow_bonuses_skipped_log")
            costs = self.parser._data.get("neow_costs_skipped_log")

        if not bonuses or not costs:
            yield "<Could not fetch data>"
            return

        for c, b in zip(costs, bonuses, strict=True):
            if c == "NONE":
                yield self.all_bonuses.get(b, b)
            else:
                yield f"{self.all_costs.get(c, c)} {self.all_bonuses.get(b, b)}"

    # All of the Neow Bonus keys should exist together, if more are added, we shouldn't need to add checks for them
    @property
    def has_data(self) -> bool:
        if "basemod:mod_saves" in self.parser._data:
            bonuses = self.parser._data["basemod:mod_saves"].get("NeowBonusesSkippedLog")
            costs = self.parser._data["basemod:mod_saves"].get("NeowCostsSkippedLog")
        else:
            bonuses = self.parser._data.get("neow_bonuses_skipped_log")
            costs = self.parser._data.get("neow_costs_skipped_log")

        return bool(bonuses and costs)

    @property
    def current_hp(self) -> int:
        try:
            return self.get_hp()[0]
        except ValueError: # modded character; we don't have the data
            return 0 # make it 0 so it doesn't break stuff

    @property
    def max_hp(self) -> int:
        try:
            return self.get_hp()[1]
        except ValueError:
            return 0

    @property
    def gold(self) -> int:
        return self.get_gold()

    @property
    def floor(self) -> int:
        return 0

    @property
    def floor_time(self) -> int:
        return 0

    @property
    def cards_obtained(self) -> list[str]:
        if self.has_data:
            return self.mod_data.get("cardsObtained", [])
        return []

    @property
    def cards_removed(self) -> list[str]:
        if self.has_data:
            return self.mod_data.get("cardsRemoved", [])
        return []

    @property
    def cards_transformed(self) -> list[str]:
        if self.has_data:
            return self.mod_data.get("cardsTransformed", [])
        return []

    @property
    def cards_upgraded(self) -> list[str]:
        if self.has_data:
            return self.mod_data.get("cardsUpgraded", [])
        return []

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

        if self.parser.ascension_level >= 14: # lower max HP
            base -= 4
            if self.parser.character == "Ironclad":
                base -= 1 # 5 total

        bonus = base // 10

        cur = base

        if self.parser.ascension_level >= 6: # take damage
            cur -= math.ceil(cur / 10)

        if self.mod_data is not None:
            cur -= self.mod_data["damageTaken"]
            cur += self.mod_data["maxHpGained"]
            base -= self.mod_data["maxHpLost"]
            base += self.mod_data["maxHpGained"]
            return (cur, base)

        match self.parser._data["neow_cost"]:
            case "TEN_PERCENT_HP_LOSS": # actually hardcoded
                base -= bonus
                if cur > base:
                    cur = base
            case "PERCENT_DAMAGE":
                cur -= (cur // 10) * 3

        match self.parser._data["neow_bonus"]:
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

        if self.parser._data["neow_cost"] == "NO_GOLD":
            base = 0

        match self.parser._data["neow_bonus"]:
            case "HUNDRED_GOLD":
                base += 100
            case "TWO_FIFTY_GOLD":
                base += 250
            case "ONE_RARE_RELIC":
                if self.parser._data["relics"][1] == "Old Coin": # this can break if N'loth is involved
                    base += 300

        return base

    def get_cards(self) -> list[str]:
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

        if self.mod_data is not None:
            for x in self.mod_data["cardsTransformed"] + self.mod_data["cardsRemoved"]:
                cards.remove(x)
            for x in self.mod_data["cardsObtained"]:
                cards.append(x)
            for x in self.mod_data["cardsUpgraded"]:
                index = cards.index(x)
                cards.insert(index, f"{x}+1")
        for x in self.parser._data[self.parser.prefix + "card_choices"]:
            if x["floor"] == 0:
                if cards["picked"] != "SKIP":
                    cards.append(x["picked"])

        return cards

    # options 1 & 2

    def bonus_THREE_CARDS(self):
        prefix = self.parser.prefix
        for cards in self.parser._data[prefix + "card_choices"]:
            if cards["floor"] == 0:
                if cards["picked"] != "SKIP":
                    return f"picked {get(cards['picked']).name} over {' and '.join(get(x).name for x in cards['not_picked'])}"
                return f"were offered {', '.join(get(x).name for x in cards['not_picked'])} but skipped them all"

        raise ValueError("That is not the right bonus??")

    bonus_RANDOM_COLORLESS = bonus_THREE_CARDS

    def bonus_RANDOM_COMMON_RELIC(self):
        if self.mod_data is not None:
            return f"got {get(self.mod_data['relicsObtained'][0]).name}"
        return "picked a random Common relic"

    def bonus_REMOVE_CARD(self):
        if self.mod_data is not None:
            return f"removed {get(self.mod_data['cardsRemoved'][0]).name}"
        return "removed a card"

    def bonus_TRANSFORM_CARD(self):
        if self.mod_data is not None:
            return f"transformed {get(self.mod_data['cardsTransformed'][0]).name} into {get(self.mod_data['cardsObtained'][0]).name}"
        return "transformed a card"

    def bonus_UPGRADE_CARD(self):
        if self.mod_data is not None:
            return f"upgraded {get(self.mod_data['cardsUpgraded'][0]).name}"
        return "upgraded a card"

    def bonus_THREE_ENEMY_KILL(self):
        return "got Neow's Lament to get three fights with enemies having 1 HP"

    def bonus_THREE_SMALL_POTIONS(self):
        potions = []
        skipped = []
        prefix = self.parser.prefix
        for potion in self.parser._data[prefix + "potions_obtained"]:
            if potion["floor"] == 0:
                potions.append(get(potion["key"]).name)
        if self.mod_data is not None:
            if "basemod:mod_saves" in self.parser._data:
                s = self.parser._data["basemod:mod_saves"]["RewardsSkippedLog"]
            else:
                s = self.parser._data["rewards_skipped"]
            for skip in s:
                if skip["floor"] == 0:
                    skipped.extend(get(x).name for x in skip["potions"])
        if skipped:
            return f"got {' and '.join(potions)}, and skipped {' and '.join(skipped)}"
        return f"got {' and '.join(potions)}"

    def bonus_TEN_PERCENT_HP_BONUS(self):
        if self.mod_data is not None:
            return f"gained {self.mod_data['maxHpGained']} Max HP"
        return "gained 10% Max HP"

    def bonus_ONE_RANDOM_RARE_CARD(self):
        if self.mod_data is not None:
            return f"picked a random Rare card, and got {get(self.mod_data['cardsObtained'][0]).name}"
        return "picked a random Rare card"

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
            return f"removed {' and '.join(get(x).name for x in self.mod_data['cardsRemoved'])}"
        return "removed two cards"

    def bonus_TRANSFORM_TWO_CARDS(self):
        if self.mod_data is not None:
            return f"transformed {' and '.join(get(x).name for x in self.mod_data['cardsTransformed'])} into {' and '.join(get(x).name for x in self.mod_data['cardsObtained'])}"
        return "transformed two cards"

    def bonus_ONE_RARE_RELIC(self):
        if self.mod_data is not None:
            return f"picked a random Rare relic and got {get(self.mod_data['relicsObtained'][0]).name}"
        return "obtained a random Rare relic"

    # option 4

    def bonus_BOSS_RELIC(self):
        if self.mod_data is not None:
            return f"swapped our starter relic for {get(self.mod_data['relicsObtained'][0]).name}"
        return f"swapped our starter relic for {get(self.parser._data['relics'][0]).name}" # N'loth can mess with this

    # more Neow mod

    bonus_CHOOSE_OTHER_CHAR_RANDOM_COMMON_CARD = bonus_THREE_CARDS
    bonus_CHOOSE_OTHER_CHAR_RANDOM_UNCOMMON_CARD = bonus_THREE_CARDS
    bonus_CHOOSE_OTHER_CHAR_RANDOM_RARE_CARD = bonus_THREE_CARDS

    # costs for option 3

    def cost_CURSE(self):
        if self.mod_data is not None:
            return f"got cursed with {get(self.mod_data['cardsObtained'][0]).name}"
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
        neg = getattr(self, f"cost_{self.parser._data['neow_cost']}", None)
        try:
            pos = getattr(self, f"bonus_{self.parser._data['neow_bonus']}")
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
        return hasattr(self, f"bonus_{self.parser._data['neow_bonus']}")

    @property
    def cards(self) -> list[str]:
        try:
            return [get(x).name for x in self.get_cards()]
        except ValueError:
            return []

    def card_delta(self) -> int:
        num = 10
        if self.parser.character == "Silent":
            num += 2

        if self.parser.ascension_level >= 10:
            num += 1

        prefix = self.parser.prefix
        for cards in self.parser._data[prefix + "card_choices"]:
            if cards["floor"] == 0:
                if cards["picked"] != "SKIP":
                    num += 1

        if self.parser._data["neow_cost"] == "CURSE":
            num += 1

        match self.parser._data["neow_bonus"]:
            case "REMOVE_CARD":
                num -= 1
            case "REMOVE_TWO":
                num -= 2
            case "ONE_RANDOM_RARE_CARD":
                num += 1

        return num

    def relic_delta(self) -> int:
        num = 1
        if self.parser._data["neow_bonus"] in ("THREE_ENEMY_KILL", "ONE_RARE_RELIC", "RANDOM_COMMON_RELIC"):
            num += 1
        return num

    def potion_delta(self) -> int:
        num = 0
        prefix = self.parser.prefix
        for potion in self.parser._data[prefix + "potions_obtained"]:
            if potion["floor"] == 0:
                num += 1
        return num

    def fights_delta(self) -> int:
        return 0

    def turns_delta(self) -> int:
        return 0

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
        return self.fights_delta()

    @property
    def turns_count(self) -> int:
        return self.turns_delta()

_chars = {
    "SLIMEBOUND": "Slime Boss",
    "GREMLIN": "Gremlin Gang",
    "THE_SPIRIT": "Hexaghost",
    "THE_SNECKO": "Snecko",
    "THE_SILENT": "Silent",
}

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

    prefix = ""
    done = False

    def __init__(self, data: dict[str, Any]): # TODO: fix all JSON_FP_PROP instances
        self._data = data
        self.neow_bonus = NeowBonus(self)
        self._cache = {"self": self} # this lets us do on-the-fly debugging
        self._character: str | None = None
        self._graph_cache: dict[tuple[str, str, tuple, str | None, str | None], str | bytes] = {}

    def get_boss_chest(self) -> dict[str, str | list[str]]:
        if "boss_chest_iter" not in self._cache:
            self._cache["boss_chest_iter"] = iter(self._data[self.prefix + "boss_relics"])

        try: # with a savefile, it's possible to try to get the same floor twice, which will the last one
            return next(self._cache["boss_chest_iter"])
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
    def display_name(self) -> str:
        return ""

    @property
    def character(self) -> str | None:
        if self._character is None:
            return None

        c = _chars.get(self._character)
        if c is None:
            c = self._character.replace("_", " ").title()
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
    @abstractmethod
    def potions_use(self) -> list[list[Potion]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def potions_alchemize(self) -> list[list[Potion]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def potions_entropic(self) -> list[list[Potion]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def potions_discarded(self) -> list[list[Potion]]:
        raise NotImplementedError

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
    @abstractmethod
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

    @property
    @abstractmethod
    def _removals(self) -> list[str]:
        raise NotImplementedError

    def get_removals(self) -> Generator[CardData, None, None]:
        removals = self._removals
        for card in set(removals):
            yield CardData(card, removals)

    @property
    def has_removals(self) -> bool:
        return bool(self._removals)

    @property
    def removals(self) -> Generator[str, None, None]:
        for card in self.get_removals():
            yield from card.as_cards()

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
    def seed(self) -> str:
        if "seed" not in self._cache:
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

            self._cache["seed"] = "".join(s)

        return self._cache["seed"]

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
                    node._card_count = card_count
                    relic_count += node.relic_delta()
                    node._relic_count = relic_count
                    potion_count += node.potion_delta()
                    node._potion_count = potion_count
                    fights_count += node.fights_delta()
                    node._fights_count = fights_count
                    turns_count += node.turns_delta()
                    node._turns_count = turns_count
                    node._floor_time = t - prev
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

    def get_floor(self, floor: int) -> NodeData | None:
        for node in self.path:
            if node.floor == floor:
                return node
        return None

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

    def description(self) -> str:
        if self._description is None:
            desc = []
            # NeowBonus isn't quite NodeData, but it has a similar-enough signature to just work
            obtained: NodeData = self.parser.neow_bonus
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

    def get_details(self, obtained: NodeData, last: NodeData) -> list[str]:
        desc = []
        try:
            text = get_relic_stats(self.relic.name) # FIXME
        except KeyError: # no stats for these
            return []
        stats = None
        if "basemod:mod_saves" in self.parser._data:
            stats = self.parser._data["basemod:mod_saves"].get(f"stats_{self.relic.name}")
        elif "relic_stats" in self.parser._data:
            stats = self.parser._data["relic_stats"].get(self.relic.name)
        if stats is None:
            return []

        per_turn = True

        if self.relic.name == "White Beast Statue":
            # if this is a savefile, only the last number matters. run files should be unaffected
            stats = [stats[-1]]
        if self.relic.name == "Snecko Eye":
            # special handling for this
            per_turn = False
            stats[-1] = stats[-1] / sum(stats[:-1])

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
    def __init__(self, card: str, cards_list: list[str], meta: int = 0):
        name, _, upgrades = card.partition("+")
        self._cards_list = cards_list
        self.internal = card
        self.card: Card = get(name)
        self.meta = meta
        self.upgrades = int(upgrades) if upgrades else 0

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
        return self._cards_list.count(self.internal)

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

class NodeData:
    """Contain relevant information for Spire nodes.

    Subclasses should define the following class variables:
    - room_type :: a human-readable name for the node
    - map_icon  :: the filename for the icon in the icons/ folder

    The recommended creation mechanism for NodeData classes is to call
    the class method `from_parser` with either a Run History parser or a
    Savefile parser, and the floor number.

    Subclasses can - and should - write their own 'get_description' method.
    This takes one argument, type 'collections.defaultdict[int, list[str]]',
    and should modify that mapping in-place. Returning any non-None value
    will raise an error. The method should **NOT** attempt to call the
    superclass version of it with super(); that will be done automatically.

    Built-in index keys all use even numbers. Result will be joined together
    with newlines, and printed in ascending order. Custom code should only add
    data to odd indices. Ranges are provided here; refer to the relevant
    subclass for details. Calling order between various methods is not
    guaranteed - appending to a key already used may have unexpected results.

    0     - Basic stuff; only for things that all nodes share
    2     - Event-specific combat setup
    4     - Combat results (damage taken, turns elapsed, etc.)
    6     - Unique values (key obtained, campfire option, etc.)
    10-20 - Potion usage data
    30-36 - Relic obtention data
    40-62 - Event results
    70-78 - Shop contents
    99    - Special stuff; reserved for bugged or modded content

    """

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
        self._fights_count = None
        self._turns_count = None
        self._skipped_relics = None
        self._skipped_potions = None
        self._cards = []
        self._relics = []
        self._potions = []
        self._usedpotions = None
        self._potions_from_alchemize = None
        self._potions_from_entropic = None
        self._discarded = None
        self._cache = {}

    # TODO: create abstract properties on FileParser to implement on the subclasses so we don't need all of these if/elifs
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
            self._maxhp = parser.max_hp_counts[floor]
            self._curhp = parser.current_hp_counts[floor]
            self._gold = parser.gold_counts[floor]

            self._usedpotions = parser.potions_use[floor]
            self._potions_from_alchemize = parser.potions_alchemize[floor]
            self._potions_from_entropic = parser.potions_entropic[floor]
            self._discarded = parser.potions_discarded[floor]
        except IndexError:
            try:
                self._maxhp = parser.max_hp_counts[floor - 1]
                self._curhp = parser.current_hp_counts[floor - 1]
                self._gold = parser.gold_counts[floor - 1]
            except IndexError:
                pass

        for cards in parser._data[prefix + "card_choices"]:
            if cards["floor"] == floor and cards not in self._cards:
                self._cards.append(cards)

        for relic in parser._data[prefix + "relics_obtained"]:
            if relic["floor"] == floor:
                self._relics.append(get(relic["key"]))

        for potion in parser._data[prefix + "potions_obtained"]:
            if potion["floor"] == floor:
                self._potions.append(get(potion["key"]))

        if "basemod:mod_saves" in parser._data:
            skipped = parser._data["basemod:mod_saves"].get("RewardsSkippedLog")
        else:
            skipped = parser._data.get("rewards_skipped")

        if skipped:
            for choice in skipped:
                if choice["floor"] == floor:
                    self._skipped_relics = [get(x) for x in choice["relics"]]
                    self._skipped_potions = [get(x) for x in choice["potions"]]

        return self

    def description(self) -> str:
        if "description" not in self._cache:
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
                    if (n := max(to_append)) > 99:
                        raise ValueError(f"Class {cls.__name__!r} used out-of-bounds index {n} (max 99)")
                    if (n := min(to_append)) < 0:
                        raise ValueError(f"Class {cls.__name__!r} used negative index {n} (positive values only)")
                except TypeError as e:
                    raise TypeError(f"Class {cls.__name__!r} did not use a number-like type") from e

            final = []
            desc = list(to_append.items())
            desc.sort(key=lambda x: x[0])
            for i, text in desc:
                final.extend(text)
            self._cache["description"] = "\n".join(final)
        return self._cache["description"]

    def escaped_description(self) -> str:
        return self.description().replace("\n", "<br>").replace("'", "\\'")

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[0].append(f"{self.room_type}")
        to_append[0].append(f"{self.current_hp}/{self.max_hp} - {self.gold} gold")

        if self.name:
            to_append[0].append(self.name)

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
    def relics(self) -> list[Relic]:
        return self._relics

    @property
    def skipped_relics(self) -> list[Relic]:
        if self._skipped_relics is None:
            return []
        return self._skipped_relics

    @property
    def potions(self) -> list[Potion]:
        return self._potions

    @property
    def used_potions(self) -> list[Potion]:
        if self._usedpotions is None:
            return []
        return self._usedpotions

    @property
    def potions_from_alchemize(self) -> list[Potion]:
        if self._potions_from_alchemize is None:
            return []
        return self._potions_from_alchemize

    @property
    def potions_from_entropic(self) -> list[Potion]:
        if self._potions_from_entropic is None:
            return []
        return self._potions_from_entropic

    @property
    def discarded_potions(self) -> list[Potion]:
        if self._discarded is None:
            return []
        return self._discarded

    @property
    def skipped_potions(self) -> list[Potion]:
        if self._skipped_potions is None:
            return []
        return self._skipped_potions

    @property
    def floor_time(self) -> int:
        if self._floor_time is None:
            return 0
        return self._floor_time

    def card_delta(self) -> int:
        return len(self.picked)

    def relic_delta(self) -> int:
        return len(self.relics)

    def potion_delta(self) -> int:
        count = len(self.potions) + len(self.potions_from_alchemize) + len(self.potions_from_entropic)
        return count - len(self.used_potions) - len(self.discarded_potions)

    def fights_delta(self) -> int:
        return 0

    def turns_delta(self) -> int:
        return 0

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

    @property
    def fights_count(self) -> int:
        if self._fights_count is None:
            return 1
        return self._fights_count

    @property
    def turns_count(self) -> int:
        if self._turns_count is None:
            return 1
        return self._turns_count

def _get_nodes(parser: FileParser, maybe_cached: list[NodeData] | None) -> Generator[tuple[NodeData, bool], None, None]:
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
                cls = EventNode # not actually a NodeData subclass, but it returns one
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
            value: NodeData = cls.from_parser(parser, floor)
        except ValueError: # this can happen for savefiles if we're on the latest floor
            if taken_len == floor:
                continue # we're on the last floor
            raise
        else:
            yield value, False

    if error:
        logger.error("\n".join(f"Actual: {str(x):<4} | Map: {y}" for x, y in nodes))

class EncounterBase(NodeData):
    """A base data class for Spire node encounters."""

    def __init__(self, damage: dict, *extra):
        super().__init__(*extra)
        self._damage = damage

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        prefix = parser.prefix
        for damage in parser._data[prefix + "damage_taken"]:
            if damage["floor"] == floor:
                break
        else:
            raise ValueError("no fight result yet")

        return super().from_parser(parser, floor, damage, *extra)

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
        return self._damage["enemies"]

    @property
    def fought(self) -> str:
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

    def __init__(self, has_blue_key: bool, relic: str, *extra):
        super().__init__(*extra)
        self._bluekey = has_blue_key
        self._key_relic = relic

    def get_description(self, to_append: dict[int, list[str]]):
        if self.blue_key:
            to_append[6].append(f"Skipped {self.key_relic} for the Sapphire key")

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        has_blue_key = False
        relic = ""
        d = parser._data.get("basemod:mod_saves", ())
        if "BlueKeyRelicSkippedLog" in d:
            if d["BlueKeyRelicSkippedLog"]["floor"] == floor:
                relic = get(d["BlueKeyRelicSkippedLog"]["relicID"]).name
                has_blue_key = True
        elif "blue_key_relic_skipped_log" in parser._data:
            if parser._data["blue_key_relic_skipped_log"]["floor"] == floor:
                relic = get(parser._data["blue_key_relic_skipped_log"]["relicID"]).name
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

    def __init__(self, damage: dict, has_key: bool, *extra):
        super().__init__(damage, *extra)
        self._has_key = has_key

    def get_description(self, to_append: dict[int, list[str]]):
        if self.has_key:
            to_append[6].append("Got the Emerald Key")

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        if "basemod:mod_saves" in parser._data:
            key_floor = parser._data["basemod:mod_saves"].get("greenKeyTakenLog")
        else:
            key_floor = parser._data.get("green_key_taken_log")
        has_key = (key_floor is not None and int(key_floor) == floor)
        return super().from_parser(parser, floor, has_key, *extra)

    @property
    def has_key(self) -> bool:
        return self._has_key

class EventElite(EliteEncounter):
    room_type = "Unknown (Elite)"
    map_icon = "event.png"

class EventNode:
    end_of_act = False

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra) -> NodeData:
        events = []
        for event in parser._data[parser.prefix + "event_choices"]:
            if event["floor"] == floor:
                events.append(event)
        if not events:
            return EmptyEvent.from_parser(parser, floor, *extra)
        if events[0]["event_name"] == "Colosseum":
            return Colosseum.from_parser(parser, floor, events, *extra)
        if len(events) != 1:
            for a in events:
                for b in events:
                    if a != b: # I'm not quite sure how this happens, but sometimes an event will be in twice?
                        return AmbiguousEvent.from_parser(parser, floor, events, *extra)
        event = events[0]
        for dmg in parser._data[parser.prefix + "damage_taken"]:
            if dmg["floor"] == floor: # not passing dmg in, as EncounterBase fills it in
                return EventFight.from_parser(parser, floor, event, *extra)
        return Event.from_parser(parser, floor, event, *extra)

class EmptyEvent(NodeData):
    room_type = "Unknown (Bugged)"
    map_icon = "event.png"

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[99].append(
            "Something happened here, but I'm not sure what...\n"
            "This is a bug with a mod. Please report this to the mod creators:\n"
            "'Missing event data in JSON'\n"
            "(Provide the event name if you can find it)"
        )

class AmbiguousEvent(NodeData):
    room_type = "Unknown (Ambiguous)"
    map_icon = "event.png"

    def __init__(self, events: list[dict[str, Any]], *extra):
        super().__init__(*extra)
        self._events = events

    def get_description(self, to_append: dict[int, list[str]]):
        to_append[99].append(
            "This event is ambiguous; multiple events map to it:\n" +
            ", ".join(x["event_name"] for x in self._events) + " -\n" +
            "This is a bug with a mod. Please report this to the mod creators."
        )

class Event(NodeData):
    room_type = "Unknown"
    map_icon = "event.png"

    def __init__(self, event: dict[str, Any], *extra):
        super().__init__(*extra)
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
    def cards_transformed(self) -> list[str]:
        if "cards_transformed" not in self._event:
            return []
        return [get(x).name for x in self._event["cards_transformed"]]

    @property
    def cards_obtained(self) -> list[str]:
        if "cards_obtained" not in self._event:
            return []
        return [get_card(x) for x in self._event["cards_obtained"]]

    @property
    def cards_removed(self) -> list[str]:
        if "cards_removed" not in self._event:
            return []
        return [get_card(x) for x in self._event["cards_removed"]]

    @property
    def cards_upgraded(self) -> list[str]:
        if "cards_upgraded" not in self._event:
            return []
        return [get_card(x) for x in self._event["cards_upgraded"]]

    @property
    def relics_obtained(self) -> list[Relic]:
        if "relics_obtained" not in self._event:
            return []
        return [get(x) for x in self._event["relics_obtained"]]

    @property
    def relics_lost(self) -> list[Relic]:
        if "relics_lost" not in self._event:
            return []
        return [get(x) for x in self._event["relics_lost"]]

    @property
    def relics(self) -> list[Relic]:
        return super().relics + self.relics_obtained

    def relic_delta(self) -> int:
        return super().relic_delta() - len(self.relics_lost)

class EventFight(Event, EncounterBase):
    """This is a subclass for fights that happen in events.

    This works for Dead Adventurer, Masked Bandits, etc.
    This does *not* work for the Colosseum fight (use Colosseum instead)

    """

    def __init__(self, damage: dict[str, Any], event: dict[str, Any], *extra):
        # swap the argument ordering around, as EncounterBase inserts damage first
        super().__init__(event, damage, *extra)

class Colosseum(Event):
    def __init__(self, damages: list[dict[str, int | str]], events: list[dict[str, Any]], *extra):
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
        super().__init__(event, *extra)
        self._damages = damages

    def get_description(self, to_append: dict[int, list[str]]):
        for i, dmg in enumerate(self._damages, 1):
            to_append[4].append(f"Fight {i} ({dmg['enemies']}):")
            to_append[4].append(f"{dmg['damage']} damage")
            to_append[4].append(f"{dmg['turns']} turns")

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        dmg = []
        for damage in parser._data[parser.prefix + "damage_taken"]:
            if damage["floor"] == floor:
                dmg.append(damage)
        return super(Event, cls).from_parser(parser, floor, dmg, *extra)

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

    def __init__(self, bought: dict[str, list[str]], purged: str | None, contents: dict[str, list[str]] | None, *extra):
        super().__init__(*extra)
        self._bought = bought
        self._purged = purged
        self._contents = contents

    def get_description(self, to_append: dict[int, list[str]]):
        if self.purged:
            to_append[70].append(f"* Removed {self.purged}")
        if self.contents:
            to_append[72].append("Skipped:")
            if self.contents["relics"]:
                to_append[74].append("* Relics")
                to_append[74].extend(f"  - {x.name}" for x in self.contents["relics"])
            if self.contents["cards"]:
                to_append[76].append("* Cards")
                to_append[76].extend(f"  - {x}" for x in self.contents["cards"])
            if self.contents["potions"]:
                to_append[78].append("* Potions")
                to_append[78].extend(f"  - {x.name}" for x in self.contents["potions"])

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        bought = {"cards": [], "relics": [], "potions": []}
        purged = None
        contents = None
        for i, purchased in enumerate(parser._data[parser.prefix + "item_purchase_floors"]):
            if purchased == floor:
                value = parser._data[parser.prefix + "items_purchased"][i]
                name, _, upgrades = value.partition("+")
                item = get(name)
                match item.cls_name:
                    case "card":
                        bought["cards"].append(get_card(value))
                    case "relic":
                        bought["relics"].append(item)
                    case "potion":
                        bought["potions"].append(item)

        try:
            index = parser._data[parser.prefix + "items_purged_floors"].index(floor)
        except ValueError:
            pass
        else:
            purged = get_card(parser._data[parser.prefix + "items_purged"][index])

        d = ()
        if "shop_contents" in parser._data:
            d = parser._data["shop_contents"]
        elif "basemod:mod_saves" in parser._data:
            d = parser._data["basemod:mod_saves"].get("ShopContentsLog", ())
        if d:
            contents = {"relics": [], "cards": [], "potions": []}
        for data in d:
            if data["floor"] == floor:
                for relic in data["relics"]:
                    contents["relics"].append(get(relic))
                for card in data["cards"]:
                    contents["cards"].append(get_card(card))
                for potion in data["potions"]:
                    contents["potions"].append(get(potion))

        return super().from_parser(parser, floor, bought, purged, contents, *extra)

    @property
    def picked(self) -> list[str]:
        return super().picked + self.bought["cards"]

    @property
    def relics(self) -> list[Relic]:
        return super().relics + self.bought["relics"]

    @property
    def potions(self) -> list[Potion]:
        return super().potions + self.bought["potions"]

    @property
    def bought(self) -> dict[str, list[str | Relic | Potion]]:
        return self._bought

    @property
    def purged(self) -> str | None:
        return self._purged

    @property
    def contents(self) -> dict[str, list[str | Relic | Potion]] | None:
        return self._contents

    def card_delta(self) -> int:
        return super().card_delta() - (self.purged is not None)

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

    def __init__(self, key: str, data: str | None, *extra):
        super().__init__(*extra)
        self._key = key
        self._data = data

    def get_description(self, to_append: dict[int, list[str]]) -> str:
        to_append[6].append(self.action)

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        key = None
        data = None
        for rest in parser._data[parser.prefix + "campfire_choices"]:
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

class BossChest(NodeData):
    room_type = "Boss Chest"
    map_icon = "boss_chest.png"
    end_of_act = True

    def __init__(self, picked: str | None, skipped: list[str], *extra):
        super().__init__(*extra)
        if picked is not None:
            self._relics.append(picked)
        self._skipped = skipped

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        boss_relics = parser.get_boss_chest()
        picked = None
        skipped = []
        if boss_relics.get("picked", "SKIP") != "SKIP":
            picked = get(boss_relics["picked"])
        for relic in boss_relics["not_picked"]:
            skipped.append(get(relic))
        return super().from_parser(parser, floor, picked, skipped, *extra)

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

    def __init__(self, score: int | None, data: list[str], *extra):
        self._score = score
        self._data = data
        super().__init__(*extra)

    def get_description(self, to_append: dict[int, list[str]]):
        if self.score:
            to_append[6].extend(self.score_breakdown)
            to_append[6].append(f"Score: {self.score}")

    @classmethod
    def from_parser(cls, parser: FileParser, floor: int, *extra):
        score = parser._data.get("score", 0)
        breakdown = parser._data.get("score_breakdown", [])
        return super().from_parser(parser, floor, score, breakdown, *extra)

    @property
    def floor_time(self) -> int:
        return 0

    @property
    def score(self) -> int:
        return self._score

    @property
    def score_breakdown(self) -> list[str]:
        return self._data

class BottleRelic(NamedTuple):
    bottle_id: str
    card: str
