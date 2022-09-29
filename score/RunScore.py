from gamedata import FileParser
from score.ScoreBonus import BeyondElitesKilled, BeyondPerfect, ScoreBonus


class RunScore:
    def __init__(self, run: FileParser):
        self.run = run
        self.bonuses: list[ScoreBonus] = []

    def get_score_for_run(self):
        self.bonuses.append(BeyondPerfect())
        self.bonuses.append(BeyondElitesKilled())

        for bonus in self.bonuses:
            bonus.bonus_for_run(self.run)