from typing import Any

import base64
import json

from aiohttp.web import Request, HTTPUnauthorized, HTTPForbidden, HTTPNotImplemented, Response

from typehints import ContextType
from gamedata import FileParser
from webpage import router
from runs import get_latest_run

import config

__all__ = ["get_savefile", "Savefile"]

_savefile = None

class Savefile(FileParser):
    """Hold data related to the ongoing run.

    API information: This should never be instantiated by custom code. There
    is only ever one savefile in memory, and it can be accessed by get_savefile().

    The 'data' instance attribute may occasionally be None, which means that no
    run is currently ongoing. However, if that were to be the case, then
    get_savefile() will return None instead.

    """

    def __init__(self):
        if _savefile is not None:
            raise RuntimeError("cannot have multiple concurrent Savefile instances running -- use get_savefile() instead")
        super().__init__(None)

    def update_data(self, data: dict[str, Any] | None, character: str, has_run: str):
        if data is None and has_run == "true":
            maybe_run = get_latest_run()
            if maybe_run["seed_played"] == self["metric_seed_played"]:
                # optimize save -> run node generation
                maybe_run._cache["old_path"] = self._cache["path"]

        self.data = data
        self._pathed = False
        if not character:
            self._character = None
            self._cache.clear()
        else:
            self._character = character
            self._cache["old_path"] = self._cache.pop("path")

    @property
    def prefix(self) -> str:
        return "metric_"

_savefile = Savefile()

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

    _savefile.update_data(j, name, req.query["has_run"])

    return Response()

async def get_savefile(ctx: ContextType | None = None) -> Savefile:
    if _savefile.character is None:
        if ctx is not None:
            await ctx.send("Not in a run.")
        return

    return _savefile
