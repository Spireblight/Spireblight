import json
import os

from events import add_listener

__all__ = ["get_relic", "get_all_relics", "get_card", "get_all_cards", "get_potion", "get_all_potions"]

_cache: dict[str, dict[str, str]] = {}

def _get_name(x: str, d: str, default: str) -> str:
    return _cache[d].get(x, {}).get("NAME", default)

def _get_all(d: str) -> dict[str, str]:
    return {b["NAME"]: a for a, b in _cache[d].items() if "DEPRECATED" not in b["NAME"]}

def get_relic(name: str, default: str = "<Unknown Relic>") -> str:
    return _get_name(name, "relics", default)

def get_all_relics() -> dict[str, str]:
    return _get_all("relics")

def get_card(name: str, default: str = "<Unknown Card>") -> str:
    if name == "Singing Bowl":
        return "Gain +2 Max HP"
    name, plus, upgrades = name.partition("+")
    val = _get_name(name, "cards", default)
    if upgrades not in ("1", ""): # Searing Blow
        return f"{val}+{upgrades}"
    return f"{val}{plus}"

def get_all_cards() -> dict[str, str]:
    return _get_all("cards")

def get_potion(name: str, default: str = "<Unknown Potion>") -> str:
    return _get_name(name, "potions", default)

def get_potions() -> dict[str, str]:
    return _get_all("potions")

@add_listener("setup_init")
async def load():
    _cache.clear()
    for file in os.listdir("eng"):
        with open(os.path.join("eng", file)) as f:
            _cache[file[:-5]] = json.load(f)
