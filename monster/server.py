from aiohttp.web import Request, Response

from webpage import router

@router.post("/sync/monster")
async def get_data(req: Request):
    return Response()
