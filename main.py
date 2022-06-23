import asyncio

from aiohttp import web

from webpage import webpage, router, setup_redirects
from logger import logger

import server, commands, save # just make sure they're imported

logger.info("Starting the bot")

async def main():
    setup_redirects()
    webpage.add_routes(router)
    loop = asyncio.get_event_loop()

    tasks = set()

    import sys
    if "--webonly" not in sys.argv:
        tasks.add(loop.create_task(server.Twitch_startup()))
        #tasks.add(loop.create_task(server.Discord_startup()))

    tasks.add(loop.create_task(web._run_app(webpage)))

    try:
        await asyncio.gather(*tasks)
    except (web.GracefulExit, KeyboardInterrupt):
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        await server.Twitch_cleanup()
        #await server.Discord_cleanup()
        loop.close()

asyncio.run(main()) # XXX: figure out why Discord doesn't see anything?
