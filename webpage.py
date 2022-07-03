import datetime
import time
import json
import os

from aiohttp import web, ClientSession

import aiohttp_jinja2
import jinja2

from logger import logger

import config

__all__ = ["webpage", "router", "setup_redirects"]

__version__ = "0.2"
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
async def main_page(req: web.Request, _cache={"video_id": config.default_video_id, "last": 1800000000}): # XXX: DO NOT PUSH THIS
    if _cache["video_id"] is None or _cache["last"] + config.cache_timeout < time.time():
        data = None
        async with ClientSession() as session:
            async with session.get("https://www.googleapis.com/youtube/v3/search", params=_query_params) as resp:
                data = await resp.json()

        if data is not None: # fallback on last/default video ID
            _cache["video_id"] = data["items"][0]["id"]["videoId"]
            _cache["last"] = time.time()

    return _cache

@router.get("/redirects")
async def redirected_totals(req: web.Request):
    with open(os.path.join("data", "redirects.json")) as f:
        j: dict[str, int] = json.load(f)
    lines = []
    for name, count in j.items():
        lines.append(f"{name:>8} :: {count} redirects")
    return web.Response(text="\n".join(lines))

router.static("/icons", os.path.join(os.getcwd(), "icons"))
router.static("/relics", os.path.join(os.getcwd(), "relics"))

def setup_redirects():
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
