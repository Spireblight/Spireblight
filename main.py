import importlib
import logging
import asyncio
import sys
import os

from aiohttp import web

import src.config

# this will load the config into the src.config namespace
# we do this here so that we can import the module without side-effects
# this is important for testing and docgen
src.config.load()

from src.webpage import webpage
from src.logger import logger
from src.config import config, __version__

from src import server, events

if config.server.debug:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format="{asctime} :: {levelname}:{name} - {message}",
        datefmt="(%Y-%m-%d %H:%M:%S)",
        style="{",
    )

logger.info("Starting the bot")

if sys.platform == "win32": # postgres compat
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

async def main():
    last = "0.6" # last version without automatic migration
    if os.path.isfile("last_version"):
        with open("last_version") as f:
            last = f.read().strip()
    if last != __version__: # need to migrate
        nomig = {}
        with open("migrate/.no-migrate", "r") as f:
            for line in f.readlines():
                bef, col, aft = line.partition(":")
                if col:
                    nomig[bef] = aft
        values = {}
        for dirpath, folders, files in os.walk("migrate"):
            for file in files:
                if file.startswith("_") or not file.endswith(".py"):
                    continue
                name = file[:-3]
                # IMPORTANT: importing migration modules MUST NOT have side effects (such as importing other modules)
                mod = importlib.import_module(f"migrate.{name}")
                values[mod.FROM] = mod

        while last != __version__:
            try:
                module = values[last]
            except KeyError:
                if last in nomig:
                    last = nomig[last]
                    continue
                raise RuntimeError(f"Could not migrate from {last}, this is a bug.")

            try:
                if not module.migrate(automatic=True):
                    raise RuntimeError(f"Migration {module.__name__!r} did not return a True value.")
            except Exception as e:
                raise RuntimeError(f"Migrating from {last} encountered an error") from e

            last = module.TO

        with open("last_version", "w") as f:
            f.write(last)

        logger.info("Migration complete. Please restart the process.")
        return # prefer a clean slate

    await events.invoke("setup_init")
    loop = asyncio.get_event_loop()

    tasks = set()

    if not any((config.twitch.enabled, config.discord.enabled)):
        logging.warning(f"None of the bots are enabled. There will be no commands on the {config.bot.name} page.")

    if config.twitch.enabled:
        tasks.add(loop.create_task(server.Twitch_startup()))
    if config.discord.enabled:
        tasks.add(loop.create_task(server.Discord_startup()))
    if config.youtube.playlist_sheet:
        tasks.add(loop.create_task(server.Youtube_startup()))
    if config.youtube.archive_id not in ("<not set>", ""):
        tasks.add(loop.create_task(server.Archive_startup()))

    tasks.add(loop.create_task(web._run_app(webpage)))

    try:
        await asyncio.gather(*tasks)
    except (web.GracefulExit, KeyboardInterrupt):
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        if config.twitch.enabled:
            await server.Twitch_cleanup()
        if config.discord.enabled:
            await server.Discord_cleanup()
        loop.close()

if __name__ == "__main__":
    asyncio.run(main()) # TODO: Signal handlers and stuff
