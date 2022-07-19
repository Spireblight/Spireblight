import json
import os

from events import add_listener

__all__ = [
    "get_relic", "get_all_relics", "get_relic_stats",
    "get_card", "get_card_metadata", "get_all_cards",
    "get_potion", "get_all_potions",
    "get_event", "get_all_events",
    "get_enemy", "get_all_enemies",
]

_cache: dict[str, dict[str, str]] = {}

def _get_name(x: str, d: str, default: str) -> str:
    return _cache[d].get(x, {}).get("NAME", default)

def _get_all(d: str) -> dict[str, str]:
    return {b["NAME"]: a for a, b in _cache[d].items()}

def get_relic(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Relic {name}>"
    return _get_name(name, "relics", default)

def get_all_relics() -> dict[str, str]:
    return _get_all("relics")

def get_card(name: str, default: str | None = None) -> str:
    if name == "Singing Bowl":
        return "Gain +2 Max HP"
    if default is None:
        default = f"<Unknown Card {name}>"
    name, plus, upgrades = name.partition("+")
    val = _get_name(name, "cards", default)
    if upgrades not in ("1", ""): # Searing Blow
        return f"{val}+{upgrades}"
    return f"{val}{plus}"

def get_card_metadata(name: str) -> dict[str, str]:
    return _cache["cards"][name.partition("+")[0]]

def get_all_cards() -> dict[str, str]:
    return _get_all("cards")

def get_potion(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Potion {name}>"
    return _get_name(name, "potions", default)

def get_all_potions() -> dict[str, str]:
    return _get_all("potions")

def get_event(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Event {name}>"
    return _get_name(name, "events", default)

def get_all_events() -> dict[str, str]:
    return _get_all("events")

def get_enemy(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Enemy {name}>"
    return _get_name(name, "monsters", default)

def get_all_enemies() -> dict[str, str]:
    return _get_all("monsters")

def get_relic_stats(name: str) -> list[str]:
    return _cache["relic_stats"][name]["TEXT"]

@add_listener("setup_init")
async def load():
    _cache.clear()
    for file in os.listdir("eng"):
        with open(os.path.join("eng", file)) as f:
            _cache[file[:-5]] = json.load(f)
