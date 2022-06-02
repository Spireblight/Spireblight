# (c) Anilyka Barry, 2022

# TODO: Split cmds into separate module (package?) for easy reload

from __future__ import annotations

from typing import Callable
import datetime
import asyncio
import random
import base64
import json
import re
import os

from twitchio.ext.commands import Context, Bot, Cooldown, Bucket
from twitchio.ext.commands import Command as _TCommand
from twitchio.channel import Channel
from twitchio.chatter import Chatter, PartialChatter
from twitchio.errors import HTTPException
from twitchio.models import Stream
#from discord.ext import commands as d_cmds
#import flask

import config

TConn: TwitchConn = None
_to_add_commands = []
_cache = {"live": (datetime.datetime.now(), False)}

_DEFAULT_BURST = 1
_DEFAULT_RATE  = 3.0
_DEFAULT_INTERVAL = 900

_consts = {
    "discord": "https://discord.gg/9XYVCSY",
}

_perms = {
    "": "Everyone",
    "m": "Moderator",
}

_timers: dict[str, Timer] = {}
_created_timers: set[str] = set()

async def _get_savefile_as_json(ctx: Context) -> dict:
    if not config.STS_path:
        await ctx.send("Could not find game files.")
        return

    possible = None
    for file in os.listdir(os.path.join(config.STS_path, "saves")):
        if file.endswith(".autosave"):
            if possible is None:
                possible = file
            else:
                await ctx.send("Multiple savefiles detected. Please delete or rename extraneous ones.")
                return

    if possible is None:
        await ctx.send("Not in a run.")
        return

    with open(os.path.join(config.STS_path, "saves", possible)) as f:
        decoded = base64.b64decode(f.read())
    arr = bytearray()
    for i, char in enumerate(decoded):
        arr.append(char ^ b"key"[i % 3])
    j = json.loads(arr)
    if "basemod:mod_saves" not in j: # make sure this key exists
        j["basemod:mod_saves"] = {}
    return j

def _get_sanitizer(ctx: Context, name: str, args: list[str], mapping: dict):
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

def _update_timers():
    timers_temp = {}
    for name, timer in _timers.items():
        timers_temp[name] = {"interval": timer.interval, "commands": timer.commands}
    with _getfile("timers.json", "w") as f:
        json.dump(timers_temp, f, indent=config.json_indent)

def _create_cmd(output):
    async def inner(ctx: Context, *s, output: str=output):
        try:
            name = ctx.author.display_name
        except AttributeError: # this fails for timers
            name = ctx.author.name
        await ctx.send(output.format(user=name, text=" ".join(s), words=s, **_consts))
    return inner

def _get_name(name: str) -> str:
    if " " not in name:
        maybe_name = re.match(r"([A-Z]\S+)([A-Z]\S+)", name)
        if maybe_name is not None:
            name = " ".join(maybe_name.groups())

    # relics
    name = name.replace("Egg 2", "Egg")
    name = name.replace("Greaves", "Boots")
    name = name.replace("Captains", "Captain's")
    name = name.replace("Slavers", "Slaver's")

    # cards
    if "+" in name:
        if not name.startswith("Searing"):
            name = name[:-1] # remove the number at the end

    return name

def load():
    _cmds.clear()
    for timer in _timers.values():
        timer.stop()
    _timers.clear()
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
    with _getfile("timers.json", "r") as f:
        timers_temp = json.load(f)
    for name, values in timers_temp.items():
        t = Timer(name, values["interval"])
        for c in values["commands"]:
            t.add_command(c, allow_duplicate=True)
        _timers[name] = t

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

def wrapper(func: Callable, force_argcount: bool):
    async def caller(ctx: Context, *args: str):
        new_args = []
        multiple = (co.co_flags & 0x04) # whether *args is supported
        for i, arg in enumerate(args, 1):
            if i < co.co_argcount:
                var = co.co_varnames[i]
            elif multiple: # all from here on will match the same type -- typically str, but could be something else
                var = co.co_varnames[co.co_argcount]
            else: # no *args and reached max argcount; no point in continuing
                break
            if var in func.__annotations__:
                expected = func.__annotations__[var]
                if expected == int:
                    try:
                        arg = int(arg)
                    except ValueError:
                        await ctx.send(f"Error: Argument #{i} ({var!r}) must be an integer.")
                        return
                elif expected == float:
                    try:
                        arg = float(arg)
                    except ValueError:
                        await ctx.send(f"Error: Argument #{i} ({var!r}) must be a floating point number.")
                        return
                elif expected == bool:
                    if arg.lower() in ("yes", "y", "on", "true", "1"):
                        arg = True
                    elif arg.lower() in ("no", "n", "off", "false", "0"):
                        arg = False
                    else:
                        await ctx.send(f"Error: Argument #{i} ({var!r}) must be parsable as a boolean value.")
                        return
                elif expected != str:
                    await ctx.send(f"Warning: Unhandled type {expected!r} for argument #{i} ({var!r}) - please ping @FaeLyka")
            new_args.append(arg)

        if req > len(new_args):
            names = co.co_varnames[len(new_args):req]
            if len(names) == 1:
                await ctx.send(f"Error: Missing required argument {names[0]!r}")
            else:
                await ctx.send(f"Error: Missing required arguments {names!r}")
            return
        if multiple: # function supports *args, don't check further
            await func(ctx, *new_args)
            return
        if len(new_args) != len(args) and force_argcount: # too many args and we enforce it
            await ctx.send(f"Error: too many arguments (maximum {co.co_argcount - 1})")
            return
        await func(ctx, *new_args)

    co = func.__code__
    req = co.co_argcount - 1
    if func.__defaults__:
        req -= len(func.__defaults__)

    caller.__required__ = req

    return caller

class Command(_TCommand):
    def __init__(self, name: str, func: Callable, flag="", **attrs):
        super().__init__(name, func, **attrs)
        self.flag = flag
        self.required = func.__required__
        self.enabled = True

    async def invoke(self, context: Context, *, index=0):
        if not self.enabled:
            return
        if "m" in self.flag:
            if not context.author.is_mod:
                return
        await super().invoke(context, index=index)

def command(name: str, *aliases: str, flag: str = "", force_argcount: bool = False, burst: int = _DEFAULT_BURST, rate: float = _DEFAULT_RATE):
    def inner(func):
        wrapped = wrapper(func, force_argcount)
        wrapped.__cooldowns__ = [Cooldown(burst, rate, Bucket.default)]
        cmd = Command(name=name, aliases=list(aliases), func=wrapped, flag=flag)
        if TConn is None:
            _to_add_commands.append(cmd)
        else:
            TConn.add_command(cmd)
        return cmd
    return inner

class TwitchConn(Bot): # use PubSub/EventSub for notice stuff
    # add !nloth to see what relic was given up to N'Loth
    async def event_ready(self):
        live = await self.fetch_streams(user_logins=[config.channel])
        _cache["live"] = (datetime.datetime.now(), bool(live))

    async def event_raw_usernotice(self, channel: Channel, tags: dict):
        user = Chatter(tags=tags, name=tags["login"], channel=channel, bot=self, websocket=self._connection)
        match tags["msg-id"]:
            case "sub" | "resub":
                self.run_event("subscription", user, channel, tags)
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

#TConn = TwitchConn(token=config.oauth, prefix=config.prefix, initial_channels=[config.channel], case_insensitive=True)
#DConn = d_cmds.Bot(config.prefix, case_insensitive=True, owner_ids=config.owners)

def get_timer(name=None) -> Timer | None:
    if name is None:
        return list(_timers)

    return _timers.get(name)

class _FakeMessage: # TODO: use get_channel() instead
    def __init__(self, text: str):
        self.content = text
        self.channel = Channel(config.channel, TConn._connection)
        self.author = PartialChatter(TConn._connection, name=config.channel, channel=config.channel, message=self)

class Timer: # Routines ext instead
    def __init__(self, name: str, interval: int):
        self.name = name
        self._interval = interval
        self._running = False
        self.commands: list[str] = []

    def add_command(self, name: str, *, allow_duplicate: bool) -> bool:
        """Add a command to the timer. Return True if the command was added."""
        cmd = TConn.get_command(name)
        if cmd is not None and not cmd.required:
            if cmd not in self.commands or allow_duplicate:
                self.commands.append(name)
                return True

        return False

    def remove_command(self, name: str) -> int:
        if name in self.commands:
            self.commands.remove(name)
        return self.commands.count(name)

    @property
    def interval(self):
        return self._interval

    @property
    def running(self):
        return self._running

    def stop(self):
        self._running = False

    async def start(self):
        if self._running:
            raise RuntimeError(f"Timer {self.name} is already running!")
        self._running = True
        while True:
            assert isinstance(self._interval, int)
            await asyncio.sleep(self._interval)
            last = _cache["live"][0]
            if (datetime.datetime.now() - last).seconds > config.cache_timeout:
                live = await TConn.fetch_streams(user_logins=[config.channel])
                _cache["live"] = (datetime.datetime.now(), bool(live))
            if self._running and self.commands and _cache["live"][1]:
                name = self.commands.pop(0)
                message = _FakeMessage(f"{config.prefix}{name}")
                ctx = await TConn.get_context(message)
                await ctx.command.invoke(ctx)
                self.commands.append(name)

_cmds: dict[str, dict[str, list[str] | bool | int | float]] = {} # internal json

@command("command", flag="m")
async def command_cmd(ctx: Context, action: str, name: str, *args: str):
    """Syntax: command <action> <name> [+<flag>] <output>"""
    args = list(args)
    msg = " ".join(args)
    name = name.lstrip(config.prefix)
    cmds: dict[str, Command] = TConn.commands
    aliases = ctx.bot._command_aliases
    sanitizer = _get_sanitizer(ctx, name, args, cmds)
    match action:
        case "add":
            if not await sanitizer(in_mapping=False):
                return
            if name in aliases:
                await ctx.send(f"Error: {name} is an alias to {aliases[name]}. Use 'unalias {aliases[name]} {name}' first.")
                return
            flag = ""
            if args[0].startswith("+"):
                flag, *args = args
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
                await ctx.send(f"Error: cannot edit alias. Use 'edit {aliases[name]}' instead.")
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
            cmds[name]._callback = _create_cmd(msg)
            await ctx.send(f"Command {name} edited successfully! Permission: {_perms[flag]}")

        case "remove" | "delete":
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.send(f"Error: cannot delete alias. Use 'remove {aliases[name]}' or 'unalias {aliases[name]} {name}' instead.")
                return
            if name not in _cmds:
                await ctx.send(f"Error: cannot delete built-in command {name}.")
                return
            del _cmds[name]
            _update_db()
            TConn.remove_command(name)
            await ctx.send(f"Command {name} has been deleted.")

        case "enable":
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.send(f"Error: cannot enable alias. Use 'enable {aliases[name]}' instead.")
                return
            if cmds[name].enabled:
                await ctx.send(f"Command {name} is already disabled.")
                return
            cmds[name].enabled = True
            if name in _cmds:
                _cmds[name]["enabled"] = True
                _update_db()
            with _getfile("disabled", "r") as f:
                disabled = f.readlines()
            disabled.remove(name)
            with _getfile("disabled", "w") as f:
                f.writelines(disabled)
            await ctx.send(f"Command {name} has been enabled.")

        case "disable":
            if not await sanitizer(require_args=False):
                return
            if name in aliases:
                await ctx.send(f"Error: cannot disable alias. Use 'disable {aliases[name]}' or 'unalias {aliases[name]} {name}' instead.")
                return
            if not cmds[name].enabled:
                await ctx.send(f"Command {name} is already disabled.")
                return
            cmds[name].enabled = False
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
                    await ctx.send(f"Alias {name} is bound to {aliases[name]}.")
                elif _cmds[name]['aliases']:
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
                aliases[arg] = name
            _cmds[name]["aliases"].extend(args)
            _update_db()
            if len(args) == 1:
                await ctx.send(f"{args[0]} has been aliased to {name}.")
            else:
                await ctx.send(f"Command {name} now has aliases {', '.join(args)}")
            await ctx.send(f"Command {name} now has aliases {', '.join(_cmds[name]['aliases'])}")

        case "unalias":
            if not args:
                await ctx.send("Error: no alias specified.")
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
            if aliases[args[0]] != name:
                await ctx.send(f"Error: alias {args[0]} does not match command {name} (bound to {aliases[args[0]]}).")
                return
            del aliases[args[0]]
            _cmds[name]["aliases"].remove(name)
            _update_db()

        case "cooldown" | "cd":
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
            cd: Cooldown = cmds[name]._cooldowns.pop()
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

            cmds[name]._cooldowns.append(Cooldown(burst, rate, cd.bucket))
            if name in _cmds:
                _cmds[name]["burst"] = burst
                _cmds[name]["rate"] = rate
                _update_db()
            await ctx.send(f"Command {name} now has a cooldown of {rate/burst}s.") # this isn't 100% accurate, but close enough
            if name not in _cmds:
                await ctx.send("Warning: settings on built-in commands do not persist past a restart.")

        case _:
            await ctx.send(f"Unrecognized action {action}.")

@command("timer", flag="m")
async def timer_cmd(ctx: Context, action: str, name: str, *args: str):
    timer = get_timer(name)
    match action:
        case "create":
            if timer:
                await ctx.send(f"Error: Timer {name} already exists.")
                return
            interval = _DEFAULT_INTERVAL
            if args and args[0].isdecimal():
                interval = int(args[0])
            _timers[name] = Timer(name, interval)
            m, s = divmod(interval, 60)
            await ctx.send(f"Created timer {name} with an interval of {m}m {s}s. This will take effect the next time the bot is launched.")

            _update_timers()
            _created_timers.add(name)

        case "add":
            if timer is None:
                await ctx.send(f"Error: Timer {name} does not exist. Use 'create {name} <interval>' instead.")
                return
            if not args:
                await ctx.send("Error: Syntax is 'add <name> <commands>'.")
                return
            added = []
            for c in args:
                allow_duplicate = False
                if c.startswith("="):
                    c = c[1:]
                    allow_duplicate = True
                if timer.add_command(c, allow_duplicate=allow_duplicate):
                    added.append(c)

            s = set(args) - set(added)

            if added:
                await ctx.send(f"Commands have been added to timer {name}! Don't forget to 'start {name}' if you haven't.")
            if s:
                await ctx.send(
                    f"Warning: Commands {', '.join(s)} were not added. Commands requiring additional parameters cannot be on a timer. "
                    f"Additionally, duplicate commands must be preceded by '=', such as 'add {name} ={s.pop()}'. Use 'status {name}' to see which commands are already in."
                )
            if name in _created_timers:
                await ctx.send("Warning: Timer has been recently created. It will not run until the bot is restarted.")

            _update_timers()

        case "remove":
            if timer is None:
                await ctx.send(f"Timer {name} does not exist.")
                return
            if not args:
                await ctx.send(f"Error: Syntax is 'remove {name} <commands>'. Use 'delete {name}' to delete the timer itself.")
                return
            count = 0
            for c in args:
                count += timer.remove_command(c)
            if not count:
                await ctx.send(f"All matching commands have been successfully removed from timer {name}.")
            else:
                await ctx.send(f"The first instance of each command has been removed. There are still {count} duplicates present. Use 'status {name}' for information.")
            _update_timers()

        case "delete":
            if timer is None:
                await ctx.send(f"Timer {name} does not exist.")
                return
            if args:
                await ctx.send(f"Error: Syntax is 'delete {name}'. Use 'remove {name} <commands>' to remove individual commands.")
                return
            if timer.running:
                timer.stop()
            del _timers[name]
            _update_timers()

        case "status" | "stat" | "stats" | "state":
            if timer is None:
                await ctx.send(f"Timer {name} does not exist.")
                return
            await ctx.send(
                f"Timer {name} is currently {'running' if timer.running else 'stopped'} on a {timer.interval}s interval. Commands: {', '.join(c.name for c in timer.commands)}"
            )

        case "start":
            if timer is None:
                await ctx.send(f"Timer {name} does not exist.")
                return
            if not timer.running:
                if name in _created_timers:
                    await ctx.send("Error: cannot start a recently-created timer. Please restart the bot to start it.")
                else:
                    await ctx.send(f"Timer {name} has been started with an interval of {timer.interval}s and {len(timer.commands)} commands.")
                    timer._running = True
            else:
                await ctx.send(f"Timer {name} is already running!")

        case "stop":
            if timer is None:
                await ctx.send(f"Timer {name} does not exist.")
                return
            if not timer.running:
                await ctx.send(f"Timer {name} is not running.")
            else:
                timer.stop()
                await ctx.send(f"Timer {name} has been stopped.")

        case "interval":
            if timer is None:
                await ctx.send(f"Timer {name} does not exist.")
                return
            if not args:
                await ctx.send("Error: No interval provided.")
                return
            if not args[0].isdigit():
                await ctx.send("Error: Interval must be a positive integer.")
                return
            timer._interval = int(args[0])
            await ctx.send(f"Interval set to {args[0]}s! It will take effect after the end of the current interval.")
            _update_timers()

        case _:
            await ctx.send(f"Error: unrecognized action {action}.")

@command("support", "shoutout", "so")
async def shoutout(ctx: Context, name: str):
    try:
        chan = await ctx.bot.fetch_channel(name)
    except IndexError as e:
        await ctx.send(e.args[0])
        return
    except HTTPException as e:
        await ctx.send(e.message)
        return

    msg = [f"Go give a warm follow to https://twitch.tv/{chan.user.name} -"]

    live: list[Stream] = await ctx.bot.fetch_streams([chan.user.id])
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

@command("bluekey", "sapphirekey", "key")
async def bluekey(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

    if not j["has_sapphire_key"]:
        await ctx.send("We do not have the Sapphire key.")
        return

    if "BlueKeyRelicSkippedLog" not in j["basemod:mod_saves"]:
        await ctx.send("RunHistoryPlus is not running; cannot get data.")
        return

    d = j["basemod:mod_saves"]["BlueKeyRelicSkippedLog"]

    await ctx.send(f"We skipped {d['relicID']} on floor {d['floor']+1} for the Sapphire key.")

@command("neow", "neowbonus")
async def neowbonus(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

    if "NeowBonusLog" not in j["basemod:mod_saves"]:
        await ctx.send("RunHistoryPlus is not running; cannot get data.")
        return

    d = j["basemod:mod_saves"]["NeowBonusLog"]

    if d["cardsUpgraded"]:
        pos = f"upgraded {' and '.join(d['cardsUpgraded'])}"

    elif d["cardsRemoved"]:
        pos = f"removed {' and '.join(d['cardsRemoved'])}"

    elif d["relicsObtained"]:
        if j["neow_bonus"] == "BOSS_RELIC":
            pos = f"swapped our Starter relic for {d['relicsObtained'][0]}"
        else:
            pos = f"obtained {d['relicsObtained'][0]}"

    elif d["maxHpGained"]:
        pos = f"gained {d['maxHpGained']} max HP"

    elif d["goldGained"]:
        pos = f"gained {d['goldGained']} gold"

    elif d["cardsObtained"]: # TODO: handle curse-as-negative
        if d["cardsTransformed"]:
            pos = f"transformed {' and '.join(d['cardsTransformed'])} into {' and '.join(d['cardsObtained'])}"
        else:
            pos = f"obtained {' and '.join(d['cardsObtained'])}"

    else:
        pos = "got no bonus? If this is wrong, ping @FaeLyka"


    if d["damageTaken"]:
        neg = f"took {d['damageTaken']} damage"

    elif d["goldLost"]:
        neg = f"lost {d['goldLost']} gold"

    elif d["maxHpLost"]:
        neg = f"lost {d['maxHpLost']} max HP"

    else:
        neg = None

    if neg is None:
        msg = f"We {pos}."
    else:
        msg = f"We {neg}, and then {pos}."

    await ctx.send(msg)

@command("seed", "currentseed")
async def seed_cmd(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

    c = "0123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"

    # this is a bit weird, but lets us convert a negative number, if any, into a positive one
    num = int.from_bytes(j["seed"].to_bytes(20, "big", signed=True).strip(b"\xff"), "big")
    s = []

    while num:
        num, i = divmod(num, 35)
        s.append(c[i])

    s.reverse() # everything's backwards, for some reason... but this works

    await ctx.send(f"Current seed: {''.join(s)}{' (set manually)' if j['seed_set'] else ''}")

@command("shopremoval", "cardremoval", "removal")
async def shop_removal_cost(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

    await ctx.send(f"Current card removal cost: {j['purgeCost']} (removed {j['metric_purchased_purges']} card{'' if j['metric_purchased_purges'] == 1 else 's'})")

@command("potionchance", "potion")
async def potion_chance(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

    await ctx.send(f"Current potion chance: {40 + j['potion_chance']}%")

@command("eventchances", "event") # note: this does not handle pRNG calls like it should - event_seed_count might have something? though only appears to be count of seen ? rooms
async def event_likelihood(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

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

@command("eventrng")
async def event_rng_caveat(ctx: Context):
    await ctx.send(
        "Pseudo-Random Number Generator calls to determine the type of event "
        "is non-random, and depends on the current state of the pRNG when the "
        "room is entered, which is affected by things like previous events. "
        "As such, the likelihood of any given type being picked is weighted "
        "related to previous event rooms. This is why fights are more likely - "
        "or, in some cases, guaranteed - to happen after a Shrine-type event, "
        "even if the likelihood is technically lower."
    )

@command("relic")
async def relic_info(ctx: Context, index: int):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

    l: list[str] = j["relics"]

    if index > len(l):
        await ctx.send(f"We only have {len(l)} relics!")
        return

    relic = _get_name(l[index-1])

    await ctx.send(f"The relic at position {index} is {relic}.")

@command("skipped", "skippedboss", "bossrelics")
async def skipped_boss_relics(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

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
                _get_name(item["picked"]),
                _get_name(item["not_picked"][0]),
                _get_name(item["not_picked"][1]),
            )
        )
        i += 1

    await ctx.send(" ".join(msg))

@command("wall")
async def wall_card(ctx: Context):
    msg = "Current card in the !hole in the wall for the ladder savefile: {0}{1}"
    if not config.STS_path:
        await ctx.send("Error: could not fetch data.")
        return
    for p in ("", "1_", "2_"):
        with open(os.path.join(config.STS_path, "preferences", f"{p}STSPlayer"), "r") as f:
            d = json.load(f)
        if "ladder" not in d["name"].lower():
            continue
        card = d["NOTE_CARD"]
        upgrade_count = int(d["NOTE_UPGRADE"])
        if card == "Searing Blow":
            await ctx.send(msg.format(card, f"+{upgrade_count}" if upgrade_count else ""))
        else:
            await ctx.send(msg.format(card, "+" if upgrade_count else ""))
        return
    await ctx.send("Error: could not find Ladder savefile.")

@command("dig", burst=5, rate=2.0)
async def dig_cmd(ctx: Context):
    with open("dig_entries.txt", "r") as f:
        line = random.choice(f.readlines())
    await ctx.send(f"{ctx.author.display_name} has dug up {line}")

@command("kills") # TODO: Read game files for this
async def kills_cmd(ctx: Context):
    msg = "A20 Heart kills in 2022: Total: {1} - Ironclad: {0[0]} - Silent: {0[1]} - Defect: {0[2]} - Watcher: {0[3]}"
    with _getfile("kills", "r") as f:
        kills = [int(x) for x in f.read().split()]
    await ctx.send(msg.format(kills, sum(kills)))

@command("losses")
async def losses_cmd(ctx: Context):
    msg = "A20 Heart losses in 2022: Total: {1} - Ironclad: {0[0]} - Silent: {0[1]} - Defect: {0[2]} - Watcher: {0[3]}"
    with _getfile("losses", "r") as f:
        losses = [int(x) for x in f.read().split()]
    await ctx.send(msg.format(losses, sum(losses)))

@command("streak")
async def streak_cmd(ctx: Context):
    msg = "Current streak: Rotating: {0[0]} - Ironclad: {0[1]} - Silent: {0[2]} - Defect: {0[3]} - Watcher: {0[4]}"
    with _getfile("streak", "r") as f:
        streak = f.read().split()
    await ctx.send(msg.format(streak))

@command("pb")
async def pb_cmd(ctx: Context):
    msg = "Baalor's PB A20H Streaks | Rotating: {0[0]} - Ironclad: {0[1]} - Silent: {0[2]} - Defect: {0[3]} - Watcher: {0[4]}"
    with _getfile("pb", "r") as f:
        pb = f.read().split()
    await ctx.send(msg.format(pb))

async def edit_counts(ctx: Context, arg: str, *, add: bool):
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

@command("win", flag="m", burst=1, rate=60.0) # 1:60.0 means we can't accidentally do it twice in a row
async def win_cmd(ctx: Context, arg: str):
    await edit_counts(ctx, arg, add=True)

@command("loss", flag="m", burst=1, rate=60.0)
async def loss_cmd(ctx: Context, arg: str):
    await edit_counts(ctx, arg, add=False)

async def main():
    global TConn
    TConn = TwitchConn(token=config.oauth, prefix=config.prefix, initial_channels=[config.channel], case_insensitive=True)
    for cmd in _to_add_commands:
        TConn.add_command(cmd)
    load()
    aws = [TConn.connect()]
    for timer in _timers.values():
        aws.append(timer.start())
    try:
        await asyncio.gather(*aws)
    finally:
        await TConn.close()

asyncio.run(main())

#async def main():
#    await asyncio.gather(TConn.run(), DConn.start(config.token))

#asyncio.run(main())
