"""Parsing of Slay the Spire 2 run history and savefile."""

from __future__ import annotations

import collections
import datetime

from src.nameinternal import get, get_card2, Relic, Card, SingleCard, Potion
from src.config import config
from src.utils import format_for_slaytabase

class Player:
    """Hold game information for one player."""

    def __init__(self, data: dict):
        self._data = data

    @property
    def character(self) -> str:
        """Which character we're playing."""
        try:
            c: str = self._data["character"] # run history
        except KeyError:
            c: str = self._data["character_id"] # savefile
        return c.partition(".")[2].title()

    @property
    def id(self) -> int:
        try:
            return self._data["id"]
        except KeyError:
            return self._data["net_id"]

    @property
    def relics(self) -> list["RelicData"]:
        """The relics at run end/current node."""
        ret = []
        for rel in self._data["relics"]:
            ret.append(RelicData(rel))
        return ret

    @property
    def deck(self):
        """The deck at run end/current node."""
        return [get_card2(x) for x in self._data["deck"]]

    def __eq__(self, value):
        if not isinstance(value, Player):
            return NotImplemented
        return self._data == value._data

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"This has not yet been implemented ({self.__class__.__name__}.{name})"

class FileParser:
    """Hold a single run (ongoing or not) data."""

    game_version: int = 2       #: Which version of the game we care about.
    done: bool = False          #: Whether the run is over.

    def __init__(self, data: dict):
        self._data = data
        self._main_player_index: int | None = None

    def get_main_player(self):
        """Return the player we care about, AKA the streamer."""
        pl = self.players
        if self._main_player_index is not None:
            return pl[self._main_player_index]

        if len(pl) == 1:
            self._main_player_index = 0
            return pl[0]

        if config.server.steam_id:
            for i, x in enumerate(pl):
                if x.id == int(config.server.steam_id): # just in case
                    self._main_player_index = i
                    return x
        return pl[0] # fallback

    def get_player_index(self):
        """Return the main player index.

        This is such that `FP.players[FP.get_player_index()] == FP.get_main_player()`."""

        if self._main_player_index is not None:
            return self._main_player_index
        pl = self.get_main_player()
        try:
            return self.players.index(pl)
        except ValueError: # for some reason
            # it's possible our call above set it
            return self._main_player_index or 0

    def get_char_portrait(self):
        c = self.character.lower()
        # we do not currently account for losses
        return f"/static/characters/{c}-portrait-3.png"

    @property
    def won(self) -> bool:
        """Whether or not we won the run."""
        return False

    @property
    def seed(self) -> str:
        try:
            return self._data["seed"]
        except KeyError:
            return self._data["rng"]["seed"]

    @property
    def is_seeded(self) -> bool:
        return False # temporary fix

    @property
    def character(self):
        return self.get_main_player().character

    @property
    def ascension_level(self) -> int:
        """Which Ascension level the run was played at."""
        return self._data["ascension"]

    @property
    def players(self):
        """Read-only list of all players in this game (host first)."""
        return [Player(x) for x in self._data["players"]]

    @property
    def relics(self):
        return self.get_main_player().relics

    @property
    def relics_bare(self) -> list[Relic]:
        return [x.relic for x in self.relics]

    @property
    def has_removals(self):
        return False # TODO

    def master_deck_as_html(self):
        return ["The deck will be here, eventually."]

    @property
    def path(self) -> list[PathNode]:
        """The path taken through the Spire."""
        paths = []
        i = 0
        acts: list[str] = self._data["acts"]
        act_names = []
        if isinstance(acts[0], dict): # savefile
            acts = [x["id"] for x in acts]
        for a in acts:
            n, _, name = a.partition(".")
            assert n == "ACT", "An update has changed the Act definition"
            act_names.append(name.title())

        for act, name in zip(self._data.get("map_point_history", ()), act_names):
            for node in act:
                i += 1
                paths.append(PathNode(self, node, i, name))

        return paths

    @property
    def epoch(self) -> int:
        """Time in seconds since Jan 1, 1970."""
        return self._data["start_time"] + self._data["run_time"]

    @property
    def timestamp(self) -> datetime.datetime:
        """Time when the run finished, as UTC."""
        return datetime.datetime.fromtimestamp(self.epoch, datetime.UTC)

    @property
    def timedelta(self) -> datetime.timedelta:
        """Difference between now and the run."""
        return datetime.datetime.now(datetime.UTC) - self.timestamp

    @property
    def modded(self):
        return False # temporary

    @property
    def modifiers(self):
        return self._data["modifiers"]

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"Not implemented ({self.__class__.__name__}.{name})"

class RelicData:
    """View relics and their information."""

    def __init__(self, data: dict[str, str]):
        self.floor: int = data["floor_added_to_deck"] # works for both run and save
        self.relic = get(data["id"])
        self.props: dict | None = data.get("props")

    @property
    def name(self):
        return self.relic.name

    @property
    def mod(self) -> str:
        if not self.relic.mod:
            # this is specifically for the github
            return "2-slay the spire 2"
        return self.relic.mod

    @property
    def image(self) -> str:
        name = self.relic.internal
        if ":" in name:
            name = name[name.index(":")+1:]
        return f"{format_for_slaytabase(name)}.png"

    def description(self):
        desc = [f"Obtained on floor {self.floor}", self.relic.description]
        return "\n".join(desc)

    def escaped_description(self) -> str:
        return self.description().replace("\n", "<br>").replace("'", "\\'")

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"Not implemented ({self.__class__.__name__}.{name})"

class PathNode:
    def __init__(self, parser: FileParser, data: dict, floor: int, act_name: str = None):
        self.parser = parser
        self._data = data
        self.floor = floor
        self.act_name = act_name
        self._set_room_name()
        self._set_picks()

    @property
    def end_of_act(self) -> bool:
        # this is a weird thing, but because of double boss, we don't wanna multiline it
        return self.floor < 48 and self._data["map_point_type"] == "boss"

    def _set_room_name(self):
        # idk why rooms is a list, but there's only ever one item, even in mp
        room = self._data["rooms"][0]
        map_point = self._data["map_point_type"]
        room_type = room["room_type"]
        model_id: str | None = room.get("model_id")
        self.name = ""
        if model_id:
            _, _, name = model_id.partition(".")
            self.name = name.replace("_", " ").title()

        match (map_point, room_type):
            case ("ancient", "event"):
                self.room_type = "Ancient"
            case ("monster", "monster"):
                self.room_type = "Enemy"
            case ("unknown", "monster"):
                self.room_type = "Enemy (unknown)"
            case ("elite", "elite"):
                self.room_type = "Elite fight"
            case ("unknown", "event"):
                self.room_type = "Event"
            case ("rest_site", "rest_site"):
                self.room_type = "Rest site"
            case ("treasure", "treasure"):
                self.room_type = "Treasure chest"
            case ("shop", "shop"):
                self.room_type = "Merchant"
            case ("boss", "boss"):
                self.room_type = "Boss fight"

    def _set_picks(self):
        """Set all the variables for this node."""
        choices: dict[str] = self._data["player_stats"][self.parser.get_player_index()]

        self.gold: int = choices["current_gold"]
        self.damage_taken: int = choices["damage_taken"]
        self.current_hp: int = choices["current_hp"]
        self.max_hp: int = choices["max_hp"]
        self.max_hp_gained: int = choices["max_hp_gained"]
        self.max_hp_lost: int = choices["max_hp_lost"]

        self.picked: list[SingleCard] = []
        self.skipped: list[SingleCard] = []
        self.cards_obtained: list[SingleCard] = []
        self.cards_removed: list[SingleCard] = []
        self.cards_transformed: list[SingleCard] = []
        self.cards_upgraded: list[SingleCard] = []

        self.relics: list[Relic] = []
        self.relics_lost: list[Relic] = []
        self.skipped_relics: list[Relic] = []

        self.potions: list[Potion] = []
        self.used_potions: list[Potion] = []
        self.potions_from_alchemize: list[Potion] = []
        self.potions_from_entropic: list[Potion] = []
        self.discarded_potions: list[Potion] = []
        self.skipped_potions: list[Potion] = []

        for c in choices.get("card_choices", ()):
            card = get_card2(c["card"], self.floor)
            if c["was_picked"]:
                self.picked.append(card)
            else:
                self.skipped.append(card)

        for g in choices.get("cards_gained", ()):
            card = get_card2(g, self.floor)
            if card not in self.picked:
                self.cards_obtained.append(card)

        for u in choices.get("upgraded_cards", ()):
            self.cards_upgraded.append(get_card2(u))

        for r in choices.get("relic_choices", ()):
            relic = get(r["choice"])
            if r["was_picked"]:
                self.relics.append(relic)
            else:
                self.skipped_relics.append(relic)

        for p in choices.get("potion_choices", ()):
            potion = get(p["choice"])
            if p["was_picked"]:
                self.potions.append(potion)
            else:
                self.skipped_potions.append(potion)

    @property
    def all_potions_received(self) -> list[Potion]:
        """All potions which were received on this floor."""
        return self.potions + self.potions_from_alchemize + self.potions_from_entropic

    @property
    def all_potions_dropped(self) -> list[Potion]:
        """All potions which were used or discarded this floor."""
        return self.used_potions + self.discarded_potions

    def short_description(self):
        """Short description meant to fit on one line."""
        # typically only Neow/floor 1 will use this
        if self.name != "Neow":
            return "If you can read this, there is a bug!"

        choices: list[dict] = self._data["player_stats"][self.parser.get_player_index()]["ancient_choice"]

        picked: Relic | None = None
        not_picked: list[Relic] = []
        for d in choices:
            relic: Relic = get(d["title"]["key"])
            if d["was_chosen"]:
                picked = relic
            else:
                not_picked.append(relic)

        if picked is not None:
            return f"We picked {picked.name}, and skipped {' and '.join(x.name for x in not_picked)}."
        return "No bonus picked yet."

    def description(self):
        result = self.get_description()

        final = []
        desc = list(result.items())
        desc.sort(key=lambda x: x[0])
        for i, text in desc:
            final.extend(text)

        return "\n".join(final)

    def get_description(self):
        to_append: dict[int, list[str]] = collections.defaultdict(list)

        if self.room_type:
            to_append[0].append(f"{self.room_type}")
        to_append[0].append(f"{self.current_hp}/{self.max_hp} - {self.gold} gold")

        if self.name:
            to_append[0].append(self.name)

        if self.potions:
            to_append[10].append("Potions obtained:")
            to_append[10].extend(f"- {x.name}" for x in self.potions)

        if self.used_potions:
            to_append[12].append("Potions used:")
            to_append[12].extend(f"- {x.name}" for x in self.used_potions)

        if self.potions_from_alchemize:
            to_append[14].append("Potions obtained from Alchemize:")
            to_append[14].extend(f"- {x.name}" for x in self.potions_from_alchemize)

        if self.potions_from_entropic:
            to_append[16].append("Potions obtained from Entropic Brew:")
            to_append[16].extend(f"- {x.name}" for x in self.potions_from_entropic)

        if self.discarded_potions:
            to_append[18].append("Potions discarded:")
            to_append[18].extend(f"- {x.name}" for x in self.discarded_potions)

        if self.skipped_potions:
            to_append[20].append("Potions skipped:")
            to_append[20].extend(f"- {x.name}" for x in self.skipped_potions)

        if self.relics:
            to_append[30].append("Relics obtained:")
            to_append[30].extend(f"- {x.name}" for x in self.relics)

        if self.skipped_relics:
            to_append[32].append("Relics skipped:")
            to_append[32].extend(f"- {x.name}" for x in self.skipped_relics)

        if self.picked:
            to_append[34].append("Picked:")
            to_append[34].extend(f"- {x}" for x in self.picked)

        if self.skipped:
            to_append[36].append("Skipped:")
            to_append[36].extend(f"- {x}" for x in self.skipped)

        return to_append

    def escaped_description(self) -> str:
        return self.description().replace("\n", "<br>").replace("'", "\\'")

    @property
    def map_icon(self):
        """The current page/run history map icon."""
        room = self._data["rooms"][0]
        on_map = self._data["map_point_type"]
        actual = room["room_type"]
        icon = actual
        if on_map == "unknown" and actual != "event":
            icon = f"unknown_{icon}"
        elif on_map in ("ancient", "boss"):
            m_id: str = room["model_id"]
            p, _, name = m_id.partition(".")
            icon = name.lower()

        if icon in ("event", "shop"):
            icon += "_2"

        return f"{icon}.png"

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"Not implemented ({self.__class__.__name__}.{name})"
