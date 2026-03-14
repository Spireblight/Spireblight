from __future__ import annotations

from collections import defaultdict
from functools import total_ordering
from aiohttp import ClientSession
from pathlib import Path

import json

from src.config import config
from src.events import add_listener
from src.utils import complete_match

# this is an iterable of 1-length str to remove from queries
_replace_str = " -'()."

__all__ = [
    "get", "get_card",
    "get_relic_stats",
    "get_event",
    "query", "get_run_mod",
]

_cache: dict[str, dict[str, str]] = {}
_internal_cache: dict[str, Base] = {}
_query_cache: dict[str, list[Base]] = defaultdict(list)

def sanitize(x: str) -> str:
    x = x.lower()
    for s in _replace_str:
        x = x.replace(s, "")
    return x

def query(name: str, type: str | None = None):
    force = False
    if name.endswith(" 1"): # force spire 1 data
        name = name[:-2]
        force = True
    name = sanitize(name)
    res = complete_match(name, _query_cache)
    if len(res) == 1:
        lst = _query_cache[res[0]]
        for i, item in enumerate(lst):
            if item.v == (force and 1 or 2):
                break
        else:
            i = 0
        ret = lst.pop(i)
        # this makes sure to cycle through cards if there are multiple
        lst.append(ret)
        return ret
    return None

def get(name: str) -> Base:
    if name in _internal_cache:
        return _internal_cache[name]

    return Unknown(name)

def get_card(card: str) -> SingleCard:
    """Return a single card for Slay the Spire."""
    name, _, upgrades = card.partition("+")
    inst = get(name)
    return SingleCard(inst, int(upgrades or 0))

def get_card2(data: dict) -> SingleCard:
    """Return a single card for Slay the Spire 2."""
    c: str = data["id"]
    _, _, name = c.partition(".")
    card = get(name)
    return SingleCard(card, data.get("current_upgrade_level", 0), data["floor_added_to_deck"], data.get("enchantment"))

@total_ordering
class Base:
    cls_name = ""
    store_internal = True
    def __init__(self, data: dict[str, str]):
        assert self.cls_name, "Cannot instantiate Base"
        self.internal = data.get("id", data["name"])
        self.name = data["name"]
        self.description = data["description"]
        self.mod = data.get("mod")
        self.v: int = data.get("v", 1)
        if self.mod in ("Slay the Spire", "Slay the Spire 2"):
            self.mod = None

    @property
    def info(self) -> str:
        return f"{self.name}: {self.description}"

    def __str__(self):
        return self.name

    def __hash__(self) -> int:
        return hash(self.internal)

    def __eq__(self, other) -> bool:
        # technically, this could be checking against just Base
        # but we don't want to accidentally compare cards and relics
        # so it's disallowed here and will throw an error instead
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.name == other.name

    def __lt__(self, other) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.name < other.name

class Card(Base):
    cls_name = "card"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.color: str = data["color"]
        self.rarity: str = data.get("rarity")
        self.type: str = data["type"]
        self.cost: str | None = data["cost"] or None
        self.star_cost: str | None = data.get("starCost")
        self.pack: str | None = data.get("pack")

    @property
    def info(self) -> str:
        mod = ""
        if self.pack:
            mod = f"(Packmaster: {self.pack})"
        elif self.mod:
            mod = f"(Mod: {self.mod})"
        cost = self.cost
        if self.star_cost:
            cost += f" (Stars: {self.star_cost})"
        return f"{self.name} - [{cost}] {self.color} {self.rarity} {self.type}: {self.description} {mod}"

class Enchantment(Base):
    cls_name = "enchantment"
    def __init__(self, data: dict[str: str | int]):
        super().__init__(data)

class SingleCard:
    enchantment: Enchantment | None = None
    amount: int = 0
    def __init__(self, card: Card, upgrades: int = 0, floor: int | None = None, enchantment: dict | None = None):
        self.card = card
        self.upgrades = upgrades
        self.floor_added = floor # if None, we simply don't have the info
        if enchantment is not None:
            enc: str = enchantment["id"]
            _, _, name = enc.partition(".")
            self.enchantment = get(name)
            self.amount = enchantment["amount"]

    @property
    def name(self):
        match self.upgrades:
            case 0:
                up = ""
            case 1:
                up = "+"
            case n:
                up = f"+{n}"

        enc = ""
        if self.enchantment:
            enc = f" [{self.enchantment.name} {self.amount}]"

        return f"{self.card.name}{up}{enc}"

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name

    def __eq__(self, value):
        return isinstance(value, SingleCard) and self.name == value.name

class Relic(Base):
    cls_name = "relic"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.pool: str | None = data.get("pool")
        self.tier: str = data["tier"]
        self.flavour_text: str = data["flavorText"]

    @property
    def info(self) -> str:
        mod = ""
        if self.mod:
            mod = f"(Mod: {self.mod})"
        pool = " "
        if self.pool:
            pool = f" ({self.pool})"
        return f"{self.name} - {self.tier}{pool}: {self.description} {mod}"

class RelicSet(Base):
    cls_name = "relic_set"
    def __init__(self, data: dict[str, list[str]]):
        super().__init__(data)
        self.relic_list: list[str] = data["relic_list"]
        self.description: str = f"{data['description']}: {', '.join(data['relic_list'])}"

class Potion(Base):
    cls_name = "potion"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.rarity: str = data.get("rarity")
        self.color: str = data.get("color")

    @property
    def info(self) -> str:
        mod = ""
        if self.mod:
            mod = f"(Mod: {self.mod})"
        color = ""
        if self.color:
            color = f" ({self.color})"
        return f"{self.name} - {self.rarity}{color}: {self.description} {mod}"

class Keyword(Base):
    cls_name = "keyword"
    store_internal = False
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.names: list[str] = data.get("names", [])

class ScoreBonus(Base):
    cls_name = "score_bonus"
    def __init__(self, data: dict[str, str]):
        super().__init__(data)
        self.format_string: str = data.get("format_string", self.name)

class Unknown(Base):
    cls_name = "<unknown>"
    def __init__(self, name: str):
        self.internal = name
        self.name = name
        self.description = f"Could not find description for {name!r} (this is a bug)"
        self.mod = None

    def __getattr__(self, attr: str):
        return f"<Unknown attribute {attr}>"

_str_to_cls: dict[str, type[Base]] = {
    "cards": Card,
    "relics": Relic,
    "relic_set": RelicSet,
    "potions": Potion,
    "keywords": Keyword,
    "score_bonuses": ScoreBonus,
    #"events": Event, # both games have it
    #"creatures": Enemy, # and this one too
    "enchantments": Enchantment,
}

def _get_name(x: str, d: str, default: str) -> str:
    return _cache[d].get(x, {}).get("NAME", default)

def get_event(name: str, default: str | None = None) -> str:
    if default is None:
        default = f"<Unknown Event {name}>"
    return _get_name(name, "events", default)

def get_relic_stats(name: str) -> list[str]:
    return _cache["relic_stats"][name]["TEXT"]

def get_run_mod(name: str) -> str:
    return f'{_cache["run_mods"][name]["NAME"]} - {_cache["run_mods"][name]["DESCRIPTION"]}'

@add_listener("setup_init")
async def load():
    _cache.clear()
    done = set()
    client = ClientSession()
    async with client as session:
        for mod in config.bot.spire_mods:
            if mod.lower() in done:
                continue
            data = None
            async with session.get(f"https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/{mod.lower()}/data.json") as resp:
                if resp.ok:
                    decoded = await resp.text()
                    data = json.loads(decoded)
            if data is None:
                raise ValueError(f"Mod {mod} could not be found.")

            for cat, maps in data.items():
                if cat in _str_to_cls:
                    for mapping in maps:
                        inst = _str_to_cls[cat](mapping)
                        if inst.store_internal:
                            _internal_cache[inst.internal] = inst
                        _query_cache[sanitize(inst.name)].append(inst)

            done.add(mod.lower())

    await client.close()

    base = Path(".")

    with (base / "argo" / "misc" / "score_bonuses.json").open() as f:
        j = json.load(f)
        for x in j["score_bonuses"]:
            inst = ScoreBonus(x)
            _internal_cache[inst.internal] = inst
            _query_cache[sanitize(inst.name)].append(inst)

    for file in (base / "argo" / "sts1").iterdir():
        if not file.stem.startswith("_"):
            with file.open() as f:
                _cache[file.stem] = json.load(f)

    # Load relic sets
    with (base / "argo" / "misc" / "relic_sets.json").open() as f:
        j = json.load(f)
    for relic_set in j["relic_sets"]:
        relset = RelicSet(relic_set)
        for alias in relic_set["set_aliases"]:
            _query_cache[alias].append(relset)
    for name, aliases in j["aliases"].items():
        inst = _internal_cache[name]
        for alias in aliases:
            _query_cache[alias].append(inst)
