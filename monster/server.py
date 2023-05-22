import json

from aiohttp.web import Request, Response, HTTPNotFound

from monster.static import get_safe
from webpage import router
from utils import get_req_data

class MonsterSave:
    def __init__(self):
        self._data = None

    def update_data(self, data: dict):
        self._data = data

    @property
    def main_class(self) -> str:
        return self._data["startingConditions"]["mainClassInfo"]["className"]

    @property
    def sub_class(self) -> str:
        return self._data["startingConditions"]["subclassInfo"]["className"]

_savefile = MonsterSave()

@router.post("/sync/monster")
async def get_data(req: Request):
    save = (await get_req_data(req, "save"))[0]
    data = json.loads(save)
    _savefile.update_data(data)
    return Response()

@router.get("/mt/debug")
async def mt_current(req: Request):
    if _savefile._data is None:
        raise HTTPNotFound(reason="No savefile present on server")
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
