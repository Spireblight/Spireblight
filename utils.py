from typing import Any
from aiohttp.web import Request, HTTPNotImplemented, HTTPForbidden, HTTPUnauthorized, FileField

import os
import json

from configuration import config

__all__ = ["get_req_data", "getfile", "update_db"]

async def get_req_data(req: Request, *keys: str) -> list[str]:
    pw = req.query.get("key")
    if pw is None:
        raise HTTPUnauthorized(reason="No API key provided")
    if not config.server.secret:
        raise HTTPNotImplemented(reason="No API key present in config")
    if pw != config.server.secret:
        raise HTTPForbidden(reason="Invalid API key provided")

    post = await req.post()

    res = []

    for key in keys:
        value = post.get(key)
        if isinstance(value, FileField):
            value = value.file.read()
        if isinstance(value, bytes):
            value = value.decode("utf-8", "xmlcharrefreplace")
        res.append(value)

    return res

def getfile(x: str, mode: str):
    return open(os.path.join("data", x), mode)

def update_db():
    from server import _cmds
    with getfile("data.json", "w") as f:
        json.dump(_cmds, f, indent=config.server.json_indent)

def convert_class_to_obj(obj: Any):
    return vars(obj)