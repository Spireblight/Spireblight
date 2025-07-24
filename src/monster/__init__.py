from src.events import add_listener

from src.monster.static import *
from src.monster.server import *

@add_listener("setup_init")
async def initial_load():
    load_mt1()
    load_mt2()
