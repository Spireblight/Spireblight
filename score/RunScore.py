from score.ScoreBonus import *
from save import Savefile


class RunScore:
    def __init__(self):
        # need to add all the bonuses, but also add checks for them (Stuffed over Well Fed)
        self.general_bonuses: list[ScoreBonus] = []
        self.general_bonuses.append(FloorsClimbed())
        self.general_bonuses.append(EnemiesKilled())
        self.general_bonuses.append(ExordiumElitesKilled())
        self.general_bonuses.append(CityElitesKilled())
        self.general_bonuses.append(BeyondElitesKilled())
        self.general_bonuses.append(BossesSlain())
        self.general_bonuses.append(Ascension())
        self.general_bonuses.append(Champion())
        self.general_bonuses.append(Collector())
        self.general_bonuses.append(Overkill())
        self.general_bonuses.append(MysteryMachine())
        self.general_bonuses.append(ILikeShiny())
        self.general_bonuses.append(Combo())
        self.general_bonuses.append(Pauper())
        self.general_bonuses.append(Curses())
        self.general_bonuses.append(Highlander())
        self.general_bonuses.append(Poopy())

        # These should go in descending order so we can stop when we hit a success
        self.bonus_exclusions: list[list[ScoreBonus]] = []
        self.bonus_exclusions.append(
            [BeyondPerfect(), Perfect()],
            [Encyclopedian(), Librarian()],
            [Stuffed(), WellFed()],
            [ILikeGold(), RainingMoney(), MoneyMoney()],
            [LightSpeed(), Speedster()]
        )

    def get_score_for_run(self, run: Savefile) -> int:
        score = 0

        for bonus in self.general_bonuses:
            score += bonus.bonus_for_run(run)        
        
        for bonuses in self.bonus_exclusions:
            for bonus in bonuses:
                score_addition = bonus.bonus_for_run(run)
                # if we get a non-zero score, add the score and do the next exclusion
                if score_addition:
                    score += score_addition
                    break
        return score
