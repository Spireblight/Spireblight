import datetime
import math
import time
import json
import os

from aiohttp import web, ClientSession

import aiohttp_jinja2
import jinja2

from logger import logger

import events

from configuration import config

__all__ = ["webpage", "router"]

__version__ = "0.5"
__author__ = "Anilyka Barry"
__github__ = "https://github.com/Spireblight/Spireblight"
__botname__ = "Spireblight"

webpage = web.Application(logger=logger)

router = web.RouteTableDef()

_query_params = {
    "key": config.youtube.api_key,
    "channelId": config.youtube.channel_id,
    "type": "video",
    "order": "date",
    "maxResults": "1",
}

_start_time = datetime.datetime.utcnow()

def uptime() -> str:
    delta = (datetime.datetime.utcnow() - _start_time)
    minutes, seconds = divmod(delta.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{delta.days} days, {hours} hours, {minutes} minutes, {seconds} seconds"

def now() -> str:
    return datetime.datetime.utcnow().isoformat(" ", "seconds")

env = aiohttp_jinja2.setup(webpage, loader=jinja2.FileSystemLoader("Templates/"))
env.globals["author"] = __author__
env.globals["github"] = __github__
env.globals["version"] = __version__
env.globals["config"] = config
env.globals["uptime"] = uptime
env.globals["start"] = _start_time.isoformat(" ", "seconds")
env.globals["now"] = now

@router.get("/")
@aiohttp_jinja2.template("main.jinja2") # TODO: perform search if it's been more than the timeout, OR it's past 3pm UTC and previous update was before 3pm
async def main_page(req: web.Request, _cache={"video_id": config.youtube.default_video, "last": 0}):
    if _cache["video_id"] is None or _cache["last"] + config.youtube.cache_timeout < time.time():
        data = None
        async with ClientSession() as session:
            async with session.get("https://www.googleapis.com/youtube/v3/search", params=_query_params) as resp:
                data = await resp.json()

        if data is not None: # fallback on last/default video ID
            # If we don't have a proper setup, there will be an error from the
            # Youtube API. Without this, the start page won't load.
            if "error" not in data:
                _cache["video_id"] = data["items"][0]["id"]["videoId"]
                _cache["last"] = time.time()

    return _cache

class ChallengeCharacter:
    def __init__(self, name: str, kills: int, losses: int, streak: int):
        self.name = name
        self.kills = kills
        self.losses = losses
        self.streak = streak

@router.get("/400")
@aiohttp_jinja2.template("400.jinja2")
async def challenge(req: web.Request):
    from cache.run_stats import get_all_run_stats # TODO: Fix circular imports with router
    run_stats = get_all_run_stats()
    kills = [run_stats.all_wins.ironclad_count, run_stats.all_wins.silent_count, run_stats.all_wins.defect_count, run_stats.all_wins.watcher_count]
    losses = [run_stats.all_losses.ironclad_count, run_stats.all_losses.silent_count, run_stats.all_losses.defect_count, run_stats.all_losses.watcher_count]
    streak = [run_stats.streaks.ironclad_count, run_stats.streaks.silent_count, run_stats.streaks.defect_count, run_stats.streaks.watcher_count]
    characters = []
    for x, char in enumerate(("Ironclad", "Silent", "Defect", "Watcher")):
        characters.append(ChallengeCharacter(char, kills[x], losses[x], streak[x]))

    # By checking the percentage of the year we've done, we can calculate what
    # the "assumed" amount of wins for today is, and therefore also if we're
    # ahead or behind.
    left = datetime.date(2022, 12, 31) - datetime.date.today()
    stream_days_left = math.floor(left.days * 5/7)
    total = run_stats.all_wins.all_character_count
    stream_year = math.floor(365 * 5/7)
    approximated = math.floor(400 * ((stream_year - stream_days_left) / stream_year))
    diff = total - approximated
    day_of_stream_year = stream_year - stream_days_left

    return {
        "rotating_streak": run_stats.streaks.all_character_count,
        "characters": characters,
        "total": total,
        "kills_left": 400 - total,
        "diff": {
            "current": diff,
            "approximated": approximated,
            "day_of_stream_year": day_of_stream_year,
            "percent_of_stream_year": int(math.floor(100 * (day_of_stream_year / stream_year))),
        },
        "stream_days_left": stream_days_left,
    }


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

    # TODO(olivia): I have no good idea how to make this better.  Please help
    # me improve it.  As long as this lives in webpage.py this will cause a
    # circular import if it's in the
    from runs import RunParser

    def __init__(self, winning_streak: bool, ongoing: bool, *runs):
        self.winning_streak = winning_streak
        # TODO(olivia): Perhaps this could be calculated by looking at the
        # status of the latest run?  A lost streak will always have a lost run
        # as its last one.
        self.ongoing = ongoing
        self.runs = runs

    @property
    def start(self):
        return self.runs[0].timestamp.strftime("%b %-d")

    @property
    def end(self):
        return self.runs[-1].timestamp.strftime("%b %-d")

    @property
    def character(self):
        return self.runs[0].character

    @property
    def length(self):
        return len(self.runs)

    @property
    def streak(self):
        """Counts the amount of runs that were actually the streak.

        Without this, the streak would show one too many once it's over."""
        return len([x for x in self.runs if x.won])

@router.get("/streaking")
@aiohttp_jinja2.template("streaking.jinja2")
async def streaking(req: web.Request):
    from runs import get_parser as run

    # TODO(olivia): 👼
    # Dummy data to test the function out with.
    hey_someone_make_a_function_that_returns_this_pls = [
        StreakContainer(True, False,
            run(1699384470),
            run(1699391738),
            run(1699470539),
            run(1699476690),
            run(1699558220),
            run(1699565425),
            run(1699990351),
            run(1699996118),
            run(1700076296),
            run(1700084198),
            run(1700161441),
        ),

        StreakContainer(False, False,
            run(1684439012),
            run(1685041066),
        ),

        StreakContainer(True, False,
            run(1683658810),
            run(1683847240),
            run(1684266057),
            run(1684439012),
            run(1685041066),
            run(1685652492),
            run(1686160250),
            run(1686260704),
        ),
    ]
    return {
        "streaks": hey_someone_make_a_function_that_returns_this_pls,
    }

@router.get("/discord")
@aiohttp_jinja2.template("socials/discord.jinja2")
async def discord(req: web.Request):
    return {}

#@router.get("/redirects")
async def redirected_totals(req: web.Request):
    with open(os.path.join("data", "redirects.json")) as f:
        j: dict[str, int] = json.load(f)
    lines = []
    for name, count in j.items():
        lines.append(f"{name:>8} :: {count} redirects")
    return web.Response(text="\n".join(lines))

@router.post("/eventsub")
@router.post("/callback")
async def eventsub_redirect(req: web.Request):
    raise web.HTTPFound("http://127.0.0.1:4000")

router.static("/static", os.path.join(os.getcwd(), "static"))

@events.add_listener("setup_init")
async def setup_redirects():
    webpage.add_routes(router)
    return # disable redirects for now
    with open(os.path.join("data", "redirects")) as f:
        data = f.readlines()
    for line in data:
        name, url = line.split(maxsplit=1)
        @router.get(f"/{name}")
        async def redirect(req: web.Request, name=name, url=url):
            with open(os.path.join("data", "redirects.json")) as fr:
                j = json.load(fr)
            if name not in j:
                j[name] = 0
            j[name] += 1
            with open(os.path.join("data", "redirects.json"), "w") as fw:
                json.dump(j, fw, indent=config.json_indent)
            raise web.HTTPFound(url)
