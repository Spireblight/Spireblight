"""Parsing of Slay the Spire 2 run history and savefile."""

import datetime

from src.nameinternal import get, get_card2
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
    def id(self):
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

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"This has not yet been implemented ({self.__class__.__name__}.{name})"

class FileParser:
    """Hold a single run (ongoing or not) data."""

    game_version: int = 2       #: Which version of the game we care about.
    done: bool = False          #: Whether the run is over.

    def __init__(self, data: dict):
        self._data = data

    def get_main_player(self):
        """Return the player we care about, AKA the streamer."""
        pl = self.players
        if len(pl) == 1:
            return pl[0]
        if config.server.steam_id:
            for x in pl:
                if x.id == config.server.steam_id:
                    return x
        return pl[0] # fallback

    def get_char_portrait(self):
        c = self.character.lower()
        # we do not currently account for losses
        return f"/static/characters/{c}-portrait-2.png"

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
    def seeded(self) -> bool:
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
    def has_removals(self):
        return False # TODO

    def master_deck_as_html(self):
        return ["The deck will be here, eventually."]

    @property
    def path(self):
        """The path taken through the Spire."""
        paths = []
        i = 0
        acts: list[str] = self._data["acts"]
        act_names = []
        if isinstance(acts, dict): # savefile
            acts = [x["id"] for x in acts]
        for a in acts:
            n, _, name = a.partition(".")
            assert n == "ACT", "An update has changed the Act definition"
            act_names.append(name.title())

        for act, name in zip(self._data["map_point_history"], act_names):
            for node in act:
                i += 1
                paths.append(PathNode(node, i, name))
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
    def __init__(self, data: dict, floor: int, act: str):
        self._data = data
        self.floor = floor
        self.act = act

    @property
    def end_of_act(self) -> bool:
        return self._data["map_point_type"] == "boss"

    def description(self):
        return "This has yet to be implemented."

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
