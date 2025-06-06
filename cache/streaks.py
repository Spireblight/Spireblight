from __future__ import annotations

from datetime import datetime, UTC
from typing import TYPE_CHECKING
from logger import logger

from cache.cache_helpers import StreakCache, StreakContainer
from sts_profile import get_profile


# TODO(olivia): Hard-coded to be the start of the Grandmastery challenge.  Move
# to config file?
_streak_collections = StreakCache(datetime(2023, 10, 24, tzinfo=UTC))

def update_streak_collections():
    # First we grab all the runs from the BaalorA20 profile.
    profile = get_profile(0)
    if profile is None or not profile.runs:
        logger.info(f"No runs found to group into streak")
        return
    all_runs = list(profile.runs)
    all_runs.reverse()


    # We build a list of all runs that have happened the cutoff date, sorted with the earliest runs
    # first in the list
    runs = [x for x in all_runs if x.timestamp > _streak_collections.since]

    logger.info(f"Grouping streaks of %s runs", len(runs))

    from pprint import pprint
    groups = []
    seen = []
    # Here, we make groups of runs based on if they are in a streak
    for x, run in enumerate(runs):
        # If we've already processed the run in a previous chain, we can skip it since it's already
        # in a group.
        if run.name in seen:
            continue

        group = []
        if run.won:
            # If this run won, start looking at the next run and see if it won as well.  If it did,
            # add it to the group and recursively do the same again.
            cur = run
            while cur and cur.won:
                seen.append(cur.name)
                group.append(cur)
                cur = cur.matched.next_char
            groups.append(group)
        else:
            # Same as above, but for runs that have lost
            cur = run
            while cur and not cur.won:
                seen.append(cur.name)
                group.append(cur)
                cur = cur.matched.next_char
            groups.append(group)

    # Now that we have the groups, let's put them into containers according to our logic:
    # - We only count a winning streak after it hits three or more wins in a row
    # - We group all runs inbetween together as non-interesting.
    _streak_collections.clear()
    _streak_collections.prepend(StreakContainer(False, []))

    for group in groups:
        run = group[0]
        if len(group) < 3 or not run.won:
            # We have a group we don't care for.  Let's check if the last
            # streak container is for losses or not.
            if _streak_collections.latest.winning_streak:
                # It's for wins, so we need to make a new one that contains
                # losses instead.
                _streak_collections.prepend(StreakContainer(False, group))
            else:
                # Otherwise, let's add the current group of runs to the current
                # streak of losses.
                _streak_collections.latest.append(group)

        else:
            # We have a winning streak! Yay!  Since it's a start of a new
            # streak, we know that the prevoius group was not a streak, so we
            # need to make a new one that contains wins instead.
            _streak_collections.prepend(StreakContainer(True, group))

    # Mark the latest streak as the ongoing one.  The UI wants to know this for
    # display purposes.
    _streak_collections.latest.ongoing = True
