import collections

from score.ScoreBonus import BeyondElitesKilled, BeyondPerfect, ScoreBonus
from save import Savefile


class RunScore:
    def __init__(self, run: Savefile):
        self.run = run
        # we could use this and pass to the individual bonuses, but it'd be unused for many of them
        # prevents having to iterate over the deck a few times
        self.card_dict = dict(collections.Counter(run.cards))

    def get_score_for_run(self):
        score = 0

        bonuses: list[ScoreBonus] = []
        bonuses.append(BeyondPerfect())
        bonuses.append(BeyondElitesKilled())
        # etc

        for bonus in bonuses:
            score += bonus.bonus_for_run(self.run)
        
        return score
