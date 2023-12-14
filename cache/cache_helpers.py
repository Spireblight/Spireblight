from __future__ import annotations

import datetime
import math

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

    def __str__(self) -> str:
        return f'all_character_count: {self.all_character_count}, IC: {self.ironclad_count}, Silent: {self.silent_count}, Defect: {self.defect_count}, Watcher: {self.watcher_count}'

class RunStats:
    def __init__(self):
        self._is_loaded = False
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

    def __str__(self) -> str:
        return f'all_wins: {self.all_wins}\nall_losses: {self.all_losses}\nstreaks: {self.streaks}'

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded
    
    @is_loaded.setter
    def is_loaded(self, val):
        self._is_loaded = val

    @property
    def date_range_string(self) -> str:
        return "all-time"

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

    def clear(self):
        self.__init__()

class RunStatsByDate(RunStats):
    def __init__(self):
        super().__init__()
        self.start_date = None
        self.end_date = None

    @property
    def date_range_string(self) -> str:
        date_str = ""
        format = "%Y/%m/%d"
        if self.start_date is None and self.end_date is None:
            date_str = "all-time"
        elif self.start_date is not None and self.end_date is None:
            date_str = f'starting with {self.start_date.strftime(format)}'
        elif self.start_date is None and self.end_date is not None:
            date_str = f'before {self.end_date.strftime(format)}'
        else:
            date_str = f'{self.start_date.strftime(format)} - {self.end_date.strftime(format)}'
        return date_str

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
        self.mastered_cards: dict[str, RunParser] = {}
        self.mastered_relics: dict[str, RunParser] = {}
        self.colors: dict[str, str] = {}
        self.last_run_timestamp: datetime.datetime = None


class StreakCache:
    """
    A streak superclass that contains StreakContainer objects.

    """

    def __init__(self, since: datetime.datetime):
        self.since = since
        self.containers = []

    def __repr__(self):
        return f"StreakCache of {len(self.containers)}: {self.containers}"

    def clear(self):
        self.containers = []

    def prepend(self, containers):
        self.containers.insert(0, containers)

    @property
    def latest(self):
        return self.containers[0]

class StreakContainer:
    """
    Collection of runs that form a winning or losing streak.

    The `winning_streak` attribute denotes if the streak contains wins
    or not.  The notion of losing streaks are used on the streak page to
    show how many runs were between the streaks.

    The `ongoing` attribute denotes if the streak is still going.  If
    it's True, this is shown on the streak date in the UI.

    The `runs` attribute is the list of runs in the streak.  If the
    streak is over, the losing run that broke it should be in there as
    well so it can be shown in the UI as the one that broke it.

    """

    def __init__(self, winning_streak: bool, runs):
        self.winning_streak = winning_streak
        self.ongoing = False
        self.runs = runs

    def __repr__(self):
        return f"Streaks<{self.character} {self.verb} of {self.length}>"

    def append(self, runs):
        self.runs += runs

    def get_run(self, x):
        return self.display_runs[x]

    @property
    def display_runs(self):
        """
        The runs, but with the losing run included if this is a winning streak that is over.

        """
        if self.ongoing:
            return self.runs
        return self.runs + [self.runs[-1].matched.next_char]

    @property
    def start(self):
        return self.runs[0].timestamp.strftime("%b %-d")

    @property
    def end(self):
        # We use 'display_runs' here so that if the streak is over we show the date of the run that
        # broke the streak.
        return self.display_runs[-1].timestamp.strftime("%b %-d")

    @property
    def character(self):
        return self.runs[0].character

    @property
    def verb(self):
        return self.runs[0].verb

    @property
    def length(self):
        return len(self.display_runs)

    @property
    def target(self):
        """
        The amount of blobs to show for this group.

        If less than 20, show 20.
        After 20, show ten more for every ten passed.
        """
        if self.length <= 20:
            return 20
        return 10 * (math.floor(self.length / 10) + 1)

    @property
    def streak(self):
        """
        Counts the amount of runs that were the actual streak.

        Without this, the streak would show one too many once it's over
        since we care to show the losing run inside the streak
        collection.

        """
        return len([x for x in self.runs if x.won])
