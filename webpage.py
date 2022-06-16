import time

from aiohttp import web, ClientSession

import aiohttp_jinja2
import jinja2

from logger import logger

import config

__all__ = ["webpage", "router"]

webpage = web.Application(logger=logger)

router = web.RouteTableDef()

_query_params = {
    "key": config.API_key,
    "channelId": config.YT_channel_id,
    "type": "video",
    "order": "date",
    "maxResults": "1",
}

aiohttp_jinja2.setup(webpage, loader=jinja2.FileSystemLoader("Templates/"))

@router.get("/")
@aiohttp_jinja2.template("main.html")
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
