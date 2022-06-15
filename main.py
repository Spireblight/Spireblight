from aiohttp import web

from webpage import webpage, router
from logger import logger

logger.info("Starting the bot")

webpage.add_routes(router)

web.run_app(webpage)
