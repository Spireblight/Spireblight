import datetime
import math
import time
import json
import os

from aiohttp import web, ClientSession

import aiohttp_jinja2
import jinja2

from logger import logger
from utils import getfile

import events

import config

__all__ = ["webpage", "router"]

__version__ = "0.4"
__author__ = "Anilyka Barry"
__github__ = "https://github.com/Vgr255/TwitchCordBot"
__botname__ = "Faelorbot"

webpage = web.Application(logger=logger)

router = web.RouteTableDef()

_query_params = {
    "key": config.API_key,
    "channelId": config.YT_channel_id,
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
env.globals["color"] = config.website_bg

@router.get("/")
@aiohttp_jinja2.template("main.jinja2") # TODO: perform search if it's been more than the timeout, OR it's past 3pm UTC and previous update was before 3pm
async def main_page(req: web.Request, _cache={"video_id": config.default_video_id, "last": 0}):
    if _cache["video_id"] is None or _cache["last"] + config.cache_timeout < time.time():
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
    with getfile("kills", "r") as f:
        kills = [int(x) for x in f.read().split()]
    with getfile("losses", "r") as f:
        losses = [int(x) for x in f.read().split()]
    with getfile("streak", "r") as f:
        rotating_streak, *streak = [int(x) for x in f.read().split()]

    characters = []
    for x, char in enumerate(("Ironclad", "Silent", "Defect", "Watcher")):
        characters.append(ChallengeCharacter(char, kills[x], losses[x], streak[x]))

    left = datetime.date(2022, 12, 31) - datetime.date.today()
    days_left = left.days

    # By checking the percentage of the year we've done, we can calculate what
    # the "assumed" amount of wins for today is, and therefore also if we're
    # ahead or behind.
    total = sum(x.kills for x in characters)
    approximated = math.floor(400 * ((365 - days_left) / 365.0))
    diff = total - approximated
    day_of_year = 365 - days_left

    return {
        "rotating_streak": rotating_streak,
        "characters": characters,
        "total": total,
        "kills_left": 400 - total,
        "diff": {
            "current": diff,
            "approximated": approximated,
            "day_of_year": day_of_year,
            "percent_of_year": int(math.floor(100 * (day_of_year / 365))),
        },
        "days_left": days_left,
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

@router.get("/debug")
@router.post("/debug")
async def debug_testing(req: web.Request):
    content = req.content()
    async for line in content:
        logger.warning(line)

router.static("/static", os.path.join(os.getcwd(), "static"))

@events.add_listener("setup_init")
async def setup_redirects():
    webpage.add_routes(router)
    if not config.spotify_code:
        async with ClientSession() as session:
            async with session.get("https://accounts.spotify.com/authorize", headers={"Content-Type": "application/x-www-form-urlencoded"}, params={
                "client_id": config.spotify_id,
                "response_type": "code",
                "redirect_uri": f"{config.website_url}/debug",
                "state": config.spotify_secret,
            }) as resp:
                print(resp.content)
    elif not config.spotify_token:
        async with ClientSession() as session:
            async with session.post("https://accounts.spotify.com/api/token", params={
                "grant_type": "authorization_code",
                "code": config.spotify_code,
                "redirect_uri": f"{config.website_url}/debug",
            }) as resp:
                print(resp.content)
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
