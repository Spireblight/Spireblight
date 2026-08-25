"""Module to handle talking to the Spotify API.

This exposes a single class, which should not be instantiated more than once."""

from aiohttp import ClientSession, ContentTypeError
import datetime
import base64
import json

# lines here end satisfyingly
from src.config import config
from src.logger import logger
from src.utils import getfile

__all__ = ["Spotify"]

class TokenHandler:
    _filename_default: str = "spotify_tokens.json" #: JSON file under the data/ folder where tokens will be saved.

    def __init__(self):
        self._token: str = None
        self._refresh_token: str = None
        self._session: ClientSession = None
        self._expires_at: datetime.datetime = None

    async def get_token(self):
        """Get the Spotify token used for accessing the API.

        If the token is expired, obtain a new one. Otherwise, return the one saved on disk."""
        if self._token is None:
            self.load_tokens()
        if self._expires_at < datetime.datetime.now(): # expired, get another one
            await self.get_new_access_token()
        return self._token

    @property
    def session(self):
        """The aiohttp session to connect to the Spotify API."""
        if self._session is None:
            self._session = ClientSession()
        return self._session

    def load_tokens(self, filename=None):
        """Load the access and refresh tokens from disk."""
        if filename is None:
            filename = self._filename_default
        fd = None
        try:
            fd = getfile(filename, "r")
            data = json.load(fd)
            self._refresh_token = data["refresh_token"]
            self._token = data["token"]
            self._expires_at = datetime.datetime.fromtimestamp(data["expires_at"])
            self._scopes = data["scopes"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return # we don't have any
        except PermissionError:
            logger.error("Cannot read from the 'data' folder.")
        finally:
            if fd is not None:
                fd.close()

    def save_tokens(self, filename=None):
        """Save the access and refresh tokens to disk."""
        if filename is None:
            filename = self._filename_default
        fd = None
        try:
            fd = getfile(filename, "w")
            data = {
                "token": self._token,
                "refresh_token": self._refresh_token,
                "expires_at": int(self._expires_at.timestamp()),
                "scopes": self._scopes,
            }
            json.dump(data, fd)
        except PermissionError:
            logger.error("Cannot write to the 'data' folder.")
        finally:
            if fd is not None:
                fd.close()

    async def get_new_access_token(self):
        """Obtain a new access token using the refresh token."""
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }

        value = base64.urlsafe_b64encode(f"{config.spotify.id}:{config.spotify.secret}".encode("utf-8")).decode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {value}",
        }

        async with self.session.post("https://accounts.spotify.com/api/token", params=params, headers=headers) as resp:
            data = await resp.json()
            if resp.ok:
                self.populate_tokens(data)
            else:
                await self.request_authentication()

    async def request_authentication(self):
        """Request authentication from Spotify API and pass it on to the client.

        This is used once at first, and then whenever the refresh token expires."""

    def populate_tokens(self, data: dict[str, str | int]):
        """Tokens freshly obtained from Spotify."""
        # we also have token_type ("Bearer")
        self._token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        # scopes are space-delimited, but storing them as a list is more convenient
        self._scopes = data["scope"].split()
        now = datetime.datetime.now()
        expires = datetime.timedelta(seconds=data["expires_in"])
        self._expires_at = now + expires
        self.save_tokens()

class Spotify:
    def __init__(self):
        self.token_handler = TokenHandler()

    @property
    def session(self):
        """The aiohttp session to connect to the Spotify API."""
        return self.token_handler.session

    async def authenticate(self, *, force=False):
        """Trigger a handshake to get new OAuth2 credentials.

        :param force: Whether to force a re-authentication.
        :type force: bool
        """

    async def now_playing(self):
        """Obtain the currently-playing song using the Spotify API."""
        token = await self.token_handler.get_token()
        if token is None: # for whatever reason
            return None

        async with self.session.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
        ) as resp:
            try:
                return await resp.json()
            except ContentTypeError:
                return {}










    ### old code

    async def refresh_spotify_token(self):
        if not config.spotify.enabled:
            return

        if self._session is None:
            self._session = ClientSession()

        value = base64.urlsafe_b64encode(
            f"{config.spotify.id}:{config.spotify.secret}".encode("utf-8")
        )
        value = value.decode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {value}",
        }

        if self._spotify_refresh_token:
            params = {
                "grant_type": "refresh_token",
                "refresh_token": self._spotify_refresh_token,
            }

        else:
            params = {
                "grant_type": "authorization_code",
                "code": config.spotify.code,
                "redirect_uri": f"{config.server.url}/spotify",
            }

        async with self._session.post(
            "https://accounts.spotify.com/api/token", headers=headers, params=params
        ) as resp:
            if resp.ok:
                content = await resp.json()
                self._spotify_token = content["access_token"]
                self._expires_at = (
                    datetime.datetime.now()
                    + datetime.timedelta(seconds=content["expires_in"])
                ).timestamp()
                if "refresh_token" in content:
                    self._spotify_refresh_token = content["refresh_token"]
                    try:
                        with open(
                            os.path.join("data", "spotify_refresh_token"), "w"
                        ) as f:
                            f.write(self._spotify_refresh_token)
                    except OSError:  # oh no
                        logger.error(
                            f"Could not write refresh token to file: {self._spotify_refresh_token}"
                        )
                return self._spotify_token
            return None
