# (c) Anilyka Barry, 2022

from __future__ import annotations

from typing import Generator, Callable

import datetime
import random
import string
import json
import sys
import re
import os

from twitchio.ext.commands import Cooldown as TCooldown, Bucket as TBucket, Bot as TBot
from twitchio.ext.routines import routine, Routine
from twitchio.ext.eventsub import EventSubClient, StreamOnlineData, StreamOfflineData
from twitchio.channel import Channel
from twitchio.chatter import Chatter
from twitchio.errors import HTTPException
from twitchio.models import Stream

import discord
from discord.ext.commands import Cooldown as DCooldown, BucketType as DBucket, Bot as DBot, command as _dcommand

from aiohttp_jinja2 import template
from aiohttp.web import Request, HTTPNotFound

from nameinternal import get_relic
from sts_profile import get_profile, get_current_profile
from webpage import router, __botname__, __version__, __github__, __author__
from wrapper import wrapper
from twitch import TwitchCommand
from logger import logger
from disc import DiscordCommand
from save import get_savefile, Savefile
from runs import get_latest_run

from typehints import ContextType, CommandType
import events

import config

TConn: TwitchConn = None
DConn: DiscordConn = None

logger.info("Setting up")

# Twitch bot server defined here - process started in main.py

_DEFAULT_BURST = 1
_DEFAULT_RATE  = 3.0

_consts = {
    "discord": config.discord_invite_link,
    "prefix": config.prefix,
    "website": config.website_url,
}

class Formatter(string.Formatter): # this does not support conversion or formatting
    def __init__(self):
        super().__init__()
        self._re = re.compile(r".+(\(.+\)).*")

    def parse(self, format_string: str) -> Generator[tuple[str, str | None, str | None, None]]:
        if format_string is None: # recursion
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

            field = format_string[idx+2:end]

            called = None
            call_args = self._re.match(field)
            if call_args:
                called = call_args.group(1)
                call_idx = field.index(called)
                field = field[:call_idx]
                called = called[1:-1]

            yield (lit, field, called, None)
            start = end+1

    def format_field(self, value: Callable, call_args: str) -> str:
        if call_args:
            return value(call_args)
        return str(value)

_formatter = Formatter()

_perms = {
    "": "Everyone",
    "m": "Moderator",
    "e": "Editor", # this has no effect in discord
}

_cmds: dict[str, dict[str, list[str] | bool | int | float]] = {} # internal json

_to_add_twitch: list[TwitchCommand] = []
_to_add_discord: list[DiscordCommand] = []

_timers: dict[str, Routine] = {}

def _get_sanitizer(ctx: ContextType, name: str, args: list[str], mapping: dict):
    async def _sanitize(require_args: bool = True, in_mapping: bool = True) -> bool:
        """Verify that user input is sane. Return True if input is sane."""

        if require_args and not args:
            await ctx.send("Error: no output provided.")
            return False

        if in_mapping and name not in mapping:
            await ctx.send(f"Error: command {name} does not exist!")
            return False

        if not in_mapping and name in mapping:
            await ctx.send(f"Error: command {name} already exists!")
            return False

        return True

    return _sanitize

def _getfile(x: str, mode: str):
    return open(os.path.join("data", x), mode)

def _update_db():
    with _getfile("data.json", "w") as f:
        json.dump(_cmds, f, indent=config.json_indent)

def _create_cmd(output):
    async def inner(ctx: ContextType, *s, output: str=output):
        try:
            msg = output.format(user=ctx.author.display_name, text=" ".join(s), words=s, **_consts)
        except KeyError as e:
            msg = f"Error: command has unsupported formatting key {e.args[0]!r}"
        keywords = {"savefile": None, "profile": get_current_profile(), "readline": readline}
        if "$<savefile" in msg:
            keywords["savefile"] = await get_savefile(ctx)
            if keywords["savefile"] is None:
                return
        msg = _formatter.vformat(msg, (), keywords)
        await ctx.send(msg)
    return inner

def readline(file: str) -> str:
    with open(os.path.join("text", file), "r") as f:
        return random.choice(f.readlines())

def load():
    _cmds.clear()
    with _getfile("data.json", "r") as f:
        _cmds.update(json.load(f))
    for name, d in _cmds.items():
        c = command(
            name,
            *d.get("aliases", []),
            flag=d.get("flag", ""),
            burst=d.get("burst", _DEFAULT_BURST),
            rate=d.get("rate", _DEFAULT_RATE)
        )(_create_cmd(d["output"]))
        c.enabled = d.get("enabled", True)
    with _getfile("disabled", "r") as f:
        for disabled in f.readlines():
            TConn.commands[disabled].enabled = False

def add_cmd(name: str, *, aliases: list[str] = None, source: str = None, flag: str = None, burst: int = None, rate: float = None, output: str):
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
    _update_db()

def command(name: str, *aliases: str, flag: str = "", force_argcount: bool = False, burst: int = _DEFAULT_BURST, rate: float = _DEFAULT_RATE, twitch: bool = True, discord: bool = True):
    def inner(func, wrapper_func=None):
        wrapped = wrapper(func, force_argcount, wrapper_func, name)
        wrapped.__cooldowns__ = [TCooldown(burst, rate, TBucket.default)]
        wrapped.__commands_cooldown__ = DCooldown(burst, rate, DBucket.default)
        if twitch:
            tcmd = TwitchCommand(name=name, aliases=list(aliases), func=wrapped, flag=flag)
            if TConn is None:
                _to_add_twitch.append(tcmd)
            else:
                TConn.add_command(tcmd)
        if discord:
            dcmd = _dcommand(name, DiscordCommand, aliases=list(aliases), flag=flag)(wrapped)
            if DConn is None:
                _to_add_discord.append(dcmd)
            else:
                DConn.add_command(dcmd)
        return tcmd
    return inner

def with_savefile(name: str, *aliases: str, **kwargs):
    """Decorator for commands that require a save."""
    def inner(func):
        async def _savefile_get(ctx) -> list:
            res = await get_savefile(ctx)
            if res is None:
                raise ValueError("No savefile")
            return [res]
        return command(name, *aliases, **kwargs)(func, wrapper_func=_savefile_get)
    return inner

class TwitchConn(TBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.esclient: EventSubClient = None
        self.live_channels: dict[str, bool] = {}

    async def eventsub_setup(self):
        self.loop.create_task(self.esclient.listen(port=4000))
        self.live_channels[config.channel] = bool(await self.fetch_streams(user_logins=[config.channel]))

        try:
            await self.esclient.subscribe_channel_stream_start(broadcaster=config.channel)
            await self.esclient.subscribe_channel_stream_end(broadcaster=config.channel)
        except HTTPException:
            pass

    async def event_raw_usernotice(self, channel: Channel, tags: dict):
        user = Chatter(tags=tags, name=tags["login"], channel=channel, bot=self, websocket=self._connection)
        match tags["msg-id"]:
            case "sub" | "resub":
                total = 0
                consecutive = None
                subtype = ""
                try:
                    total = int(tags["msg-param-cumulative-months"])
                    if int(tags["msg-param-should-share-streak"]):
                        consecutive = int(tags["msg-param-streak-months"])
                    subtype: str = tags["msg-param-sub-plan"]
                    if subtype.isdigit():
                        subtype = f"Tier {subtype[0]}"
                except (KeyError, ValueError):
                    pass
                self.run_event("subscription", user, channel, total, consecutive, subtype)
            case "subgift" | "anonsubgift" | "submysterygift" | "giftpaidupgrade" | "rewardgift" | "anongiftpaidupgrade":
                self.run_event("gift_sub", user, channel, tags)
            case "raid":
                self.run_event("raid", user, channel, int(tags["msg-param-viewerCount"]))
            case "unraid":
                self.run_event("unraid", user, channel, tags)
            case "ritual":
                self.run_event("ritual", user, channel, tags)
            case "bitsbadgetier":
                self.run_event("bits_badge", user, channel, tags)

    async def event_subscription(self, user: Chatter, channel: Channel, total: int, consecutive: int | None, subtype: str):
        pass

    async def event_ritual(self, user: Chatter, channel: Channel, tags: dict):
        if tags["msg-param-ritual-name"] == "new_chatter":
            self.run_event("new_chatter", user, channel, tags["message"])

    async def event_new_chatter(self, user: Chatter, channel: Channel, message: str):
        if "youtube" in message.lower() or "yt" in message.lower():
            await channel.send(f"Hello {user.display_name}! Glad to hear that you're enjoying the YouTube content, and welcome along baalorLove")

    async def event_raid(self, user: Chatter, channel: Channel, viewer_count: int):
        if viewer_count < 10:
            return
        chan = await self.fetch_channel(user.id)
        await channel.send(f"Welcome along {user.display_name} with your {viewer_count} friends! "
                           f"Everyone, go give them a follow over at https://twitch.tv/{user.name} - "
                           f"last I checked, they were playing some {chan.game_name}!")

    def __getattr__(self, name: str):
        if name.startswith("event_"): # calling events -- insert our own event system in
            name = name[6:]
            evt = events.get(name)
            if evt:
                async def invoke(*args, **kwargs):
                    for e in evt:
                        e.invoke(args, kwargs)
                return invoke
        raise AttributeError(name)

class EventSubBot(TBot):
    async def event_eventsub_notification_stream_start(self, evt: StreamOnlineData):
        TConn.live_channels[evt.broadcaster.name] = True
        try:
            _timers["global"].start(config.global_commands, stop_on_error=False)
            _timers["sponsored"].start(config.sponsored_commands, stop_on_error=False)
        except RuntimeError: # already running; don't worry about it
            pass

    async def event_eventsub_notification_stream_end(self, evt: StreamOfflineData):
        TConn.live_channels[evt.broadcaster.name] = False
        _timers["global"].stop()
        _timers["sponsored"].stop()

class DiscordConn(DBot):
    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        if message.content.startswith(config.prefix) or isinstance(message.channel, discord.DMChannel):
            content = message.content.lstrip(config.prefix).split()
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

async def _timer(cmds: list[str]):
    chan = TConn.get_channel(config.channel)
    if not chan or not TConn.live_channels[config.channel]:
        return
    cmd = None
    i = 0
    while cmd is None:
        i += 1
        if i > len(cmds):
            return
        maybe_cmd = cmds.pop(0)
        if maybe_cmd not in _cmds and maybe_cmd not in TConn.commands:
            i -= 1 # we're not adding it back, so it's fine
            continue
        if not TConn.commands[maybe_cmd].enabled:
            cmds.append(maybe_cmd) # in case it gets enabled again
            continue
        if maybe_cmd == "current":
            save = await get_savefile()
            if save is None:
                cmds.append(maybe_cmd)
                continue
        cmd = maybe_cmd
    # don't use the actual command, just send the raw output
    msg: str = _cmds[cmd]["output"]
    try:
        msg = msg.format(**_consts)
    except KeyError:
        logger.error(f"Timer-command {cmd} needs non-constant formatting. Sending raw line.")
    await chan.send(msg)
    cmds.append(cmd)

@command("command", flag="me")
async def command_cmd(ctx: ContextType, action: str, name: str, *args: str):
    """Syntax: command <action> <name> <output>"""
    args = list(args)
    msg = " ".join(args)
    name = name.lstrip(config.prefix)
    cmds: dict[str, list[CommandType]] = {}
    if TConn is not None:
        for cname, cmd in TConn.commands.items():
            cmds[cname] = [cmd]
    if DConn is not None:
        for cmd in DConn.commands:
            if cmd.name not in cmds:
                cmds[cmd.name] = []
            cmds[cmd.name].append(cmd)
    aliases: dict[str, list[CommandType]] = {}
    if TConn is not None:
        for alias, cmd in TConn._command_aliases.items():
            aliases[alias] = [cmd]
    if DConn is not None:
        for dcmd in DConn.commands:
            for alias in dcmd.aliases:
                if alias not in aliases:
                    aliases[alias] = []
                aliases[alias].append(dcmd)

    sanitizer = _get_sanitizer(ctx, name, args, cmds)
    match action:
        case "add":
            if not await sanitizer(in_mapping=False):
                return
            if name in aliases:
                await ctx.send(f"Error: {name} is an alias to {aliases[name][0].name}. Use 'unalias {aliases[name][0].name} {name}' first.")
                return
            flag = ""
            if args[0].startswith("+"):
                flag, *args = args
            flag = flag[1:]
            if flag not in _perms:
                await ctx.send("Error: flag not recognized.")
                return
            if flag:
                add_cmd(name, flag=flag, output=msg)
            else:
                add_cmd(name, output=msg)
            command(name, flag=flag)(_create_cmd(msg))
            await ctx.send(f"Command {name} added! Permission: {_perms[flag]}")

        case "edit":
            if not await sanitizer():
                return
            if name in aliases:
                await ctx.send(f"Error: cannot edit alias. Use 'edit {aliases[name][0].name}' instead.")
                return
            if name not in _cmds:
                await ctx.send(f"Error: cannot edit built-in command {name}.")
                return
            _cmds[name]["output"] = msg
            flag = ""
            if args[0].startswith("+"):
                flag, *args = args
            if flag not in _perms:
                await ctx.send("Error: flag not recognized.")
                return
            if flag:
                _cmds[name]["flag"] = flag
            _update_db()
            for cmd in cmds[name]:
                cmd._callback = _create_cmd(msg)
            await ctx.send(f"Command {name} edited successfully! Permission: {_perms[flag]}")

        case "remove" | "delete":
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.send(f"Error: cannot delete alias. Use 'remove {aliases[name][0].name}' or 'unalias {aliases[name][0].name} {name}' instead.")
                return
            if name not in _cmds:
                await ctx.send(f"Error: cannot delete built-in command {name}.")
                return
            del _cmds[name]
            _update_db()
            if TConn is not None:
                TConn.remove_command(name)
            if DConn is not None:
                DConn.remove_command(name)
            await ctx.send(f"Command {name} has been deleted.")

        case "enable":
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.send(f"Error: cannot enable alias. Use 'enable {aliases[name][0].name}' instead.")
                return
            if all(cmds[name]):
                await ctx.send(f"Command {name} is already enabled.")
                return
            for cmd in cmds[name]:
                cmd.enabled = True
            if name in _cmds:
                _cmds[name]["enabled"] = True
                _update_db()
            with _getfile("disabled", "r") as f:
                disabled = f.readlines()
            disabled.remove(name)
            with _getfile("disabled", "w") as f:
                f.writelines(disabled)
            if name == "sponsored_cmd" and "sponsored" in _timers:
                _timers["sponsored"].restart()
            await ctx.send(f"Command {name} has been enabled.")

        case "disable":
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.send(f"Error: cannot disable alias. Use 'disable {aliases[name][0].name}' or 'unalias {aliases[name][0].name} {name}' instead.")
                return
            if not all(cmds[name]):
                await ctx.send(f"Command {name} is already disabled.")
                return
            for cmd in cmds[name]:
                cmd.enabled = False
            if name in _cmds:
                _cmds[name]["enabled"] = False
                _update_db()
            with _getfile("disabled", "r") as f:
                disabled = f.readlines()
            disabled.append(name)
            with _getfile("disabled", "w") as f:
                f.writelines(disabled)
            await ctx.send(f"Command {name} has been disabled.")

        case "alias": # cannot sanely sanitize this
            if not args:
                if name not in _cmds and name in aliases:
                    await ctx.send(f"Alias {name} is bound to {aliases[name][0].name}.")
                elif _cmds[name].get("aliases"):
                    await ctx.send(f"Command {name} has the following aliases: {', '.join(_cmds[name]['aliases'])}")
                else:
                    await ctx.send(f"Command {name} does not have any aliases.")
                return
            if name not in cmds and args[0] in cmds:
                await ctx.send(f"Error: use 'alias {args[0]} {name}' instead.")
                return
            if name not in cmds:
                await ctx.send(f"Error: command {name} does not exist.")
                return
            if name not in _cmds:
                await ctx.send("Error: cannot alias built-in commands.")
                return
            if set(args) & cmds.keys():
                await ctx.send(f"Error: aliases {set(args) & cmds.keys()} already exist as commands.")
                return
            for arg in args:
                if TConn is not None:
                    TConn._command_aliases[arg] = name
                if DConn is not None:
                    DConn.get_command(name).aliases.append(arg)
            if "aliases" not in _cmds[name]:
                _cmds[name]["aliases"] = []
            _cmds[name]["aliases"].extend(args)
            _update_db()
            await ctx.send(f"Command {name} now has aliases {', '.join(_cmds[name]['aliases'])}")

        case "unalias":
            if not args:
                await ctx.send("Error: no alias specified.")
                return
            if len(args) > 1:
                await ctx.send("Can only remove one alias at a time.")
                return
            if name not in cmds and args[0] in cmds:
                await ctx.send(f"Error: use 'unalias {args[0]} {name}' instead.")
                return
            if name not in cmds:
                await ctx.send(f"Error: command {name} does not exist.")
                return
            if args[0] not in aliases:
                await ctx.send("Error: not an alias.")
                return
            if name not in _cmds:
                await ctx.send("Error: cannot unalias built-in commands.")
                return
            if aliases[args[0]][0].name != name:
                await ctx.send(f"Error: alias {args[0]} does not match command {name} (bound to {aliases[args[0]][0].name}).")
                return
            if TConn is not None:
                TConn._command_aliases.pop(args[0], None)
            if DConn is not None:
                dcmd: DiscordCommand = DConn.get_command(name)
                if args[0] in dcmd.aliases:
                    dcmd.aliases.remove(args[0])
            _cmds[name]["aliases"].remove(name)
            _update_db()
            await ctx.send(f"Alias {args[0]} has been removed from command {name}.")

        case "cooldown" | "cd":
            await ctx.send("Cooldown cannot be changed currently")
            return
            if not await sanitizer(require_args=False):
                return
            if not args:
                if name not in cmds and name not in aliases:
                    await ctx.send(f"Error: command {name} does not exist.")
                else:
                    if name in aliases:
                        name = aliases[name]
                    cd = cmds[name]._cooldowns[0]
                    await ctx.send(f"Command {name} has a cooldown of {cd._per/cd._rate}s.")
                return
            if name in aliases:
                await ctx.send(f"Error: cannot edit alias cooldown. Use 'cooldown {aliases[name]}' instead.")
                return
            cd: TCooldown = cmds[name]._cooldowns.pop()
            try:
                burst = int(args[0])
            except ValueError:
                try:
                    rate = float(args[0])
                except ValueError:
                    await ctx.send("Error: invalid argument.")
                    return
                else:
                    burst = cd._rate # _rate is actually the burst, it's weird
            else:
                try:
                    rate = float(args[1])
                except IndexError:
                    rate = cd._per
                except ValueError:
                    await ctx.send("Error: invalid argument.")
                    return

            cmds[name]._cooldowns.append(TCooldown(burst, rate, cd.bucket))
            if name in _cmds:
                _cmds[name]["burst"] = burst
                _cmds[name]["rate"] = rate
                _update_db()
            await ctx.send(f"Command {name} now has a cooldown of {rate/burst}s.") # this isn't 100% accurate, but close enough
            if name not in _cmds:
                await ctx.send("Warning: settings on built-in commands do not persist past a restart.")

        case _:
            await ctx.send(f"Unrecognized action {action}.")

@command("help")
async def help_cmd(ctx: ContextType, name: str = ""):
    """Find help on the various commands in the bot."""
    if not name:
        await ctx.send(f"I am {__botname__} v{__version__}, made by {__author__}. I am running on Python "
                       f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}, and "
                       f"my source code is available at {__github__} . The website is {config.website_url}")
        return

    tcmd = dcmd = None
    if TConn is not None:
        tcmd = TConn.get_command(name)
    if DConn is not None:
        dcmd = DConn.get_command(name)
    cmd = (tcmd or dcmd)
    if cmd:
        await ctx.send(f"Full information about this command can be viewed at {config.website_url}/commands/{cmd.name}")
        return

    await ctx.send(f"Could not find matching command. You may view all existing commands here: {config.website_url}/commands")

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
        td = datetime.timedelta(seconds=(datetime.datetime.now().timestamp() - started_at.timestamp()))
        msg.append(f"they are currently live with {viewers} viewers playing {game}! They have been live for {str(td).partition('.')[0]}")

    else:
        msg.append(f"last time they were live, they were seen playing {chan.game_name}!")

    await ctx.send(" ".join(msg))

@command("title")
async def stream_title(ctx: ContextType):
    """Display the current stream title."""
    live: list[Stream] = await TConn.fetch_streams(user_logins=[config.channel])

    if live:
        await ctx.send(live[0].title)
    else:
        await ctx.send("Could not connect to the Twitch API (or stream is offline).")

@command("uptime")
async def stream_uptime(ctx: ContextType):
    """Display the stream uptime."""
    live: list[Stream] = await TConn.fetch_streams(user_logins=[config.channel])

    if live:
        td = datetime.timedelta(seconds=(datetime.datetime.now().timestamp() - live[0].started_at.timestamp()))
        await ctx.send(f"The stream has been live for {str(td).partition('.')[0]}")
    else:
        await ctx.send("Stream is offline (if this is wrong, the Twitch API broke).")

@with_savefile("bluekey", "sapphirekey", "key")
async def bluekey(ctx: ContextType, j: Savefile):
    """Display what was skipped for the Sapphire key."""
    if not j["has_sapphire_key"]:
        await ctx.send("We do not have the Sapphire key.")
        return

    if "BlueKeyRelicSkippedLog" not in j["basemod:mod_saves"]:
        await ctx.send("RunHistoryPlus is not running; cannot get data.")
        return

    d = j["basemod:mod_saves"]["BlueKeyRelicSkippedLog"]

    await ctx.send(f"We skipped {d['relicID']} on floor {d['floor']} for the Sapphire key.")

@with_savefile("neow", "neowbonus")
async def neowbonus(ctx: ContextType, j: Savefile):
    """Display what the Neow bonus was."""
    await ctx.send(f"Option taken: {j.neow_bonus.picked} {j.neow_bonus.as_str() if j.neow_bonus.has_info else ''}")

@with_savefile("seed", "currentseed")
async def seed_cmd(ctx: ContextType, j: Savefile):
    """Display the run's current seed."""
    await ctx.send(f"Current seed: {j.seed}{' (set manually)' if j['seed_set'] else ''}")

@with_savefile("seeded", "isthisseeded")
async def is_seeded(ctx: ContextType, j: Savefile):
    """Display whether the current run is seeded."""
    if j["seed_set"]:
        await ctx.send(f"This run is seeded! See '{config.prefix}seed' for the seed.")
    else:
        await ctx.send("This run is not seeded! Everything you're seeing is unplanned!")

@with_savefile("shopremoval", "cardremoval", "removal")
async def shop_removal_cost(ctx: ContextType, j: Savefile):
    """Display the current shop removal cost."""
    await ctx.send(f"Current card removal cost: {j.current_purge} (removed {j.purge_totals} card{'' if j.purge_totals == 1 else 's'})")

@with_savefile("shopprices", "shopranges", "shoprange", "ranges", "range", "shop", "prices")
async def shop_prices(ctx: ContextType, j: Savefile):
    """Display the current shop price ranges."""
    cards, colorless, relics, potions = j.shop_prices
    cc, uc, rc = cards
    ul, rl = colorless
    cr, ur, rr = relics
    cp, up, rp = potions
    await ctx.send(
        f"Cards: Common {cc.start}-{cc.stop}, Uncommon {uc.start}-{uc.stop}, Rare {rc.start}-{rc.stop} | "
        f"Colorless: Uncommon {ul.start}-{ul.stop}, Rare {rl.start}-{rl.stop} | "
        f"Relics: Common/Shop {cr.start}-{cr.stop}, Uncommon {ur.start}-{ur.stop}, Rare {rr.start}-{rr.stop} | "
        f"Potions: Common {cp.start}-{cp.stop}, Uncommon {up.start}-{up.stop}, Rare {rp.start}-{rp.stop} | "
        f"Card removal: {j.current_purge}"
    )

@with_savefile("rest", "heal", "restheal")
async def campfire_heal(ctx: ContextType, j: Savefile):
    """Display the current heal at campfires."""
    base = int(j.max_health * 0.3)
    for relic in j.relics:
        if relic.name == "Regal Pillow":
            base += 15
            break

    lost = max(0, (base + j.current_health) - j.max_health)
    extra = ""
    if lost:
        extra = f" (extra healing lost: {lost} HP)"

    await ctx.send(f"Current campfire heal: {base} HP{extra}")

@with_savefile("nloth")
async def nloth_traded(ctx: ContextType, j: Savefile):
    """Display which relic was traded for N'loth's Gift."""
    if "Nloth's Gift" not in j["relics"]:
        await ctx.send("We do not have N'loth's Gift.")
        return

    for evt in j["metric_event_choices"]:
        if evt["event_name"] == "N'loth":
            await ctx.send(f"We traded {get_relic(evt['relics_lost'][0])} for N'loth's Gift.")
            return
    else:
        await ctx.send("Something went terribly wrong.")

@with_savefile("eventchances", "event") # note: this does not handle pRNG calls like it should - event_seed_count might have something? though only appears to be count of seen ? rooms
async def event_likelihood(ctx: ContextType, j: Savefile):
    """Display current event chances for the various possibilities in ? rooms."""
    elite, hallway, shop, chest = j["event_chances"]
    # elite likelihood is only for the "Deadly Events" custom modifier

    await ctx.send(
        f"Event type likelihood: "
        f"Normal fight: {hallway:.0%} - "
        f"Shop: {shop:.0%} - "
        f"Treasure: {chest:.0%} - "
        f"Event: {hallway+shop+chest:.0%} - "
        f"See {config.prefix}eventrng for more information."
    )

@with_savefile("rare", "rarecard", "rarechance") # see comment in save.py -- this is not entirely accurate
async def rare_card_chances(ctx: ContextType, j: Savefile):
    """Display the current chance to see rare cards in rewards and shops."""
    regular, elites, shops = j.rare_chance
    await ctx.send(
        f"The rough likelihood of seeing a rare card is {regular:.2%} "
        f"in normal fight card rewards, {elites:.2%} in elite fight "
        f"card rewards, and {shops:.2%} in shops."
    )

@with_savefile("relic")
async def relic_info(ctx: ContextType, j: Savefile, index: int):
    """Display information about the current relics."""
    if index < 0:
        await ctx.send("Why do you insist on breaking me?")
        return
    l = list(j.relics)
    if index > len(l):
        await ctx.send(f"We only have {len(l)} relics!")
        return
    if not index:
        await ctx.send(f"We have {len(l)} relics.")
        return

    await ctx.send(f"The relic at position {index} is {l[index-1].name}.")

@with_savefile("skipped", "picked", "skippedboss", "bossrelic")
async def skipped_boss_relics(ctx: ContextType, j: Savefile):
    """Display the boss relics that were taken and skipped."""
    l: list[dict] = j["metric_boss_relics"]

    if not l:
        await ctx.send("We have not picked any boss relics yet.")
        return

    template = "We picked {1} at the end of Act {0}, and skipped {2} and {3}."
    msg = []
    i = 1
    for item in l:
        msg.append(
            template.format(
                i,
                get_relic(item["picked"]),
                get_relic(item["not_picked"][0]),
                get_relic(item["not_picked"][1]),
            )
        )
        i += 1

    await ctx.send(" ".join(msg))

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
            pass # nothing to worry about
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
                char = char.capitalize() # might be a mod character

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
    except KeyError:
        await ctx.send(f"Could not understand character {character}.")
        return
    value = "run"
    if character is not None:
        value = f"{character} run"
    if arg:
        value = f"winning {value}"
    elif arg is not None:
        value = f"lost {value}"
    await ctx.send(f"The last {value}'s history can be viewed at {config.website_url}/runs/{latest.name}")

@command("wall")
async def wall_card(ctx: ContextType):
    """Fetch the card in the wall for the ladder savefile."""
    for i in range(2):
        try:
            p = get_profile(i)
        except KeyError:
            continue
        if "ladder" in p.name.lower():
            break
    else:
        await ctx.send("Error: could not find Ladder savefile.")
        return

    await ctx.send(f"Current card in the {config.prefix}hole in the wall for the ladder savefile: {p.hole_card}")

@command("kills", "wins") # TODO: Read game files for this
async def kills_cmd(ctx: ContextType):
    """Display the cumulative number of wins for the year-long challenge."""
    msg = "A20 Heart kills in 2022: Total: {1} - Ironclad: {0[0]} - Silent: {0[1]} - Defect: {0[2]} - Watcher: {0[3]}"
    with _getfile("kills", "r") as f:
        kills = [int(x) for x in f.read().split()]
    await ctx.send(msg.format(kills, sum(kills)))

@command("losses")
async def losses_cmd(ctx: ContextType):
    """Display the cumulative number of losses for the year-long challenge."""
    msg = "A20 Heart losses in 2022: Total: {1} - Ironclad: {0[0]} - Silent: {0[1]} - Defect: {0[2]} - Watcher: {0[3]}"
    with _getfile("losses", "r") as f:
        losses = [int(x) for x in f.read().split()]
    await ctx.send(msg.format(losses, sum(losses)))

@command("streak")
async def streak_cmd(ctx: ContextType):
    """Display Baalor's current streak for Ascension 20 Heart kills."""
    msg = "Current streak: Rotating: {0[0]} - Ironclad: {0[1]} - Silent: {0[2]} - Defect: {0[3]} - Watcher: {0[4]}"
    with _getfile("streak", "r") as f:
        streak = f.read().split()
    await ctx.send(msg.format(streak))

@command("pb")
async def pb_cmd(ctx: ContextType):
    """Display Baalor's Personal Best streaks for Ascension 20 Heart kills."""
    msg = "Baalor's PB A20H Streaks | Rotating: {0[0]} - Ironclad: {0[1]} - Silent: {0[2]} - Defect: {0[3]} - Watcher: {0[4]}"
    with _getfile("pb", "r") as f:
        pb = f.read().split()
    await ctx.send(msg.format(pb))

@command("winrate")
async def winrate_cmd(ctx: ContextType):
    """Display the current winrate for Baalor's 2022 A20 Heart kills."""
    with _getfile("kills", "r") as f:
        kills = [int(x) for x in f.read().split()]
    with _getfile("losses", "r") as f:
        losses = [int(x) for x in f.read().split()]
    rate = [a/(a+b) for a, b in zip(kills, losses)]
    await ctx.send(f"Baalor's winrate: Ironclad: {rate[0]:.2%} - Silent: {rate[1]:.2%} - Defect: {rate[2]:.2%} - Watcher: {rate[3]:.2%}")

async def edit_counts(ctx: ContextType, arg: str, *, add: bool):
    if arg.lower().startswith("i"):
        i = 0
    elif arg.lower().startswith("s"):
        i = 1
    elif arg.lower().startswith("d"):
        i = 2
    elif arg.lower().startswith("w"):
        i = 3
    else:
        await ctx.send(f"Unrecognized character {arg}")
        return

    with _getfile("kills", "r") as f:
        kills = [int(x) for x in f.read().split()]
    with _getfile("losses", "r") as f:
        losses = [int(x) for x in f.read().split()]
    with _getfile("streak", "r") as f:
        streak = [int(x) for x in f.read().split()]
    cur = streak.pop(0)
    with _getfile("pb", "r") as f:
        pb = [int(x) for x in f.read().split()]
    rot = pb.pop(0)

    pb_changed = False

    if add:
        kills[i] += 1
        streak[i] += 1
        cur += 1
        if cur > rot:
            rot = cur
            pb_changed = True
        if streak[i] > pb[i]:
            pb[i] = streak[i]
            pb_changed = True

        with _getfile("kills", "w") as f:
            f.write(" ".join(str(x) for x in kills))
        if pb_changed:
            with _getfile("pb", "w") as f:
                f.write(f"{rot} {pb[0]} {pb[1]} {pb[2]} {pb[3]}")

    else:
        losses[i] += 1
        streak[i] = 0
        cur = 0

        with _getfile("losses", "w") as f:
            f.write(" ".join(str(x) for x in losses))

    with _getfile("streak", "w") as f:
        f.write(f"{cur} {streak[0]} {streak[1]} {streak[2]} {streak[3]}")

    d = ("Ironclad", "Silent", "Defect", "Watcher")

    if pb_changed:
        await ctx.send(f"[NEW PB ATTAINED] Win #{kills[i]} recorded for the {d[i]}. Total wins: {sum(kills)}")
    elif add:
        await ctx.send(f"Win #{kills[i]} recorded for the {d[i]}. Total wins: {sum(kills)}")
    else:
        await ctx.send(f"Loss #{losses[i]} recorded for the {d[i]}. Total losses: {sum(losses)}")

@command("win", flag="me", burst=1, rate=60.0) # 1:60.0 means we can't accidentally do it twice in a row
async def win_cmd(ctx: ContextType, arg: str):
    """Register a win for a given character."""
    await edit_counts(ctx, arg, add=True)

@command("loss", flag="me", burst=1, rate=60.0)
async def loss_cmd(ctx: ContextType, arg: str):
    """Register a loss for a given character."""
    await edit_counts(ctx, arg, add=False)

@router.get("/commands")
@template("commands.jinja2")
async def commands_page(req: Request):
    d = {"prefix": config.prefix, "commands": []}
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
    cmd = (tcmd or dcmd)
    if cmd is None:
        raise HTTPNotFound()
    if name in _cmds:
        d["builtin"] = False
        output: str = _cmds[name]["output"]
        try:
            output = output.format(user="<username>", text="<text>", words="<words>", **_consts)
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
        d["enabled"] = _cmds[name].get("enabled", True)
        d["aliases"] = ", ".join(_cmds[name].get("aliases", []))
    else:
        d["builtin"] = True
        d["fndoc"] = cmd.__doc__
        d["enabled"] = ("Yes" if cmd.enabled else "No")

    d["twitch"] = ("No" if tcmd is None else "Yes")
    d["discord"] = ("No" if dcmd is None else "Yes")

    d["permissions"] = ", ".join(_perms[x] for x in cmd.flag) or _perms[""]

    return d

async def Twitch_startup():
    global TConn
    TConn = TwitchConn(token=config.oauth, prefix=config.prefix, initial_channels=[config.channel], case_insensitive=True)
    for cmd in _to_add_twitch:
        TConn.add_command(cmd)
    load()

    esbot = EventSubBot.from_client_credentials(config.client_id, config.client_secret, prefix=config.prefix)
    TConn.esclient = EventSubClient(esbot, config.webhook_secret, f"{config.website_url}/callback")
    TConn.loop.run_until_complete(TConn.eventsub_setup())

    if config.global_interval and config.global_commands:
        _timers["global"] = _global_timer = routine(seconds=config.global_interval)(_timer)
        @_global_timer.before_routine
        async def before_global():
            await TConn.wait_for_ready()

        @_global_timer.error
        async def error_global(e):
            logger.error(f"Timer global error with {e}")

        if TConn.live_channels[config.channel]:
            _global_timer.start(config.global_commands, stop_on_error=False)

    if config.sponsored_interval and config.sponsored_commands:
        _timers["sponsored"] = _sponsored_timer = routine(seconds=config.sponsored_interval)(_timer)
        @_sponsored_timer.before_routine
        async def before_sponsored():
            await TConn.wait_for_ready()

        @_sponsored_timer.error
        async def error_sponsored(e):
            logger.error(f"Timer sponsored error with {e}")

        if TConn.live_channels[config.channel]:
            _sponsored_timer.start(config.sponsored_commands, stop_on_error=False)

    await TConn.connect()

async def Twitch_cleanup():
    await TConn.close()

async def Discord_startup():
    global DConn
    DConn = DiscordConn(config.prefix, case_insensitive=True, owner_ids=config.owners, help_command=None)
    for cmd in _to_add_discord:
        DConn.add_command(cmd)
    await DConn.start(config.token)

async def Discord_cleanup():
    await DConn.close()
