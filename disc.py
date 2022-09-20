from discord.ext.commands import Command, Context

from logger import logger

from configuration import config

__all__ = ["DiscordCommand"]

class DiscordCommand(Command):
    def __init__(self, func, flag="", **kwargs):
        self.__doc__ = func.__doc__
        self.flag = flag
        logger.debug(f"Creating Discord command {func.__name__}")
        super().__init__(func, **kwargs)

    def __bool__(self):
        return self.enabled

    async def invoke(self, context: Context):
        if not self.enabled:
            return
        if self.flag:
            for guild in context.bot.guilds:
                if guild.id == config.discord.server_id:
                    break
            else:
                return
            mod_role = guild.get_role(config.discord.moderator_role)
            if self.flag and (
                (context.author().id not in config.baalorbot.owners) and
                ("m" in self.flag and mod_role not in context.author().roles)
            ):
                return
        logger.debug(f"Invoking Discord command {self.name} by {context.author().display_name}")
        await super().invoke(context)
