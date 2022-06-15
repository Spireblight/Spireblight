from typing import Union

from twitchio.ext.commands import Context as TContext
from discord.ext.commands import Context as DContext

__all__ = ["ContextType"]

ContextType = Union[TContext, DContext]


