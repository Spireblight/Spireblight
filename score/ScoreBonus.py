from nameinternal import get_card_metadata, get_score_bonus
from collections import Counter, namedtuple
from save import Savefile
from abc import ABC, abstractmethod

# In general, these should only be needed for the Ongoing run
# If for a completed run, use RunHistoryPlus's score_breakdown field
class ScoreBonus(ABC):
    def __init__(self, name: str):
        data = get_score_bonus(name)
        self.name = data["NAME"]
        self.description = ""
        if data["DESCRIPTIONS"]:
            self.description = data["DESCRIPTIONS"][0]

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def bonus_for_run(self, save: Savefile):
        raise NotImplementedError

    def get_starting_max_hp(self, save: Savefile):
        max_hp_tuple = namedtuple("MaxHP", ["base_max_hp", "asc_max_hp_loss"])
        max_hp_dict = {
            "Ironclad": max_hp_tuple(80, 5),
            "Silent": max_hp_tuple(70, 4),
            "Defect": max_hp_tuple(75, 4),
            "Watcher": max_hp_tuple(72, 4)
        }

        character_max_hp = max_hp_dict[save.character].base_max_hp
        if save.ascension_level >= 14:
            character_max_hp -= max_hp_dict[save.character].asc_max_hp_loss

        return character_max_hp

class Ascension(ScoreBonus):
    def __init__(self):
        super().__init__("Ascension")

    def bonus_for_run(self, save: Savefile):
        # Only applies to the score from the following bonuses:
        # Floors Climbed
        # Enemies Killed
        # Elites Killed
        # Bosses Slain
        # Champion
        # Perfect
        # Beyond Perfect
        # Overkill
        # C-c-c-combo.
        return 0

class FloorsClimbed(ScoreBonus):
    def __init__(self):
        super().__init__("Floors Climbed", "Number of the Floor you reached")

    def bonus_for_run(self, save: Savefile):
        return 5 * save.current_floor

class EnemiesKilled(ScoreBonus):
    def __init__(self):
        super().__init__("Enemies Killed", "For each Monster encounter defeated")

    def bonus_for_run(self, save: Savefile):
        return 2 * save._data.get("monsters_killed", 0)

class ExordiumElitesKilled(ScoreBonus):
    def __init__(self):
        super().__init__("Exordium Elites Killed")

    def bonus_for_run(self, save: Savefile):
        """Return 10 points for each elite killed."""
        return 10 * save._data.get("elites1_killed", 0)

class CityElitesKilled(ScoreBonus):
    def __init__(self):
        super().__init__("City Elites Killed")

    def bonus_for_run(self, save: Savefile):
        """Return 20 points for each elite killed."""
        return 20 * save._data.get("elites2_killed", 0)

class BeyondElitesKilled(ScoreBonus):
    def __init__(self):
        super().__init__("Beyond Elites Killed")

    def bonus_for_run(self, save: Savefile):
        """Return 30 points for each elite killed."""
        return 30 * save._data.get("elites3_killed", 0)

class Champion(ScoreBonus):
    def __init__(self):
        super().__init__("Champion")
    
    def bonus_for_run(self, save: Savefile):
        """Return 25 points for each elite perfected.""" 
        return 25 * save._data.get("champions", 0)

class BossesSlain(ScoreBonus):
    def __init__(self):
        super().__init__("Bosses Slain")

    def bonus_for_run(self, save: Savefile):
        # do this based on floor number or path == "BOSS"?
        return 0

class BeyondPerfect(ScoreBonus):
    def __init__(self):
        super().__init__("Beyond Perfect")
    
    def bonus_for_run(self, save: Savefile):
        """Return 50 points for each boss perfected, if 3 or more, return 200.""" 
        if save._data.get("perfect", 0) >= 3:
            return 200
        return 0

class Collector(ScoreBonus):
    def __init__(self):
        super().__init__("Collector")
    
    def bonus_for_run(self, save: Savefile):
        """Have 4 copies of any non-starter card.""" 
        card_dict = dict(Counter(save.cards))
        nonstarter_cards = [key for key, value in card_dict.items() if value >= 4 and get_card_metadata(key)["RARITY"] != "Starter"]
        return 25 * len(nonstarter_cards)

class Librarian(ScoreBonus):
    def __init__(self):
        super().__init__("Librarian")
    
    def bonus_for_run(self, save: Savefile):
        """Deck size greater than 35 cards.""" 
        if len(list(save.cards)) > 35:
            return 25
        return 0
    
class Encyclopedian(ScoreBonus):
    def __init__(self):
        super().__init__("Encyclopedian")
    
    def bonus_for_run(self, save: Savefile):
        """Deck size greater than 50 cards.""" 
        if len(list(save.cards)) > 50:
            return 50
        return 0

class Overkill(ScoreBonus):
    def __init__(self):
        super().__init__("Overkill")
    
    def bonus_for_run(self, save: Savefile):
        """Deal 99 damage with a single attack.""" 
        if save._data.get("overkill", False):
            return 25
        return 0

class MysteryMachine(ScoreBonus):
    def __init__(self):
        super().__init__("Mystery Machine")
    
    def bonus_for_run(self, save: Savefile):
        """Visited 15+ events.""" 
        if save._data.get("mystery_machine", 0) >= 15:
            return 25
        return 0

class ILikeShiny(ScoreBonus):
    def __init__(self):
        super().__init__("Shiny")
    
    def bonus_for_run(self, save: Savefile):
        """Has 25+ relics.""" 
        if len(save._data.get("relics", [])) >= 25:
            return 50
        return 0

class WellFed(ScoreBonus):
    def __init__(self):
        super().__init__("Well Fed")
    
    def bonus_for_run(self, save: Savefile):
        """Has 15+ additional Max HP."""
        if save._data.get("max_health", 0) - self.get_starting_max_hp(save) > 15:
            return 25
        return 0

class Stuffed(ScoreBonus):
    def __init__(self):
        super().__init__("Stuffed")
    
    def bonus_for_run(self, save: Savefile):
        """Has 30+ additional Max HP."""
        if save._data.get("max_health", 0) - self.get_starting_max_hp(save) > 30:
            return 50
        return 0

class MoneyMoney(ScoreBonus):
    def __init__(self):
        super().__init__("Money Money")
    
    def bonus_for_run(self, save: Savefile):
        """Gained 1000+ gold."""
        if save._data.get("gold_gained", 0) >= 1000:
            return 25
        return 0

class RainingMoney(ScoreBonus):
    def __init__(self):
        super().__init__("Raining Money")
    
    def bonus_for_run(self, save: Savefile):
        """Gained 2000+ gold."""
        if save._data.get("gold_gained", 0) >= 2000:
            return 50
        return 0

class ILikeGold(ScoreBonus):
    def __init__(self):
        super().__init__("I Like Gold")
    
    def bonus_for_run(self, save: Savefile):
        """Gained 3000+ gold."""
        if save._data.get("gold_gained", 0) >= 3000:
            return 75
        return 0

class Combo(ScoreBonus):
    def __init__(self):
        super().__init__("Combo")
    
    def bonus_for_run(self, save: Savefile):
        """Play 20 cards in a single turn."""
        if save._data.get("combo", False):
            return 25
        return 0

class Pauper(ScoreBonus):
    def __init__(self):
        super().__init__("Pauper")
    
    def bonus_for_run(self, save: Savefile):
        """Have 0 rare cards."""
        rare_cards = [card for card in save.cards if get_card_metadata(card)["RARITY"] == "Rare"]
        if not rare_cards:
            return 50
        return 0

class Curses(ScoreBonus):
    def __init__(self):
        super().__init__("Curses")
    
    def bonus_for_run(self, save: Savefile):
        """Your deck contains 5 curses."""
        curses = [card for card in save.cards if get_card_metadata(card)["CHARACTER"] == "Curse"]
        if len(curses) >= 5:
            return 100
        return 0

class Highlander(ScoreBonus):
    def __init__(self):
        super().__init__("Highlander")
    
    def bonus_for_run(self, save: Savefile):
        """Your deck contains no duplicates."""
        card_dict = dict(Counter(save.cards))
        multiple_copies = [key for key, value in card_dict.items() if value > 1 and get_card_metadata(key)["RARITY"] != "Starter"]
        if not multiple_copies:
            return 100
        return 0

class Poopy(ScoreBonus):
    def __init__(self):
        super().__init__("Poopy")
    
    def bonus_for_run(self, save: Savefile):
        """Possess Spirit Poop."""
        relics = save._data.get("relics", [])
        if "Spirit Poop" in relics:
            return -1
        return 0

# Probably never include any of the below in an ongoing run?
class Speedster(ScoreBonus):
    def __init__(self):
        super().__init__("Speedster")
    
    def bonus_for_run(self, save: Savefile):
        """Victory in under 60 minutes."""
        if save._data.get("metric_playtime", 0) < 3600:
            return 25
        return 0

class LightSpeed(ScoreBonus):
    def __init__(self):
        super().__init__("Light Speed")
    
    def bonus_for_run(self, save: Savefile):
        """Victory in under 60 minutes."""
        if save._data.get("metric_playtime", 0) < 2700:
            return 50
        return 0

class Heartbreaker(ScoreBonus):
    def __init__(self):
        super().__init__("Heartbreaker")
    
    def bonus_for_run(self, save: Savefile):
        return 250

class OnMyOwnTerms(ScoreBonus):
    def __init__(self):
        super().__init__("On My Own Terms")
    
    def bonus_for_run(self, save: Savefile):
        """Killed yourself."""
        # no idea how this is checked or if we care
        return 50