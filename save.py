from typing import Optional, Any

import base64
import json

from twitchio.ext.commands import Context
from aiohttp.web import Request, HTTPUnauthorized, HTTPBadRequest

from logger import logger
from webpage import router

import config

Savefile = dict[str, Any] # this lets us change this later on

current_savefile: Optional[str] = None

@router.post("/sync/save")
async def receive_save(req: Request):
    pw = req.query.get("key")
    if pw is None:
        raise HTTPUnauthorized(reason="No API key provided")

    if pw != config.secret:
        raise HTTPBadRequest(reason="Invalid API key provided")

    post = await req.post()

    file = post.get("savefile")
    # TODO

async def get_savefile_as_json(ctx: Context) -> Savefile:
    if current_savefile is None:
        await ctx.send("Not in a run.")
        return

    decoded = base64.b64decode(current_savefile)
    arr = bytearray()
    for i, char in enumerate(decoded):
        arr.append(char ^ b"key"[i % 3])
    j = json.loads(arr)
    if "basemod:mod_saves" not in j: # make sure this key exists
        j["basemod:mod_saves"] = {}
    return j
