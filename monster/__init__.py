from events import add_listener

from monster.static import *

@add_listener("setup_init")
async def initial_load():
    load()
