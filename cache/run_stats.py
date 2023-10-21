from datetime import datetime
from cache.cache_helpers import RunStats, RunStatsByDate
from sts_profile import get_profile
from logger import logger
from utils import parse_date_range

_all_run_stats = RunStats()
_run_stats_by_date = RunStatsByDate()

__all__ = ["update_all_run_stats", 
           "get_all_run_stats", 
           "get_run_stats_by_date", 
           "get_run_stats_by_date_string"]

def update_all_run_stats():
    _update_run_stats(_all_run_stats)

def update_range(start_date: datetime | None, end_date: datetime | None):
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
        if not _run_stats_by_date.streaks.is_loaded:
            _update_run_stats(_run_stats_by_date, _run_stats_by_date.start_date, _run_stats_by_date.end_date)
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
        if not run_stats.streaks.is_loaded:
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

                if run_stats.streaks.is_loaded:
                    continue
                
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
