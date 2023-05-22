import json

from aiohttp.web import Request, Response

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
