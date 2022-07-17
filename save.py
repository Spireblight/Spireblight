from typing import Any

import base64
import json
import time

from aiohttp.web import Request, HTTPUnauthorized, HTTPForbidden, HTTPNotImplemented, HTTPNotFound, HTTPFound, Response, FileField

import aiohttp_jinja2

from typehints import ContextType
from gamedata import FileParser, generate_graph
from webpage import router
from logger import logger
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

    prefix = "metric_"

    def __init__(self):
        if _savefile is not None:
            raise RuntimeError("cannot have multiple concurrent Savefile instances running -- use get_savefile() instead")
        super().__init__(None)
        self._last = time.time()
        self._matches = False

    def update_data(self, data: dict[str, Any] | None, character: str, has_run: str):
        if data is None and has_run == "true" and self.data is not None:
            maybe_run = get_latest_run(None, None)
            if maybe_run["seed_played"] == self["metric_seed_played"]:
                # optimize save -> run node generation
                maybe_run._cache["old_path"] = self._cache["path"]
                self._matches = True

        self.data = data
        self._graph_cache.clear()
        if not character:
            self._last = time.time()
            self._character = None
            self._cache.clear()
        else:
            self._matches = False
            self._character = character
            if "path" in self._cache:
                self._cache["old_path"] = self._cache.pop("path")
            self._cache.pop("relics", None) # because N'loth and Boss relic starter upgrade, we need to regen it everytime

    @property
    def in_game(self) -> bool:
        return self.character is not None

    @property
    def timestamp(self) -> int:
        return self["save_date"]

    @property
    def display_name(self) -> str:
        if self.character is not None:
            return f"Current {self.character} run"
        return "Slay the Spire follow-along"

    @property
    def current_health(self) -> int:
        return self["current_health"]

    @property
    def max_health(self) -> int:
        return self["max_health"]

    @property
    def current_gold(self) -> int:
        return self["gold"]

    @property
    def current_purge(self) -> int:
        return self["purgeCost"]

    @property
    def purge_totals(self) -> int:
        return self["metric_purchased_purges"]

    @property
    def current_floor(self) -> int:
        return self["metric_floor_reached"]

    @property
    def potion_chance(self) -> int:
        return self["potion_chance"] + 40

    @property
    def upcoming_boss(self) -> str:
        return self["boss"]

_savefile = Savefile()

def _truthy(x: str | None) -> bool:
    if x and x.lower() in ("1", "true", "yes"):
        return True
    return False

@router.get("/current")
@aiohttp_jinja2.template("savefile.jinja2")
async def current_run(req: Request):
    redirect = _truthy(req.query.get("redirect"))
    context = {"parser": _savefile, "redirect": redirect}
    if not _savefile.in_game and not redirect:
        if _savefile._matches and time.time() - _savefile._last <= 60:
            latest = get_latest_run(None, None)
            raise HTTPFound(f"/runs/{latest.name}?redirect=true")

    return context

@router.get("/current/raw")
async def current_as_raw(req: Request):
    if _savefile.character is None:
        raise HTTPNotFound()
    return Response(text=json.dumps(_savefile.data, indent=4), content_type="application/json")

@router.get("/current/{type}")
async def save_chart(req: Request) -> Response:
    if _savefile.character is None:
        raise HTTPNotFound()

    return generate_graph(_savefile, req.match_info["type"], req.query, req.query_string)

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

    content = post.get("savefile")
    if isinstance(content, FileField):
        content = content.file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8", "xmlcharrefreplace")

    name = post.get("character")
    if isinstance(name, FileField):
        name = name.file.read()
    if isinstance(name, bytes):
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
    logger.debug("Received savefile. Updated data.")

    return Response()

async def get_savefile(ctx: ContextType | None = None) -> Savefile:
    if _savefile.character is None:
        if ctx is not None:
            await ctx.send("Not in a run.")
        return

    return _savefile
