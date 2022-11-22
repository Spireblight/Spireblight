from cache.cache_helpers import RunStats
from sts_profile import get_profile
from logger import logger

_run_stats = RunStats()

__all__ = ["update_run_stats", "get_run_stats"]

def update_run_stats():
    # we should only have to load this one time this way, after that we can just use the most recent run to update values
    try:
        runs = list(get_profile(0).runs) # BaalorA20 profile
    except:
        runs = []

    if runs:
        if not _run_stats.streaks.is_loaded:
            _run_stats.streaks.all_character_count = 0

            for run in runs[1:]:
                if run.modded or run.modifiers:
                    logger.info(f"Found modded or custom run in stats: {run.name}")
                elif run.ascension_level < 20:
                    logger.info(f"Found non-A20 run in stats: {run.name}")

                _run_stats.check_pb(run)
                if run.timestamp.year != 2022:
                    continue

                if run.won:
                    _run_stats.add_win(run.character)
                else:
                    _run_stats.add_loss(run.character)

                if _run_stats.streaks.is_loaded:
                    continue
                
                if _run_stats.streaks.ironclad_count is None and run.character == "Ironclad":
                    _run_stats.streaks.ironclad_count = run.character_streak.streak
                elif _run_stats.streaks.silent_count is None and run.character == "Silent":
                    _run_stats.streaks.silent_count = run.character_streak.streak
                elif _run_stats.streaks.defect_count is None and run.character == "Defect":
                    _run_stats.streaks.defect_count = run.character_streak.streak
                elif _run_stats.streaks.watcher_count is None and run.character == "Watcher":
                    _run_stats.streaks.watcher_count = run.character_streak.streak

        # set the stats from most recent run's rotating streak and character streak
        last_run = runs[0]
        if _run_stats.last_timestamp != last_run.timestamp and not last_run.modded:
            _run_stats.last_timestamp = last_run.timestamp # if this happens to get called multiple times between runs, we want to make sure we don't continually increment
            _run_stats.check_pb(last_run)
            if last_run.won:
                _run_stats.add_win(last_run.character)
            else:
                _run_stats.add_loss(last_run.character)
            _run_stats.streaks.all_character_count = last_run.rotating_streak.streak
            match last_run.character:
                case "Ironclad":
                    _run_stats.streaks.ironclad_count = last_run.character_streak.streak
                case "Silent":
                    _run_stats.streaks.silent_count = last_run.character_streak.streak
                case "Defect":
                    _run_stats.streaks.defect_count = last_run.character_streak.streak
                case "Watcher":
                    _run_stats.streaks.watcher_count = last_run.character_streak.streak
    else:
        _run_stats.streaks.ironclad_count = 0
        _run_stats.streaks.silent_count = 0
        _run_stats.streaks.defect_count = 0
        _run_stats.streaks.watcher_count = 0

def get_run_stats():
    return _run_stats
