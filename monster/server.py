import json
import os

from aiohttp.web import Request, Response, HTTPServiceUnavailable, FileField

from monster.static import get_safe
from webpage import router
from logger import logger
from utils import get_req_data

from typehints import ContextType

from configuration import config

class MonsterSave:
    def __init__(self):
        data = None
        try:
            with open(os.path.join("data", "monster-train-save.json"), "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self._data = data

    def update_data(self, data: dict):
        self._data = data

    @property
    def main_class(self) -> str:
        return self._data["startingConditions"]["mainClassInfo"]["className"]

    @property
    def sub_class(self) -> str:
        return self._data["startingConditions"]["subclassInfo"]["className"]

_savefile = MonsterSave()

async def get_savefile(ctx: ContextType | None = None) -> MonsterSave:
    if _savefile._data is None or not (_savefile.main_class and _savefile.sub_class):
        if ctx is not None:
            await ctx.reply("Not in a run.")
        return

    return _savefile

@router.post("/sync/monster")
async def get_data(req: Request): # lots of logging is temporary
    print("Monster Train syncing.")
    try:
        save = (await get_req_data(req, "save"))[0]
    except Exception as e:
        import traceback
        traceback.print_exception(e)
        raise
    data = json.loads(save)
    print("Data parsed.")
    _savefile.update_data(data)
    print("Data loaded.")
    with open(os.path.join("data", "monster-train-save.json"), "w") as f:
        json.dump(data, f, indent=config.server.json_indent)
        print("Data saved to disk.")

    print("Grabbing run files.")
    # handle database stuff
    post = await req.post()
    print("Post grabbed. Writing to disk.")

    def write_db(name: str):
        print(f"Writing {name} to disk.")
        value = post[name]
        if isinstance(value, FileField):
            value = value.file.read()
        with open(os.path.join("data", f"mt-runs-{name}.sqlite3"), "wb") as f:
            f.write(value)
            print("Wrote to disk.")

    for k in post:
        if k == "main" or k.isdigit() or k.endswith(".db"):
            write_db(k)

    print("Done, returning 200.")
    return Response()

@router.get("/mt/debug")
async def mt_current(req: Request):
    if _savefile._data is None:
        raise HTTPServiceUnavailable(reason="No savefile present on server")
    data = _savefile._data
    if "raw" not in req.query:
        data = _get_sanitized(data)
    return Response(text=json.dumps(data, indent=4), content_type="application/json")

def _get_sanitized(x):
    match x:
        case str():
            return get_safe(x)
        case list():
            return [_get_sanitized(a) for a in x]
        case dict():
            return {k: _get_sanitized(v) for k,v in x.items()}
        case _:
            return x
