# (c) Anilyka Barry, 2022-Present

from __future__ import annotations

from typing import Generator, Callable, Optional, Iterable

from collections import defaultdict

import urllib.parse
import traceback
import datetime
import aiohttp
import asyncio
import random
import string
import base64
import json
import time
import sys
import csv
import re
import os

from twitchio.ext.commands import (
    Cooldown as TCooldown,
    Bucket as TBucket,
    AutoBot as TBot,
    Context as TContext,
)
from twitchio.ext.routines import routine, Routine
# from twitchio.ext.eventsub import EventSubClient
#from twitchio.channel import Channel
from twitchio import Chatter, StreamOffline, StreamOnline, PartialUser, ChatNotification, ChatRaid
from twitchio.exceptions import HTTPException
from twitchio.models import Stream, Prediction, Clip as TClip

from twitchio import eventsub as WSSub

import discord
from discord.ext.commands import (
    Cooldown as DCooldown,
    BucketType as DBucket,
    Bot as DBot,
    command as _dcommand,
)

from aiohttp_jinja2 import template
from aiohttp.web import Request, HTTPNotFound, Response, HTTPServiceUnavailable
from aiohttp import ClientSession, ContentTypeError

from src.cache.run_stats import (
    get_all_run_stats,
    get_run_stats_by_date,
    get_run_stats_by_date_string,
    update_range,
)

from src.cache.mastered import get_current_masteries, get_mastered
from src.nameinternal import get, query, sanitize, Base, Card, Relic, RelicSet, _internal_cache
from src.sts_profile import get_profile, get_current_profile
from src.webpage import router, playlists
from src.wrapper import wrapper
from src.monster import query as mt_query, get_savefile as get_mt_save, MonsterSave
from src.twitch import TwitchCommand
from src.logger import logger
from src.events import add_listener
from src.config import config, __botname__, __version__, __github__, __author__
from src.slice import get_runs, CurrentRun
from src.utils import (
    format_for_slaytabase,
    getfile,
    parse_date_range,
    update_db,
    get_req_data,
    post_prediction,
)

from src.disc import DiscordCommand
from src.save import get_savefile, Savefile
from src.runs import get_latest_run, get_parser, _ts_cache as _runs_cache, RunParser
from src.gamedata import RelicData, Treasure, Event

from src.typehints import ContextType, CommandType
from src import events, archive

TConn: TwitchConn = None
DConn: DiscordConn = None

logger.info("Setting up")

# Twitch bot server defined here - process started in main.py

_DEFAULT_BURST = 1
_DEFAULT_RATE = 3.0

_consts = {
    "discord": config.discord.invite_links.main,
    "prefix": config.bot.prefix,
    "website": config.server.url,
}

_quotes: list[Quote] = []
_clips: list[Clip] = [None] # means un-itialized


class Formatter(string.Formatter):  # this does not support conversion or formatting
    def __init__(self):
        super().__init__()
        self._re = re.compile(r".+(\(.+\)).*")

    def parse(
        self, format_string: str
    ) -> Generator[tuple[str, str | None, str | None, None]]:
        if format_string is None:  # recursion
            yield ("", None, None, None)
            return
        start = 0
        while start < len(format_string):
            try:
                idx = format_string.index("$<", start)
                end = format_string.index(">", idx)
            except ValueError:
                yield (format_string[start:], None, None, None)
                break

            lit = format_string[start:idx]

            field = format_string[idx + 2 : end]

            called = None
            call_args = self._re.match(field)
            if call_args:
                called = call_args.group(1)
                call_idx = field.index(called)
                field = field[:call_idx]
                called = called[1:-1]

            yield (lit, field, called, None)
            start = end + 1

    def format_field(self, value: Callable, call_args: str) -> str:
        if call_args:
            return value(call_args)
        return str(value)


_formatter = Formatter()

_perms = {
    "": "Everyone",
    "m": "Moderator",
    "e": "Editor",  # this has no effect in discord
}

_cmds: dict[str, dict[str, list[str] | bool | int | float]] = {}  # internal json

_to_add_twitch: list[TwitchCommand] = []
_to_add_discord: list[DiscordCommand] = []

_timers: dict[str, Timer] = {}

_prediction_terms = {}

_eventsub_subs: list[WSSub.SubscriptionPayload] = [
    WSSub.ChatMessageSubscription(broadcaster_user_id=str(config.twitch.owner_id), user_id=str(config.twitch.bot_id)),
    WSSub.ChannelRaidSubscription(to_broadcaster_user_id=str(config.twitch.owner_id)),
    WSSub.ChatNotificationSubscription(broadcaster_user_id=str(config.twitch.owner_id), user_id=str(config.twitch.bot_id))
]

def _get_sanitizer(ctx: ContextType, name: str, args: list[str], mapping: dict):
    async def _sanitize(require_args: bool = True, in_mapping: bool = True) -> bool:
        """Verify that user input is sane. Return True if input is sane."""

        if require_args and not args:
            await ctx.reply("Error: no output provided.")
            return False

        if in_mapping and name not in mapping:
            await ctx.reply(f"Error: command {name} does not exist!")
            return False

        if not in_mapping and name in mapping:
            await ctx.reply(f"Error: command {name} already exists!")
            return False

        return True

    return _sanitize


def _create_cmd(output: str, name: str):
    def count(x: str = "") -> str:
        # we expect something to increase or decrease
        # but if it's invalid, just return existing count
        # we don't want text commands to fail for no reason
        update = False
        match x:
            case "increase" | "++":
                inner.count += 1
                update = True
            case "decrease" | "--":
                inner.count -= 1
                update = True

        if update:
            _cmds[name]["count"] = inner.count
            update_db()

        return str(inner.count)

    async def inner(ctx: ContextType, *s, output: str = output):
        try:
            msg = output.format(
                user=ctx.author.display_name, text=" ".join(s), words=s, **_consts
            )
        except KeyError as e:
            msg = f"Error: command has unsupported formatting key {e.args[0]!r}"
        keywords = {
            "mt-save": None,
            "savefile": None,
            "profile": None,
            "readline": readline,
            "count": count,
        }
        if "$<profile" in msg:
            profile = get_current_profile()
            if profile is None:
                msg = f"Error: command requires an existing profile, and none exist."
            else:
                keywords["profile"] = profile
        if "$<savefile" in msg:
            keywords["savefile"] = get_savefile()
            # No save file found:
            if not keywords["savefile"].in_game:
                await ctx.reply("Not in a run.")
                return
        if "$<mt-save" in msg:
            keywords["mt-save"] = await get_mt_save(ctx)
            if keywords["mt-save"] is None:
                return
        msg = _formatter.vformat(msg, (), keywords)
        # TODO: Add a flag to the command that says whether it's a reply
        # or a regular message.
        await ctx.reply(msg)

    inner.count = 0
    return inner


def readline(file: str) -> str:
    if ".." in file:
        return "Error: '..' in filename is not allowed."
    with open(os.path.join("text", file), "r") as f:
        return random.choice(f.readlines()).rstrip()


def load(loop: asyncio.AbstractEventLoop):
    _cmds.clear()
    try:
        with getfile("data.json", "r") as f:
            _cmds.update(json.load(f))
    except FileNotFoundError:
        pass
    for name, d in _cmds.items():
        c = command(
            name,
            *d.get("aliases", []),
            flag=d.get("flag", ""),
            burst=d.get("burst", _DEFAULT_BURST),
            rate=d.get("rate", _DEFAULT_RATE),
        )(_create_cmd(d["output"], name))
        c.enabled = d.get("enabled", True)
        c.count = d.get("count", c.count)
    try:
        with getfile("disabled", "r") as f:
            for disabled in f.readlines():
                pass
                # TConn.commands[disabled].enabled = False
    except FileNotFoundError:
        pass

    _prediction_terms.clear()
    with open("prediction_terms.json", "r") as f:
        _prediction_terms.update(json.load(f))

    try:
        to_start = []
        with getfile("timers.json", "r") as f:
            j = json.load(f)
        for name, d in j.items():
            if name not in _timers:
                _timers[name] = Timer(name, d["interval"], loop=loop)
            _timers[name].commands.extend(d["commands"])
            if d.get("enabled", True):
                to_start.append(_timers[name])
        loop.create_task(_launch_timers(to_start))
    except FileNotFoundError:
        pass

    try:
        with getfile("quotes.json", "r") as f:
            j = json.load(f)
    except FileNotFoundError:
        pass
    else:
        for line, author, adder, isq, ts in j:
            q = Quote(line, author, adder, datetime.datetime.fromtimestamp(ts))
            if not isq:
                q.is_quote = False
            _quotes.append(q)

def _update_quotes():
    q = [x.to_json() for x in _quotes]
    with getfile("quotes.json", "w") as f:
        json.dump(q, f, indent=config.server.json_indent)


async def _launch_timers(timers: list[Timer]):
    for timer in timers:
        timer.start()
        await asyncio.sleep(config.twitch.timers.stagger_interval)


def _update_timers():
    final = {}
    for name, timer in _timers.items():
        d = {"interval": timer.interval, "commands": timer.commands}
        if not timer.running:
            d["enabled"] = False
        final[name] = d
    with getfile("timers.json", "w") as f:
        json.dump(final, f, indent=config.server.json_indent)


# Adds non built-in commands to internal json structure
def add_cmd(
    name: str,
    *,
    aliases: list[str] = None,
    source: str = None,
    flag: str = None,
    burst: int = None,
    rate: float = None,
    output: str,
):
    _cmds[name] = {"output": output}
    if aliases is not None:
        _cmds[name]["aliases"] = aliases
    if source is not None:
        _cmds[name]["source"] = source
    if flag is not None:
        _cmds[name]["flag"] = flag
    if burst is not None:
        _cmds[name]["burst"] = burst
    if rate is not None:
        _cmds[name]["rate"] = rate
    update_db()


def command(
    name: str,
    *aliases: str,
    flag: str = "",
    force_argcount: bool = False,
    burst: int = _DEFAULT_BURST,
    rate: float = _DEFAULT_RATE,
    twitch: bool = True,
    discord: bool = True,
):
    """This decorator builds TwitchCommand and DiscordCommand versions of commands while leaving the original functions untouched."""

    def inner(func: Callable, wrapper_func=None):
        wrapped = wrapper(func, force_argcount, wrapper_func, name)
        wrapped.__cooldowns__ = [TCooldown(rate=burst, per=rate)]
        wrapped.__doc__ = func.__doc__
        # wrapped.__commands_cooldown__ = DCooldown(burst, rate, DBucket.default)
        if twitch:
            tcmd = TwitchCommand(
                name=name, aliases=list(aliases), func=wrapped, flag=flag
            )
            if TConn is None:
                _to_add_twitch.append(tcmd)
            else:
                TConn.add_command(tcmd)
        if discord:
            dcmd = _dcommand(name, DiscordCommand, aliases=list(aliases), flag=flag)(
                wrapped
            )
            if DConn is None:
                _to_add_discord.append(dcmd)
            else:
                DConn.add_command(dcmd)
        return func

    return inner


def with_savefile(name: str, *aliases: str, optional_save: bool = False, **kwargs):
    """Decorator for commands that require a save."""

    def inner(func):
        async def _savefile_get(ctx) -> list:
            res = get_savefile()
            if res is None:
                raise ValueError("No savefile")
            if res.character is None and not optional_save:
                if ctx is not None:
                    await ctx.reply("Not in a run.")
                raise ValueError("Not in a run")
            if res.character is None and optional_save:
                return [None]
            return [res]

        return command(name, *aliases, **kwargs)(func, wrapper_func=_savefile_get)

    return inner


def slice_command(name: str, *aliases: str, **kwargs):
    def inner(func):
        async def _slice_get(ctx: ContextType | None) -> list:
            res = get_runs()
            if not res:
                if ctx:
                    await ctx.reply("We are not playing Slice & Dice currently.")
                raise ValueError("No Slice & Dice run going on")
            return [res["classic"]]  # FIXME: Does not support multiple S&D runs at once

        return command(name, *aliases, **kwargs)(func, wrapper_func=_slice_get)

    return inner


def mt_command(name: str, *aliases: str, **kwargs):
    def inner(func):
        async def _mt_get(ctx) -> list:
            res = await get_mt_save(ctx)
            if res is None:
                raise ValueError("No savefile")
            return [res]

        return command(name, *aliases, **kwargs)(func, wrapper_func=_mt_get)

    return inner


class TwitchConn(TBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.esclient: EventSubClient = None
        self.live_channels: dict[str, bool] = {config.twitch.channel: False}
        self._session: ClientSession | None = None
        self._spotify_token: str = None
        self._expires_at: int | float = 0
        self._spotify_refresh_token: str = None
        try:
            with open(os.path.join("data", "spotify_refresh_token"), "r") as f:
                self._spotify_refresh_token = f.read().strip()
        except OSError:
            pass

    async def setup_hook(self):
        """Set-up the bot's hooks."""
        for cmd in _to_add_twitch:
            self.add_command(cmd)
        load(asyncio.get_event_loop())

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

    async def event_ready(self):
        self.live_channels[config.twitch.channel] = live = bool(
            await self.fetch_streams(user_logins=[config.twitch.channel])
        )

    async def event_chat_notification(self, payload: ChatNotification):
        match payload.notice_type:
            case "raid":
                await self.event_raid(payload.broadcaster, payload.raid)

    async def event_raid(self, channel: PartialUser, payload: ChatRaid):
        viewer_count = payload.viewer_count
        user = payload.user
        if viewer_count < 10:
            return
        chan = await self.fetch_channel(user.id)
        await channel.send_announcement(
            f"Welcome along {user.display_name} with your {viewer_count} friends! "
            f"Everyone, go give them a follow over at https://twitch.tv/{user.name} - "
            f"last I checked, they were playing some {chan.game_name}!"
        )

    def __getattr__(self, name: str):
        if name.startswith(
            "event_"
        ):  # calling events -- insert our own event system in
            name = name[6:]
            evt = events.get(name)
            if evt:

                async def invoke(*args, **kwargs):
                    for e in evt:
                        await e.invoke(args, kwargs)

                return invoke
        raise AttributeError(name)


class DiscordConn(DBot):
    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        if message.content.startswith(config.bot.prefix) or isinstance(
            message.channel, discord.DMChannel
        ):
            content = message.content.lstrip(config.bot.prefix).split()
            if not content:
                return
            ctx = await self.get_context(message)
            cmd: DiscordCommand = self.get_command(content[0])
            if cmd:
                await cmd(ctx, *content[1:])

    def dispatch(self, name, /, *args, **kwargs):
        evt = events.get(name)
        if evt is not None:
            for event in evt:
                self.add_listener(event, name)
        value = super().dispatch(name, *args, **kwargs)
        if evt is not None:
            for event in evt:
                self.remove_listener(event, name)
        return value


class Timer:
    def __init__(self, name: str, interval: int, *, loop=None):
        self.name = name
        self.interval = interval
        self.commands = []
        self.running = False
        self.loop = loop
        self._task = None
        self.set_routine()

    def set_routine(self):
        if self.running:
            self._routine.stop()
        self._routine = Routine(
            coro=self._coro_internal, delta=float(self.interval), loop=self.loop
        )
        self._routine.before_routine(self.before_ready)
        self._routine.error(self.on_error)
        if self.running:
            self.task = self._routine.start()

    async def _coro_internal(self):
        if not self.running:
            return
        live = await TConn.fetch_streams(user_logins=[config.twitch.channel])
        chan = TConn.get_channel(config.twitch.channel)
        if not live or not chan:
            if self.name.startswith("auto_"): # stream ended, kill this timer
                self.stop()
                del _timers[self.name]
                _update_timers()
                # XXX: This is now the only reference of itself
                # It should get GC'd properly, but might have issues
            return
        cmd = None
        i = 0
        while cmd is None:
            i += 1
            if i > len(self.commands):
                return
            maybe_cmd = self.commands.pop(0)
            if maybe_cmd not in _cmds and maybe_cmd not in TConn.commands:
                i -= 1  # we're not adding it back, so it's fine
                continue
            if not TConn.commands[maybe_cmd].enabled:
                self.commands.append(maybe_cmd)  # in case it gets enabled again
                continue
            if maybe_cmd == "current":
                save = get_savefile()
                if not save.in_game:
                    self.commands.append(maybe_cmd)
                    continue
            cmd = maybe_cmd
        # don't use the actual command, just send the raw output
        msg: str = _cmds[cmd]["output"]
        try:
            msg = msg.format(**_consts)
        except KeyError:
            logger.error(
                f"Command {cmd} of timer {self.name} needs non-constant formatting. Sending raw line."
            )
        await chan.send(msg)
        self.commands.append(cmd)
        _update_timers()  # keep track of command ordering

    async def before_ready(self):
        await TConn.wait_for_ready()

    async def on_error(self, error: Exception):
        logger.error(f"Error in timer {self.name}:")
        logger.error(
            "\n".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
        )

    def start(self):
        if not self.running:
            self.running = True
            self.task = self._routine.start()

    def stop(self):
        self._routine.stop()
        self.running = False


@command("timers", flag="me")
async def timers_list(ctx: ContextType):
    await ctx.reply(f"The existing timers are {', '.join(_timers)}.")


@command("timer", flag="me")
async def timer_cmd(ctx: ContextType, action: str, name: str, *args: str):
    """Manipulate the timers. Syntax:

    - `create <name> [interval]`
       will create a new timer with the name and the given interval,
       if specified. It has no other effect.
    - `add <name> <commands>`
       will add all of the commands (space-separated) to the timer `name` -
       it does not start the timer. If it is running, it will seamlessly
       integrate the new command at the current point in the rotation.
    - `remove <name> <commands>`
       will remove all of the commands (space-separated) to the timer `name` -
       it does not stop or delete the timer.
    - `delete <name>` completely removes a timer and associated commands.
       This cannot be undone.
    - `auto <name> [interval]`
       creates a new timer with the given interval, if specified, and exactly
       one command `name`. It immediately starts it. This is basically used for
       single-command sponsored timers and the like. The internal timer name will
       start with `auto_`, followed by the command name, and can be edited normally
       afterwards. It will automatically delete itself when the stream ends.
    - `status <name>`
       outputs the commands and interval tied to this timer.
    - `start <name>`
       starts the given timer.
    - `stop <name>`
       stops the given timer.
    - `interval <name> <interval>`
       changes the interval of an existing timer. This will have some weird
       double-send glitch if editing the interval of a running timer, but is
       mostly fine otherwise.
    """

    match action:
        case "create":
            if name in _timers:
                await ctx.reply(f"Timer {name} already exists.")
                return
            if name.startswith("auto_"):
                await ctx.reply(
                    f"Cannot manually create automatic timers. Use 'auto {name[5:]}' instead."
                )
                return
            interval = config.twitch.timers.default_interval
            if args:
                interval = args[0]
            _timers[name] = Timer(name, interval)
            _update_timers()
            await ctx.reply(
                f"Timer {name} has been created! Use 'add {name} <commands>' to add commands to it."
            )

        case "add":
            if name not in _timers:
                await ctx.reply(
                    f"Timer {name} doesn't exist. Use 'create {name}' first."
                )
                return
            if not args:
                await ctx.reply("No commands to add.")
                return
            t = _timers[name]
            for arg in args:
                cmd = TConn.get_command(arg)
                if cmd is not None and cmd.name not in t.commands:
                    t.commands.append(cmd.name)
            _update_timers()
            await ctx.reply(
                f"Timer {name} now has commands {', '.join(t.commands)} on an interval of {t.interval}s."
            )

        case "remove":
            if name not in _timers:
                await ctx.reply(
                    f"Timer {name} doesn't exist. Use 'create {name}' first."
                )
                return
            if not args:
                await ctx.reply("No commands to remove.")
                return
            t = _timers[name]
            for arg in args:
                if arg in t.commands:
                    t.commands.remove(arg)
            _update_timers()
            await ctx.reply(
                f"Timer {name} now has commands {', '.join(t.commands)} on an interval of {t.interval}s."
            )

        case "delete":
            if name not in _timers:
                await ctx.reply(
                    f"Timer {name} doesn't exist. Use 'create {name}' first."
                )
                return
            t = _timers[name]
            t.stop()
            del _timers[name]
            _update_timers()
            await ctx.reply(f"Timer {name} has been removed.")

        case "auto":
            cmd = TConn.get_command(name)
            if cmd is None:
                await ctx.reply(f"Command {name} does not exist.")
                return
            timer_name = f"auto_{cmd.name}"
            if timer_name in _timers:
                await ctx.reply(
                    f"Automatic timer {name} ({timer_name}) already exists; starting it."
                )
                _timers[timer_name].start()
                return
            interval = config.twitch.timers.default_interval
            if args:
                interval = args[0]
            _timers[timer_name] = t = Timer(timer_name, interval)
            t.commands.append(cmd.name)
            t.start()
            _update_timers()
            await ctx.reply(
                f"Automatic timer {name} ({timer_name}) has been created and started. It will self-remove after stream."
            )

        case "status" | "info":
            if name not in _timers:
                await ctx.reply(f"Timer {name} does not exist.")
                return
            t = _timers[name]
            await ctx.reply(
                f"Timer {name} has an interval of {t.interval}s with commands {', '.join(t.commands)} and is currently {t.running and 'running' or 'stopped'}."
            )

        case "start":
            if name not in _timers:
                await ctx.reply(f"Timer {name} does not exist.")
                return
            t = _timers[name]
            if t.running:
                await ctx.reply(f"Timer {name} is already running.")
                return
            t.start()
            _update_timers()
            await ctx.reply(f"Timer {name} has been started.")

        case "stop":
            if name not in _timers:
                await ctx.reply(f"Timer {name} does not exist.")
                return
            t = _timers[name]
            if not t.running:
                await ctx.reply(f"Timer {name} is not running.")
                return
            t.stop()
            _update_timers()
            await ctx.reply(f"Timer {name} has been stopped.")

        case "interval":
            if name not in _timers:
                await ctx.reply(f"Timer {name} does not exist.")
                return
            t = _timers[name]
            interval = config.twitch.timers.default_interval
            if args:
                interval = args[0]
            t.interval = interval
            t.set_routine()
            _update_timers()
            await ctx.reply(
                f"Timer {name} has been set to interval {interval}. If it was running, it will complete the existing interval."
            )


@command("command", flag="me")
async def command_cmd(ctx: ContextType, action: str, name: str, *args: str):
    """Syntax: command <action> <name> [+flag] <output>"""
    args = list(args)
    msg = " ".join(args)
    name = name.lstrip(config.bot.prefix)
    cmds: dict[str, list[CommandType]] = {}
    if TConn is not None:
        for cname, cmd in TConn.commands.items():
            cmds[cname] = [cmd]
    if DConn is not None:
        for cmd in DConn.commands:
            if cmd.name not in cmds:
                cmds[cmd.name] = []
            cmds[cmd.name].append(cmd)
    aliases: dict[str, list[str]] = {}
    if TConn is not None:
        for alias, cmd in TConn._command_aliases.items():
            aliases[alias] = [cmd]
    if DConn is not None:
        for dcmd in DConn.commands:
            for alias in dcmd.aliases:
                if alias not in aliases:
                    aliases[alias] = []
                aliases[alias].append(dcmd.name)

    sanitizer = _get_sanitizer(ctx, name, args, cmds)
    match action:
        case "add":
            # sanitizer will call ctx.reply() with error message if input is invalid
            if not await sanitizer(in_mapping=False):
                return
            if name in aliases:
                await ctx.reply(
                    f"Error: {name} is an alias to {aliases[name][0]}. Use 'unalias {aliases[name][0]} {name}' first."
                )
                return
            flag = ""
            if args[0].startswith("+"):
                flag, *args = args
            flag = flag[1:]
            if flag not in _perms:
                await ctx.reply("Error: flag not recognized.")
                return
            if flag:
                add_cmd(name, flag=flag, output=msg)
            else:
                add_cmd(name, output=msg)
            command(name, flag=flag)(_create_cmd(msg, name))
            await ctx.reply(f"Command {name} added! Permission: {_perms[flag]}")

        case "edit":
            # sanitizer will call ctx.reply() with error message if input is invalid
            if not await sanitizer():
                return
            if name in aliases:
                await ctx.reply(
                    f"Error: cannot edit alias. Use 'edit {aliases[name][0]}' instead."
                )
                return
            if name not in _cmds:
                await ctx.reply(f"Error: cannot edit built-in command {name}.")
                return
            _cmds[name]["output"] = msg
            flag = ""
            if args[0].startswith("+"):
                flag, *args = args
            if flag not in _perms:
                await ctx.reply("Error: flag not recognized.")
                return
            if flag:
                _cmds[name]["flag"] = flag
            update_db()
            for cmd in cmds[name]:
                cmd._callback = _create_cmd(msg, name)
            await ctx.reply(
                f"Command {name} edited successfully! Permission: {_perms[flag]}"
            )

        case "remove" | "delete":
            # sanitizer will call ctx.reply() with error message if input is invalid
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.reply(
                    f"Error: cannot delete alias. Use 'remove {aliases[name][0]}' or 'unalias {aliases[name][0]} {name}' instead."
                )
                return
            if name not in _cmds:
                await ctx.reply(f"Error: cannot delete built-in command {name}.")
                return
            del _cmds[name]
            update_db()
            if TConn is not None:
                TConn.remove_command(name)
            if DConn is not None:
                DConn.remove_command(name)
            await ctx.reply(f"Command {name} has been deleted.")

        case "enable":
            # sanitizer will call ctx.reply() with error message if input is invalid
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.reply(
                    f"Error: cannot enable alias. Use 'enable {aliases[name][0]}' instead."
                )
                return
            if all(cmds[name]):
                await ctx.reply(f"Command {name} is already enabled.")
                return
            for cmd in cmds[name]:
                cmd.enabled = True
            if name in _cmds:
                _cmds[name]["enabled"] = True
                update_db()
            with getfile("disabled", "r") as f:
                disabled = f.readlines()
            disabled.remove(name)
            with getfile("disabled", "w") as f:
                f.writelines(disabled)
            await ctx.reply(f"Command {name} has been enabled.")

        case "disable":
            # sanitizer will call ctx.reply() with error message if input is invalid
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.reply(
                    f"Error: cannot disable alias. Use 'disable {aliases[name][0]}' or 'unalias {aliases[name][0]} {name}' instead."
                )
                return
            if not all(cmds[name]):
                await ctx.reply(f"Command {name} is already disabled.")
                return
            for cmd in cmds[name]:
                cmd.enabled = False
            if name in _cmds:
                _cmds[name]["enabled"] = False
                update_db()
            with getfile("disabled", "r") as f:
                disabled = f.readlines()
            disabled.append(name)
            with getfile("disabled", "w") as f:
                f.writelines(disabled)
            await ctx.reply(f"Command {name} has been disabled.")

        case "alias":  # cannot sanely sanitize this
            if not args:
                if name not in _cmds and name in aliases:
                    await ctx.reply(f"Alias {name} is bound to {aliases[name][0]}.")
                elif _cmds[name].get("aliases"):
                    await ctx.reply(
                        f"Command {name} has the following aliases: {', '.join(_cmds[name]['aliases'])}"
                    )
                else:
                    await ctx.reply(f"Command {name} does not have any aliases.")
                return
            if name not in cmds and args[0] in cmds:
                await ctx.reply(f"Error: use 'alias {args[0]} {name}' instead.")
                return
            if name not in cmds:
                await ctx.reply(f"Error: command {name} does not exist.")
                return
            if name not in _cmds:
                await ctx.reply("Error: cannot alias built-in commands.")
                return
            if set(args) & cmds.keys():
                await ctx.reply(
                    f"Error: aliases {set(args) & cmds.keys()} already exist as commands."
                )
                return
            for arg in args:
                if TConn is not None:
                    TConn._command_aliases[arg] = name
                if DConn is not None:
                    DConn.get_command(name).aliases.append(arg)
            if "aliases" not in _cmds[name]:
                _cmds[name]["aliases"] = []
            _cmds[name]["aliases"].extend(args)
            update_db()
            await ctx.reply(
                f"Command {name} now has aliases {', '.join(_cmds[name]['aliases'])}"
            )

        case "unalias":
            if not args:
                await ctx.reply("Error: no alias specified.")
                return
            if len(args) > 1:
                await ctx.reply("Can only remove one alias at a time.")
                return
            if name not in cmds and args[0] in cmds:
                await ctx.reply(f"Error: use 'unalias {args[0]} {name}' instead.")
                return
            if name not in cmds:
                await ctx.reply(f"Error: command {name} does not exist.")
                return
            if args[0] not in aliases:
                await ctx.reply("Error: not an alias.")
                return
            if name not in _cmds:
                await ctx.reply("Error: cannot unalias built-in commands.")
                return
            if aliases[args[0]][0] != name:
                await ctx.reply(
                    f"Error: alias {args[0]} does not match command {name} (bound to {aliases[args[0]][0].name})."
                )
                return
            if TConn is not None:
                TConn._command_aliases.pop(args[0], None)
            if DConn is not None:
                dcmd: DiscordCommand = DConn.get_command(name)
                if args[0] in dcmd.aliases:
                    dcmd.aliases.remove(args[0])
            _cmds[name]["aliases"].remove(name)
            update_db()
            await ctx.reply(f"Alias {args[0]} has been removed from command {name}.")

        case "cooldown" | "cd":
            await ctx.reply("Cooldown cannot be changed currently")
            return
            # sanitizer will call ctx.reply() with error message if input is invalid
            if not await sanitizer(require_args=False):
                return
            if not args:
                if name not in cmds and name not in aliases:
                    await ctx.reply(f"Error: command {name} does not exist.")
                else:
                    if name in aliases:
                        name = aliases[name]
                    cd = cmds[name]._cooldowns[0]
                    await ctx.reply(
                        f"Command {name} has a cooldown of {cd._per/cd._rate}s."
                    )
                return
            if name in aliases:
                await ctx.reply(
                    f"Error: cannot edit alias cooldown. Use 'cooldown {aliases[name][0]}' instead."
                )
                return
            cd: TCooldown = cmds[name]._cooldowns.pop()
            try:
                burst = int(args[0])
            except ValueError:
                try:
                    rate = float(args[0])
                except ValueError:
                    await ctx.reply("Error: invalid argument.")
                    return
                else:
                    burst = cd._rate  # _rate is actually the burst, it's weird
            else:
                try:
                    rate = float(args[1])
                except IndexError:
                    rate = cd._per
                except ValueError:
                    await ctx.reply("Error: invalid argument.")
                    return

            cmds[name]._cooldowns.append(TCooldown(burst, rate, cd.bucket))
            if name in _cmds:
                _cmds[name]["burst"] = burst
                _cmds[name]["rate"] = rate
                update_db()
            await ctx.reply(
                f"Command {name} now has a cooldown of {rate/burst}s."
            )  # this isn't 100% accurate, but close enough
            if name not in _cmds:
                await ctx.reply(
                    "Warning: settings on built-in commands do not persist past a restart."
                )

        case _:
            await ctx.reply(f"Unrecognized action {action}.")


class Quote:
    def __init__(
        self, line: str, author: Optional[str], added_by: str, ts: datetime.datetime
    ):
        self.line = line
        self.author = author
        self.added_by = added_by
        self.is_quote = True
        self.ts = ts

    def to_json(self):
        return [
            self.line,
            self.author,
            self.added_by,
            self.is_quote,
            self.ts.timestamp() if self.ts is not None else 0,
        ]


@router.get("/quotes/as-json")
async def get_raw_quotes(req: Request):
    l = []
    def _d(i, x):
        return {
            "num": i,
            "line": x[0],
            "author": x[1],
            "adder": x[2],
            "is_quote": x[3],
            "epoch": x[4],
        }

    for i, q in enumerate(_quotes):
        l.append(_d(i, q.to_json()))

    return Response(text=json.dumps(l, indent=4), content_type="application/json")

@command("quote", "randomquote")
async def quote_stuff(ctx: ContextType, arg: str = "random", *rest):
    """Edit the quote database or pull a specific or random quote."""
    update = False
    line = " ".join(rest)
    match arg:
        case "add":
            if line is not None:
                line, _, author = line.partition(" -- ")
                _quotes.append(
                    Quote(
                        line, author or None, ctx.author.display_name, datetime.datetime.now()
                    )
                )
                update = True
                await ctx.reply(f"Quote #{len(_quotes) - 1} successfully added!")

        case "edit":
            try:
                i = int(rest[0])
                line = " ".join(rest[1:])
            except ValueError:
                await ctx.reply("Give me a number for the quote to edit.")
            except IndexError:
                await ctx.reply("You want me to edit what, exactly?")
            else:
                if i < 0:
                    i += len(_quotes)
                if not line:
                    await ctx.reply("Replace it with what? Use 'delete' to delete.")
                elif 0 <= i < len(_quotes):
                    _quotes[i].line = line
                    update = True
                    await ctx.reply("It is done. No one will remember this.")
                else:
                    await ctx.reply("No such quote.")

        case "author":
            try:
                i = int(rest[0])
                author = " ".join(rest[1:])
            except (ValueError, IndexError):
                await ctx.reply("Invalid input or not enough arguments.")
            else:
                if i < 0:
                    i += len(_quotes)
                if 0 <= i < len(_quotes):
                    _quotes[i].author = author
                    update = True
                    await ctx.reply(
                        "The author of this quote has been properly attributed."
                    )
                else:
                    await ctx.reply("No such quote.")

        case "no-adder" | "noadder":
            try:
                i = int(rest[0])
            except (ValueError, IndexError):
                await ctx.reply("No argument or not a number.")
            else:
                if i < 0:
                    i += len(_quotes)
                if 0 <= i < len(_quotes):
                    _quotes[i].added_by = None
                    update = True
                    await ctx.reply("Done. No one added this quote.")
                else:
                    await ctx.reply("No such quote.")

        case "no-quote" | "noquote":
            try:
                i = int(rest[0])
            except (ValueError, IndexError):
                await ctx.reply("No argument or not a number.")
            else:
                if i < 0:
                    i += len(_quotes)
                if 0 <= i < len(_quotes):
                    _quotes[i].is_quote = False
                    update = True
                    await ctx.reply("This is no longer a quote.")
                else:
                    await ctx.reply("No such quote.")

        case "timestamp" | "ts":
            try:
                i = int(rest[0])
                date = [int(x) for x in rest[1:]]
            except (ValueError, IndexError):
                await ctx.reply("Need to be all numbers.")
            else:
                if i < 0:
                    i += len(_quotes)
                if 0 <= i < len(_quotes):
                    try:
                        d = datetime.datetime(*date)
                    except Exception as e:
                        await ctx.reply(f"Error: {e.args[0]}")
                    else:
                        _quotes[i].ts = d
                        update = True
                        await ctx.reply(
                            f"Timestamp successfully changed to {d.isoformat()[:10]}. You have rewritten history."
                        )
                else:
                    await ctx.reply("No such quote.")

        case "delete" | "remove":
            try:
                i = int(rest[0])
            except (ValueError, IndexError):
                await ctx.reply("Nothing to delete or invalid input.")
            else:
                if i < 0:
                    i += len(_quotes)
                if 0 <= i < len(_quotes):
                    del _quotes[i]
                    update = True
                    await ctx.reply("This quote is now gone forever.")
                else:
                    await ctx.reply("I don't even HAVE that many quotes!")

        case "search" | "find":
            if not line:
                await ctx.reply("You need to search for something!")
                return

            line = line.lower()
            found = []
            for i, q in enumerate(_quotes):
                if line in q.line.lower():
                    found.append(i)
            match len(found):
                case 0:
                    await ctx.reply(
                        "No quotes match this. Maybe try narrowing it down?"
                    )
                case 1:
                    await ctx.reply(_get_quote(found[0]))
                case n:
                    if n > 20:  # sanity threshold
                        await ctx.reply(
                            "Too many quotes match this. Try a narrower search."
                        )
                    else:
                        await ctx.reply(
                            f"The quotes with this text are {', '.join(str(x) for x in found)}."
                        )

        case "list" | "json" | "db":
            if not _quotes:
                await ctx.reply("There are no quotes.")
                return

            await ctx.reply(f"You can see (barebones) quotes here: {config.server.url}/quotes/as-json")

        case "random":
            if not _quotes:
                await ctx.reply("There are no quotes.")
                return
            i = random.randint(0, len(_quotes) - 1)
            await ctx.reply(_get_quote(i))

        case e:
            try:
                i = int(e)
            except ValueError:
                await ctx.reply("I'm afraid I don't understand what that means.")
            else:
                if i < 0:
                    i += len(_quotes)
                if 0 <= i < len(_quotes):
                    await ctx.reply(_get_quote(i))
                else:
                    await ctx.reply("No such quote.")

    if update:
        _update_quotes()


def _get_quote(i: int):
    q = _quotes[i]
    if not q.is_quote:
        return q.line
    author = ""
    if q.author is not None:
        author = f" - {q.author}"
    added_by = ", on {ts}"
    # Keep that information, but don't display it for now. maybe later
    # if q.added_by:
    #    added_by = f" (Added by {q.added_by} on {{ts}})"
    added_by = added_by.format(ts=q.ts.isoformat()[:10])
    return f'Quote #{i}: "{q.line}"{author}{added_by}'


def _update_clips():
    c = [x.to_json() for x in _clips]
    with getfile("clips.json", "w") as f:
        json.dump(c, f, indent=config.server.json_indent)


async def setup_clips():
    assert _clips == [None], "already been setup"
    clips = []
    maps = {}
    try:
        with getfile("clips.json", "r") as f:
            cj = json.load(f)
    except FileNotFoundError:
        pass
    else:
        for id, adder, tags in cj:
            clips.append(id)
            maps[id] = (adder, tags)

    assert TConn is not None, "need Twitch active for this"

    if clips:
        try:
            result = await TConn.fetch_clips(clips)
        except HTTPException:
            return # idk

        result.sort(key=lambda x: clips.index(x.id))
        for clip in result:
            _clips.append(Clip(clip, *maps[clip.id]))

    if _clips.pop(0) is not None: # remove None, confirm it's been setup
        raise RuntimeError("Clips got setup twice, somehow")


class Clip:
    def __init__(self, data: TClip, added_by: str, tags: Iterable[str]):
        self.data = data
        self.added_by = added_by
        self.tags = set(tags)

    @property
    def cf_tags(self):
        return [x.casefold() for x in self.tags]

    def to_json(self):
        return [self.data.id, self.added_by, tuple(self.tags)]

    def __contains__(self, value: str):
        value = value.casefold()
        return value in self.cf_tags or value in self.data.title.casefold()

    def __eq__(self, value):
        return isinstance(value, Clip) and self.data.id == value.data.id


async def get_clip_info(url: str) -> TClip:
    assert _clips != [None], "setup clips first"
    if "/clip/" in url:
        id = urllib.parse.urlparse(url).path.partition("/clip/")[2]
    elif "clips.twitch.tv" in url:
        id = urllib.parse.urlparse(url).path[1:]
    else:
        id = url # idk man

    return ( await TConn.fetch_clips([id]) )[0]


@command("clip")
async def clip_cmd(ctx: ContextType, arg: str = "random", *rest: str):
    """Add a new clip or find a clip."""
    if _clips == [None]: # need to setup
        await setup_clips()
    if _clips == [None]:
        return await ctx.reply("The Twitch API broke, can't setup clips.")

    if "/clip/" in arg or "clips.twitch.tv" in arg:
        try:
            res = await get_clip_info(arg)
        except HTTPException:
            return await ctx.reply("This isn't a clip (or the Twitch API broke).")
        adder = ctx.author.display_name
        cl = Clip(res, adder, rest)
        if cl in _clips:
            return await ctx.reply("That clip exists already!")
        _clips.append(cl)
        _update_clips()
        return await ctx.reply(f"Clip {cl.data.title!r} has been added!")

    arg = arg.casefold()

    match arg:
        case "tags":
            try:
                i = int(rest[0])
                tags = rest[1:]
            except (ValueError, IndexError):
                return await ctx.reply("I need a clip number to edit tags.")
            if i < 0:
                i += len(_clips)
            if not (0 <= i < len(_clips)):
                return await ctx.reply("No such clip.")
            clip = _clips[i]
            if not tags:
                return await ctx.reply(f"This clip has the tags {', '.join(clip.tags)}.")
            for x in tags:
                fn = clip.tags.add
                if x[0] == "-":
                    x = x[1:]
                    fn = clip.tags.discard
                fn(x)
            _update_clips()
            await ctx.reply("Tags have been updated.")

        case "random":
            if not _clips:
                return await ctx.reply("We have no clips!")
            i = random.randint(0, len(_clips) - 1)
            await ctx.reply(f"Clip #{i}: https://clips.twitch.tv/{_clips[i].data.id}")

        case "delete" | "remove":
            try:
                i = int(rest[0])
            except (ValueError, IndexError):
                return await ctx.reply("I need a clip number to delete.")
            if i < 0:
                i += len(_clips)
            if not (0 <= i < len(_clips)):
                return await ctx.reply("No such clip.")
            await ctx.reply(f"Clip deleted. Enjoy it one last time: https://clips.twitch.tv/{_clips[i].data.id}")
            del _clips[i]
            _update_clips()

        case _:
            try:
                i = int(arg)
            except ValueError:
                pass
            else:
                if i < 0:
                    i += len(_clips)
                if not (0 <= i < len(_clips)):
                    return await ctx.reply("No such clip.")
                return await ctx.reply(f"Clip #{i}: https://clips.twitch.tv/{_clips[i].data.id}")
                
            # searching for a specific clip
            possible: list[tuple[int, Clip]] = []
            tags = (arg,) + rest
            for i, c in enumerate(_clips):
                matched = 0
                for tag in tags:
                    if tag in c:
                        matched += 1
                if matched == len(tags):
                    possible.append((i, c))

            match len(possible):
                case 0:
                    return await ctx.reply("No clips match all of those tags.")
                case 1:
                    return await ctx.reply(f"Clip #{possible[0][0]}: https://clips.twitch.tv/{possible[0][1].data.id}")
                case n:
                    if n <= 10:
                        return await ctx.reply(f"The clips that match are {', '.join(str(x[0]) for x in possible)}.")
                    return await ctx.reply("Too many clips match. Try adding more keywords to narrow it down?")

@command("bot")
async def bot_cmd(ctx: ContextType):
    """Give general information on the bot itself."""
    p = config.bot.prefix
    await ctx.reply(
        f"I am {__botname__} v{__version__}, made by {__author__}. Thanks to Baalor running a "
        f"script on his computer, I can access the game's data for commands like {p}neow and "
        f"{p}boss, as well as the {config.server.url}/current page. I am running on Python "
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}, "
        f"my source code is at {p}github, and you can financially support "
        f"my continued development with {p}donate"
    )

@command("help")
async def help_cmd(ctx: ContextType, name: str = ""):
    """Find help on the various commands in the bot."""
    if not name:
        p = config.bot.prefix
        await ctx.reply(
            f"Welcome to the stream! Website: {config.server.url} | Current run: {p}current | "
            f"Stream overlay: {p}str | Useful commands: {p}discord {p}mods {p}neow {p}boss "
            f"{p}stats {p}games {p}youtube {p}winrate | Silly commands: {p}the {p}dig {p}lift "
            f"{p}quote | All commands: {p}commands | Specific help: {p}help <command> | About this bot: {p}bot"
        )
        return

    tcmd = dcmd = None
    if TConn is not None:
        tcmd = TConn.get_command(name)
    if DConn is not None:
        dcmd = DConn.get_command(name)
    cmd = tcmd or dcmd
    if cmd:
        await ctx.reply(
            f"Full information about this command can be viewed at {config.server.url}/commands/{cmd.name}"
        )
        return

    await ctx.reply(
        f"Could not find matching command. You may view all existing commands here: {config.server.url}/commands"
    )


@command("support", "shoutout", "so")
async def shoutout(ctx: ContextType, name: str):
    """Give a shoutout to a fellow streamer."""
    try:
        chan = await TConn.fetch_channel(name)
    except IndexError as e:
        await ctx.send(e.args[0])
        return
    except HTTPException as e:
        await ctx.send(e.message)
        return

    msg = [f"Go give a warm follow to https://twitch.tv/{chan.user.name} -"]

    live: list[Stream] = await TConn.fetch_streams([chan.user.id])
    if live:
        stream = live[0]
        game = stream.game_name
        viewers = stream.viewer_count
        started_at = stream.started_at
        # somehow, doing now() - started_at triggers an error due to conflicting timestamps
        td = datetime.timedelta(
            seconds=(datetime.datetime.now().timestamp() - started_at.timestamp())
        )
        msg.append(
            f"they are currently live with {viewers} viewers playing {game}! They have been live for {str(td).partition('.')[0]}"
        )

    else:
        msg.append(
            f"last time they were live, they were seen playing {chan.game_name}!"
        )

    await ctx.send(" ".join(msg))


@command("title")
async def stream_title(ctx: ContextType):
    """Display the current stream title."""
    live: list[Stream] = await TConn.fetch_streams(user_logins=[config.twitch.channel])

    if live:
        await ctx.reply(live[0].title)
    else:
        await ctx.reply("Could not connect to the Twitch API (or stream is offline).")


@command("uptime")
async def stream_uptime(ctx: ContextType):
    """Display the stream uptime."""
    live: list[Stream] = await TConn.fetch_streams(user_logins=[config.twitch.channel])

    if live:
        td = datetime.timedelta(
            seconds=(
                datetime.datetime.now().timestamp() - live[0].started_at.timestamp()
            )
        )
        await ctx.reply(f"The stream has been live for {str(td).partition('.')[0]}")
    else:
        await ctx.reply("Stream is offline (if this is wrong, the Twitch API broke).")


@add_listener("run_end")
async def fetch_run_offset(run: RunParser):
    """Fetch and store the run start offset."""
    live: list[Stream] = await TConn.fetch_streams(user_logins=[config.twitch.channel])

    if live: # just in case
        started = live[0].started_at
        runtime = run.timestamp # should be very close to now
        duration = datetime.timedelta(0, run.playtime)

        run_start = runtime - duration

        offset = run_start - started

        try:
            with getfile("offsets.json", "r") as f:
                j = json.load(f)
        except FileNotFoundError:
            j = {}

        j[run.name] = offset.total_seconds()

        with getfile("offsets.json", "w") as f:
            json.dump(j, f, indent=config.server.json_indent)


# DO NOT MERGE INTO MAIN UNTIL THE FOLLOWING IS COMPLETELY DONE
# im merging it and you cant stop me. suck it, past faely!!!
# TODO:
# [X] Cover all basic cases (classic, extended, more)
# [X] When receiving the run file at the end, automatically resolve prediction
# [ ] (optional) Figure out announcement so the bot can tell chat to vote
# [ ] Test the heck out of it (does not need to be automated tests)
# [ ] Implement create, info, resolve, cancel, sync
# [ ] Add a way to lock in prediction after... something
# [ ] Have enough text variety that it doesn't get repetitive
# [X] Refuse to create a prediction if a Neow bonus was picked
#
# More info:
# - Type 'classic' is prediction with only win/lose options
# - Type 'extended' is 5 outcomes (death in each act+win)
# - Other types do not need to be about a Spire outcome (e.g. FTL)
# - Character is *optional* and could be used for text
# - If a savefile exists (but no Neow bonus was picked), use character from that and ignore 'char' argument
# - Duration is is to be coerced to an int but we should accept things like "5m" and be clever about it
# - If for a Spire run outcome, and a savefile is detected, disallow resolving or cancelling it
# - TwitchIO's PartialUser (of which User is a subclass) has method end_prediction

_prediction = {
    "running": False,
    "type": None,
    "pred": None,
}


async def start_prediction(
    ctx: TContext, title: str, outcomes: list[str], duration: int
):
    user = await ctx.channel.user()
    value = await post_prediction(TConn, user.id, title, outcomes, duration)
    _prediction["pred"] = value
    _prediction["running"] = True


async def resolve_prediction(index: int):
    pred: Prediction = _prediction["pred"]
    outcome = pred.outcomes[index]
    _prediction["running"] = False
    _prediction["type"] = None
    _prediction["pred"] = None
    # todo: there's some bug here, idk what, but it's fine. probably. it resolves, anyway
    await pred.user.end_prediction(
        TConn._http.token, pred.prediction_id, "RESOLVED", outcome.outcome_id
    )


@add_listener("run_end")
async def auto_resolve_pred(run: RunParser):
    if _prediction["running"]:
        match _prediction["type"]:
            case "classic":
                await resolve_prediction(not run.won)
            case "extended":
                await resolve_prediction(run.acts_beaten)
            case a:
                raise RuntimeError(f"Unsupported prediction type {a!r} encountered.")


@command("prediction", "pred", discord=False, flag="m")
async def handle_prediction(ctx: TContext, type: str = "info", *args: str):
    # TODO: After poll feature is added, if it was to pick a character to play, immediately start a prediction
    return await ctx.reply("Predictions are currently disabled.")
    match type:
        case "start" | "create":
            if _prediction["running"]:
                return await ctx.reply("A prediction is already running.")

            values = {
                "char": None,  # limited to 15 characters, if any
                "type": "classic",
                "duration": "300",
            }
            for pair in args:
                key, eq, val = pair.partition("=")
                val = val.replace("_", " ")  # just in case
                if not eq:
                    return await ctx.reply(
                        f"Needs key-value pair ('{pair}' is invalid)."
                    )
                if key in values:
                    values[key] = val
                else:
                    return await ctx.reply(f"Error: key {key!r} is not recognized.")

            save = get_savefile()
            if save.in_game and save.neow_bonus.choice_made:
                return await ctx.reply(
                    "Cannot start a prediction after a Neow bonus was picked."
                )

            try:
                duration = int(values["duration"])
            except ValueError:
                return await ctx.reply("Duration must be an integer if specified.")

            match values["type"]:
                case "classic":
                    outcomes = [
                        random.choice(_prediction_terms["classic"]["victory"])[:25],
                        random.choice(_prediction_terms["classic"]["defeat"])[:25],
                    ]

                case "extended":
                    outcomes = [
                        random.choice(_prediction_terms["extended"]["act1_death"])[:25],
                        random.choice(_prediction_terms["extended"]["act2_death"])[:25],
                        random.choice(_prediction_terms["extended"]["act3_death"])[:25],
                        random.choice(_prediction_terms["extended"]["act4_death"])[:25],
                        random.choice(_prediction_terms["extended"]["victory"])[:25],
                    ]

                case a:
                    return await ctx.reply(
                        f"Error: prediction type {a!r} is not recognized."
                    )

            char = values["char"]
            if save.in_game:
                char = save.character

            if char is not None:
                if len(char) > 15:
                    return await ctx.reply(
                        "Character ('char') cannot be longer than 15 characters if provided."
                    )
                title = random.choice(
                    _prediction_terms[values["type"]]["char_title"]
                ).format(char)[:45]
            else:
                title = random.choice(_prediction_terms[values["type"]]["title"])[:45]

            _prediction["type"] = values["type"]
            await start_prediction(ctx, title, outcomes, duration)
            await ctx.send(
                "baalorWaffle Predict with your channel points on the outcome of this run! baalorWaffle"
            )

        case "info" | "cancel":
            await ctx.reply("Sadly, that's not been implemented yet.")

        case "resolve":
            if not _prediction["running"]:
                return await ctx.reply("No prediction is running.")

            if not args:
                return await ctx.reply(
                    "Please provide a number to resolve the prediction with."
                )

            try:
                idx = int(args[0])
            except ValueError:
                return await ctx.reply(
                    "This should be a number, not... whatever this is."
                )

            if 0 <= idx < len(_prediction["pred"].outcomes):
                await resolve_prediction(idx)
                await ctx.send("Results are in! Did you win?")
            else:
                await ctx.reply("And how do you plan to do that?")

        case a:
            await ctx.reply(f"I don't know what {a!r} means.")


@command("playing", "nowplaying", "spotify", "np")
async def now_playing(ctx: ContextType):
    """Return the currently-playing song on Spotify (if any)."""
    if not config.server.debug and not TConn.live_channels[config.twitch.channel]:
        # just in case
        TConn.live_channels[config.twitch.channel] = live = bool(
            await TConn.fetch_streams(user_logins=[config.twitch.channel])
        )
        if not live:
            await ctx.reply("That's kinda creepy, not gonna lie...")
            return

    j = await TConn.spotify_call()
    if j is None:
        await ctx.reply("Could not get token from Spotify API. Retry in a few seconds.")
    elif "error" in j:
        await ctx.reply(
            f"Something went wrong with the Spotify API ({j['status']}: {j['message']})"
        )
    elif j["is_playing"]:
        await ctx.reply(
            f"We are listening to {j['item']['name']} on the album {j['item']['album']['name']}."
        )
    else:
        await ctx.reply("We are not currently listening to anything.")


@router.get("/playing")
async def now_playing_client(req: Request):
    await get_req_data(req)  # just checking if key is OK

    if TConn is None:  # no Twitch, no Spotify
        raise HTTPServiceUnavailable(reason="Need Twitch connection for Spotify")

    data = await TConn.spotify_call()

    if data:
        return Response(text=json.dumps(data), content_type="application/json")
    raise HTTPServiceUnavailable(reason="Could not connect to the Spotify API")


_ongoing_giveaway = {
    "running": False,
    "count": 0,
    "users": set(),
    "starter": None,
}


@command("giveaway", flag="m")
async def giveaway_handle(ctx: ContextType, count: int = 1):
    """Manage a giveaway."""

    if not _ongoing_giveaway["running"]:
        _ongoing_giveaway["running"] = True
        _ongoing_giveaway["starter"] = ctx.author.name
        if count > 0:
            _ongoing_giveaway["count"] = count
        else:
            _ongoing_giveaway["count"] = 1
        await ctx.send(
            f"A giveaway has started! Type {config.bot.prefix}enter to enter!"
        )

    elif _ongoing_giveaway["starter"] != ctx.author.name:
        await ctx.reply("Only the person who started the giveaway can resolve it!")

    else:
        _ongoing_giveaway["running"] = False
        _ongoing_giveaway["starter"] = None
        _ongoing_giveaway["users"].discard(None)  # just in case
        if not _ongoing_giveaway["users"]:
            await ctx.reply("uhhh, no one entered??")
            return

        # TODO: replace with random.sample, maybe?
        users = random.choices(
            list(_ongoing_giveaway["users"]), k=_ongoing_giveaway["count"]
        )
        _ongoing_giveaway["users"].clear()
        if len(users) == 1:
            await ctx.send(f"Congratulations to {users[0]}, you have won the giveaway!")
        else:
            await ctx.send(
                f"Congratulations to the following users for winning the giveaway: {', '.join(users)}"
            )


@command("enter", burst=25, rate=1.0)
async def giveaway_enter(ctx: ContextType):
    """Enter into the current giveaway."""
    # it's a set, dupes won't do matter. don't respond to not spam
    if not _ongoing_giveaway["running"]:
        await ctx.reply("No giveaway is happening")
        return

    _ongoing_giveaway["users"].add(ctx.author.name)


@command("info", "cardinfo", "relicinfo")
async def card_info(ctx: ContextType, *line: str, _cache={}):
    # TODO: improve this
    if False:
        mods = ["slaythespire", "downfall", "packmaster"]

        line = " ".join(line).lower() + " ".join(mods)

        line = urllib.parse.quote(line)

        if "session" not in _cache:
            _cache["session"] = ClientSession()

        session: ClientSession = _cache["session"]

        async with session.get(f"https://slay.ocean.lol/s?{line}%20limit=1") as resp:
            if resp.ok:
                j = await resp.json()
                j = j[0]["item"]
                desc = j["description"].replace("\n", " ")
                pack = j.get("pack")
                mod = j["mod"]
                if pack:
                    mod = f"Pack: {pack}"
                if mod == "Slay the Spire":
                    mod = None
                text = ""
                if mod:
                    text = f" ({mod})"
                await ctx.reply(
                    f"{j['name']} ({j['rarity']} {j['type']}): {desc} - {j['character'][0]}{text}"
                )
                return

    line = " ".join(line)
    info: Base = query(line)
    if info is None:
        await ctx.reply(f"Could not find info for {line!r}")
        return

    await ctx.reply(info.info)


@command("mtinfo")
async def mt_info(ctx: ContextType, *line: str):
    line = " ".join(line)
    info = mt_query(line)
    if info is None:
        await ctx.reply(f"Could not find info for {line!r}")
        return

    await ctx.reply(info.info)


@command("card", "cardart")
async def card_with_art(ctx: ContextType, *line: str):
    line = " ".join(line)
    info: Base = query(line)
    if info is None:
        await ctx.reply(f"Could not find card {line!r}")
        return
    if info.cls_name != "card":
        await ctx.reply(
            f"Can only find art for cards. Use {config.bot.prefix}info instead."
        )
        return

    info: Card

    base = "https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/"
    mod = urllib.parse.quote(info.mod or "Slay the Spire").lower()
    id = format_for_slaytabase(info.internal)
    link = f"{mod}/cards/{id}.png"

    await ctx.reply(
        f"{base}{link}"
    )


@with_savefile("cache", flag="m")
async def save_cache(ctx: ContextType, save: Savefile, arg: str, *args: str):
    # TODO: 'cache reload', to reload the JSON, but it needs a bunch of state changing
    # (need to clear all the commands from both bots first)
    match arg:
        case "clear":
            save._cache.clear()
            save._cache["self"] = save
            await ctx.reply("Cache cleared.")
        case "key" | "find":
            if arg == "key":
                val = save._cache
            else:
                val = get_parser(args[0])._cache
            for a in args:
                try:
                    val = getattr(val, a)
                except AttributeError:
                    try:
                        a = int(a)
                    except ValueError:
                        pass
                    try:
                        val = val[a]
                    except (IndexError, KeyError, TypeError):
                        break

            await ctx.reply(f"Value in cache: {val}")
        case a:
            await ctx.reply(f"Argument {a!r} not recognized.")


@with_savefile("bluekey", "sapphirekey", "key")
async def bluekey(ctx: ContextType, save: Savefile):
    """Display what was skipped for the Sapphire key."""
    if not save.keys.sapphire_key_obtained:
        await ctx.reply("We do not have the Sapphire key.")
        return

    for node in save.path:
        if isinstance(node, Treasure):
            if node.blue_key:
                await ctx.reply(
                    f"We skipped {node.key_relic} on floor {node.floor} for the Sapphire key."
                )
                return

    await ctx.reply("RunHistoryPlus is not running; cannot get data.")


@with_savefile("removals", "removed")
async def cards_removed(ctx: ContextType, save: Savefile):
    """Display which cards were removed."""
    removed = []
    for card, floor in save.removals:
        removed.append(f"{card} on floor {floor}")
    if not removed:
        await ctx.reply("We did not remove any cards yet.")
    else:
        await ctx.reply(f"We removed {len(removed)} cards: {', '.join(removed)}.")


@with_savefile("neow", "neowbonus")
async def neowbonus(ctx: ContextType, save: Savefile):
    """Display what the Neow bonus was."""
    if not save.neow_bonus.choice_made:
        await ctx.reply("No Neow bonus taken yet.")
    else:
        await ctx.reply(
            f"Option taken: {save.neow_bonus.boon_picked} {save.neow_bonus.as_str() if save.neow_bonus.has_info else ''}"
        )


@with_savefile("neowskipped", "skippedbonus")
async def neow_skipped(ctx: ContextType, save: Savefile):
    if not save.neow_bonus.choice_made:
        await ctx.reply("No Neow bonus taken yet.")
    else:
        await ctx.reply(f"Options skipped: {' | '.join(save.neow_bonus.boons_skipped)}")


@with_savefile("pandora", "pbox", "pandorasbox")
async def what_if_box(ctx: ContextType, save: Savefile):
    """Tell us what the Pandora's Box gave us."""
    pbox = None
    for data in save.relics:
        if data.name == "Pandora's Box":
            pbox = data
            break

    # what if n'loth steals our box?
    if pbox is None and "Nloth's Gift" in save._data["relics"]:
        for evt in save._data["metric_event_choices"]:
            if evt["event_name"] == "N'loth":
                if evt["relics_lost"][0] == "Pandora's Box":
                    pbox = RelicData(save, "Pandora's Box")
                break

    if pbox is not None:
        cards = pbox.get_stats()
        formatted = ", ".join(get(x).name for x in cards)
        await ctx.reply(f"Pandora's Box gave us {formatted}")
    else:
        await ctx.reply("We do not have Pandora's Box.")


@with_savefile("seed", "currentseed")
async def seed_cmd(ctx: ContextType, save: Savefile):
    """Display the run's current seed."""
    await ctx.reply(
        f"Current seed: {save.seed}{' (set manually)' if save.is_seeded else ''}"
    )


@with_savefile("seeded", "isthisseeded")
async def is_seeded(ctx: ContextType, save: Savefile):
    """Display whether the current run is seeded."""
    if save.is_seeded:
        await ctx.reply(
            f"This run is seeded! See '{config.bot.prefix}seed' for the seed."
        )
    else:
        await ctx.reply(
            "This run is not seeded! Everything you're seeing is unplanned!"
        )


@with_savefile("playtime", "runtime", "time", "played")
async def run_playtime(ctx: ContextType, save: Savefile):
    """Display the current playtime for the run."""
    start = save.timestamp - save.timedelta
    seconds = int(time.time() - start.timestamp())
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    await ctx.reply(
        f"This run has been going on for {hours}:{minutes:>02}:{seconds:>02}"
    )


@with_savefile("shopremoval", "cardremoval", "removal")
async def shop_removal_cost(ctx: ContextType, save: Savefile):
    """Display the current shop removal cost."""
    await ctx.reply(
        f"Current card removal cost: {save.current_purge} (removed {save.purge_totals} card{'' if save.purge_totals == 1 else 's'})"
    )


@with_savefile("shopprices", "shopranges", "shoprange", "ranges", "shop", "prices")
async def shop_prices(ctx: ContextType, save: Savefile):
    """Display the current shop price ranges."""
    cards, colorless, relics, potions = save.shop_prices
    cc, uc, rc = cards
    ul, rl = colorless
    cr, ur, rr = relics
    cp, up, rp = potions
    await ctx.reply(
        f"Cards: Common {cc.start}-{cc.stop}, Uncommon {uc.start}-{uc.stop}, Rare {rc.start}-{rc.stop} | "
        f"Colorless: Uncommon {ul.start}-{ul.stop}, Rare {rl.start}-{rl.stop} | "
        f"Relics: Common/Shop {cr.start}-{cr.stop}, Uncommon {ur.start}-{ur.stop}, Rare {rr.start}-{rr.stop} | "
        f"Potions: Common {cp.start}-{cp.stop}, Uncommon {up.start}-{up.stop}, Rare {rp.start}-{rp.stop} | "
        f"Card removal: {save.current_purge}"
    )


@with_savefile("rest", "heal", "restheal")
async def campfire_heal(ctx: ContextType, save: Savefile):
    """Display the current heal at campfires."""
    base = int(save.max_health * 0.3)
    for relic in save.relics:
        if relic.name == "Regal Pillow":
            base += 15
            break

    lost = max(0, (base + save.current_health) - save.max_health)
    extra = ""
    if lost:
        extra = f" (extra healing lost: {lost} HP)"

    await ctx.reply(f"Current campfire heal: {base} HP{extra}")


@with_savefile("nloth")
async def nloth_traded(ctx: ContextType, save: Savefile):
    """Display which relic was traded for N'loth's Gift."""
    if get("Nloth's Gift") not in save.relics_bare:
        await ctx.reply("We do not have N'loth's Gift.")
        return

    for node in save.path:
        if isinstance(node, Event): # this check isn't strictly needed, but it makes the type checker happy
            if node.name == "N'loth":
                return await ctx.reply(f"We traded {node.relics_lost[0].name} for N'loth's Gift.")

    await ctx.reply("Something went terribly wrong.")


@with_savefile("eventchances", "event")
async def event_likelihood(ctx: ContextType, save: Savefile):
    """Display current event chances for the various possibilities in ? rooms."""
    # note: this does not handle pRNG calls like it should - event_seed_count might have something? though only appears to be count of seen ? rooms
    elite, hallway, shop, chest = save.event_chances
    # elite likelihood is only for the "Deadly Events" custom modifier

    await ctx.reply(
        f"Event type likelihood: "
        f"Normal fight: {hallway:.0%} - "
        f"Shop: {shop:.0%} - "
        f"Treasure: {chest:.0%} - "
        f"Event: {1-hallway-shop-chest:.0%} - "
        f"See {config.bot.prefix}eventrng for more information."
    )


@with_savefile("rare", "rarecard", "rarechance")  # see comment in save.py -- this is not entirely accurate
async def rare_card_chances(ctx: ContextType, save: Savefile):
    """Display the current chance to see rare cards in rewards and shops."""
    regular, elites, shops = save.rare_chance
    await ctx.reply(
        f"The current chance of seeing a rare card is {regular:.2%} "
        f"in normal fight card rewards, {elites:.2%} in elite fight "
        f"card rewards, and {shops:.2%} in shops."
    )


@with_savefile("relic")
async def relic_info(ctx: ContextType, save: Savefile, index: int = 0):
    """Display information about the current relics."""
    l = list(save.relics)
    if not index:
        await ctx.reply(f"We have {len(l)} relics.")
        return
    if index < 0:
        index = len(l) + index + 1
    if index > len(l) or index <= 0:
        await ctx.reply(f"We only have {len(l)} relics!")
        return

    relicData = l[index - 1]
    stats = ""
    if (s := relicData.get_details()):
        stats = " (" + " | ".join(s) + ")"
    await ctx.reply(
        f"The relic at position {index} is {relicData.name}: {relicData.relic.description}{stats}"
    )


@with_savefile("allrelics", "offscreen", "page2")
async def relics_page2(ctx: ContextType, save: Savefile):
    """Display the relics on page 2."""
    l = list(save.relics)
    if len(l) <= 25:
        await ctx.reply("We only have one page of relics!")
        return

    relics = []
    for relic in l[25:]:
        relics.append(relic.name)

    await ctx.reply(f"The relics past page 1 are {', '.join(relics)}")


@with_savefile("seen", "seenrelic", "available")
async def seen_relic(ctx: ContextType, save: Savefile, *relic: str):
    """Output whether a given relic has been seen."""
    relic = " ".join(relic)
    relics = [relic]

    # Check if the relic is referencing a relic set:
    relic_set = query(relic)
    if isinstance(relic_set, RelicSet):
        relics = relic_set.relic_list

    replies = []
    for relic in relics:
        data: Relic = query(relic)
        if not data:
            replies.append(f"Could not find relic {relic!r}.")
        elif data.cls_name != "relic":
            replies.append("Can only look for relics seen.")
        elif data in save.relics_bare:
            replies.append(
                f"We already have {data.name}! It's at position {save.relics_bare.index(data)+1}."
            )
        elif data.tier not in ("Common", "Uncommon", "Rare", "Shop"):
            match data.tier:
                case "Boss":
                    s = f"For boss relics, see {config.bot.prefix}picked instead."
                case "Starter":
                    s = "Starter relics can't exactly be seen during a run. What?"
                case "Special":
                    s = "We can only see Special relics from events."
                case a:
                    s = f"This relic is tagged as rarity {a!r}, and I don't know what that means."
            replies.append(
                f"We can only check for Common, Uncommon, Rare, or Shop relics. {s}"
            )
        elif save.available_relic(data):
            replies.append(
                f"We have not seen {data.name} yet! There's a chance we'll see it!"
            )
        else:
            s = ""
            if data.pool:
                s = " (or maybe it doesn't belong to this character)"
            replies.append(
                f"We have already seen {data.name} this run{s}, and cannot get it again baalorHubris"
            )
    await ctx.reply("\n".join(replies))


@with_savefile("skipped", "picked", "skippedboss", "bossrelic")
async def skipped_boss_relics(ctx: ContextType, save: Savefile):
    """Display the boss relics that were taken and skipped."""
    choices = save.boss_relics
    if not choices:
        await ctx.reply("We have not picked any boss relics yet.")
        return

    skip_template = "We saw {1[0]}, {1[1]} and {1[2]} at the end of Act {0} and skipped all that junk! baalorBoot"
    template = "We picked {1[0]} at the end of Act {0}, and skipped {1[1]} and {1[2]}."
    msg = []
    i = 1
    for picked, skipped in choices:
        use = skip_template
        args = []
        if picked is not None:
            use = template
            args.append(picked.name)
        args.extend(x.name for x in skipped)

        msg.append(use.format(i, args))
        i += 1

    await ctx.reply(" ".join(msg))


@with_savefile("bottle", "bottled", "bottledcards", "bottledcard")
async def bottled_cards(ctx: ContextType, save: Savefile):
    """List all bottled cards."""
    emoji_dict = {
        "Bottled Flame": "\N{FIRE}",
        "Bottled Lightning": "\N{HIGH VOLTAGE SIGN}",
        "Bottled Tornado": "\N{CLOUD WITH TORNADO}",
    }
    bottle_strings: list[str] = []
    for bottle in save.bottles:
        bottle_strings.append(f"{emoji_dict[bottle.bottle_id]} {bottle.card}")

    if bottle_strings:
        await ctx.reply(", ".join(bottle_strings))
    else:
        await ctx.reply("We do not have any bottled cards.")


@with_savefile("dagger", "ritualdagger") # TODO: add tests for these
async def dagger_scaling(ctx: ContextType, save: Savefile):
    """Get the damage value of Ritual Dagger."""
    ret = []
    scaling = save.get_meta_scaling_cards()
    for card, num in scaling:
        if "RitualDagger" in card: # account for upgrade
            ret.append((card, num))

    match len(ret):
        case 0:
            await ctx.reply("We do not have a Ritual Dagger.")
        case 1:
            card, num = ret[0]
            name = "Ritual Dagger"
            if card.endswith("+"):
                name += "+"
            await ctx.reply(f"{name} is currently at {num} damage.")
        case n:
            last = ret[-1][1]
            rest = [str(x[1]) for x in ret[:-1]]
            await ctx.reply(f"Our Ritual Daggers are at {', '.join(rest)} and {last} damage.")


@with_savefile("algo", "genetic", "algorithm")
async def algo_scaling(ctx: ContextType, save: Savefile):
    """Get the block value of Genetic Algorithm."""
    ret = []
    scaling = save.get_meta_scaling_cards()
    for card, num in scaling:
        if "Genetic Algorithm" in card: # account for upgrade
            ret.append((card, num))

    match len(ret):
        case 0:
            await ctx.reply("We do not have a Genetic Algorithm.")
        case 1:
            card, num = ret[0]
            await ctx.reply(f"{card} is currently at {num} block.")
        case n:
            last = ret[-1][1]
            rest = [str(x[1]) for x in ret[:-1]]
            await ctx.reply(f"Our Genetic Algorithms are at {', '.join(rest)} and {last} block.")


@with_savefile("custom", "modifiers")
async def modifiers(ctx: ContextType, save: Savefile):
    """List all custom modifiers for the run."""
    if save.modifiers:
        await ctx.reply(", ".join(save.modifiers))
    else:
        await ctx.reply("This is a standard run.")


@with_savefile("score")
async def score(ctx: ContextType, save: Savefile):
    """Display the current score of the run"""
    if save.modded:
        await ctx.reply(f"Current Score: ~{save.score} points")
    else:
        await ctx.reply(f"Current Score: {save.score} points")


@mt_command("clans")
async def mt_clans(ctx: ContextType, save: MonsterSave):
    main = save.main_class
    if save.main_exiled:
        main = f"{main} (Exiled)"
    sub = save.sub_class
    if save.sub_exiled:
        sub = f"{sub} (Exiled)"
    await ctx.reply(f"The clans are {main} and {sub}.")


@mt_command("mutators")
async def mt_mutators(ctx: ContextType, save: MonsterSave):
    if m := save.mutators:
        val = ", ".join(f"{x.name} ({x.description})" for x in m)
        await ctx.reply(f"The mutators are: {val}")


# @mt_command("challenge")
async def mt_challenge(ctx: ContextType, save: MonsterSave):
    if not save.challenge:
        await ctx.reply("We are not currently playing an Expert Challenge.")
    else:
        await ctx.reply(
            f"We are currently playing the Expert Challenge {save.challenge.info}."
        )


@mt_command("artifact")
async def mt_artifact(ctx: ContextType, save: MonsterSave, index: int = 0):
    l = list(save.artifacts)
    if not index:
        await ctx.reply(f"We have {len(l)} artifacts.")
        return
    if index < 0:
        index = len(l) + index + 1
    if index > len(l) or index <= 0:
        await ctx.reply(f"We only have {len(l)} artifacts!")
        return

    relicData = l[index - 1]
    await ctx.reply(f"The artifact at position {index} is {relicData.info}")


@mt_command("pyre")
async def mt_pyre(ctx: ContextType, save: MonsterSave):
    ability = ""
    if save.pyre.ability:
        ability = f" (Ability: {save.pyre.ability})"
    await ctx.reply(f"We are using {save.pyre.name}: {save.pyre.description}{ability}")


@slice_command("curses")
async def curses(ctx: ContextType, save: CurrentRun):
    """Display the current run's curses."""
    await ctx.reply(
        f"We are running Classic on {save.difficulty} with {'; '.join(save.modifiers)}."
    )


@slice_command("items")
async def items(ctx: ContextType, save: CurrentRun):
    """Display the current run's unequipped items."""
    if save.items:
        await ctx.reply(f"The unequipped items are {'; '.join(save.items)}.")
    else:
        await ctx.reply("We have no unequipped items.")


@command("fairyreleased", "released")
async def fairy_released(ctx: ContextType):
    """Get the count of fairy that have been released after the Heart."""
    count = 0
    for run in _runs_cache.values():
        if run.won:
            for pot in run.path[-2].discarded_potions:
                if pot.internal == "FairyPotion":
                    count += 1

    await ctx.reply(f"We have freed {count} fairies at the top of the Spire!")


@command("last")
async def get_last(ctx: ContextType, arg1: str = "", arg2: str = ""):
    """Get the last run/win/loss."""
    char = None
    won = None
    value = None
    if arg2:
        value = [arg1.lower(), arg2.lower()]
    elif arg1:
        value = [arg1.lower()]
    match value:
        case None:
            pass  # nothing to worry about
        case ["win"] | ["victory"] | ["w"]:
            won = True
        case ["loss"] | ["death"] | ["l"]:
            won = False
        case [a]:
            char = a
        case [a, b]:
            match a:
                case "win" | "victory" | "w":
                    won = True
                    char = b
                case "loss" | "death" | "l":
                    won = False
                    char = b
                case _:
                    char = a
                    match b:
                        case "win" | "victory" | "w":
                            won = True
                        case "loss" | "death" | "l":
                            won = False

    match char:
        case "ironclad" | "ic" | "i":
            char = "Ironclad"
        case "silent" | "s":
            char = "Silent"
        case "defect" | "d":
            char = "Defect"
        case "watcher" | "wa":
            char = "Watcher"
        case _:
            if char is not None:
                char = char.capitalize()  # might be a mod character

    await _last_run(ctx, char, won)


@command("lastrun")
async def get_last_run(ctx: ContextType):
    """Get the last run."""
    await _last_run(ctx, None, None)


@command("lastwin", "lastvictory")
async def get_last_win(ctx: ContextType):
    """Get the last win."""
    await _last_run(ctx, None, True)


@command("lastloss", "lastdeath")
async def get_last_loss(ctx: ContextType):
    """Get the last loss."""
    await _last_run(ctx, None, False)


async def _last_run(ctx: ContextType, character: str | None, arg: bool | None):
    try:
        latest = get_latest_run(character, arg)
        latest.won  # making sure it's not None
    except (KeyError, AttributeError):
        await ctx.reply(f"Could not understand character {character}.")
        return
    value = "run"
    if character is not None:
        value = f"{character} run"
    if arg:
        value = f"winning {value}"
    elif arg is not None:
        value = f"lost {value}"
    await ctx.reply(
        f"The last {value}'s history can be viewed at {config.server.url}/runs/{latest.name}"
    )


@command("next")
async def next_run(ctx: ContextType):
    """Return which character is next in the rotation."""
    save = get_savefile()
    if save.character is not None and save.profile.index == 0:
        return await ctx.reply("You're watching it right now!")

    latest = get_latest_run(None, None)
    while latest.profile.index != 0:
        latest = latest.matched.prev

    c = ("Ironclad", "Silent", "Defect", "Watcher")
    try:
        i = c.index(latest.character)
    except ValueError:
        return await ctx.reply("Something went wrong.")

    if i == 3:
        i = -1

    await ctx.reply(f"The next run will be with {c[i+1]}.")

@command("wall")
async def wall_card(ctx: ContextType):
    """Fetch the card in the wall for the ladder savefile."""
    for i in range(2):
        p = get_profile(i)
        if p is not None and "ladder" in p.name.lower():
            break
    else:
        await ctx.reply("Error: could not find Ladder savefile.")
        return

    await ctx.reply(
        f"Current card in the {config.bot.prefix}hole in the wall for the ladder savefile: {p.hole_card}"
    )


@command("range", flag="me")
async def set_run_stats_by_date(ctx: ContextType, date_string: str):
    """Update the default range for the run stats by date, this is separate from the all-time stats run cache."""
    if date_string == "reset":
        update_range(None, None)
        await ctx.reply("Range has been reset for all-time stats")
        return

    try:
        date_tuple = parse_date_range(date_string)
    except:
        await ctx.reply(
            "Invalid date string. Use YYYY/MM/DD-YYYY/MM/DD (MM and DD optional), YYYY/MM/DD+ (no end date), YYYY/MM/DD- (no start date)"
        )
        return
    update_range(date_tuple[0], date_tuple[1])
    await ctx.reply("Run stats have been updated for the given range")


@command("kills", "wins")
async def calculate_wins_cmd(ctx: ContextType, date_string: Optional[str] = None):
    """Display the cumulative number of wins for an optional date range."""
    msg = "A20 Heart kills ({0.date_range_string}): Total: {1.all_character_count} - Ironclad: {1.ironclad_count} - Silent: {1.silent_count} - Defect: {1.defect_count} - Watcher: {1.watcher_count}"
    await _send_standard_run_stats_message(ctx, msg, "all_wins", date_string)


@command("losses")
async def calculate_losses_cmd(ctx: ContextType, date_string: Optional[str] = None):
    """Display the cumulative number of losses for an optional date range."""
    msg = "A20 Heart losses ({0.date_range_string}): Total: {1.all_character_count} - Ironclad: {1.ironclad_count} - Silent: {1.silent_count} - Defect: {1.defect_count} - Watcher: {1.watcher_count}"
    await _send_standard_run_stats_message(ctx, msg, "all_losses", date_string)


async def _send_standard_run_stats_message(
    ctx: ContextType, msg: str, prop_name: str, date_string: Optional[str] = None
):
    run_stats = None
    if date_string is None:
        run_stats = get_run_stats_by_date()
    else:
        try:
            run_stats = get_run_stats_by_date_string(date_string)
        except ValueError:
            await ctx.reply(
                "Invalid date string or start date was after end date. Use YYYY/MM/DD-YYYY/MM/DD (MM and DD optional), YYYY/MM/DD+ (no end date), YYYY/MM/DD- (no start date)"
            )
            return
        except TypeError:
            await ctx.reply("Start date is after end date")
            return
    await ctx.reply(msg.format(run_stats, getattr(run_stats, prop_name)))


_display = []
_words = ("Rotating", "Ironclad", "Silent", "Defect", "Watcher")


def _get_set_display():
    if not _display:  # we get
        with open(os.path.join("data", "streak")) as f:
            toggles = f.read().strip()

        for i in toggles:
            _display.append(int(i))

    elif _display:  # we set
        with open(os.path.join("data", "streak"), "w") as f:
            f.write("".join(str(i) for i in _display))


@command("rotation", "display", flag="m")
async def streak_display(ctx: ContextType, new: str):
    """Change the !streak command display."""
    value = "risdw"
    word = []
    _display.clear()
    for i, l in enumerate(value):
        if l in new:
            _display.append(1)
            word.append(_words[i])
        else:
            _display.append(0)
    _get_set_display()
    await ctx.reply(f"Streak display changed to {', '.join(word)}.")


@command("streak")
async def calculate_streak_cmd(ctx: ContextType):
    """Display Baalor's current streak for Ascension 20 Heart kills."""
    if not _display:
        _get_set_display()
    msg = []
    for i, l in enumerate(_display):
        if l:
            word = _words[i]
            arg = (
                f"{word.lower()}_count" if word != "Rotating" else "all_character_count"
            )
            msg.append(f"{word}: {{0.{arg}}}")

    final = f"Current streak: {' - '.join(msg)}"
    run_stats = get_all_run_stats()
    await ctx.reply(final.format(run_stats.streaks))


@command("pb")
async def calculate_pb_cmd(ctx: ContextType, date_string: Optional[str] = None):
    """Display Baalor's Personal Best streaks for Ascension 20 Heart kills for an optional date range."""
    msg = "Baalor's PB A20H Streaks ({0.date_range_string}) | Rotating: {1.all_character_count} - Ironclad: {1.ironclad_count} - Silent: {1.silent_count} - Defect: {1.defect_count} - Watcher: {1.watcher_count}"
    run_stats = None
    if date_string is None:
        run_stats = get_all_run_stats()
    else:
        try:
            run_stats = get_run_stats_by_date_string(date_string)
        except ValueError:
            await ctx.reply(
                "Invalid date string or start date was after end date. Use YYYY/MM/DD-YYYY/MM/DD (MM and DD optional), YYYY/MM/DD+ (no end date), YYYY/MM/DD- (no start date)"
            )
            return
        except TypeError:
            await ctx.reply("Start date is after end date")
            return
    await ctx.reply(msg.format(run_stats, run_stats.pb))


@command("wr", "worldrecords")
async def get_wrs(ctx: ContextType):
    url = "https://script.google.com/macros/s/AKfycbwwVnFP2FhAuTi1a4xh67uv_GYI63ggnX7e6wezlQmWlpr8z4B0IXVKuT_ta-seYnrt/exec?format=json"
    if TConn is not None:
        if TConn._session is None:
            TConn._session = ClientSession()
        client = TConn._session
    else:
        client = ClientSession()

    async with client.get(url) as resp:
        if not resp.ok:
            return await ctx.reply("Sorry, couldn't access the data. Try again later.")
        data = await resp.json()

    msg = []

    for char in _words:
        c = data[char.lower()]
        line = f"{char}: {c['streak']} by {c['username']}"
        if c['ongoing']:
            line += " (ongoing)"
        msg.append(line)

    await ctx.reply(f"As far as we know, these are the current A20H world records: {' | '.join(msg)} -- For Baalor's own records, see {config.bot.prefix}pb")


@command("winrate")
async def calculate_winrate_cmd(ctx: ContextType, date_string: Optional[str] = None):
    """Display the winrate for Baalor's A20 Heart kills for an optional date range."""
    run_stats = None
    if date_string is None:
        run_stats = get_run_stats_by_date()
    else:
        try:
            run_stats = get_run_stats_by_date_string(date_string)
        except ValueError:
            await ctx.reply(
                "Invalid date string or start date was after end date. Use YYYY/MM/DD-YYYY/MM/DD (MM and DD optional), YYYY/MM/DD+ (no end date), YYYY/MM/DD- (no start date)"
            )
            return
        except TypeError:
            await ctx.reply("Start date is after end date")
            return
    wins = [
        run_stats.all_wins.all_character_count,
        run_stats.all_wins.ironclad_count,
        run_stats.all_wins.silent_count,
        run_stats.all_wins.defect_count,
        run_stats.all_wins.watcher_count,
    ]
    losses = [
        run_stats.all_losses.all_character_count,
        run_stats.all_losses.ironclad_count,
        run_stats.all_losses.silent_count,
        run_stats.all_losses.defect_count,
        run_stats.all_losses.watcher_count,
    ]
    rate = [0 if (a + b == 0) else a / (a + b) for a, b in zip(wins, losses)]
    await ctx.reply(
        f"Baalor's winrate ({run_stats.date_range_string}): Overall: {rate[0]:.2%} - Ironclad: {rate[1]:.2%} - Silent: {rate[2]:.2%} - Defect: {rate[3]:.2%} - Watcher: {rate[4]:.2%}"
    )


@with_savefile("unmastered", optional_save=True)
async def unmastered(ctx: ContextType, save: Savefile):
    if save is not None and "unmastered" in save._cache:
        await ctx.reply(save._cache["unmastered"])
        return

    cards = get_mastered().mastered_cards

    final = []

    for value in _internal_cache.values():
        if value.cls_name != "card":
            continue
        value: Card
        if value.mod is not None:
            continue
        if (
            value.type == "Status" or value.rarity == "Special"
        ):  # all "special" ones are already mastered
            continue

        if value.name not in cards:
            final.append(value.name)

    msg = ""
    if len(final) > 1:
        msg = f"The cards left to master are {', '.join(final)}."
    elif len(final) == 1:
        msg = f"The final card left to master is {final[0]}."
    else:
        msg = "Mastery Challenge Complete! Nothing left to master! baalorEZ baalorX2"

    if save is not None:
        save._cache["unmastered"] = msg

    await ctx.reply(msg)


@command("mastered")
async def mastered_stuff(ctx: ContextType, *card: str):
    """Tell us whether a certain card or relic is mastered."""
    mastery_stats = get_mastered()
    # total = (75 * 4) + 39 + 13 # 178 relics
    # chars = {"Red": "Ironclad", "Green": "Silent", "Blue": "Defect", "Purple": "Watcher"}
    # d = defaultdict(dict)

    # for card, (color, char, ts) in cards.items():
    #    d[color][card] = (char, ts)

    # msg = ["Current mastery progression:"]

    info = query("".join(card))
    if info is None:
        await ctx.reply(f"Could not find card or relic {' '.join(card)}.")
        return

    if info.mod:
        await ctx.reply("We do not attempt to master modded content.")
        return

    match info.cls_name:
        case "card":
            d = mastery_stats.mastered_cards
        case "relic":
            d = mastery_stats.mastered_relics
        case _:
            await ctx.reply("Only cards or relics may be mastered.")
            return

    if info.name in d:
        await ctx.reply(
            f"The {info.cls_name} {info.name} IS mastered! Run: {config.server.url}/runs/{d[info.name].name}"
        )
    else:
        await ctx.reply(f"The {info.cls_name} {info.name} is NOT mastered.")


@with_savefile("candidates")
async def current_mastery_check(ctx: ContextType, save: Savefile):
    """Output what cards in the current run can be mastered if won."""
    one_ofs, cards_can_master, relics_can_master = get_current_masteries(save)
    if cards_can_master:
        await ctx.reply(
            f"The cards that can be mastered this run are: {', '.join(cards_can_master)}"
        )
    else:
        await ctx.reply(f"There are no new cards in this run that can be mastered.")


@with_savefile("cwbgh", "cwbg", optional_save=True)
async def calipers(ctx: ContextType, save: Optional[Savefile]):
    msg = "Calipers would be good here baalorCalipers baalorSmug"
    if save:
        if 'Barricade' in save.deck_card_ids:
            msg = "Who needs calipers when we have Barricade!? baalorStare"
        elif query("calipers") in save.relics_bare:
            msg = "Calipers ARE good here! baalorCalipers baalorSmug"
        elif 'Blur' in save.deck_card_ids:
            msg = "We have Calipers at home! baalorSmug\nAt home: Blur"
        elif not save.available_relic(query("calipers")):
            msg = "Calipers would have been good here... baalorHubris"
    await ctx.reply(msg)

@with_savefile("mods", optional_save=True)
async def active_mods(ctx: ContextType, save: Savefile):
    # use the old message if we don't have info from activemods
    msg = "Baalor uses a variety of mods for the stream. You can see a list of all mods here: https://baalorlord.tv/mods"
    if save and save.has_activemods:
        names = [x.name for x in save.mods]
        mods = ", ".join(names[:-1])
        mods += f", and {names[-1]}"
        msg += f"\nFor this run, we're using the mods {mods}.\nFor more info, try !mod [mod name]"

    await ctx.reply(msg)

@with_savefile("mod")
async def active_mod_info(ctx: ContextType, save: Savefile, *modname):
    # don't do anything if we don't have info from activemods
    if save.has_activemods:
        modname = " ".join(modname).strip()

        if len(modname) == 0:
            choice = random.choice([x.name for x in save.mods])
            msg = f"This can tell you information about a specific mod.  Use it like this: !mod {choice}"
        else:
            mod = save.find_mod(modname)

            if mod is None:
                msg = f"Couldn't find any mod called {modname}"
            else:                                
                msg = f"{mod.name} was created by {mod.authors_formatted}.\nDescription: {mod.description_formatted}\nTry it out here: {mod.mod_url}"

        await ctx.reply(msg)


@router.get("/commands")
@template("commands.jinja2")
async def commands_page(req: Request):
    d = {"prefix": config.bot.prefix, "botname": config.bot.name, "commands": []}
    cmds = set()
    if TConn is not None:
        cmds.update(TConn.commands)
    if DConn is not None:
        cmds.update(DConn.all_commands)
    d["commands"].extend(cmds)
    d["commands"].sort()
    return d


@router.get("/commands/{name}")
@template("command_single.jinja2")
async def individual_cmd(req: Request):
    name = req.match_info["name"]
    d = {"name": name}
    tcmd = dcmd = None
    if TConn is not None:
        tcmd: TwitchCommand = TConn.get_command(name)
    if DConn is not None:
        dcmd: DiscordCommand = DConn.get_command(name)
    cmd = tcmd or dcmd
    if cmd is None:
        raise HTTPNotFound()
    if name in _cmds:
        d["builtin"] = False
        output: str = _cmds[name]["output"]
        try:
            output = output.format(
                user="<username>", text="<text>", words="<words>", **_consts
            )
        except KeyError:
            pass
        out = []
        for word in output.split():
            if "<" in word:
                word = word.replace("<", "&lt")
            if word.startswith("http"):
                word = f'<a href="{word}">{word}</a>'
            out.append(word)
        d["output"] = " ".join(out)
        d["enabled"] = _cmds[name].get("enabled", True) is True
        d["aliases"] = _cmds[name].get("aliases", [])
        # Just in case it's not a list...
        if not isinstance(d["aliases"], list):
            d["aliases"] = [d["aliases"]]
    else:
        d["builtin"] = True
        d["fndoc"] = cmd.__doc__
        d["enabled"] = cmd.enabled

    # d["twitch"] = ("No" if tcmd is None else "Yes")
    # d["discord"] = ("No" if dcmd is None else "Yes")
    d["twitch"] = tcmd
    d["discord"] = dcmd

    d["permissions"] = ", ".join(_perms[x] for x in cmd.flag) or _perms[""]
    d["prefix"] = config.bot.prefix

    return d


@router.post("/report")
async def automatic_client_report(req: Request):
    data = (await get_req_data(req, "traceback"))[0]
    ar = config.discord.auto_report
    if not ar.enabled or not ar.server or not ar.channel:
        raise HTTPServiceUnavailable

    guild = DConn.get_guild(ar.server)
    if guild is None:
        raise HTTPServiceUnavailable
    channel = guild.get_channel(ar.channel)
    if channel is None:
        raise HTTPServiceUnavailable

    await channel.send("[Automatic Client Reporting]\n\n" + data)
    return Response()


_oauth_state = None


@router.post("/twitch/check-token")
async def check_token_validity(req: Request):
    await get_req_data(req)  # check if the key is OK
    if not config.twitch.enabled:
        return Response(text="DISABLED")
    if not (config.twitch.client_id and config.twitch.client_secret):
        return Response(text="NO_CREDENTIALS")

    if str(config.twitch.owner_id) in TConn.tokens:
        return Response(text="WORKING")

    # Need to authenticate for the first time (presumably)

    import secrets, urllib.parse

    global _oauth_state
    _oauth_state = secrets.token_urlsafe(16)

    params = {
        "client_id": config.twitch.client_id,
        "redirect_uri": f"{config.server.url}/twitch/receive-token",
        "response_type": "code",
        "scope": " ".join(config.twitch.scopes),
        "state": _oauth_state,
    }

    url = "https://id.twitch.tv/oauth2/authorize?" + urllib.parse.urlencode(params)

    return Response(text=f"NEEDS_CONNECTION:{url}")


@router.view("/twitch/receive-token")
async def get_new_token(req: Request):
    values = req.query
    global _oauth_state
    if values["state"] != _oauth_state:
        return

    _oauth_state = None

    if "error" in values or "code" not in values:
        return  # idk man, not much you can do

    client = ClientSession()

    form = {
        "client_id": config.twitch.client_id,
        "client_secret": config.twitch.client_secret,
        "code": values["code"],
        "grant_type": "authorization_code",
        "redirect_uri": f"{config.server.url}/twitch/receive-token",
    }

    import urllib.parse

    enc = urllib.parse.urlencode(form)

    async with client.post(f"https://id.twitch.tv/oauth2/token?{enc}") as resp:
        if resp.ok:
            data = await resp.json()
            await TConn.add_token(data["access_token"], data["refresh_token"])

    await client.close()

    return Response(text="Handshake successful! You may now close this tab.")

async def Twitch_startup():
    global TConn

    TConn = TwitchConn(
        #token=config.twitch.oauth_token,
        prefix=config.bot.prefix,
        #initial_channels=[config.twitch.channel],
        case_insensitive=True,
        client_id=config.twitch.client_id,
        client_secret=config.twitch.client_secret,
        bot_id=config.twitch.bot_id,
        owner_id=config.twitch.owner_id,
        subscriptions=_eventsub_subs,
        force_subscribe=True,
    )

    await TConn.start()

async def Twitch_cleanup():
    if TConn._session is not None:
        await TConn._session.close()
    await TConn.save_tokens()
    await TConn.close()


async def Discord_startup():
    global DConn
    DConn = DiscordConn(
        config.bot.prefix,
        case_insensitive=True,
        owner_ids=config.discord.owners,
        help_command=None,
        intents=discord.Intents.all(),
    )
    for cmd in _to_add_discord:
        DConn.add_command(cmd)
    await DConn.start(config.discord.oauth_token)


async def Discord_cleanup():
    await DConn.close()


async def Youtube_startup():
    ref = 60
    prev = ""
    if TConn is not None:
        if TConn._session is None:
            TConn._session = ClientSession()
        client = TConn._session
    else:
        client = ClientSession()
    async with client as session:
        logger.info(f"Starting Youtube playlist sheet download. Will refresh every {ref}s.")
        while True:
            text = ""
            async with session.get(config.youtube.playlist_sheet) as response:
                text = await response.text()
            if text == prev or not text: # no need to update anything (or nothing to update)
                await asyncio.sleep(ref)
                continue
            data = text.splitlines()
            # We're using DictReader with a defined set of fields so that if any keys are added to
            # the sheet the display code here won't break.
            reader = csv.DictReader(data, fieldnames=(
                "Game", "Youtube Link", "Origin", "Steam Link",
            ))
            # Skip the header line (needed when setting fieldnames)
            next(reader)
            # Serialize from a special object down to a pure list so we can json dump later
            playlists.clear()
            playlists.extend(reader)
            prev = text
            await asyncio.sleep(ref)

async def Archive_startup():
    logger.info("Fetching YouTube Archive run information.")
    archive.archive.load_from_disk()
    while True:
        if not await archive.archive.load_from_api():
            logger.info("Failed to fetch archive data.")
        archive.archive.determine_offset()
        archive.archive.write_to_disk()
        await asyncio.sleep(config.youtube.cache_timeout)
