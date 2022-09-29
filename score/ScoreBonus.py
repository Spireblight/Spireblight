from nameinternal import get_score_bonus
from gamedata import FileParser
from abc import ABC, abstractmethod

class ScoreBonus(ABC):
    def __init__(self, name: str):
        data = get_score_bonus(name)
        self.name = data["NAME"]
        self.description = ""
        if data["DESCRIPTIONS"]:
            self.description = data["DESCRIPTIONS"][0]

    @abstractmethod
    def bonus_for_run(self, run: FileParser):
        raise NotImplementedError

class BeyondPerfect(ScoreBonus):
    def __init__(self):
        super().__init__("Beyond Perfect")
    
    def bonus_for_run(self, run: FileParser):
        # check if run has 3 perfect boss fights, return 200 if it has, return 0 otherwise 
        return 200

class BeyondElitesKilled(ScoreBonus):
    def __init__(self):
        super().__init__("Beyond Elites Killed")

    def bonus_for_run(self, run: FileParser):
        # check how many elites have been killed in The Beyond (Act 3): 30 per elite
        return 0