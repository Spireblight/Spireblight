"""Parsing of Slay the Spire 2 run history and savefile."""

from src.nameinternal import get, get_card2
from src.utils import format_for_slaytabase

class Player:
    """Hold game information for one player."""

    def __init__(self, data: dict):
        self._data = data

    @property
    def character(self):
        """Which character we're playing."""
        try:
            c: str = self._data["character"] # run history
        except KeyError:
            c: str = self._data["character_id"] # savefile
        return c.partition(".")[2]

    @property
    def relics(self):
        """The relics at run end/current node."""

    @property
    def deck(self):
        """The deck at run end/current node."""
        return [get_card2(x) for x in self._data["deck"]]

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"This has not yet been implemented ({self.__class__}.{name})"

class FileParser:
    """Hold a single run (ongoing or not) data."""

    def __init__(self, data: dict):
        self._data = data

    @property
    def ascension(self) -> int:
        """Which Ascension level the run was played at."""
        return self._data["ascension"]

    @property
    def players(self):
        """Read-only list of all players in this game (host first)."""
        return [Player(x) for x in self._data["players"]]

    @property
    def path(self):
        """The path taken through the Spire."""
        paths = []
        for player_list in self._data["map_point_history"]:
            # there's one list per player, even though we all climb together
            # but everyone gets different rewards, so keep track of that
            paths.extend(PathNode(x) for x in player_list)

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"This has not yet been implemented ({self.__class__}.{name})"

class RelicData:
    """View relics and their information."""

    def __init__(self, data: dict[str, str]):
        self.floor: int = data["floor_added_to_deck"] # works for both run and save
        r, _, name = data["id"].partition(".")
        self.relic = get(name)
        self.props: dict | None = data.get("props")

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

    def __getattr__(self, name):
        """Backup to prevent crashing pages."""
        return f"This has not yet been implemented ({self.__class__}.{name})"

class PathNode:
    def __init__(self, data: dict):
        self._data = data

    @property
    def end_of_act(self) -> bool:
        return self._data["map_point_type"] == "boss"

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
        return f"This has not yet been implemented ({self.__class__}.{name})"
