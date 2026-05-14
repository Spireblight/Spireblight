"""Port the data missing from Slaytabase"""

from aiohttp import ClientSession

import asyncio
import pathlib
import json

from src import nameinternal # this should not have a cascading effect..... hopefully

# It is very difficult to compare what's old and new
# because the data are in slightly different formats,
# but the goal is to have a script we can run after
# every beta patch to just dump the difference into
# the stb_missing.json file. I'm sure someone smarter
# than me (maybe future me?) can figure it out. Using
# something like difflib doesn't work since they all
# went through Ocean's script which changes the data
# to be more human-readable. - Faely, 2026/05/14

async def export():
    file = pathlib.Path("C:") / "Program Files (x86)" / "Steam" / "steamapps" / "common" / "Slay the Spire 2" / "export" / "items.json"
    out = pathlib.Path(".") / "argo" / "misc" / "stb_missing_2.json"
    client = ClientSession()

    cur_data = await nameinternal.fetch_mod_data(client, "2-slay the spire 2")

    with file.open() as f:
        new_data: dict = json.load(f)

    diff = {}

    for key, values in new_data.items():
        oldv = cur_data[key]
        for d in values:
            cid = d["id"]



if __name__ == "__main__":
    asyncio.run(export())
