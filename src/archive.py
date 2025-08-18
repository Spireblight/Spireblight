import datetime
import asyncio
import json
import os
import re

from typing import Optional

from configuration import config
from dataclasses import dataclass, asdict
from aiohttp import ClientSession
from events import add_listener
from utils import getfile
from runs import get_parser

_api_base = "https://youtube.googleapis.com/youtube/v3"
_date_re = re.compile(r"(\d\d\d\d\-\d\d\-\d\d)")

_vods = []

@dataclass
class VideoMetadata:
    id: str
    title: str
    duration: int
    description: str

class VOD:
    def __init__(self, data: VideoMetadata):
        self._data = data
        self.runs = []

    @property
    def datetime(self):
        matched = _date_re.search(self._data.title)
        if matched is None:
            return None
        return datetime.datetime.fromisoformat(matched.group())

# JSON architecture

_internal = [
    {
        "id": "11-character ID for the VOD",
        "runs": [ # can be empty
            {
                "run": "name of the run as in /runs/RUN, usually a UNIX timestamp",
                "start": 1800, # the calculated start offset for the run
                "offset": 0, # user-submitted offset from 'start'
            }
        ],
    }
]

async def archive_setup():
    try:
        with getfile("archive.json", "r") as f:
            pass
    except FileNotFoundError:
        pass






# old code by zanzan


class YoutubeArchive:
    _cache: list[VideoMetadata]

    def __init__(self, filename: str, channel_id: str, api_key: str):
        self._filename = filename
        self._channel_id = channel_id
        self._api_key = api_key
        self._session: Optional[ClientSession] = None

        self._cache = []

        self._reload_cache()

    @property
    def archive(self):
        return self._cache

    def _reload_cache(self):
        if not os.path.isfile(self._filename):
            return

        with open(self._filename, "r") as json_raw:
            loaded = json.load(json_raw)

            cache = []
            for raw in loaded:
                cache.append(VideoMetadata(**raw))
            self._cache = cache

    async def _sync_archive(self):
        new_videos = []

        async with ClientSession() as session:
            search_params = {
                "part": "id", 
                "order": "date",
                "maxResults": 50,
                "channelId": self._channel_id,
                "key": self._api_key,
            }

            has_new = True
            while has_new:
                # Get the next page of videos.
                search_resp = {}
                async with session.get(f"{_api_base}/search", params=search_params) as resp:
                    resp_raw = await resp.text()
                    search_resp = json.loads(resp_raw)

                # For each video, request the metadata.
                for item in search_resp["items"]:
                    id = item.get("id", {}).get("videoId", "")
                    if id == "":
                        continue

                    if any(old.id == id for old in self._cache):
                        has_new = False
                        break

                    video_resp = {}
                    async with session.get(f"{_api_base}/videos", params={"part": "snippet,contentDetails", "id": id, "key": self._api_key}) as resp:
                        resp_raw = await resp.text()
                        video_resp = json.loads(resp_raw)

                    video_info = video_resp["items"][0]
                    snippet = video_info["snippet"]
                    # XXX
                    duration = isodate.parse_duration(video_info["contentDetails"]["duration"]).total_seconds()
                    new_videos.append(VideoMetadata(id, snippet["title"], duration, snippet["description"]))

                # Go to the next page, or stop.
                next_token = search_resp.get("nextPageToken", "")
                if not next_token:
                    has_new = False
                search_params["pageToken"] = next_token

        if len(new_videos) > 0:
            new_videos.extend(self._cache)
            self._cache = new_videos
            with open(self._filename, "w") as f:
                json.dump([asdict(metadata) for metadata in self._cache], f, ensure_ascii=False, indent=4)

_global_Youtube_Archive = YoutubeArchive("", "", "")

def Global_Youtube_Archive():
    return _global_Youtube_Archive

async def Refresh_Global_Youtube_Archive():
    global _global_Youtube_Archive 
    _global_Youtube_Archive = YoutubeArchive("./data/youtube_archive.json", config.youtube_archive.channel_id, config.youtube_archive.api_key)

    # Reload the cache at the start, then every hour.
    while True:
        await _global_Youtube_Archive._sync_archive()
        await asyncio.sleep(60*60)
