"""Contain all the configuration as classes.

This allows proper type hinting and autocomplete."""

class _ConfigMapping:
    def update(self, mapping: dict):
        for k, v in mapping.items():
            if isinstance(v, dict): # another level down
                getattr(self, k).update(v)
                continue
            setattr(self, k, v)

class Config(_ConfigMapping):
    def __init__(self, twitch: dict, discord: dict, youtube: dict, bot: dict, server: dict, spotify: dict):
        self.twitch = Twitch(**twitch)

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
