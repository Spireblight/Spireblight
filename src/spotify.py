"""Module to handle talking to the Spotify API.

This exposes a single instance, and the main class should not be instantiated more than once."""

from __future__ import annotations

from aiohttp import ClientSession, ContentTypeError
from aiohttp.web import Request, Response, HTTPForbidden, HTTPServiceUnavailable

import urllib.parse
import datetime
import secrets
import base64
import json

from src.webpage import router
from src.config import config
from src.logger import logger
from src.utils import getfile, get_req_data, catch_error

@router.get("/spotify/oauth2")
@catch_error
async def get_new_tokens(req: Request):
    params = req.query
    if spotify.token_handler.state != params["state"]:
        raise HTTPForbidden(reason="Invalid request state")

    spotify.token_handler.state = None # no matter what, we're done with it

    if "error" in params:
        raise HTTPForbidden(reason=params["error"])

    await spotify.token_handler.get_new_access_token(code=params["code"])
    return Response(text="Authentication successful! You may close this tab.")

@router.get("/spotify/now-playing")
@catch_error
async def get_now_playing(req: Request):
    await get_req_data(req)  # just checking if key is OK

    if not await spotify.is_token_valid():
        from src.server import TConn
        if TConn is not None:
            live = await TConn.fetch_streams(user_logins=[config.twitch.channel])
            if not live: # don't prompt if we're not live
                raise HTTPServiceUnavailable(reason="No active token and stream is offline")
        return Response(text=f"SPOTIFY_OAUTH2:{spotify.authenticate()}")

    data = await spotify.now_playing()

    if data is not None:
        return Response(text=json.dumps(data), content_type="application/json")
    raise HTTPServiceUnavailable(reason="Could not connect to the Spotify API")

class TokenHandler:
    _filename_default: str = "spotify_tokens.json" #: JSON file under the data/ folder where tokens will be saved.

    def __init__(self):
        self._token: str = None
        self._refresh_token: str = None
        self._session: ClientSession = None
        self._expires_at: datetime.datetime = None
        self.state = None

    async def get_token(self):
        """Get the Spotify token used for accessing the API.

        If the token is expired, obtain a new one. Otherwise, return the one saved on disk."""

        if self._token is None:
            self.load_tokens()
        if self._expires_at is None or self._expires_at < datetime.datetime.now(): # expired, get another one
            self._token = None
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

    async def get_new_access_token(self, *, code=None):
        """Obtain a new access token using the refresh token.

        This doesn't return any value."""

        if self._refresh_token is None and code is None: # need first auth
            return

        if code is None:
            params = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }
        else:
            params = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{config.server.url}/spotify/oauth2",
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

    def request_authentication_link(self):
        """Request authentication from Spotify API and pass it on to the client.

        This is used once at first, and then whenever the refresh token expires."""

        self.state = secrets.token_urlsafe(16)

        params = {
            "client_id": config.spotify.id,
            "response_type": "code",
            "redirect_uri": f"{config.server.url}/spotify/oauth2",
            "state": self.state,
            "scope": " ".join(config.spotify.scopes),
            "show_dialog": "false", # whether to prompt every time
        }

        return f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"

    def populate_tokens(self, data: dict[str, str | int]):
        """Tokens freshly obtained from Spotify."""
        # we also have token_type ("Bearer")
        self._token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        # scopes are space-delimited, but storing them as a list is more convenient
        # we technically have the list of scopes in config, but they might be wrong
        # they should be equal at all times, but on the off chance they're not, we save them here
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

    async def is_token_valid(self):
        """Check if the tokens are still valid."""
        return await self.token_handler.get_token() is not None

    def authenticate(self):
        """Trigger a handshake to get new OAuth2 credentials."""

        return self.token_handler.request_authentication_link()

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


spotify = Spotify()
