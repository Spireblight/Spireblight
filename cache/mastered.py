from __future__ import annotations

from typing import TYPE_CHECKING

from collections import Counter

from cache.cache_helpers import MasteryStats, MasteryCounts
from nameinternal import get, get_color, get_relics
from sts_profile import get_profile

if TYPE_CHECKING:
    from runs import RunParser
    from save import Savefile

_mastery_stats = MasteryStats()

__all__ = ["update_mastery_stats", "get_mastered", "get_mastery_counts", "get_current_masteries"]

def update_mastery_stats():
    try:
        runs = list(get_profile(0).runs) # BaalorA20 profile
    except IndexError:
        runs = []

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
        if relic.relic not in _mastery_stats.mastered_relics:
            _mastery_stats.mastered_relics[relic.relic] = run

    totals = Counter([get(x.partition("+")[0]) for x in run._master_deck])
    for card, count in totals.items():
        if count >= 2 and card not in _mastery_stats.mastered_cards:
            _mastery_stats.mastered_cards[card] = run

def get_mastered():
    return _mastery_stats

def get_mastery_counts(*, force: bool = False, _cached: dict = {}) -> list[MasteryCounts]:
    if force or not _cached or _cached.get("last") != _mastery_stats.last_run_timestamp:
        _cached.clear()
        if not _update_mastery_counts(_cached):
            raise ValueError("Could not update mastery counts")

    ret = []
    for k, v in _cached.items():
        if k == "last":
            continue

        counts = MasteryCounts(k, v["mastered"], v["unmastered"])
        ret.append(counts)

    _cached["last"] = _mastery_stats.last_run_timestamp
    return ret

def _update_mastery_counts(cache: dict) -> bool:
    for char, color in (
        ("Ironclad", "Red"),
        ("Silent", "Green"),
        ("Defect", "Blue"),
        ("Watcher", "Purple"),
        ("Colorless", "Colorless"),
        ("Curse", "Curse")
    ):
        d = {"mastered": [], "unmastered": []}
        for card in get_color(color):
            if card.rarity == "Special":
                if card.name not in (
                    "Apparition",
                    "Bite",
                    "J.A.X.",
                    "Ritual Dagger",
                    "Ascender's Bane",
                    "Necronomicurse",
                    "Curse of the Bell"
                ):
                    continue
            if card in _mastery_stats.mastered_cards:
                d["mastered"].append(card)
            else:
                d["unmastered"].append(card)

        cache[char] = d

    d = {"mastered": [], "unmastered": []}
    for relic in get_relics():
        if relic in _mastery_stats.mastered_relics:
            d["mastered"].append(relic)
        else:
            d["unmastered"].append(relic)

    cache["Relics"] = d

    return True

def get_current_masteries(save: Savefile):
    if save is None:
        return ([], [], [])
    deck = Counter([get(x.partition("+")[0]) for x in save.deck_card_ids])
    one_ofs: list[str] = []
    cards_can_master: list[str] = []
    for card, count in deck.items():
        if card not in _mastery_stats.mastered_cards:
            if count == 1:
                one_ofs.append(card)
            cards_can_master.append(card)

    relics_can_master: list[str] = []
    for relic in save.relics:
        if relic.name not in _mastery_stats.mastered_relics:
            relics_can_master.append(relic.name)

    return (one_ofs, cards_can_master, relics_can_master)
