from typing import Optional, Any

import base64
import json

from aiohttp.web import Request, HTTPUnauthorized, HTTPForbidden, HTTPNotImplemented, Response

from typehints import ContextType
from webpage import router

import config

Savefile = dict[str, Any] # this lets us change this later on

current_savefile: Optional[str] = None

@router.post("/sync/save")
async def receive_save(req: Request):
    pw = req.query.get("key")
    if pw is None:
        raise HTTPUnauthorized(reason="No API key provided")
    if not config.secret:
        raise HTTPNotImplemented(reason="No API key present in config")
    if pw != config.secret:
        raise HTTPForbidden(reason="Invalid API key provided")

    post = await req.post()

    file = post.get("savefile")
    content = file.file.read()
    content = content.decode("utf-8", "xmlcharrefreplace")

    global current_savefile # done here just so it passed preliminary checks

    if not content:
        current_savefile = None
        return Response()

    current_savefile = content
    return Response()

async def get_savefile_as_json(ctx: ContextType) -> Savefile:
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
