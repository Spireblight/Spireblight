import collections

from nameinternal import get_card_metadata, get_score_bonus
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
        # do this based on floor number?
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
        card_dict = dict(collections.Counter(save.cards))
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
        if save._data.get("overkill", False):
            return 25
        return 0

# I don't think this one will be used in an ongoing run?
class Heartbreaker(ScoreBonus):
    def __init__(self):
        super().__init__("Heartbreaker")
    
    def bonus_for_run(self, save: Savefile):
        return 250