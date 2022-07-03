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

from gamedata import FileParser, get_character

_cache: dict[str, RunParser] = {}

class RunParser(FileParser):
    def __init__(self, filename: str, data: dict[str, Any]):
        super().__init__(data)
        self.filename = filename
        self.name, _, ext = filename.partition(".")

    @property
    def character(self) -> str:
        return get_character(self)

    @property
    def display_name(self) -> str:
        return f"({self.character} {'victory' if self.won else 'loss'}) {self.timestamp}"

    @property
    def timestamp(self) -> str:
        return datetime.fromtimestamp(self.data["timestamp"]).isoformat(" ")

    @property
    def won(self) -> bool:
        return self.data["victory"]

    @property
    def killed_by(self) -> str | None:
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
    if "view" not in req.query:
        raise HTTPForbidden()
    for x in req.query["view"].split(","):
        arg, _, name = x.partition(":")
        if arg.startswith("_"):
            raise HTTPForbidden()
        totals[arg] = []
        names[arg] = name if name else arg

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

@router.get("/runs/compare")
async def compare_runs(req: Request) -> Response:
    pass

@router.post("/sync/run")
async def receive_run(req: Request) -> Response:
    pass
