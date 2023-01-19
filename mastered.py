from collections import Counter
from datetime import datetime

from nameinternal import get
from sts_profile import get_profile
from runs import RunParser

__all__ = ["get_mastered"]

def get_mastered():
    cards: dict[str, RunParser] = {}
    relics: dict[str, RunParser] = {}
    colors: dict[str, str] = {}
    for run in get_profile(0).runs:
        if run.timestamp.year < 2023:
            continue
        if run.ascension_level != 20: # just in case
            continue
        if not run.won:
            continue

        for relic in run.relics:
            if relic.name not in relics:
                relics[relic.name] = run

        totals = Counter([get(x.partition("+")[0]) for x in run._master_deck])
        for card, count in totals.items():
            if count >= 2 and card not in cards:
                cards[card.name] = run
                colors[card.name] = card.color

    return (cards, relics, colors)
