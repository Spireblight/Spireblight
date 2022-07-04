from typing import Any

import base64
import json

from aiohttp.web import Request, HTTPUnauthorized, HTTPForbidden, HTTPNotImplemented, Response

from typehints import ContextType
from gamedata import FileParser
from webpage import router

import config

__all__ = ["get_savefile"]

class Savefile(FileParser):
    def update_data(self, data: dict[str, Any] | None, character: str):
        self.data = data
        self._pathed = False
        if not character:
            self._character = None
            self._cache.clear()
        else:
            self._character = character
            self._cache.pop("path")

    @property
    def prefix(self) -> str:
        return "metric_"

_savefile = Savefile(None)

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
    name = post.get("character")
    name = name.file.read()
    name = name.decode("utf-8", "xmlcharrefreplace")

    j = None
    if content:
        decoded = base64.b64decode(content)
        arr = bytearray()
        for i, char in enumerate(decoded):
            arr.append(char ^ b"key"[i % 3])
        j = json.loads(arr)
        if "basemod:mod_saves" not in j: # make sure this key exists
            j["basemod:mod_saves"] = {}

    _savefile.update_data(j, name)

    return Response()

async def get_savefile(ctx: ContextType) -> Savefile:
    if _savefile.character is None:
        await ctx.send("Not in a run.")
        return

    return _savefile
