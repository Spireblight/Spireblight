from discord.ext.commands import Command

from logger import logger

__all__ = ["DiscordCommand"]

class DiscordCommand(Command):
    def __init__(self, func, **kwargs):
        logger.debug(f"Creating Discord command {func.__name__}")
        super().__init__(func, **kwargs)
