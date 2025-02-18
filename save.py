from typing import Any

import datetime
import base64
import json
import time
import math
import os

from aiohttp.web import Request, HTTPNotFound, HTTPFound, Response

import aiohttp_jinja2

from response_objects.run_single import RunResponse
from nameinternal import get, get_card, Relic, Potion
from sts_profile import get_current_profile
from gamedata import FileParser, BottleRelic, KeysObtained
from webpage import router
from logger import logger
from events import invoke
from utils import convert_class_to_obj, get_req_data
from runs import get_latest_run, StreakInfo
from activemods import ActiveMods, ActiveMod, ACTIVEMODS_KEY

import score as _s

from configuration import config

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
        data = None
        try:
            with open(os.path.join("data", "spire-save.json"), "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            pass
        super().__init__(data)
        self._last = time.time()
        self._matches = False
        self._activemods = None
        

    def update_data(self, data: dict[str, Any] | None, character: str, has_run: str):
        if character.startswith(("1_", "2_")):
            character = character[2:]
        if data is None and has_run == "true" and self._data is not None:
            maybe_run = get_latest_run(None, None)
            if maybe_run is not None and "path" in self._cache and maybe_run._data["seed_played"] == self._data["metric_seed_played"]:
                # optimize save -> run node generation
                maybe_run._cache["old_path"] = self._cache["path"]
                self._matches = True

        self._data = data
        self._graph_cache.clear()
        if not character:
            self._last = time.time()
            self._character = None
            self._cache.clear()
            self._cache["self"] = self
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
    def act(self) -> int:
        return self._data["act_num"]

    @property
    def timestamp(self) -> datetime.datetime:
        """Return the save time for the run, as UTC."""
        date = self._data.get("save_date")
        if date is not None:
            # Since the save date has milliseconds, we need to shave those
            # off. A bit too much precision otherwise
            date = datetime.datetime.utcfromtimestamp(date / 1000)
        else:
            date = datetime.datetime.utcnow()

        return date

    @property
    def timedelta(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.playtime)

    @property
    def display_name(self) -> str:
        if self.character is not None:
            return f"Current {self.character} run"
        return "Slay the Spire follow-along"

    @property
    def keys(self) -> KeysObtained:
        keys = KeysObtained()
        if self._data["has_ruby_key"]:
            for choice in self._data["metric_campfire_choices"]:
                if choice["key"] == "RECALL":
                    keys.ruby_key_obtained = True
                    keys.ruby_key_floor = int(choice["floor"])
        if self._data["has_emerald_key"]:
            keys.emerald_key_obtained = True
            floor = self._data["basemod:mod_saves"].get("greenKeyTakenLog")
            if floor:
                keys.emerald_key_floor = int(floor)
        if self._data["has_sapphire_key"]:
            keys.sapphire_key_obtained = True
            floor = self._data["basemod:mod_saves"].get("BlueKeyRelicSkippedLog")
            if floor:
                keys.sapphire_key_floor = int(floor["floor"])

        return keys

    @property
    def _master_deck(self) -> list[str]:
        ret = []
        for x in self._data["cards"]:
            if x["upgrades"]:
                ret.append(f"{x['id']}+{x['upgrades']}")
            else:
                ret.append(x["id"])

        return ret

    def get_meta_scaling_cards(self) -> list[tuple[str, int]]:
        ret = []
        for x in self._data["cards"]:
            if x["misc"]:
                card = x["id"]
                if x["upgrades"]:
                    card = f"{x['id']}+{x['upgrades']}"
                ret.append((card, x["misc"]))

        return ret

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
                base = self._data["purgeCost"] * 0.5
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

    def _potion_handling(self, key: str) -> list[list[Potion]]:
        final = [[]] # empty list for Neow
        # this needs RHP, so it might not be present
        # but we want a list anyway, which is why we iterate like this
        for i in range(self.current_floor):
            potions = []
            try:
                for x in self._data["basemod:mod_saves"][key][i]:
                    potions.append(get(x))
            except (KeyError, IndexError):
                # Either we don't have RHP, or the floor isn't stored somehow
                pass

            final.append(potions)

        return final

    @property
    def potions_use(self) -> list[list[Potion]]:
        return self._potion_handling("PotionUseLog")

    @property
    def potions_alchemize(self) -> list[list[Potion]]:
        return self._potion_handling("potionsObtainedAlchemizeLog")

    @property
    def potions_entropic(self) -> list[list[Potion]]:
        return self._potion_handling("potionsObtainedEntropicBrewLog")

    @property
    def potions_discarded(self) -> list[list[Potion]]:
        return self._potion_handling("PotionDiscardLog")

    @property
    def potion_chance(self) -> int:
        for relic in self.relics:
            if relic.name == "White Beast Statue":
                return 100
            if relic.name == "Sozu":
                return 0
        return self._data["potion_chance"] + 40

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
    def _available_rare_relics(self) -> list[str]:
        floor = self.current_floor
        ret = []
        for relic in self._data["rare_relics"]:
            match relic:
                case "WingedGreaves":
                    if floor > 40:
                        continue
                case "Old Coin" | "Prayer Wheel":
                    if floor >= 48:
                        continue
                case "Peace Pipe" | "Girya" | "Shovel":
                    if floor > 48 or ((
                            "Peace Pipe" in self._data["relics"],
                            "Shovel" in self._data["relics"],
                            "Girya" in self._data["relics"],
                            ).count(True) > 1):
                        continue
            ret.append(relic)
        return ret

    def available_relic(self, relic: Relic) -> bool:
        """Return True if the relic can be acquired still this run."""
        if relic.tier in ("Common", "Uncommon", "Shop"):
            return relic.internal in self._data[f"{relic.tier.lower()}_relics"]
        if relic.tier != "Rare": # just in case
            raise ValueError("Relic rarity can only be Common, Uncommon, Rare, or Shop.")

        return relic.internal in self._available_rare_relics

    @property
    def upcoming_boss(self) -> str:
        return self._data["boss"]

    @property
    def bottles(self) -> list[BottleRelic]:
        bottles = []
        if self._data.get("bottled_flame"):
            bottles.append(BottleRelic("Bottled Flame", get_card(f"{self._data['bottled_flame']}+{self._data['bottled_flame_upgrade']}")))
        if self._data.get("bottled_lightning"):
            bottles.append(BottleRelic("Bottled Lightning", get_card(f"{self._data['bottled_lightning']}+{self._data['bottled_lightning_upgrade']}")))
        if self._data.get("bottled_tornado"):
            bottles.append(BottleRelic("Bottled Tornado", get_card(f"{self._data['bottled_tornado']}+{self._data['bottled_tornado_upgrade']}")))
        return bottles

    @property
    def rotating_streak(self) -> StreakInfo:
        last = get_latest_run(None, None)
        if last is not None:
            return last.rotating_streak
        return StreakInfo(0, 0, True)

    @property
    def character_streak(self) -> StreakInfo:
        try:
            return get_latest_run(self.character, None).character_streak
        except AttributeError: # no character played like this; likely a mod
            return StreakInfo(0, 0, True)

    @property
    def score(self) -> int:
        return sum(bonus.score_bonus for bonus in self._get_score_bonuses())

    @property
    def score_breakdown(self) -> list[str]:
        return [bonus.full_display for bonus in self._get_score_bonuses() 
                        if bonus.should_show or bonus.score_bonus != 0]

    def _get_score_bonuses(self) -> list[_s.Score]:
        score_bonuses: list[_s.Score] = []
        score_bonuses.append(_s.get_floors_climbed_bonus(self))
        score_bonuses.append(_s.get_enemies_killed_bonus(self))
        score_bonuses.append(_s.get_act1_elites_killed_bonus(self))
        score_bonuses.append(_s.get_act2_elites_killed_bonus(self))
        score_bonuses.append(_s.get_act3_elites_killed_bonus(self))
        score_bonuses.append(_s.get_champions_bonus(self))
        score_bonuses.append(_s.get_bosses_slain_bonus(self))
        score_bonuses.append(_s.get_perfect_bosses_bonus(self))
        score_bonuses.append(_s.get_overkill_bonus(self))
        score_bonuses.append(_s.get_combo_bonus(self))
        score_bonuses.append(_s.get_ascension_score_bonus(self))
        score_bonuses.append(_s.get_collector_bonus(self))
        score_bonuses.append(_s.get_deck_bonus(self))
        score_bonuses.append(_s.get_mystery_machine_bonus(self))
        score_bonuses.append(_s.get_shiny_bonus(self))
        score_bonuses.append(_s.get_max_hp_bonus(self))
        score_bonuses.append(_s.get_gold_bonus(self))
        score_bonuses.append(_s.get_curses_bonus(self))
        score_bonuses.append(_s.get_poopy_bonus(self))
        return score_bonuses

    @property
    def monsters_killed(self) -> int:
        return self._data.get("monsters_killed", 0)

    @property
    def act1_elites_killed(self) -> int:
        return self._data.get("elites1_killed", 0)

    @property
    def act2_elites_killed(self) -> int:
        return self._data.get("elites2_killed", 0)

    @property
    def act3_elites_killed(self) -> int:
        return self._data.get("elites3_killed", 0)

    @property
    def perfect_elites(self) -> int:
        return self._data.get("champions", 0)

    @property
    def perfect_bosses(self) -> int:
        return self._data.get("perfect", 0)

    @property
    def has_overkill(self) -> bool:
        return self._data.get("overkill", False)

    @property
    def mystery_machine_counter(self) -> int:
        return self._data.get("mystery_machine", 0)

    @property
    def total_gold_gained(self) -> int:
        return self._data.get("gold_gained", 0)

    @property
    def has_combo(self) -> bool:
        return self._data.get("combo", False)

    @property
    def act_num(self) -> int:
        return self._data["act_num"]

    @property
    def deck_card_ids(self) -> list[str]:
        return [card["id"] for card in self._data["cards"]]

    @property
    def has_activemods(self) -> bool:
        return ACTIVEMODS_KEY in self._data
    
    @property
    def activemods(self) -> ActiveMods:
        if self._activemods is None:
            self._activemods = ActiveMods(self._data)

        return self._activemods

    def find_mod(self, mod_name: str) -> ActiveMod | None:
        return self.activemods.find_mod(mod_name)
    
    @property
    def mods(self) -> list[ActiveMod]:
        return self.activemods.all_mods

_savefile = Savefile()

def _truthy(x: str | None) -> bool:
    if x and x.lower() in ("1", "true", "yes"):
        return True
    return False

@router.get("/current")
@aiohttp_jinja2.template("run_single.jinja2")
async def current_run(req: Request):
    redirect = _truthy(req.query.get("redirect"))
    context = RunResponse(_savefile, autorefresh=True, redirect=redirect)
    if not _savefile.in_game and not redirect:
        if _savefile._matches and time.time() - _savefile._last <= 60:
            latest = get_latest_run(None, None)
            if latest is not None:
                raise HTTPFound(f"/runs/{latest.name}?redirect=true")

    return convert_class_to_obj(context)

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

    in_run = _savefile.in_game
    _savefile.update_data(j, name, req.query["has_run"])
    if in_run and not _savefile.in_game:
        run = get_latest_run(None, None)
        await invoke("run_end", run)
    with open(os.path.join("data", "spire-save.json"), "w") as f:
        if j:
            json.dump(j, f, indent=config.server.json_indent)
        else:
            f.write("{}")
    logger.debug(f"Updated data. Final transaction time: {time.time() - float(req.query['start'])}s")

    return Response()

async def get_savefile() -> Savefile:
    return _savefile
