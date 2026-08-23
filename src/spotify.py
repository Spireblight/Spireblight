from aiohttp import ClientSession, ContentTypeError
import datetime
import base64
import json

# lines here end satisfyingly
from src.config import config
from src.logger import logger
from src.utils import getfile

class Spotify:
    _filename_default = "spotify_tokens.json"

    def __init__(self):
        self._token: str = None
        self._refresh_token: str = None
        self._session: ClientSession = None
        self._expires: int | float = None

    @property
    def token(self):
        if self._token is None:
            self.load_tokens()
        return self._token

    @token.setter
    def token(self, value):
        self._token = value
        self.save_tokens()

    @property
    def refresh_token(self):
        if self._refresh_token is None:
            self.load_tokens()
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, value):
        self._refresh_token = value
        self.save_tokens()

    @property
    def session(self):
        if self._session is None:
            self._session = ClientSession()
        return self._session

    def load_tokens(self, filename=None):
        if filename is None:
            filename = self._filename_default
        fd = None
        try:
            fd = getfile(filename, "r")
            data = json.load(fd)
            self._refresh_token = data["refresh_token"]
            self._token = data["token"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return # we don't have any
        except PermissionError:
            logger.error("Cannot read from the 'data' folder.")
        finally:
            if fd is not None:
                fd.close()

    def save_tokens(self, filename=None):
        if filename is None:
            filename = self._filename_default
        fd = None
        try:
            fd = getfile(filename, "w")
            data = {"token": self._token, "refresh_token": self._refresh_token}
            json.dump(data, fd)
        except PermissionError:
            logger.error("Cannot write to the 'data' folder.")
        finally:
            if fd is not None:
                fd.close()

    async def get_new_token(self):
        if not config.spotify.enabled:
            return

        value = base64.urlsafe_b64encode(f"{config.spotify.id}:{config.spotify.secret}".encode("utf-8")).decode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {value}",
        }


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

    async def spotify_call(self):
        if not config.spotify.enabled:
            return

        if self._session is None:
            self._session = ClientSession()

        if not self._spotify_token or self._expires_at < time.time():
            token = await self.refresh_spotify_token()
            if not token:
                return None

        async with self._session.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._spotify_token}",
            },
        ) as resp:
            try:
                return await resp.json()
            except ContentTypeError:
                return {}

