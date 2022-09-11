import json
from dataclasses import dataclass
from os import path
from typing import List


@dataclass(frozen=True)
class Config:
    token: str
    oauth: str
    prefix: str
    API_key: str
    YT_channel_id: str
    channel: str
    editors: List[str]
    website_url: str
    secret: str
    json_indent: int
    cache_timeout: int
    default_video_id: str
    STS_path: str
    global_interval: int
    global_commands: List[str]
    sponsored_interval: int
    sponsored_commands: List[str]
    discord_servid: str
    discord_invite_link: str
    client_id: str
    client_secret: str
    webhook_secret: str
    moderator_role: str
    owners: List[str]
    website_bg: str

    @staticmethod
    def from_file(fileName: str) -> 'Config':
        jsonStr = "{}"
        if path.isfile(fileName):
            with open(fileName) as fileContents:
                jsonStr = fileContents.read()
        return Config.from_jsons(jsonStr)

    @staticmethod
    def from_jsons(jsonStr: str) -> 'Config':
        jsonConfig = json.loads(jsonStr)
        _token = str(jsonConfig.get("token") or "")
        _oauth = str(jsonConfig.get("oauth") or "")
        _prefix = str(jsonConfig.get("prefix") or "")
        _API_key = str(jsonConfig.get("API_key") or "")
        _YT_channel_id = str(jsonConfig.get("YT_channel_id") or "")
        _channel = str(jsonConfig.get("channel") or "")
        _editors = [str(y) for y in jsonConfig.get("editors") or []]
        _website_url = str(jsonConfig.get("website_url") or "")
        _secret = str(jsonConfig.get("secret") or "")
        _json_indent = int(jsonConfig.get("json_indent") or 0) 
        _cache_timeout = int(jsonConfig.get("cache_timeout") or 0)
        _default_video_id = str(jsonConfig.get("default_video_id") or "")
        _STS_path = str(jsonConfig.get("STS_path") or "")
        _global_interval = int(jsonConfig.get("global_interval") or 0)
        _global_commands = [str(y) for y in jsonConfig.get("global_commands") or []]
        _sponsored_interval = int(jsonConfig.get("sponsored_interval") or 0)
        _sponsored_commands = [str(y) for y in jsonConfig.get("sponsored_commands") or []]
        _discord_servid = str(jsonConfig.get("discord_servid") or "")
        _discord_invite_link = str(jsonConfig.get("discord_invite_link") or "")
        _client_id = str(jsonConfig.get("client_id") or "")
        _client_secret = str(jsonConfig.get("client_secret") or "")
        _webhook_secret = str(jsonConfig.get("webhook_secret") or "")
        _moderator_role = str(jsonConfig.get("moderator_role") or "")
        _owners = [str(y) for y in jsonConfig.get("owners") or []]
        _website_bg = str(jsonConfig.get("website_bg") or "")
        return Config(_token, _oauth, _prefix, _API_key, _YT_channel_id, 
        _channel, _editors, _website_url, _secret, _json_indent, _cache_timeout, 
        _default_video_id, _STS_path, _global_interval, _global_commands, _sponsored_interval, 
        _sponsored_commands, _discord_servid, _discord_invite_link, _client_id, _client_secret,
        _webhook_secret, _moderator_role, _owners, _website_bg)

global_config = Config.from_file("config.json")