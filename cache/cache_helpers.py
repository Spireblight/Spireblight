from __future__ import annotations

import datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        self.wins = Statistic(set_default=True)
        self.losses = Statistic(set_default=True)
        self.pb = Statistic(set_default=True)
        self.streaks = Statistic()
        self.last_timestamp: datetime.datetime = None

    def add_win(self, char: str):
        self._increment_stat(self.wins, char)

    def add_loss(self, char: str):
        self._increment_stat(self.losses, char)

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