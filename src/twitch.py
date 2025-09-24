from typing import Callable

from twitchio.ext.commands import Command, Context

from src.logger import logger

from src.config import config

__all__ = ["TwitchCommand"]

class TwitchCommand(Command):
    def __init__(self, name: str, func: Callable, flag="", **attrs):
        super().__init__(name, func, **attrs)
        self.__doc__ = func.__doc__
        self.flag = flag
        self.required = func.__required__
        self.enabled = True

    def __bool__(self):
        return self.enabled

    async def invoke(self, context: Context, *, index=0):
        if not self.enabled:
            return
        if self.flag:
            is_editor = (context.author.name in config.bot.editors or context.author.is_broadcaster)
            is_mod = (context.author.is_mod or context.author.is_broadcaster)
            if "m" in self.flag:
                if "e" in self.flag:
                    if not (is_mod or is_editor):
                        return
                elif not is_mod:
                    return
            elif "e" in self.flag:
                if not is_editor:
                    return
        logger.debug(f"Invoking Twitch command {self.name} by {getattr(context.author, 'display_name', context.author.name)}")
        await super().invoke(context, index=index)
