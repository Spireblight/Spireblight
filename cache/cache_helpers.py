from __future__ import annotations

import datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nameinternal import Card, Relic
    from runs import RunParser

class Statistic:
    def __init__(self, *, set_default: bool = False):
        self.all_character_count = None
        self.ironclad_count = None
        self.silent_count = None
        self.defect_count = None
        self.watcher_count = None
        if set_default:
            self.all_character_count = 0
            self.ironclad_count = 0
            self.silent_count = 0
            self.defect_count = 0
            self.watcher_count = 0

    @property
    def is_loaded(self) -> bool:
        return self.all_character_count is not None and self.ironclad_count is not None and self.silent_count is not None and self.defect_count is not None and self.watcher_count is not None

class RunStats:
    def __init__(self):
        self.current_year = datetime.datetime.now().year
        self.all_wins = Statistic(set_default=True)
        self.all_losses = Statistic(set_default=True)
        self.year_wins: dict[int, Statistic] = {
            self.current_year: Statistic(set_default=True)
        }
        self.year_losses: dict[int, Statistic] = {
            self.current_year: Statistic(set_default=True)
        }
        self.pb = Statistic(set_default=True)
        self.streaks = Statistic()
        self.last_timestamp: datetime.datetime = None

    def add_win(self, char: str, run_date: datetime):
        date = run_date.date()
        if not date.year in self.year_wins:
            self.year_wins[date.year] = Statistic(set_default=True)

        self._increment_stat(self.all_wins, char)
        self._increment_stat(self.year_wins[date.year], char)

    def add_loss(self, char: str, run_date: datetime):
        date = run_date.date()
        if not date.year in self.year_losses:
            self.year_losses[date.year] = Statistic(set_default=True)

        self._increment_stat(self.all_losses, char)
        self._increment_stat(self.year_losses[date.year], char)

    def check_pb(self, run: RunParser):
        if not run.modded:
            if self.pb.all_character_count < run.rotating_streak.streak:
                self.pb.all_character_count = run.rotating_streak.streak
            match run.character:
                case "Ironclad":
                    if self.pb.ironclad_count < run.character_streak.streak:
                        self.pb.ironclad_count = run.character_streak.streak
                case "Silent":
                    if self.pb.silent_count < run.character_streak.streak:
                        self.pb.silent_count = run.character_streak.streak
                case "Defect":
                    if self.pb.defect_count < run.character_streak.streak:
                        self.pb.defect_count = run.character_streak.streak
                case "Watcher":
                    if self.pb.watcher_count < run.character_streak.streak:
                        self.pb.watcher_count = run.character_streak.streak

    def _increment_stat(self, stat: Statistic, char: str):
        match char:
            case "Ironclad":
                stat.ironclad_count += 1
            case "Silent":
                stat.silent_count += 1
            case "Defect":
                stat.defect_count += 1
            case "Watcher":
                stat.watcher_count += 1
        stat.all_character_count += 1

class RunLinkedListNode:
    def __init__(self):
        self.next: RunParser = None
        self.prev: RunParser = None
        self.next_char: RunParser = None
        self.prev_char: RunParser = None
        self.next_win: RunParser = None
        self.prev_win: RunParser = None
        self.next_loss: RunParser = None
        self.prev_loss: RunParser = None

    def get_run(self, *, is_prev: bool, is_character_specific: bool) -> RunParser:
        if is_prev:
            if is_character_specific:
                return self.prev_char
            else:
                return self.prev
        else:
            if is_character_specific:
                return self.next_char
            else:
                return self.next

class MasteryStats:
    def __init__(self) -> None:
        self.mastered_cards: dict[Card, RunParser] = {}
        self.mastered_relics: dict[Relic, RunParser] = {}
        self.last_run_timestamp: datetime.datetime = None

class MasteryCounts:
    def __init__(self, character: str, mastered: list[Card | Relic], unmastered: list[Card | Relic]) -> None:
        self.character = character
        self.mastered = mastered
        self.unmastered = unmastered

    @property
    def mastered_count(self):
        return len(self.mastered)

    @property
    def total_count(self):
        return self.mastered_count + len(self.unmastered)
