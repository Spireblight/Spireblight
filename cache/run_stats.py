from datetime import datetime
import json
import os
from cache.cache_helpers import RunStats, RunStatsByDate
from src.sts_profile import get_profile
from src.logger import logger
from src.utils import parse_date_range, _parse_dates_with_optional_month_day

class _RangeCache():
    def __init__(self) -> None:
        # Because nulls are a valid state (all-time), we need a distinction between the file saying the dates are null or 
        # we haven't set a date so we're not trying to read from the file every time we see nulls
        self.is_loaded = False
        self.dateDict: dict[str, str] = {
            "start_date": None,
            "end_date": None
        }

_range = _RangeCache()
_all_run_stats = RunStats()
_run_stats_by_date = RunStatsByDate()

__all__ = ["update_all_run_stats", 
           "get_all_run_stats", 
           "get_run_stats_by_date", 
           "get_run_stats_by_date_string"]

def update_all_run_stats():
    _update_run_stats(_all_run_stats)
    _update_run_stats(_run_stats_by_date)

def _write_range_to_file(start_date: datetime | None, end_date: datetime | None):
    _range.dateDict["start_date"] = start_date.strftime("%Y/%m/%d") if start_date is not None else None
    _range.dateDict["end_date"] = end_date.strftime("%Y/%m/%d") if end_date is not None else None
    _range.is_loaded = True
    jsonObj = json.dumps(_range.dateDict)
    with open(os.path.join("data", "range.json"), "w") as f:
        f.write(jsonObj)

def _set_range_from_file():
    dateDict = {}
    try:
        with open(os.path.join("data", "range.json")) as f:
            dateDict = json.load(f)
    except:
        dateDict["start_date"] = None
        dateDict["end_date"] = None
    _range.dateDict["start_date"] = dateDict["start_date"]
    _range.dateDict["end_date"] = dateDict["end_date"]
    _range.is_loaded = True
    _run_stats_by_date.clear()
    if _range.dateDict["start_date"] is not None:
        _run_stats_by_date.start_date = _parse_dates_with_optional_month_day(_range.dateDict["start_date"])
    if _range.dateDict["end_date"] is not None:
        _run_stats_by_date.end_date = _parse_dates_with_optional_month_day(_range.dateDict["end_date"])
    _update_run_stats(_run_stats_by_date, _run_stats_by_date.start_date, _run_stats_by_date.end_date)

def update_range(start_date: datetime | None, end_date: datetime | None):
    _write_range_to_file(start_date, end_date)
    _run_stats_by_date.clear()
    _run_stats_by_date.start_date = start_date
    _run_stats_by_date.end_date = end_date
    _update_run_stats(_run_stats_by_date, _run_stats_by_date.start_date, _run_stats_by_date.end_date)

def get_run_stats_by_date_string(date_string: str) -> RunStatsByDate:
    date_tuple = parse_date_range(date_string)
    start_date = date_tuple[0]
    end_date = date_tuple[1]
    return get_run_stats_by_date(start_date, end_date)

def get_run_stats_by_date(start_date: datetime | None = None, end_date: datetime | None = None) -> RunStatsByDate:
    # return the cached range stats if dates are the exact same or both are none
    if (start_date is None and end_date is None) or (start_date == _run_stats_by_date.start_date and end_date == _run_stats_by_date.end_date):
        if start_date is None and end_date is None and not _range.is_loaded:
            _set_range_from_file()
        return _run_stats_by_date
    run_stats_by_date = RunStatsByDate()
    run_stats_by_date.start_date = start_date
    run_stats_by_date.end_date = end_date
    _update_run_stats(run_stats_by_date, run_stats_by_date.start_date, run_stats_by_date.end_date)
    return run_stats_by_date

def _update_run_stats(run_stats: RunStats, start_date: datetime | None = None, end_date: datetime | None = None):
    # we should only have to load this one time this way, after that we can just use the most recent run to update values
    try:
        runs = list(get_profile(0).runs) # BaalorA20 profile
    except:
        runs = []

    if runs:
        if not run_stats.is_loaded:
            run_stats.is_loaded =  True
            run_stats.streaks.all_character_count = 0
            for run in runs[1:]:
                if run.modded or run.modifiers:
                    logger.info(f"Found modded or custom run in stats: {run.name}")
                elif run.ascension_level < 20:
                    logger.info(f"Found non-A20 run in stats: {run.name}")

                if start_date is not None and run.timestamp < start_date:
                    continue
                if end_date is not None and run.timestamp > end_date:
                    continue

                run_stats.check_pb(run)
                if run.won:
                    run_stats.add_win(run.character, run.timestamp)
                else:
                    run_stats.add_loss(run.character, run.timestamp)
                
                if run_stats.streaks.ironclad_count is None and run.character == "Ironclad":
                    run_stats.streaks.ironclad_count = run.character_streak.streak
                elif run_stats.streaks.silent_count is None and run.character == "Silent":
                    run_stats.streaks.silent_count = run.character_streak.streak
                elif run_stats.streaks.defect_count is None and run.character == "Defect":
                    run_stats.streaks.defect_count = run.character_streak.streak
                elif run_stats.streaks.watcher_count is None and run.character == "Watcher":
                    run_stats.streaks.watcher_count = run.character_streak.streak

        # set the stats from most recent run's rotating streak and character streak
        last_run = runs[0]
        if start_date is not None and last_run.timestamp < start_date:
            return
        if end_date is not None and last_run.timestamp > end_date:
            return
        if run_stats.last_timestamp != last_run.timestamp and not last_run.modded:
            run_stats.last_timestamp = last_run.timestamp # if this happens to get called multiple times between runs, we want to make sure we don't continually increment
            run_stats.check_pb(last_run)
            if last_run.won:
                run_stats.add_win(last_run.character, last_run.timestamp)
            else:
                run_stats.add_loss(last_run.character, last_run.timestamp)
            run_stats.streaks.all_character_count = last_run.rotating_streak.streak
            match last_run.character:
                case "Ironclad":
                    run_stats.streaks.ironclad_count = last_run.character_streak.streak
                case "Silent":
                    run_stats.streaks.silent_count = last_run.character_streak.streak
                case "Defect":
                    run_stats.streaks.defect_count = last_run.character_streak.streak
                case "Watcher":
                    run_stats.streaks.watcher_count = last_run.character_streak.streak
    else:
        run_stats.streaks.ironclad_count = 0
        run_stats.streaks.silent_count = 0
        run_stats.streaks.defect_count = 0
        run_stats.streaks.watcher_count = 0

def get_all_run_stats():
    return _all_run_stats
