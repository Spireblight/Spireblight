from __future__ import annotations

from typing import Any, Generator

from datetime import datetime

import json
import io
import os

from aiohttp.web import Request, Response, HTTPNotFound, HTTPForbidden
from matplotlib import pyplot as plt

import aiohttp_jinja2

from webpage import router

from gamedata import NodeData, get_nodes, get_character, get_seed

_cache: dict[str, RunParser] = {}

class RunParser:
    def __init__(self, filename: str, data: dict[str, Any]):
        self.data = data
        self.filename = filename
        self.name, _, ext = filename.partition(".")
        self._cache = {}
        self._pathed = False

    def __getitem__(self, item: str) -> Any:
        return self.data[item]

    @property
    def character(self) -> str:
        return get_character(self)

    @property
    def display_name(self) -> str:
        try:
            ts = int(self.name)
        except ValueError:
            return self.name
        return f"({self.character} {'victory' if self.won else 'loss'}) {datetime.fromtimestamp(ts).isoformat(' ')}"

    @property
    def won(self) -> bool:
        return self.data["victory"]

    @property
    def killed_by(self) -> str:
        return self.data.get("killed_by")

    @property
    def score(self) -> int:
        return int(self.data["score"])

    @property
    def run_length(self) -> str:
        seconds = self.data["playtime"]
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:>02}:{seconds:>02}"
        return f"{minutes:>02}:{seconds:>02}"

    @property
    def seed(self) -> int:
        if "seed" not in self._cache:
            self._cache["seed"] = get_seed(self)
        return self._cache["seed"]

    @property
    def path(self) -> Generator[NodeData, None, None]:
        """Return the run's path. This is cached."""
        if not self._pathed:
            if "path" in self._cache:
                raise RuntimeError("Called RunParser.path while it's generating")
            self._cache["path"] = []
            for node in get_nodes(self):
                self._cache["path"].append(node)
                yield node
            self._pathed = True
            return

        yield from self._cache["path"] # generator so that it's a consistent type

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

@router.get("/runs/{name}/{type}")
async def run_chart(req: Request) -> Response:
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

    totals: dict[str, list[int]] = {}
    names = {}
    ends = []
    floors = []
    for x in req.query["view"].split(","):
        arg, _, name = x.partition(":")
        if arg.startswith("_"):
            raise HTTPForbidden()
        totals[arg] = []
        names[arg] = name

    for node in parser.path:
        floors.append(node.floor)
        if node.end_of_act:
            ends.append(node.floor)
        for name, d in totals.items():
            d.append(getattr(node, name, 0))

    fig, ax = plt.subplots()
    match req.match_info["type"]:
        case "plot":
            func = ax.plot
        case "scatter":
            func = ax.scatter
        case "bar":
            func = ax.bar
        case "stem":
            func = ax.stem
        case x:
            raise HTTPNotFound()

    for num in ends:
        plt.axvline(num, color="black", linestyle="dashed")

    for name, d in totals.items():
        func(floors, d, label=names[name])
    ax.legend()

    plt.xlabel("Floor")
    if "label" in req.query:
        plt.ylabel(req.query["label"])
    plt.xlim(left=0)
    plt.ylim(bottom=0)
    if "title" in req.query:
        plt.suptitle(req.query["title"])

    with io.BytesIO() as file:
        plt.savefig(file, format="png", transparent=True)

        return Response(body=file.getvalue(), content_type="image/png")

@router.post("/sync/run")
async def receive_run(req: Request) -> Response:
    pass
