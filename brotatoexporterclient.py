import json
import aiohttp
from logger import logger

from typing import List, TypeAlias

from websockets.asyncio.client import connect as ws_connect
from websockets.asyncio.client import ClientConnection 
from websockets.exceptions import ConnectionClosed as WSConnectionClosed
from asyncio import sleep

_starting_backoff_seconds = 1

_method_close_message = "Called `close` method."

_error_code_timeout = 408

# Should be assumed that this is going to be a "diff" from the last object received.
# See (https://github.com/benw10-1/brotato-exporter/blob/main/swagger.yaml#L94) for example schema.
BrotatoExporterMessage: TypeAlias = dict[str, str|int|float]

class BrotatoExporterClient:
    """
Client for interfacing with the Brotato Exporter (https://github.com/benw10-1/brotato-exporter) mod.
Coupled tightly to single user because the functionality does not need to support multiple users.
Currently used to show the current character that is being played by the user displayed via `!tater`.
    """
    secure_host: bool # Whether to use (wss, ws) for websocket and (http, https).
    host: str # What service are we connecting to. May vary based on the Docker or external server setup.
    user_token: str # auth token created by running `mod-user-create.sh`. Unzip `user-mod.zip` and find `mods-unpacked/benw10-BrotatoExporter/connect-config.json`. In that file its the field "auth_token".
    max_backoff_seconds: int # maximum amount of time to wait before reconnecting to the ws endpoint
    subbed_fields: List[str] # list of fields to receive updates for. See (https://github.com/benw10-1/brotato-exporter/blob/main/swagger.yaml#L51) for examples. Is all fields by default.
    
    _current_state: BrotatoExporterMessage
    _cur_ws: ClientConnection
    _closed: bool
    _current_backoff_seconds: int
    _timed_out_last_retry: bool

    def __init__(self, host: str, user_token: str, secure_host: bool, max_backoff_seconds: int = 30, subbed_fields: List[str] = ["*"]):
        self.secure_host = secure_host
        self.host = host
        self.user_token = user_token
        self.max_backoff_seconds = max_backoff_seconds
        self.subbed_fields = subbed_fields

        self._current_state = BrotatoExporterMessage()
        self._closed = False
        self._current_backoff_seconds = _starting_backoff_seconds
        self._timed_out_last_retry = False
    
    async def connect(self):
        while not self._closed:
            try:
                # notify of initial state, as no message is even guaranteed to be received from the ws
                self._current_state = await self._req_current_state()

                async with ws_connect(self._get_ws_uri(), additional_headers=self._get_header_obj()) as conn:
                    if not self._timed_out_last_retry:
                        logger.info(f"brotatoexporter.BrotatoExporterClient.connect: Connected successfully to `{self.host}`.")
                    
                    self._timed_out_last_retry = False
                    self._cur_ws = conn

                    message = await conn.recv(decode=False) # disable utf-8 decoding as we are going to decode as JSON anyways
                    self._current_backoff_seconds = _starting_backoff_seconds # after receiving a message successfully, reset backoff

                    event_payload: dict = json.loads(message)
                    
                    
                    err_code = event_payload.get("error_code", 0)
                    # https://github.com/benw10-1/brotato-exporter/blob/main/gosrc/exporterserver/ctrlmessage/ctrlmessage.go#L222
                    if err_code > 0 and err_code == _error_code_timeout:
                        self._timed_out_last_retry = True
                        continue
                    
                    # since receiving as diff, update just the incoming fields instead of setting to whole obj
                    for key in event_payload:
                        self._current_state[key] = event_payload[key]
            
            except WSConnectionClosed as e:
                if e.reason == _method_close_message:
                    logger.info("brotatoexporter.BrotatoExporterClient.connect: Closed gracefully.")
                    break
                
                # will timeout ws conn after a few seconds, so we don't need to backoff in this case
                if self._timed_out_last_retry:
                    continue
                
                logger.error(f"brotatoexporter.BrotatoExporterClient.connect: WebSocket closed with code {e.code} and reason: {e.reason}.")
                
                await self._do_backoff()
                
                continue
            except aiohttp.ClientConnectorError as e:
                logger.error(f"brotatoexporter.BrotatoExporterClient.connect: Failed to request from {self._get_current_state_uri()} - {e.os_error}.")
                
                await self._do_backoff()

                continue
                
            except aiohttp.ClientResponseError as e:
                logger.error(f"brotatoexporter.BrotatoExporterClient.connect: Failed to request from {self._get_current_state_uri()}. Status ({e.status}) - Message ({e.message}).")
                
                await self._do_backoff()

                continue

            except Exception as e:
                logger.error(f"brotatoexporter.BrotatoExporterClient.connect: uncaught exception `{e}`, exiting.")
                
                await self._do_backoff()

                continue

        self._current_state = BrotatoExporterMessage()

        self._cur_ws = None
    
    async def _do_backoff(self):
        logger.info(f"brotatoexporter.BrotatoExporterClient.connect: Sleeping for {self._current_backoff_seconds} seconds before reconnecting.")

        await sleep(self._current_backoff_seconds)

        self._current_backoff_seconds *= 2 # primitive progressive backoff
        if self._current_backoff_seconds > self.max_backoff_seconds:
            self._current_backoff_seconds = self.max_backoff_seconds

    def get_current_state(self)->BrotatoExporterMessage:
        return self._current_state.copy()

    # Request the current state of the run. Used to get the initial state of the user (if any), as messages are expressed as a diff from the last.
    async def _req_current_state(self)->BrotatoExporterMessage:
        async with aiohttp.ClientSession() as session:
            async with session.get(self._get_current_state_uri(), headers=self._get_header_obj()) as response:
                if response.status == 404:
                    return {}
                
                if response.status != 200:
                    # trigger backoff by erroring
                    raise Exception(f"brotatoexporter.BrotatoExporterClient.connect: response with status `{response.status}` returned when trying to get current state")
                
                data = await response.json()
                
                return data

    def _get_header_obj(self):
        return {
            "Authorization": f"Bearer {self.user_token}",
            "Content-Type": "application/json",
        }
    
    def _get_current_state_uri(self):
        proto = "http"
        if self.secure_host:
            proto = "https"

        return f"{proto}://{self.host}/api/message/current-state"

    def _get_ws_uri(self):
        query_str = ""
        
        if self.subbed_fields and len(self.subbed_fields) > 0:
            query_str += "?"
            count = 0
            for field in self.subbed_fields:
                query_str += field + "=" + "1"
                if count < len(self.subbed_fields) - 1:
                    query_str += "&"
                count += 1

        proto = "ws"
        if self.secure_host:
            proto = "wss"

        return f"{proto}://{self.host}/api/message/subscribe{query_str}"

    # Gracefully close the websocket connection and block until its finished.
    async def close(self):
        if self._closed or not self._cur_ws:
            return
        
        self._cur_ws.close(code=1000, reason="Called `close` method.")

        await self._cur_ws.wait_closed()

        self._closed = True