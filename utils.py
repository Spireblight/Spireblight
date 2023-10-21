from datetime import datetime
from typing import Any
from aiohttp.web import Request, HTTPNotImplemented, HTTPForbidden, HTTPUnauthorized, FileField

import os
import json

from configuration import config

__all__ = ["get_req_data", "getfile", "update_db"]

async def get_req_data(req: Request, *keys: str) -> list[str]:
    pw = req.query.get("key")
    if pw is None:
        raise HTTPUnauthorized(reason="No API key provided")
    if not config.server.secret:
        raise HTTPNotImplemented(reason="No API key present in config")
    if pw != config.server.secret:
        raise HTTPForbidden(reason="Invalid API key provided")

    post = await req.post()

    res = []

    for key in keys:
        value = post.get(key)
        if isinstance(value, FileField):
            value = value.file.read()
        if isinstance(value, bytes):
            value = value.decode("utf-8", "xmlcharrefreplace")
        res.append(value)

    return res

def getfile(x: str, mode: str):
    return open(os.path.join("data", x), mode)

def update_db():
    from server import _cmds
    with getfile("data.json", "w") as f:
        json.dump(_cmds, f, indent=config.server.json_indent)

def convert_class_to_obj(obj: Any) -> dict[str, Any]:
    return vars(obj)

def format_for_slaytabase(val: str) -> str:
    return val.replace(":", "-").replace("'", "").replace(" ", "").lower()

def parse_date_range(date_string: str) -> tuple[datetime]:
    """valid date strings: YYYY-MM-DD-YYYY-MM-DD (MM and DD optional), YYYY-MM-DD+ (no end date), YYYY-MM-DD- (no start date)"""
    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None
    if date_string[-1] == "+":
        start_date = _parse_dates_with_optional_month_day(date_string[:-1])
    elif date_string[-1] == "-":
        end_date = _parse_dates_with_optional_month_day(date_string[:-1], True)
    else:
        date_parts = date_string.split("-")
        if len(date_string) == 4 and len(date_parts) == 1:
            # only a year was passed, default to Jan 1 - Dec 31 of the specified year
            return (datetime(int(date_parts[0]), 1, 1), datetime(int(date_parts[0]), 12, 31, 23, 59, 59))
        second_date_start = -1
        for i, s in enumerate(date_parts):
            if len(s) == 4 and i != 0: # year
                second_date_start = i
        if second_date_start == -1:
            raise TypeError("Range format was invalid")

        start_date_string = "-".join(date_parts[:second_date_start])
        end_date_string = "-".join(date_parts[second_date_start:])
        start_date = _parse_dates_with_optional_month_day(start_date_string)
        end_date = _parse_dates_with_optional_month_day(end_date_string, True)
    return (start_date, end_date)


def _parse_dates_with_optional_month_day(val: str, isEndDate: bool = False) -> datetime:
    """Base val should be in YYYY-MM-DD where MM and DD are optional, defaulted to start or end of year"""
    date_parts = val.split("-")
    year = int(date_parts[0])
    month = 12 if isEndDate else 1
    day = 31 if isEndDate else 1
    if (len(date_parts) > 1):
        month = int(date_parts[1])
    if (len(date_parts) > 2):
        day = int(date_parts[2])
    if isEndDate:
        return datetime(year, month, day, hour=23, minute=59, second=59)
    else:
        return datetime(year, month, day)

