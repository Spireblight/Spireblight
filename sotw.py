from aiohttp.web import HTTPFound, Request, Response
import aiohttp_jinja2

from webpage import router

placeholder = None

@router.get("/seedoftheweek")
@router.get("/sotw")
async def _sotw_redirect(req: Request):
    raise HTTPFound("/seed-of-the-week")

# TODO: Query the spreadsheet for all the data asukii is putting in

@router.get("/seed-of-the-week")
@aiohttp_jinja2.template("sotw.jinja2")
async def sotw(req: Request):
    return {}

@router.post("/sotw/submit-run")
async def get_run(req: Request):
    pass