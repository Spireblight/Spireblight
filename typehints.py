from collections import defaultdict
from typing import Union, TypeAlias, TYPE_CHECKING

from twitchio.ext.commands import Context as TContext
from discord.ext.commands import Context as DContext

from twitch import TwitchCommand
from disc import DiscordCommand


if TYPE_CHECKING:
    from gamedata import Relic, Potion
else:
    # type-checking will ignore this
    # but actual code will hit this, and doesn't care about type
    Relic = None
    Potion = None

__all__ = [
    "ContextType", "CommandType",
    "CardRewards", "RelicRewards", "PotionRewards",
    "PotionsListing", "ItemFloor",
]

# transport-related support
ContextType: TypeAlias = Union[TContext, DContext]
CommandType: TypeAlias = Union[TwitchCommand, DiscordCommand]

# this is for specifically things which take an int for floor number
# in the future, this may become an int subclass
Floor: TypeAlias = int

# these are mappings of things obtained on a floor
CardRewards: TypeAlias = defaultdict[Floor, list[str]]
RelicRewards: TypeAlias = defaultdict[Floor, list[Relic]]
PotionRewards: TypeAlias = defaultdict[Floor, list[Potion]]

PotionsListing: TypeAlias = list[list[Potion]]

ItemFloor: TypeAlias = tuple[str, Floor]
