from __future__ import annotations

from typing import TYPE_CHECKING

from collections import Counter

from cache.cache_helpers import MasteryStats
from src.nameinternal import get
from src.sts_profile import get_profile

if TYPE_CHECKING:
    from src.runs import RunParser
    from src.save import Savefile

_mastery_stats = MasteryStats()

__all__ = ["update_mastery_stats", "get_mastered", "get_current_masteries"]

def update_mastery_stats():
    profile = get_profile(0)
    if profile is None:
        runs = []
    else:
        runs = list(profile.runs)

    if _mastery_stats.last_run_timestamp is None:
        for run in runs:
            _update_mastery_stats_from_run(run)
    else:
        if runs and _mastery_stats.last_run_timestamp != runs[0].timestamp:
            _update_mastery_stats_from_run(runs[0])

def _update_mastery_stats_from_run(run: RunParser):
    if run.timestamp.year < 2023:
        return
    if run.ascension_level != 20: # just in case
        return
    if not run.won:
        return

    _mastery_stats.last_run_timestamp = run.timestamp
    for relic in run.relics:
        if relic.name not in _mastery_stats.mastered_relics:
            _mastery_stats.mastered_relics[relic.name] = run

    totals = Counter([get(x.partition("+")[0]) for x in run._master_deck])
    for card, count in totals.items():
        if count >= 2 and card not in _mastery_stats.mastered_cards:
            _mastery_stats.mastered_cards[card.name] = run
            _mastery_stats.colors[card.name] = card.color

def get_mastered():
    return _mastery_stats

def get_current_masteries(save: Savefile):
    if save is None:
        return ([], [], [])
    deck = Counter([get(x.partition("+")[0]).name for x in save.deck_card_ids])
    one_ofs: list[str] = []
    cards_can_master: list[str] = []
    for card, count in deck.items():
        if card not in _mastery_stats.mastered_cards:
            if count == 1:
                one_ofs.append(card)
                cards_can_master.append(card)
            else:
                cards_can_master.append(f'({card})')
    
    relics_can_master: list[str] = []
    for relic in save.relics:
        if relic.name not in _mastery_stats.mastered_relics:
            relics_can_master.append(relic.name)

    return (one_ofs, cards_can_master, relics_can_master)
