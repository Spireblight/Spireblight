from __future__ import annotations

from typing import Optional

from dataclasses import dataclass
from aiohttp import ClientSession

import datetime
import json
import os
import re

from src.config import config
from src.events import add_listener
from src.utils import getfile
from src.runs import get_parser, RunParser, _cache

_date_re = re.compile(r"(\d\d\d\d\-\d\d\-\d\d)")
_chapter_re = re.compile(r"^(\d\d?):(\d\d):(\d\d) Slay the Spire \- (\w+)$")

archive: _ArchiveHandler = None

@dataclass
class VideoMetadata:
    """Hold YouTube video metadata."""
    id: str
    title: str
    duration: int
    description: str

class Run:
    """Contain run offset information from a vod."""
    def __init__(self, run: RunParser, start: int, vod: VOD):
        self.run = run
        self.start = start
        self.vod = vod

    def __repr__(self):
        return f"ArchiveRun<{self.run}>"

    def to_json(self):
        return {"id": self.run.name, "start": self.start}

    def get_url(self):
        ts = ""
        if self.start > 5: # don't timestamp if it's at the start
            ts = f"?t={self.start}"
        return f"https://youtu.be/{self.vod.id}{ts}"

class VOD:
    """Information from a stream vod with optional run information."""
    def __init__(self, id: str):
        self.id = id
        self.runs: list[Run] = []
        self.data: VideoMetadata = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, value):
        return (
            (isinstance(value, VOD) and value.id == self.id) or
            (isinstance(value, str) and value == self.id)
        )

    def to_json(self):
        return {**self.data.__dict__, "runs": self.runs}

    def get_offsets(self):
        """Return a mapping of offset to character played."""
        final: list[tuple[int, str]] = []
        for line in self.data.description.splitlines():
            if (c := _chapter_re.match(line)):
                h, m, s, char = c.groups()
                minutes = int(m)
                minutes += int(h) * 60
                seconds = int(s) + minutes * 60
                final.append( (seconds, char) )

        return final

    @property
    def datetime(self):
        matched = _date_re.search(self.data.title)
        if matched is None:
            return None
        return datetime.datetime.fromisoformat(matched.group())

class _ArchiveHandler:
    """Handle archive maintenance.

    :meta public:"""
    def __init__(self, filename: str, channel_id: str, api_key: str):
        self.vods: set[VOD] = set()
        self.unparsed: dict[datetime.date, list[VOD]] = {}
        self.errored: list[VOD] = [] #: For the VODs with Spire that no run matches, somehow
        self._session: Optional[ClientSession] = None

        self._filename = filename
        self._channel_id = channel_id
        self._key = api_key

    @property
    def cached(self):
        """Whether we have cached data on the run VOD information."""
        return os.path.isfile(os.path.join("data", self._filename))

    def load_from_disk(self):
        """Load video information from disk."""
        try:
            with getfile(self._filename, "r") as f:
                j = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            j = []
        else: # only clear if we can parse the on-disk data
            self.vods.clear()
        for vod in j:
            v = VOD(vod["id"])
            for run in vod["runs"]:
                r = get_parser(run["id"])
                r.vod = v
                v.runs.append(Run(r, run["start"], v))
            v.data = VideoMetadata(vod["id"], vod["title"], vod["duration"], vod["description"])
            self.vods.add(v)

        try:
            with getfile("unmatched_" + self._filename, "r") as f:
                j = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            j = []
        else:
            self.errored.clear()
        for vod in j:
            v = VOD(vod["id"])
            v.data = VideoMetadata(vod["id"], vod["title"], vod["duration"], vod["description"])
            self.errored.append(v)

    def write_to_disk(self):
        """Write all the vod information to disk."""
        with getfile(self._filename, "w") as f:
            json.dump(list(self.vods - self.unparsed.keys()), f, default=lambda x: x.to_json())
        with getfile("unmatched_" + self._filename, "w") as f:
            json.dump(self.errored, f, default=lambda x: x.to_json())

    def determine_offset(self):
        """Determine the run offset from the start of the vod."""
        if not self.unparsed: # no need to determine anything
            return
        res: dict[VOD, list[RunParser]] = {}
        # map all the vods to the runs that match
        for run in _cache.values():
            if (d := run.timestamp.date()) in self.unparsed:
                for vod in self.unparsed[d]:
                    if vod not in res:
                        res[vod] = []
                    res[vod].append(run)

        # check to make sure all the vods with Spire were mapped to run(s)
        # some will not have runs, check to make sure there was no Spire
        spireless: list[VOD] = []
        for vods in self.unparsed.values():
            for vod in vods:
                if vod not in res:
                    spireless.append(vod)

        self.unparsed.clear()
        while spireless:
            vod = spireless.pop(0)
            if vod.get_offsets(): # has Spire info
                self.errored.append(vod)
            else:
                self.vods.remove(vod)

        for vod, runs in res.items():
            runs.sort(key=lambda x: x.timestamp)
            final_runs: list[Run] = []
            offsets = vod.get_offsets()
            if len(offsets) != len(runs): # ach no!
                # it could be because the vod is split in multiple parts
                # we could (probably) figure it out, but I'll just save it to disk
                # I can figure it out later or something, idk
                # - Faely, 2025-08-22
                self.errored.append(vod)
                continue # :(

            for run, (offset, char) in zip(runs, offsets):
                if run.character == char:
                    final_runs.append(Run(run, offset, vod))
                    run.vod = vod

            vod.runs.extend(final_runs)

    async def load_from_api(self) -> bool:
        """Fetch VOD information from YouTube. Return True if it succeeded."""
        search_params = {
            "part": "snippet",
            "maxResults": 50,
            "playlistId": "UU" + self._channel_id[2:], # easy
            "key": self._key,
        }
        video_params = {
            "part": "contentDetails",
            "maxResults": 50,
            "key": self._key,
            "id": "",
        }

        if self._session is None:
            self._session = ClientSession("https://youtube.googleapis.com/youtube/v3/")


        all_videos: dict[str, tuple[str, str]] = {}
        while True:
            next_token = None
            search_resp = None
            async with self._session.get("playlistItems", params=search_params) as resp:
                if resp.ok:
                    search_resp: dict = await resp.json()

            if not search_resp:
                return False

            for item in search_resp["items"]:
                snippet = item.get("snippet")
                if snippet is None:
                    continue # ??

                vid = snippet["resourceId"]["videoId"]
                if vid in self.vods: # we already have it, no need to query further
                    break

                all_videos[vid] = (snippet["title"], snippet["description"])
            else: # did not break out of it, so we continue
                next_token = search_resp.get("nextPageToken")

            if not next_token:
                break
            search_params["pageToken"] = next_token

        start = 0
        end = 50
        av = list(all_videos)
        while True:
            lst = video_params["id"] = av[start:end]
            if not lst:
                break
            video_resp = None
            async with self._session.get("videos", params=video_params) as resp:
                if resp.ok:
                    video_resp: dict = await resp.json()

            if not video_resp:
                return False

            for item in video_resp["items"]:
                c = item["id"]
                title, description = all_videos[c]
                vod = VOD(c)
                if vod in self.vods:
                    return True # we already have this one, so anything after this is older and we have it

                if not _date_re.search(title): # doesn't have a date in the title, not a vod
                    continue
                duration: str = item["contentDetails"]["duration"][2:-1] # string in the format PT#H#M#S; remove PT and S
                hours, H, rest = duration.partition("H")
                if not H: # if it's <1 hour
                    hours, rest = "", hours
                minutes, M, seconds = rest.partition("M")
                total_minutes = int(hours or 0) * 60 + int(minutes or 0)
                total_seconds = total_minutes * 60 + int(seconds or 0)
                vod.data = VideoMetadata(c, title, total_seconds, description)

                self.vods.add(vod)
                date = vod.datetime.date()
                if date not in self.unparsed:
                    self.unparsed[date] = []
                self.unparsed[date].append(vod)

            start = end
            end += 50

        return True


archive = _ArchiveHandler("archive.json", config.youtube.archive_id, config.youtube.api_key)
