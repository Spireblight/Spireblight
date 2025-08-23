import logging
import asyncio
import sys

from aiohttp import web

from src.webpage import webpage
from src.logger import logger

from src import server, events

from src.configuration import config

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
    await events.invoke("setup_init")
    loop = asyncio.get_event_loop()

    tasks = set()

    if not any((config.twitch.enabled, config.discord.enabled)):
        logging.warning("None of the bots are enabled. There will be no commands on the baalorbot page.")

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
