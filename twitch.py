from typing import Callable

from twitchio.ext.commands import Command, Context

from logger import logger

from configuration import config

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
            is_editor = (context.author.name in config.baalorbot.editors)
            if (
                (not context.author.is_broadcaster) and
                (("e" in self.flag and not is_editor) or
                ("m" in self.flag and not context.author.is_mod))
            ):
                return
        logger.debug(f"Invoking Twitch command {self.name} by {getattr(context.author, 'display_name', context.author.name)}")
        await super().invoke(context, index=index)
