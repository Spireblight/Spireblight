"""Contain all the configuration as classes.

This allows proper type hinting and autocomplete."""

from __future__ import annotations

from src.exceptions import InvalidConfigType
from src.logger import logger

class _ConfigMapping:
    def update(self, mapping: dict):
        """Update the configuration with user config.

        :param mapping: The decoded YAML mapping of configuration.
        :type mapping: dict
        :raises InvalidConfigType: If the user config gives a wrong value type.
        """
        for k, v in mapping.items():
            try:
                exp = getattr(self, k)
            except AttributeError:
                logger.warning(f"No attribute {k!r} in the config.")
                continue
            match exp:
                case _ConfigMapping(): # another level down
                    if not isinstance(v, dict): # dicts should always result in another class
                        raise InvalidConfigType(self, k, dict)
                    exp.update(v)
                case list():
                    if isinstance(v, str):
                        v = [v]
                    try:
                        lst = list(v)
                    except TypeError:
                        raise InvalidConfigType(self, k, list)
                    for item in lst:
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
                case bool():
                    if not isinstance(v, bool):
                        raise InvalidConfigType(self, k, bool)
                    setattr(self, k, v)
                case a:
                    raise RuntimeError(f"Config has unsupported type {a.__class__.__name__!r} (this is a bug).")

class Config(_ConfigMapping):
    def __init__(self, twitch: dict, discord: dict, youtube: dict, bot: dict, server: dict, spotify: dict, **kwargs):
        """Hold all of the configuration data.

        :param twitch: A mapping to be passed to :class:`Twitch`.
        :type twitch: dict
        :param discord: A mapping to be passed to :class:`Discord`.
        :type discord: dict
        :param youtube: A mapping to be passed to :class:`YouTube`.
        :type youtube: dict
        :param bot: A mapping to be passed to :class:`Bot`.
        :type bot: dict
        :param server: A mapping to be passed to :class:`Server`.
        :type server: dict
        :param spotify: A mapping to be passed to :class:`Spotify`.
        :type spotify: dict
        """

        self.twitch = Twitch(**twitch)
        self.discord = Discord(**discord)
        self.youtube = YouTube(**youtube)
        self.bot = Bot(**bot)
        self.server = Server(**server)
        self.spotify = Spotify(**spotify)

        if kwargs:
            raise RuntimeError(f"Unrecognized config values: {', '.join(kwargs.keys())}")

class Twitch(_ConfigMapping):
    def __init__(self, channel: str, enabled: bool, editors: list[str], bot_id: int, owner_id: int, client_id: str, client_secret: str, scopes: list[str], timers: dict):
        """Handle the Twitch aspect of the configuration.

        :param channel: The channel name to connect to.
        :type channel: str
        :param enabled: Whether to use the Twitch connection.
        :type enabled: bool
        :param editors: A list of Twitch usernames who are editors for the channel.
        :type editors: list[str]
        :param bot_id: The user ID of the bot.
        :type bot_id: int
        :param owner_id: The user ID of the owner of the bot.
        :type owner_id: int
        :param client_id: The publicly-available Client ID.
        :type client_id: str
        :param client_secret: The Twitch app Client Secret.
        :type client_secret: str
        :param scopes: a list of the scopes requested, defaults to None.
        :type scopes: list[str] | None, optional
        :param timers: A mapping that will be used for timer interval.
        :type timers: dict
        """

        self._enabled = enabled

        self.channel = channel
        self.editors = editors

        self.bot_id = bot_id
        self.owner_id = owner_id

        self.client_id = client_id
        self.client_secret = client_secret

        self.scopes = scopes or []

        self.timers = _TimerIntervals(**timers)

    @property
    def enabled(self):
        if not (self.channel):
            return False
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

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
    def __init__(self, server_id: int, moderator_role: int, oauth_token: str, invite_links: dict, auto_report: dict, *, enabled: bool = True, owners: list[int]):
        """Handle the Discord side of the configuration.

        :param server_id: The server ("Guild") ID where we will operate.
        :type server_id: int
        :param moderator_role: The user role which is considered to be a moderator.
        :type moderator_role: int
        :param oauth_token: The OAuth token needed to connect to Discord.
        :type oauth_token: str
        :param invite_links: A mapping of the various Discord invite links we have.
        :type invite_links: dict
        :param auto_report: A mapping of the automatic report feature.
        :type auto_report: dict
        :param enabled: Whether the Discord part is enabled, defaults to True.
        :type enabled: bool, optional
        :param owners: A list of Discord user IDs who are owner(s) of the bot.
        :type owners: list[int]
        """

        self._enabled = enabled

        self.server_id = server_id
        self.moderator_role = moderator_role
        self.oauth_token = oauth_token

        self.invite_links = _InviteLinks(**invite_links)
        self.auto_report = _AutoReport(**auto_report)

        self.owners = owners

    @property
    def enabled(self):
        if not self.oauth_token:
            return False
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

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

class _AutoReport(_ConfigMapping):
    def __init__(self, server: int, channel: int, *, enabled: bool = False):
        """Hold automatic bug report information

        :param server: The server ID where the bot will report.
        :type server: int
        :param channel: The channel ID where the messages will go.
        :type channel: int
        :param enabled: If we use automatic reports, defaults to False.
        :type enabled: bool, optional
        """

        self._enabled = enabled

        self.server = server
        self.channel = channel

    @property
    def enabled(self):
        if not (self.server and self.channel):
            return False
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

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
    def __init__(self, prefix: str, name: str, spire_mods: list[str]):
        """Hold the bot config information

        :param prefix: The prefix to identify that something is a command.
        :type prefix: str
        :param name: The name that the bot will be referred by.
        :type name: str
        :param spire_mods: The Spire mods that the bot will know.
        :type spire_mods: list[str]
        """

        self.prefix = prefix
        self.name = name
        self.spire_mods = spire_mods

class Server(_ConfigMapping):
    def __init__(self, debug: bool, secret: str, url: str, host: str, port: int, json_indent: int, business_email: str, websocket_client: dict, webhook: dict):
        """Hold server-related configuration.

        :param debug: Whether we are in debug mode.
        :type debug: bool
        :param secret: The secret key for client-server communication. Generated with :func:`secrets.token_urlsafe`.
        :type secret: str
        :param url: The URL of the server we are running on.
        :type url: str
        :param host: The hostname of the server we are running on.
        :type host: str
        :param port: The port we are listening on.
        :type port: int
        :param json_indent: How many spaces to put in the JSON dumps.
        :type json_indent: int
        :param business_email: The streamer's business email.
        :type business_email: str
        :param websocket_client: The websocket client ID and secret.
        :type websocket_client: dict
        :param webhook: The webhook secret.
        :type webhook: dict
        """

        self.debug = debug
        self.secret = secret
        # TODO: Change url to only be user-facing, and use host+port for connection
        # Currently, the options are there for future use, but unused
        # The goal is to let us use the host and port for server setup
        # And url will be for user-facing stuff (like the !website url)
        self.url = url
        self.host = host
        self.port = port
        self.json_indent = json_indent
        self.business_email = business_email

        self.websocket_client = _WebsocketClient(**websocket_client)
        self.webhook = _Webhook(**webhook)

class _WebsocketClient(_ConfigMapping):
    def __init__(self, id: str, secret: str):
        """Hold Websocket Client information.

        :param id: The client ID.
        :type id: str
        :param secret: The client secret.
        :type secret: str
        """

        self.id = id
        self.secret = secret

class _Webhook(_ConfigMapping):
    def __init__(self, secret: str):
        """Hold webhook secret.

        :param secret: The webhook secret.
        :type secret: str
        """

        self.secret = secret

class Spotify(_ConfigMapping):
    def __init__(self, enabled: bool, id: str, secret: str, code: str):
        """Hold information for the Spotify "Now Playing" feature.

        :param enabled: Whether we use the "Now Playing" feature.
        :type enabled: bool
        :param id: The client ID of our app.
        :type id: str
        :param secret: The client secret of our app.
        :type secret: str
        :param code: The one-time code needed to kickstart it.
        :type code: str
        """

        self.enabled = enabled
        self.id = id
        self.secret = secret
        self.code = code # XXX: when we receive the code, immediately use it, don't store it
