from __future__ import annotations

from typing import Optional

from dataclasses import dataclass, asdict
from aiohttp import ClientSession

import datetime
import asyncio
import json
import os
import re

from configuration import config
from events import add_listener
from utils import getfile
from runs import get_parser

_date_re = re.compile(r"(\d\d\d\d\-\d\d\-\d\d)")

archive: ArchiveHandler = None

@dataclass
class VideoMetadata:
    """Hold YouTube video metadata."""
    id: str
    title: str
    duration: int
    description: str

class Run:
    """Contain run offset information from a vod."""
    def __init__(self, id: str, start: int, offset: int):
        self.id = id
        self.start = start
        self.offset = offset

    def to_json(self):
        return {"id": self.id, "start": self.start, "offset": self.offset}

    @property
    def run(self):
        return get_parser(self.id)

class VOD:
    """Information from a stream vod with optional run information."""
    def __init__(self, id: str, runs: Optional[list[Run]] = None):
        self.id = id
        self.runs = runs or []
        self.data: VideoMetadata = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, value):
        return isinstance(value, VOD) and value.id == self.id

    def to_json(self):
        return {**self.data.__dict__, "runs": self.runs}

    def add_run(self, run: Run):
        self.runs.append(run)

    @property
    def datetime(self):
        matched = _date_re.search(self.data.title)
        if matched is None:
            return None
        return datetime.datetime.fromisoformat(matched.group())

# JSON architecture

_internal = [
    {
        "id": "11-character ID for the VOD",
        "title": "video title",
        "duration": 3600, # duration of the vod, in seconds
        "description": "video description",
        "runs": [ # can be empty
            {
                "id": "name of the run as in url/runs/RUN, usually a UNIX timestamp",
                "start": 1800, # the calculated start offset for the run
                "offset": 0, # user-submitted offset from 'start'
            }
        ],
    }
]

class ArchiveHandler:
    """Handle archive maintenance."""
    def __init__(self, filename: str, channel_id: str, api_key: str):
        self.vods = set()
        self.unparsed = set()
        self._session: Optional[ClientSession] = None

        self._filename = filename
        self._channel_id = channel_id
        self._key = api_key

    @property
    def cached(self):
        return os.path.isfile(os.path.join("data", self._filename))

    def load_from_disk(self):
        """Load video information from disk."""
        self.vods.clear()
        with getfile(self._filename, "r") as f:
            j = json.load(f)
        for vod in j:
            runs = []
            for run in vod["runs"]:
                runs.append(Run(**run))
            self.vods.add(VOD(vod["id"], runs))

    def write_to_disk(self):
        """Write all the vod information to disk."""
        with getfile(self._filename, "w") as f:
            json.dump(list(self.vods - self.unparsed), f, default=lambda x: x.to_json())

    async def load_from_api(self) -> bool:
        """Fetch VOD information from YouTube. Return True if it succeeded."""
        search_params = {
            "part": "id", 
            "order": "date",
            "maxResults": 50,
            "channelId": self._channel_id,
            "key": self._key,
        }

        if self._session is None:
            self._session = ClientSession("https://youtube.googleapis.com/youtube/v3")

        while True:
            search_resp = None
            async with self._session.get("/search", params=search_params) as resp:
                search_resp = await resp.json()

            if not search_resp:
                return False

            # get metadata and save it in a VideoMetadata file
            for item in search_resp["items"]:
                info = item.get("id")
                if info is None or not (c := info.get("videoId")):
                    continue

                vod = VOD(c)
                if vod in self.vods:
                    return True # we already have this one, so anything after this is older and we have it

                video_resp = None
                async with self._session.get("/videos", params={"part": "snippet,contentDetails", "id": c, "key": self._key}) as resp:
                    video_resp = await resp.json()

                if not video_resp:
                    return False
                
                video_info = video_resp["items"][0]
                snippet = video_info["snippet"]
                if not _date_re.search(snippet["title"]): # doesn't have a date in the title, not a vod
                    continue
                duration: str = video_info["contentDetails"]["duration"][2:-1] # string in the format PT#H#M#S; remove PT and S
                hours, H, rest = duration.partition("H")
                if not H: # if it's <1 hour
                    hours, rest = "", hours
                minutes, M, seconds = rest.partition("M")
                total_minutes = int(hours or 0) * 60 + int(minutes or 0)
                total_seconds = total_minutes * 60 + int(seconds or 0)
                vod.data = VideoMetadata(c, snippet["title"], total_seconds, snippet["description"])

                self.vods.add(vod)
                self.unparsed.add(vod)


archive = ArchiveHandler("archive.json", config.youtube.archive_id, config.youtube.api_key)



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
