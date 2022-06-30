import logging
import asyncio
import sys

if "--debug" in sys.argv:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="{asctime} :: {levelname}:{name} - {message}", datefmt="(%Y-%m-%d %H:%M:%S)", style="{")

from aiohttp import web

from webpage import webpage, router, setup_redirects
from logger import logger

import server, runs

logger.info("Starting the bot")

async def main():
    setup_redirects()
    webpage.add_routes(router)
    loop = asyncio.get_event_loop()

    tasks = set()

    import sys
    if "--webonly" not in sys.argv:
        tasks.add(loop.create_task(server.Twitch_startup()))
        tasks.add(loop.create_task(server.Discord_startup()))

    tasks.add(loop.create_task(web._run_app(webpage)))

    try:
        await asyncio.gather(*tasks)
    except (web.GracefulExit, KeyboardInterrupt):
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        await server.Twitch_cleanup()
        await server.Discord_cleanup()
        loop.close()

asyncio.run(main()) # TODO: Signal handlers and stuff
