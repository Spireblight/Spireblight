"""Contain all the configuration as classes.

This allows proper type hinting and autocomplete."""

from __future__ import annotations

from src.exceptions import InvalidConfigType

class _ConfigMapping:
    def update(self, mapping: dict):
        """Update the configuration with user config.

        :param mapping: The decoded YAML mapping of configuration.
        :type mapping: dict
        :raises InvalidConfigType: If the user config gives a wrong value type.
        """
        for k, v in mapping.items():
            exp = getattr(self, k)
            match exp:
                case _ConfigMapping(): # another level down
                    if not isinstance(v, dict): # dicts should always result in another class
                        raise InvalidConfigType(self, k, dict)
                    exp.update(v)
                case list():
                    if not isinstance(v, list):
                        raise InvalidConfigType(self, k, list)
                    for item in v:
                        if item not in exp:
                            exp.append(item)
                case int():
                    if not isinstance(v, int):
                        try:
                            v = int(v) # if it's e.g. a str of an int, allow it
                        except ValueError:
                            raise InvalidConfigType(self, k, int)
                    setattr(self, k, v)
                case str():
                    if not isinstance(v, str):
                        raise InvalidConfigType(self, k, str)
                    setattr(self, k, v)
                case a:
                    raise RuntimeError(f"Config has unsupported type {a.__class__.__name__!r} (this is a bug).")

class Config(_ConfigMapping):
    def __init__(self, twitch: dict, discord: dict, youtube: dict, baalorbot: dict, server: dict, spotify: dict):
        """Hold all of the configuration data.

        :param twitch: A mapping to be passed to :class:`Twitch`.
        :type twitch: dict
        :param discord: A mapping to be passed to :class:`Discord`.
        :type discord: dict
        :param youtube: A mapping to be passed to :class:`YouTube`.
        :type youtube: dict
        :param baalorbot: A mapping to be passed to :class:`Bot`.
        :type baalorbot: dict
        :param server: A mapping to be passed to :class:`Server`.
        :type server: dict
        :param spotify: A mapping to be passed to :class:`Spotify`.
        :type spotify: dict
        """

        self.twitch = Twitch(**twitch)
        self.discord = Discord(**discord)
        self.youtube = YouTube(**youtube)
        self.baalorbot = Bot(**baalorbot) # XXX: Rename this

class Twitch(_ConfigMapping):
    def __init__(self, channel: str, oauth_token: str, *, enabled: bool = True, extended: dict, timers: dict):
        """Handle the Twitch aspect of the configuration.

        :param channel: The channel name to connect to.
        :type channel: str
        :param oauth_token: The OAuth token of the account to use.
        :type oauth_token: str
        :param enabled: Whether to use the Twitch connection, defaults to True.
        :type enabled: bool, optional
        :param extended: A mapping that will be used for Extended OAuth.
        :type extended: dict
        :param timers: A mapping that will be used for timer interval.
        :type timers: dict
        """

        self.channel = channel
        self.enabled = enabled
        self.oauth_token = oauth_token

        self.extended = _TwitchExtendedOAuth(**extended)

        self.timers = _TimerIntervals(**timers)

class _TwitchExtendedOAuth(_ConfigMapping):
    def __init__(self, client_id: str, client_secret: str, scopes: list[str] | None = None, *, enabled: bool = False):
        """Create an Extended OAuth mapping.

        If this is used, we will be using the full Authorization Grant Flow.
        This needs the streamer to accept the connection, and then the
        client ID and secret stored here will no longer be needed.

        :param client_id: The publicly-available Client ID.
        :type client_id: str
        :param client_secret: The Twitch app Client Secret.
        :type client_secret: str
        :param scopes: a list of the scopes requested, defaults to None.
        :type scopes: list[str] | None, optional
        :param enabled: Whether we use Extended OAuth, defaults to False.
        :type enabled: bool, optional
        """

        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes or []
        self.enabled = enabled

class _TimerIntervals(_ConfigMapping):
    def __init__(self, default_interval: int, stagger_interval: int):
        """Hold timer interval information.

        :param default_interval: The default interval for newly-created timers.
        :type default_interval: int
        :param stagger_interval: The start time between different timers at startup.
        :type stagger_interval: int
        """

        self.default_interval = default_interval
        self.stagger_interval = stagger_interval

class Discord(_ConfigMapping):
    def __init__(self, server_id: int, moderator_role: int, oauth_token: str, invite_links: dict, *, enabled: bool = True):
        """Handle the Discord side of the configuration.

        :param server_id: The server ("Guild") ID where we will operate.
        :type server_id: int
        :param moderator_role: The user role which is considered to be a moderator.
        :type moderator_role: int
        :param oauth_token: The OAuth token needed to connect to Discord.
        :type oauth_token: str
        :param invite_links: A mapping of the various Discord invite links we have.
        :type invite_links: dict
        :param enabled: Whether the Discord part is enabled, defaults to True.
        :type enabled: bool, optional
        """

        self.server_id = server_id
        self.moderator_role = moderator_role
        self.oauth_token = oauth_token
        self.enabled = enabled

        self.invite_links = _InviteLinks(**invite_links)

class _InviteLinks(_ConfigMapping):
    def __init__(self, main: str, dev: str):
        """The various Discord invite links we have.

        :param main: The invite link to the main streamer server.
        :type main: str
        :param dev: The invite link to the development (i.e. Spireblight) server.
        :type dev: str
        """
        self.main = main
        self.dev = dev

class YouTube(_ConfigMapping):
    def __init__(self, channel_id: str, default_video: str, archive_id: str, api_key: str, cache_timeout: int, playlist_sheet: str):
        """Store the YouTube configuration.

        :param channel_id: The main channel ID used when searching.
        :type channel_id: str
        :param default_video: The fallback video ID to use if none is found (likely due to a dev environment).
        :type default_video: str
        :param archive_id: The channel ID where the archives/VODs are located.
        :type archive_id: str
        :param api_key: The API key needed to query YouTube.
        :type api_key: str
        :param cache_timeout: The maximum time, in seconds, where we cache call results.
        :type cache_timeout: int
        :param playlist_sheet: The sheet with links for the YouTube playlists, in CSV format.
        :type playlist_sheet: str
        """

        self.channel_id = channel_id
        self.default_video = default_video
        self.archive_id = archive_id
        self.api_key = api_key
        self.cache_timeout = cache_timeout
        self.playlist_sheet = playlist_sheet

class Bot(_ConfigMapping):
    def __init__(self, prefix: str, owners: list[int], editors: list[int]):
        """Hold the bot config information

        :param prefix: The prefix to identify that something is a command.
        :type prefix: str
        :param owners: A list of Discord user IDs who are owner(s) of the bot.
        :type owners: list[int]
        :param editors: A list of Discord user IDs who are editors for the channel.
        :type editors: list[int]
        """

        self.prefix = prefix

        # both of these will eventually be split into discord/twitch
        self.owners = owners
        self.editors = editors

class Server(_ConfigMapping):
    def __init__(self, secret: str):
        pass
