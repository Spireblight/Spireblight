from discord.ext.commands import Command, Context

from logger import logger

from config import global_config

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
                if guild.id == global_config.discord_servid:
                    break
            else:
                return
            mod_role = guild.get_role(global_config.moderator_role)
            if self.flag and (
                (context.author().id not in global_config.owners) and
                ("m" in self.flag and mod_role not in context.author().roles)
            ):
                return
        logger.debug(f"Invoking Discord command {self.name} by {context.author().display_name}")
        await super().invoke(context)
