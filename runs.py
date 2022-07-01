from __future__ import annotations

from typing import Any

from datetime import datetime

import json
import os

from aiohttp.web import Request, Response, HTTPNotFound

import aiohttp_jinja2

from webpage import router

from gamedata import get_nodes, get_character

_cache: dict[str, RunParser] = {}

class RunParser:
    def __init__(self, filename: str, data: dict[str, Any]):
        self.data = data
        self.filename = filename
        self.name, _, ext = filename.partition(".")

    def __getitem__(self, item: str) -> Any:
        return self.data[item]

    @property
    def display_name(self) -> str:
        try:
            ts = int(self.name)
        except ValueError:
            return self.name
        return f"({get_character(self)} {'victory' if self.won else 'loss'}) {datetime.fromtimestamp(ts).isoformat(' ')}"

    @property
    def won(self) -> bool:
        return self.data["victory"]

    @property
    def killed_by(self) -> str:
        return self.data.get("killed_by")

    @property
    def path(self):
        return get_nodes(self)

    @property
    def relics(self):
        return self.data["relics"]

def _update_cache():
    for file in os.listdir(os.path.join("data", "runs")):
        if file not in _cache:
            with open(os.path.join("data", "runs", file)) as f:
                _cache[file] = RunParser(file, json.load(f))

@router.get("/runs")
@aiohttp_jinja2.template("runs.jinja2")
async def runs_page(req: Request):
    _update_cache()
    return {"runs": reversed(_cache.values())} # return most recent runs at the top

@router.get("/runs/{name}")
@aiohttp_jinja2.template("run_single.jinja2")
async def run_single(req: Request):
    name = req.match_info["name"]
    parser = _cache.get(f"{name}.run") # most common case
    if parser is None:
        _update_cache()
        parser = _cache.get(f"{name}.run") # try again, just in case
        if parser is None: # okay, iterate through everything
            for run_parser in _cache.values():
                if run_parser.name == name:
                    parser = run_parser
                    break

    if parser is None:
        raise HTTPNotFound()

    return {"parser": parser}

@router.post("/sync/run")
async def receive_run(req: Request) -> Response:
    pass
