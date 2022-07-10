from __future__ import annotations

from typing import Any

from datetime import datetime

import json
import time
import io
import os

from aiohttp.web import Request, Response, HTTPNotFound, HTTPForbidden, HTTPUnauthorized, HTTPNotImplemented, FileField
from matplotlib import pyplot as plt

import aiohttp_jinja2
import mpld3

from nameinternal import get_all_relics, get_all_cards
from gamedata import FileParser
from webpage import router

import config

__all__ = ["get_latest_run"]

_cache: dict[str, RunParser] = {}
_ts_cache: dict[int, RunParser] = {}

_variables_map = {
    "current_hp": "Current HP",
    "max_hp": "Max HP",
    "gold": "Gold",
    "floor_time": "Time spent in the floor (seconds)",
    "card_count": "Number of cards in the deck",
    "relic_count": "Number of relics",
    "potion_count": "Number of potions",
}

def get_latest_run():
    _update_cache()
    latest = max(_ts_cache)
    return _ts_cache[latest]

class RunParser(FileParser):
    def __init__(self, filename: str, data: dict[str, Any]):
        if filename in _cache:
            raise RuntimeError(f"Created duplicate run parser with name {filename}")
        super().__init__(data)
        self.filename = filename
        self.name, _, ext = filename.partition(".")
        self._character = data["character_chosen"]

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
                _cache[file] = parser = RunParser(file, json.load(f))
                _ts_cache[parser.timestamp] = parser

@router.get("/runs")
@aiohttp_jinja2.template("runs.jinja2")
async def runs_page(req: Request):
    _update_cache()
    return {"runs": reversed(_cache.values())} # return most recent runs at the top

def _get_parser(name) -> RunParser | None:
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
    parser = _get_parser(req.match_info["name"])
    if parser is None:
        raise HTTPNotFound()
    embed = _falsey(req.query.get("embed"))
    return {"parser": parser, "embed": embed}

@router.get("/runs/{name}/{type}")
async def run_chart(req: Request) -> Response:
    parser = _get_parser(req.match_info["name"])
    if parser is None:
        raise HTTPNotFound()

    totals: dict[str, list[int]] = {}
    ends = []
    floors = []
    if "view" not in req.query or "type" not in req.query:
        raise HTTPForbidden()
    if req.query["type"] not in ("image", "embed"):
        raise HTTPNotImplemented(reason=f"Display type {req.query['type']} is undefined")
    for arg in req.query["view"].split(","):
        if arg.startswith("_"):
            raise HTTPForbidden()
        totals[arg] = []

    for name, d in totals.items():
        val = getattr(parser.neow_bonus, name)
        if val is not None:
            if not floors:
                floors.append(0)
            d.append(val)

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
        case _:
            raise HTTPNotFound()

    # this doesn't work well with embedding
    if req.query["type"] != "embed":
        for num in ends:
            plt.axvline(num, color="black", linestyle="dashed")

    for name, d in totals.items():
        func(floors, d, label=_variables_map.get(name, name))
    ax.legend()

    plt.xlabel("Floor")
    if "label" in req.query:
        plt.ylabel(req.query["label"])
    plt.xlim(left=0)
    plt.ylim(bottom=0)
    if "title" in req.query: # doesn't appear to work with mpld3
        plt.suptitle(req.query["title"])

    if req.query["type"] == "embed":
        value: str = mpld3.fig_to_html(fig)
        plt.close(fig)
        value = value.replace('"axesbg": "#FFFFFF"', f'"axesbg": "{config.website_bg}"')
        return Response(body=value, content_type="text/html")

    elif req.query["type"] == "image":
        with io.BytesIO() as file:
            plt.savefig(file, format="png", transparent=True)
            plt.close(fig)

            return Response(body=file.getvalue(), content_type="image/png")

@router.get("/compare")
@aiohttp_jinja2.template("runs_compare.jinja2")
async def compare_choose(req: Request):
    return {
        "characters": ("Ironclad", "Silent", "Defect", "Watcher"),
        "relics": get_all_relics(),
        "cards": get_all_cards(),
    }

@router.get("/compare/view")
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
    pw = req.query.get("key")
    if pw is None:
        raise HTTPUnauthorized(reason="No API key provided")
    if not config.secret:
        raise HTTPNotImplemented(reason="No API key present in config")
    if pw != config.secret:
        raise HTTPForbidden(reason="Invalid API key provided")

    post = await req.post()

    content = post.get("run")
    if isinstance(content, FileField):
        content = content.file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8", "xmlcharrefreplace")

    name = post.get("name")
    if isinstance(name, FileField):
        name = name.file.read()
    if isinstance(name, bytes):
        name = name.decode("utf-8", "xmlcharrefreplace")

    with open(os.path.join("data", "runs", name), "w") as f:
        f.write(content)
    data = json.loads(content)
    _cache[name] = parser = RunParser(name, data)
    _ts_cache[parser.timestamp] = parser

    return Response()
