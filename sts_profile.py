from __future__ import annotations

import time
import json

from aiohttp.web import Request, Response, HTTPUnauthorized, HTTPNotImplemented, HTTPForbidden, FileField

from nameinternal import get_card
from webpage import router
from logger import logger

import config

__all__ = ["get_profile", "get_current_profile"]

_profiles: dict[int, Profile] = {}
_slots: dict[str, str] = {}

def get_profile(x: int) -> Profile:
    return _profiles[x]

def get_current_profile() -> Profile:
    return _profiles[int(_slots["DEFAULT_PROFILE"])]

class Profile:
    def __init__(self, index: int, data: dict[str, str]):
        self.index = index
        self._prefix = ""
        if index:
            self._prefix = f"{index}_"
        self.data = data

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
        name = get_card(self.data["NOTE_CARD"])
        if (c := self.data["NOTE_UPGRADE"]) != "0":
            if c == "1":
                name += "+"
            else:
                name = f"{name}+{c}"

        return name

@router.post("/sync/profile")
async def sync_profiles(req: Request) -> Response:
    pw = req.query.get("key")
    if pw is None:
        raise HTTPUnauthorized(reason="No API key provided")
    if not config.secret:
        raise HTTPNotImplemented(reason="No API key present in config")
    if pw != config.secret:
        raise HTTPForbidden(reason="Invalid API key provided")

    post = await req.post()

    slots = post.get("slots")
    if isinstance(slots, FileField):
        slots = slots.file.read()
    if isinstance(slots, bytes):
        slots = slots.decode("utf-8", "xmlcharrefreplace")

    _slots.clear()
    _slots.update(json.loads(slots))

    for i in range(3):
        profile = post.get(str(i))
        if isinstance(profile, FileField):
            profile = profile.file.read()
        if isinstance(profile, bytes):
            profile = profile.decode("utf-8", "xmlcharrefreplace")
        if not profile:
            continue # either it doesn't exist, or it hasn't changed
        if i not in _profiles:
            _profiles[i] = Profile(i, profile)
        else:
            _profiles[i].data = profile

    logger.debug(f"Received profiles. Transaction time: {time.time() - float(req.query['start'])}s")

    return Response()
