from collections import defaultdict
from typing import Union, TypeAlias, Optional, TYPE_CHECKING

from twitchio.ext.commands import Context as TContext
from discord.ext.commands import Context as DContext

from src.twitch import TwitchCommand
from src.disc import DiscordCommand

from src.nameinternal import Relic, Potion, SingleCard

__all__ = [
    "ContextType", "CommandType",
    "CardRewards", "RelicRewards", "PotionRewards",
    "PotionsListing", "ItemFloor",
    "BossRelicChoice",
]

# transport-related support
ContextType: TypeAlias = Union[TContext, DContext]
CommandType: TypeAlias = Union[TwitchCommand, DiscordCommand]

# this is for specifically things which take an int for floor number
# in the future, this may become an int subclass
Floor: TypeAlias = int

# these are mappings of things obtained on a floor
CardRewards: TypeAlias = defaultdict[Floor, list[SingleCard]]
RelicRewards: TypeAlias = defaultdict[Floor, list[Relic]]
PotionRewards: TypeAlias = defaultdict[Floor, list[Potion]]

PotionsListing: TypeAlias = list[list[Potion]]

ItemFloor: TypeAlias = tuple[str, Floor]

BossRelicChoice: TypeAlias = tuple[Optional[Relic], tuple[Relic, ...]]
