import json
import os

from events import add_listener

__all__ = ["get_relic", "get_card", "get_potion"]

_cache = {}

def _get_name(x: str, d: str) -> str:
    return _cache[d].get(x, {}).get("NAME", "<Unknown>")

def get_relic(name: str) -> str:
    return _get_name(name, "relics")

def get_card(name: str) -> str:
    if name == "Singing Bowl":
        return "Gained +2 Max HP"
    name, plus, upgrades = name.partition("+")
    val = _get_name(name, "cards")
    if upgrades not in ("1", ""):
        return f"{val}+{upgrades}"
    return f"{val}{plus}"

def get_potion(name: str) -> str:
    return _get_name(name, "potions")

@add_listener("setup_init")
async def load():
    _cache.clear()
    for file in os.listdir("eng"):
        with open(os.path.join("eng", file)) as f:
            _cache[file[:-5]] = json.load(f)
