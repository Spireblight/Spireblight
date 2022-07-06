import logging
import asyncio
import sys

if "--debug" in sys.argv:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="{asctime} :: {levelname}:{name} - {message}", datefmt="(%Y-%m-%d %H:%M:%S)", style="{")

from aiohttp import web

from webpage import webpage
from logger import logger

import server, events

logger.info("Starting the bot")

async def main():
    await events.invoke("setup_init")
    loop = asyncio.get_event_loop()

    tasks = set()

    import sys
    if "--webonly" not in sys.argv:
        tasks.add(loop.create_task(server.Twitch_startup()))
        if "--nodiscord" not in sys.argv:
            tasks.add(loop.create_task(server.Discord_startup()))

    tasks.add(loop.create_task(web._run_app(webpage)))

    try:
        await asyncio.gather(*tasks)
    except (web.GracefulExit, KeyboardInterrupt):
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        if "--webonly" not in sys.argv:
            await server.Twitch_cleanup()
            if "--nodiscord" not in sys.argv:
                await server.Discord_cleanup()
        loop.close()

asyncio.run(main()) # TODO: Signal handlers and stuff
