from events import add_listener

from brotato.server import *


@add_listener("setup_init")
async def initial_load():
    load()

