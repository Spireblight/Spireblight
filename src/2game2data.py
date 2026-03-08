"""Parsing of Slay the Spire 2 run history and savefile."""

from src.nameinternal import get, get_card2

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

class FileParser:
    """Hold a single run (ongoing or not) data."""

    def __init__(self, data: dict):
        self._data = data

    @property
    def ascension(self):
        return self._data["ascension"]

    @property
    def players(self):
        """Read-only list of all players in this game."""
        return [Player(x) for x in self._data["players"]]

class RelicData:
    """View relics and their information."""

    def __init__(self, data: dict[str, str]):
        self.floor: int = data["floor_added_to_deck"] # works for both run and save
        r, _, name = data["id"].partition(".")
        self.relic = get(name)
