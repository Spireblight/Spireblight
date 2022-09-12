from typing import Any

import datetime
import base64
import json
import time
import math

from aiohttp.web import Request, HTTPNotFound, HTTPFound, Response

import aiohttp_jinja2

from sts_profile import get_current_profile
from typehints import ContextType
from gamedata import FileParser
from webpage import router
from logger import logger
from utils import get_req_data
from runs import get_latest_run

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
        if character.startswith(("1_", "2_")):
            character = character[2:]
        if data is None and has_run == "true" and self._data is not None:
            maybe_run = get_latest_run(None, None)
            if maybe_run._data["seed_played"] == self._data["metric_seed_played"]:
                # optimize save -> run node generation
                maybe_run._cache["old_path"] = self._cache["path"]
                self._matches = True

        self._data = data
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
        date = self._data.get("save_date")
        if date is not None:
            # Since the save date has milliseconds, we need to shave those
            # off. A bit too much precision otherwise
            date = datetime.datetime.utcfromtimestamp(date / 1000)
        else:
            date = datetime.datetime.now()

        return date

    @property
    def timedelta(self) -> datetime.timedelta:
        # TODO(olivia): Do something better
        return datetime.timedelta(hours=0)

    @property
    def display_name(self) -> str:
        if self.character is not None:
            return f"Current {self.character} run"
        return "Slay the Spire follow-along"

    @property
    def profile(self):
        return get_current_profile()

    @property
    def current_health(self) -> int:
        return self._data["current_health"]

    @property
    def max_health(self) -> int:
        return self._data["max_health"]

    @property
    def current_gold(self) -> int:
        return self._data["gold"]

    @property
    def current_purge(self) -> int:
        base = self._data["purgeCost"]
        membership = False
        for relic in self.relics:
            if relic.name == "Smiling Mask":
                return 50
            if relic.name == "Membership Card":
                base = self["purgeCost"] * 0.5
                membership = True
            if relic.name == "The Courier" and not membership:
                base *= 0.8

        return math.ceil(base)

    @property
    def purge_totals(self) -> int:
        return self._data["metric_purchased_purges"]

    @property
    def shop_prices(self) -> tuple[tuple[range, range, range], tuple[range, range], tuple[range, range, range], tuple[range, range, range]]:
        m = 1.0
        if self.ascension_level >= 16:
            m += 0.1
        for relic in self.relics:
            if relic.name == "Membership Card":
                m *= 0.5
            if relic.name == "The Courier":
                m *= 0.8
        cards = [50*m, 75*m, 150*m] # 10% range
        colorless = [90*m, 180*m] # 10%
        relics = [150*m, 250*m, 300*m] # 5%
        potions = [50*m, 75*m, 100*m] # 5%

        return (
            tuple(range(int(x - x*0.10), int(x + x*0.10)) for x in cards),
            tuple(range(int(x - x*0.10), int(x + x*0.10)) for x in colorless),
            tuple(range(int(x - x*0.05), int(x + x*0.05)) for x in relics),
            tuple(range(int(x - x*0.05), int(x + x*0.05)) for x in potions),
        )

    @property
    def current_floor(self) -> int:
        return self._data["metric_floor_reached"]

    @property
    def potion_chance(self) -> int:
        for relic in self.relics:
            if relic.name == "White Beast Statue":
                return 100
            if relic.name == "Sozu":
                return 0
        return self["potion_chance"] + 40

    @property
    def rare_chance(self) -> tuple[float, float, float]:
        base = self._data["card_random_seed_randomizer"]
        regular = 3
        if "Busted Crown" in self._data["relics"]:
            regular -= 2
        if "Question Card" in self._data["relics"]:
            regular += 1
        elites = regular
        if "Prayer Wheel" in self._data["relics"]:
            regular *= 2
        mult = 1
        if "Nloth\u0027s Gift" in self._data["relics"]:
            mult = 3
        # NOTE: This formula is... not very good. I'm not sure that the base is what
        # gets added to the 3% chance, but I'm rolling with it for now. As for that
        # weirdness with 0.006 at the end, it's the base chance for common cards, so
        # I add that to the final likelihood, as it can skew the chance a bit. I
        # *could* calculate it, but that's already more trouble than I care to do.
        # (The base chance is 0.6, but as everything is divided by 100, it's 0.006)
        rew_reg = 1 - ( (1-((3*mult-base)/100)) ** regular ) + 0.006 * (regular-1)
        rew_eli = 1 - ( (1-((10*mult-base)/100)) ** elites ) + 0.006 * (elites-1)
        shops = 1 - ( (1-(9-base)/100) ** 5 )
        return max(rew_reg, 0.0), max(rew_eli, 0.0), max(shops, 0.0)

    def rare_chance_as_str(self) -> tuple[str, str, str]:
        return tuple(f"{x:.2%}" for x in self.rare_chance)

    @property
    def upcoming_boss(self) -> str:
        return self._data["boss"]

_savefile = Savefile()

def _truthy(x: str | None) -> bool:
    if x and x.lower() in ("1", "true", "yes"):
        return True
    return False

@router.get("/current")
@aiohttp_jinja2.template("run_single.jinja2")
async def current_run(req: Request):
    redirect = _truthy(req.query.get("redirect"))
    context = {
        "run": _savefile,
        "autorefresh": True,
        "redirect": redirect
    }
    if not _savefile.in_game and not redirect:
        if _savefile._matches and time.time() - _savefile._last <= 60:
            latest = get_latest_run(None, None)
            raise HTTPFound(f"/runs/{latest.name}?redirect=true")

    return context

@router.get("/current/raw")
async def current_as_raw(req: Request):
    if _savefile.character is None:
        raise HTTPNotFound()
    return Response(text=json.dumps(_savefile._data, indent=4), content_type="application/json")

@router.get("/current/{type}")
async def save_chart(req: Request) -> Response:
    if _savefile.character is None:
        raise HTTPNotFound()

    return _savefile.graph(req)

@router.post("/sync/save")
async def receive_save(req: Request):
    content, name = await get_req_data(req, "savefile", "character")

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
    logger.debug(f"Updated data. Final transaction time: {time.time() - float(req.query['start'])}s")

    return Response()

async def get_savefile(ctx: ContextType | None = None) -> Savefile:
    if _savefile.character is None:
        if ctx is not None:
            await ctx.send("Not in a run.")
        return

    return _savefile
