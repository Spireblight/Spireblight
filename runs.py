from typing import Any

from aiohttp.web import Request

from webpage import router

from gamedata import get_nodes

class RunParser: # TODO: cache
    def __init__(self, data: dict[str, Any]):
        self.data = data

    def __getitem__(self, item: str) -> Any:
        return self.data[item]

    @property
    def won(self) -> bool:
        return self.data["victory"]

    @property
    def killed_by(self) -> str:
        return self.data.get("killed_by")

    @property
    def path(self):
        return get_nodes(self)

@router.post("/sync/run")
async def receive_run(req: Request):
    pass
