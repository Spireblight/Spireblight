"""Parsing of Slay the Spire 2 run history and savefile."""

from __future__ import annotations

import datetime

from src.nameinternal import get, get_card2, Relic
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
        r, _, name = data["id"].partition(".")
        self.relic = get(name)
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

    @property
    def end_of_act(self) -> bool:
        # this is a weird thing, but because of double boss, we don't wanna multiline it
        return self.floor < 48 and self._data["map_point_type"] == "boss"

    def description(self):
        choices = self._data["player_stats"][self.parser.get_player_index()]

        match self._data["map_point_type"]:
            case "ancient":
                not_picked = []
                picked = None
                if "ancient_choice" not in choices:
                    return "No bonus picked."

                for d in choices["ancient_choice"]:
                    key: str = d["title"]["key"]
                    name, _, _ = key.partition(".")
                    relic = get(name)
                    if d["was_chosen"]:
                        picked = relic
                    else:
                        not_picked.append(relic)

                return f"We picked {picked.name}."

        return "Data coming soon . . ."

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
