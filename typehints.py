from typing import Union

from twitchio.ext.commands import Context as TContext
from discord.ext.commands import Context as DContext

from twitch import TwitchCommand
from disc import DiscordCommand

__all__ = ["ContextType", "CommandType"]

ContextType = Union[TContext, DContext]

CommandType = Union[TwitchCommand, DiscordCommand]
