import json
import os

from typehints import ContextType


class BrotatoSave:
    def __init__(self):
        data = None
        try:
            with open(os.path.join("data", "brotato-save.json"), "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self._data = data

    def update_data(self, data: dict):
        self._data = data


_savefile = BrotatoSave()


async def get_savefile(ctx: ContextType | None = None) -> BrotatoSave:
    # Check if in a run, shortcut reply if not:
    if _savefile._data is None or not _savefile.potato:
        if ctx is not None:
            await ctx.reply("Not in a run.")
        return

    return _savefile

