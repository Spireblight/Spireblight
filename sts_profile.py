from __future__ import annotations

from typing import Generator, TYPE_CHECKING

import zipfile
import math
import time
import json
import os
import io

from aiohttp.web import Request, Response, HTTPForbidden, HTTPNotFound
from itertools import islice
from datetime import datetime

import aiohttp_jinja2

from nameinternal import get
from webpage import router
from logger import logger
from events import add_listener
from utils import get_req_data

if TYPE_CHECKING: # circular imports otherwise
    from runs import RunParser

__all__ = ["get_profile", "get_current_profile"]

_profiles: dict[int, Profile] = {}
_slots: dict[str, str] = {}

def get_profile(x: int) -> Profile:
    return _profiles.get(x, None)

def get_current_profile() -> Profile:
    return _profiles[int(_slots["DEFAULT_SLOT"])]

def profile_from_request(req: Request) -> Profile:
    try:
        profile = get_profile(int(req.match_info["profile"]))
        if profile is None:
            raise HTTPNotFound()
    except ValueError:
        raise HTTPForbidden(reason="profile must be integer")
    return profile

class Profile:
    RUNS_PER_PAGE = 50

    def __init__(self, index: int, data: dict[str, str]):
        self.index = index
        self._prefix = ""
        if index:
            self._prefix = f"{index}_"
        self.data = data

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return _slots[f"{self._prefix}PROFILE_NAME"]

    @property
    def completion(self) -> str:
        return "{:.2%}".format(_slots[f"{self._prefix}COMPLETION"])

    @property
    def playtime(self) -> str:
        minutes, seconds = divmod(int(_slots[f"{self._prefix}PLAYTIME"]), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:>2}:{minutes:>02}:{seconds:>02}"

    @property
    def hole_card(self) -> str:
        item = get(self.data["NOTE_CARD"])
        match self.data["NOTE_UPGRADE"]:
            case "0":
                name = item.name
            case "1":
                name = f"{item.name}+"
            case a:
                name = f"{name}+{a}"

        return name

    @property
    def runs(self) -> Generator[RunParser, None, None]:
        """Return all runs from the matching profile, newest first."""
        from runs import _ts_cache
        l = list(_ts_cache)
        l.sort()
        l.reverse()
        for ts in l:
            if _ts_cache[ts]._profile == self.index:
                yield _ts_cache[ts]

    def paged_runs(self, page):
        page -= 1 # UI serves the page number one-indexed, we want zero-indexed
        start = page * self.RUNS_PER_PAGE
        end = start + self.RUNS_PER_PAGE
        print(page, start, end)
        return islice(self.runs, start, end)

    @property
    def pages(self):
        return math.floor(sum(1 for _ in self.runs) / self.RUNS_PER_PAGE) + 1

@router.get("/profile/{profile}/runs")
@router.get("/profile/{profile}/runs/{page}")
@aiohttp_jinja2.template("runs.jinja2")
async def runs_page(req: Request):
    profile = profile_from_request(req)

    from runs import _update_cache
    _update_cache()

    try:
        page = int(req.match_info.get("page", 1))
        if page < 1:
            page = 1
    except:
        page = 1

    return {
        "profile": profile,
        "page": page,
        "pages": profile.pages,
    }

@router.get("/profile/{profile}/runs/by-timestamp/{timestamp}/")
@aiohttp_jinja2.template("runs_timestamp.jinja2")
async def runs_by_timestamp(req: Request):
    profile = profile_from_request(req)
    from runs import _update_cache
    _update_cache()
    try:
        timestamp = req.match_info.get("timestamp", "")
        start, _, end = timestamp.partition("..")
        start = int(start) if start else 0
        end = int(end) if end else time.time()
    except ValueError:
        raise HTTPForbidden(reason="Timestamp must be integers if given.")
    has_runs = False

    runs = []
    for run in profile.runs:
        if start <= run.timestamp.timestamp() <= end:
            runs.append(run)
            has_runs = True

    if not has_runs:
        raise HTTPForbidden(reason="No run file matches the given range.")

    return {
        "profile": profile,
        "runs": runs,
        "back": req.rel_url.query.get('back'),
        "start": datetime.utcfromtimestamp(start),
        "end": datetime.utcfromtimestamp(end),
    }


@router.get("/profile/{profile}/runs/{timestamp}.zip")
@router.get("/profile/{profile}/runs.zip")
async def runs_as_zipfile(req: Request) -> Response:
    profile = profile_from_request(req)
    from runs import _update_cache
    _update_cache()
    try:
        timestamp = req.match_info.get("timestamp", "")
        start, _, end = timestamp.partition("..")
        start = int(start) if start else 0
        end = int(end) if end else time.time()
    except ValueError:
        raise HTTPForbidden(reason="Timestamp must be integers if given.")
    has_file = False

    with io.BytesIO() as zfile:
        with zipfile.ZipFile(zfile, mode="w") as archive:
            for run in profile.runs:
                if start <= run.timestamp.timestamp() <= end:
                    archive.write(f"data/runs/{profile.index}/{run.filename}")
                    has_file = True

        if not has_file:
            raise HTTPForbidden(reason="No run file matches the given range.")
        return Response(body=zfile.getvalue(), content_type="application/zip")

@router.post("/sync/profile")
async def sync_profiles(req: Request) -> Response:
    slots, *profiles = await get_req_data(req, "slots", "0", "1", "2")

    if slots:
        _slots.clear()
        _slots.update(json.loads(slots))
        with open(os.path.join("data", "slots"), "w") as f:
            f.write(slots)

    for i in range(3):
        profile = profiles[i]
        if not profile:
            continue # either it doesn't exist, or it hasn't changed
        with open(os.path.join("data", f"profile_{i}"), "w") as f:
            f.write(profile)
        profile = json.loads(profile)
        if i not in _profiles:
            _profiles[i] = Profile(i, profile)
        else:
            _profiles[i].data = profile

    logger.debug(f"Received profiles. Transaction time: {time.time() - float(req.query['start'])}s")

    return Response()

@add_listener("setup_init")
async def fetch_profiles():
    try:
        with open(os.path.join("data", "slots")) as f:
            _slots.update(json.load(f))
    except OSError:
        pass

    for i in range(3):
        try:
            with open(os.path.join("data", f"profile_{i}")) as f:
                _profiles[i] = Profile(i, json.load(f))
        except OSError:
            continue
