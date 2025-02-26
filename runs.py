from __future__ import annotations

from typing import Any, NamedTuple

import datetime
import json
import time
import os

from aiohttp.web import Request, Response, HTTPNotFound, HTTPForbidden, HTTPNotImplemented

import aiohttp_jinja2

from response_objects.run_single import RunResponse
from response_objects.profiles import ProfilesResponse
from cache.run_stats import update_all_run_stats
from cache.cache_helpers import RunLinkedListNode
from cache.mastered import update_mastery_stats
from cache.streaks import update_streak_collections
from nameinternal import get, Potion
from sts_profile import get_profile
from gamedata import FileParser, KeysObtained
from webpage import router
from logger import logger
from events import add_listener
from utils import convert_class_to_obj, get_req_data
from activemods import ActiveMods, ActiveMod, ACTIVEMODS_KEY

__all__ = ["get_latest_run"]

_cache: dict[str, RunParser] = {}
_ts_cache: dict[int, RunParser] = {}

def get_latest_run(character: str | None, victory: bool | None) -> RunParser:
    _update_cache()
    if not _ts_cache:
        return None
    latest = _ts_cache[max(_ts_cache)]
    is_character_specific = False
    if character is not None:
        is_character_specific = True
        while latest.character != character:
            latest = latest.matched.prev

    if victory is not None:
        if victory:
            while not latest.won:
                latest = latest.matched.get_run(is_prev=True, is_character_specific=is_character_specific)
        else:
            while latest.won:
                latest = latest.matched.get_run(is_prev=True, is_character_specific=is_character_specific)

    return latest

class RunParser(FileParser):
    done = True
    def __init__(self, filename: str, profile: int, data: dict[str, Any]):
        if filename in _cache:
            raise RuntimeError(f"Created duplicate run parser with name {filename}")
        super().__init__(data)
        self.filename = filename
        self.name, _, ext = filename.partition(".")
        self.matched = RunLinkedListNode()
        self._character = data["character_chosen"]
        self._profile = profile
        self._character_streak = None
        self._rotating_streak = None
        self._activemods = None

    def __repr__(self):
        return f"Run<{self.display_name}>"

    @property
    def display_name(self) -> str:
        return f"({self.character} {self.verb}) {self.timestamp}"

    @property
    def profile(self):
        return get_profile(self._profile)

    @property
    def timestamp(self) -> datetime.datetime:
        return datetime.datetime.utcfromtimestamp(self._data["timestamp"])

    @property
    def timedelta(self) -> datetime.timedelta:
        return datetime.datetime.now() - self.timestamp

    @property
    def keys(self) -> KeysObtained:
        keys = KeysObtained()
        for choice in self._data["campfire_choices"]:
            if choice["key"] == "RECALL":
                keys.ruby_key_obtained = True
                keys.ruby_key_floor = int(choice["floor"])
        if "green_key_taken_log" in self._data:
            keys.emerald_key_obtained = True
            keys.emerald_key_floor = int(self._data["green_key_taken_log"])
        if "blue_key_relic_skipped_log" in self._data:
            keys.sapphire_key_obtained = True
            keys.sapphire_key_floor = int(self._data["blue_key_relic_skipped_log"]["floor"])

        return keys

    @property
    def _master_deck(self) -> list[str]:
        return list(self._data["master_deck"])

    @property
    def won(self) -> bool:
        return self._data["victory"]

    @property
    def verb(self) -> str:
        return "victory" if self.won else "loss"

    @property
    def killed_by(self) -> str | None:
        return self._data.get("killed_by")

    @property
    def floor_reached(self) -> int:
        return int(self._data["floor_reached"])

    @property
    def acts_beaten(self) -> int:
        """Return how many acts were beaten."""
        return self._data["path_per_floor"].count(None) # None is a boss chest, act 4 transition, AND final screen

    @property
    def final_health(self) -> tuple[int, int]:
        return self._data["current_hp_per_floor"][-1], self._data["max_hp_per_floor"][-1]

    def _potion_handling(self, key: str) -> list[list[Potion]]:
        final = [[]] # empty list for Neow
        # this needs RHP, so it might not be present
        # but we want a list anyway, which is why we iterate like this
        for i in range(self.floor_reached):
            potions = []
            try:
                for x in self._data[key][i]:
                    potions.append(get(x))
            except (KeyError, IndexError):
                # Either we don't have RHP, or the floor isn't stored somehow
                pass

            final.append(potions)

        return final

    @property
    def potions_use(self) -> list[list[Potion]]:
        return self._potion_handling("potion_use_per_floor")

    @property
    def potions_alchemize(self) -> list[list[Potion]]:
        return self._potion_handling("potions_obtained_alchemize")

    @property
    def potions_entropic(self) -> list[list[Potion]]:
        return self._potion_handling("potions_obtained_entropic_brew")

    @property
    def potions_discarded(self) -> list[list[Potion]]:
        return self._potion_handling("potion_discard_per_floor")

    @property
    def score(self) -> int:
        return int(self._data["score"])

    @property
    def score_breakdown(self) -> list[str]:
        return self._data.get("score_breakdown", [])

    @property
    def run_length(self) -> str:
        seconds = self._data["playtime"]
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:>02}:{seconds:>02}"
        return f"{minutes:>02}:{seconds:>02}"

    @property
    def character_streak(self) -> StreakInfo:
        """Get the run position in the character streak."""
        streak = self._character_streak
        if streak is None:
            streak = self._get_streak(is_character_streak=True)
            if not streak.is_ongoing:
                self._character_streak = streak
        return streak

    @property
    def rotating_streak(self) -> StreakInfo:
        """Get the run position in the rotating streak."""
        streak = self._rotating_streak
        if streak is None:
            streak = self._get_streak(is_character_streak=False)
            if not streak.is_ongoing:
                self._rotating_streak = streak
        return streak

    def _get_streak(self, *, is_character_streak: bool) -> StreakInfo:
        if self.won:
            streak_total = 1
            position_in_streak = 1
            is_ongoing = True

            def loop_cached_runs(*, is_prev: bool):
                nonlocal streak_total, position_in_streak, is_ongoing
                current_run: RunParser = self.matched.get_run(is_prev=is_prev, is_character_specific=is_character_streak)
                if current_run is not None:
                    last_char = self.character
                    while current_run.won:
                        # If rotating, only iterate if not same char
                        if is_character_streak or current_run.character != last_char:
                            streak_total += 1
                            # only iterate the position if the Win came before the current run
                            if is_prev:
                                position_in_streak += 1

                        if (run := current_run.matched.get_run(is_prev=is_prev, is_character_specific=is_character_streak)) is not None:
                            last_char = current_run.character
                            current_run = run
                        else:
                            break
                    does_upcoming_loss_exist = not is_prev and not current_run.won
                    if does_upcoming_loss_exist:
                        is_ongoing = False
            loop_cached_runs(is_prev=True)
            loop_cached_runs(is_prev=False)
            return StreakInfo(streak_total, position_in_streak, is_ongoing)
        return StreakInfo(0, 0, False)

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

class StreakInfo(NamedTuple):
    streak: int
    position: int
    is_ongoing: bool

@add_listener("setup_init")
async def _setup_cache():
    for i in range(3):
        os.makedirs(os.path.join("data", "runs", str(i)), exist_ok=True)
    _update_cache()

def _update_cache():
    start = time.time()
    for path, folders, files in os.walk(os.path.join("data", "runs")):
        for folder in folders:
            profile = int(folder)
            _cur_cache: dict[int, RunParser] = {}
            for p1, d1, f1 in os.walk(os.path.join(path, folder)):
                for file in f1:
                    if file in _cache:
                        parser = _cache[file]
                    else:
                        with open(os.path.join(p1, file)) as f:
                            _cache[file] = parser = RunParser(file, profile, json.load(f))
                            _ts_cache[parser._data["timestamp"]] = parser
                    _cur_cache[parser._data["timestamp"]] = parser

            prev = None
            prev_char: dict[str, RunParser | None] = {}
            prev_win = None
            prev_loss = None

            for t in sorted(_cur_cache):
                cur = _cur_cache[t]
                if prev is not None:
                    if cur.matched.prev is None:
                        prev.matched.next = cur
                        cur.matched.prev = prev
                    if cur.character not in prev_char:
                        prev_char[cur.character] = None
                    if cur.matched.prev_char is None and (c := prev_char[cur.character]) is not None:
                        c.matched.next_char = cur
                        cur.matched.prev_char = c
                    prev_char[cur.character] = cur
                    if cur.won:
                        if cur.matched.prev_win is None and prev_win is not None:
                            prev_win.matched.next_win = cur
                            cur.matched.prev_win = prev_win
                        prev_win = cur
                    else:
                        if cur.matched.prev_loss is None and prev_loss is not None:
                            prev_loss.matched.next_loss = cur
                            cur.matched.prev_loss = prev_loss
                        prev_loss = cur
                prev = cur

    update_all_run_stats()
    update_mastery_stats()
    update_streak_collections()

    # I don't actually know how long this cache updating is going to take...
    # I think it's as optimized as I could make it while still being safe,
    # but it's possible it still takes some time. I'm not going to focus on
    # that for now, but logging the update time everytime, in case it turns
    # out to be a bottleneck. We only want to actually update new runs.
    logger.info(f"Updated run parser cache in {time.time() - start}s")

@router.get("/runs")
@aiohttp_jinja2.template("runs_profile.jinja2")
async def pick_profile(req: Request):
    profiles = []
    for i in range(3):
        profile = get_profile(i)
        if profile is not None:
            profiles.append(profile)

    if not profiles:
        raise HTTPNotImplemented(reason="No run files were found")

    return convert_class_to_obj(ProfilesResponse(profiles))

def get_parser(name) -> RunParser | None:
    parser = _cache.get(f"{name}.run") # most common case
    if parser is None:
        _update_cache()
        parser = _cache.get(f"{name}.run") # try again, just in case
        if parser is None: # okay, iterate through everything
            for run_parser in _cache.values():
                if run_parser.name == name:
                    parser = run_parser
                    break

    return parser

def _truthy(x: str | None) -> bool:
    if x and x.lower() in ("1", "true", "yes"):
        return True
    return False

def _falsey(x: str | None) -> bool:
    if x and x.lower() in ("0", "false", "no"):
        return False
    return True

@router.get("/runs/{name}")
@aiohttp_jinja2.template("run_single.jinja2")
async def run_single(req: Request):
    parser = get_parser(req.match_info["name"])
    if parser is None:
        raise HTTPNotFound()
    redirect = _truthy(req.query.get("redirect"))

    response = RunResponse(parser, parser.matched, autorefresh=False, redirect=redirect)
    return convert_class_to_obj(response)

@router.get("/runs/{name}/raw")
async def run_raw_json(req: Request) -> Response:
    parser = get_parser(req.match_info["name"])
    if parser is None:
        raise HTTPNotFound()

    return Response(text=json.dumps(parser._data, indent=4), content_type="application/json")

@router.get("/runs/{name}/{type}")
async def run_chart(req: Request) -> Response:
    parser = get_parser(req.match_info["name"])
    if parser is None:
        raise HTTPNotFound()

    return parser.graph(req)

#@router.get("/compare/view")
@aiohttp_jinja2.template("compare_single.jinja2")
async def compare_runs(req: Request):
    context = {}
    try:
        start = int(req.query.get("start", 0))
        end = int(req.query.get("end", time.time()))
        score = int(req.query.get("score", 0))
    except ValueError:
        raise HTTPForbidden(reason="'start', 'end', 'score' params must be integers if present")

    chars = req.query.getall("character", [])
    victory = _truthy(req.query.get("victory"))
    loss = _falsey(req.query.get("loss"))
    relics = req.query.getall("relic", [])
    cards = req.query.getall("card", [])

    return context

@router.post("/sync/run")
async def receive_run(req: Request) -> Response:
    content, name, profile = await get_req_data(req, "run", "name", "profile")

    with open(os.path.join("data", "runs", profile, name), "w") as f:
        f.write(content)
    data = json.loads(content)
    if name not in _cache:
        _cache[name] = parser = RunParser(name, int(profile), data)
        _ts_cache[parser._data["timestamp"]] = parser
        _update_cache()

    logger.debug(f"Received run history file. Updated data. Transaction time: {time.time() - float(req.query['start'])}s")

    return Response()
