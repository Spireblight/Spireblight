import datetime
import math
import time
import json
import os

from aiohttp import web, ClientSession
from collections import namedtuple

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

Mastery = namedtuple(
    "MasterySummary",
    ["key", "label", "amount", "total"],
)

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
    from cache.year_run_stats import get_run_stats # TODO: Fix circular imports with router
    run_stats = get_run_stats()
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

@router.get("/mastery")
@aiohttp_jinja2.template("mastery.jinja2")
async def mastery(req: web.Request):
    # TODO(olivia): Faely, I'm sorry for function local imports. You can
    # probably make better sense of it than I can.
    from cache.mastered import get_mastery_counts

    mastered = get_mastery_counts()
    import pprint
    # pprint.pprint(mastered.mastered_relics)

    ret = {
        "amount": sum(x.mastered_count for x in mastered),
        "total": sum(x.total_count for x in mastered),
        "characters": [x for x in mastered if x.character in ("Ironclad", "Silent", "Defect", "Watcher")],
        "categories": [x for x in mastered if x.character in ("Colorless", "Curse", "Relics")],
    }
    pprint.pprint(ret)
    return ret


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
