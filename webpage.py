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
async def main_page(req: web.Request):
    body = {"video_id": ""}
    data = None
    async with ClientSession() as session:
        async with session.get("https://www.googleapis.com/youtube/v3/search", params=_query_params) as resp:
            data = await resp.json()

    if data is not None: # TODO: fallback for failed API call?
        body["video_id"] = data["items"][0]["id"]["videoId"]

    return body

import sys # TODO: Make this into a proper config module
if "--webonly" not in sys.argv:
    import server
    webpage.on_startup.append(server.Twitch_startup)
    webpage.on_cleanup.append(server.Twitch_cleanup)
