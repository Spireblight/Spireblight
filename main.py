# (c) Anilyka Barry, 2022

# TODO: Split cmds into separate module (package?) for easy reload

from __future__ import annotations

from typing import Callable
import asyncio
import json
import os

from twitchio.ext import commands as t_cmds
from twitchio.ext.commands import Context
from twitchio.channel import Channel
from twitchio.chatter import Chatter
from discord.ext import commands as d_cmds
import flask

import config

def _getfile(x: str, mode: str):
    return open(os.path.join("data", x), mode)

def _update_db():
    with _getfile("data.json", "w") as f:
        json.dump(_cmds, f)

def load():
    _cmds.clear()
    with _getfile("data.json", "r") as f:
        _cmds.update(json.load(f))
    for name, d in _cmds.items():
        async def inner(ctx: Context, *s, output: str=d["output"]):
            await ctx.channel.send(output.format(user=ctx.author.display_name))
        c = Command(name=name, aliases=d["aliases"], func=inner, flag=d["flag"])
        c.enabled = d["enabled"]
        TConn.add_command(c)
    with _getfile("disabled", "r") as f:
        for disabled in f.readlines():
            TConn.commands[disabled].enabled = False

def add_cmd(name: str, aliases: list[str], source: str, flag: str, output: str):
    _cmds[name] = {"aliases": aliases, "enabled": True, "source": source, "flag": flag, "output": output}
    _update_db()

def wrapper(func: Callable, force_argcount: bool):
    async def caller(ctx: Context, *args):
        co = func.__code__
        req = co.co_argcount
        if func.__defaults__:
            req -= len(func.__defaults__)
        if req > (len(args) + 1): # missing args; don't count ctx
            names = co.co_varnames[1+len(args):req]
            if len(names) == 1:
                await ctx.channel.send(f"Error: Missing required argument {names[0]!r}")
                return
            else:
                await ctx.channel.send(f"Error: Missing required arguments {names!r}")
                return
        if co.co_flags & 0x04: # function supports *args, don't check further
            await func(ctx, *args)
            return
        if (len(args) + 1) > co.co_argcount and force_argcount: # too many args and we enforce it
            await ctx.channel.send(f"Error: too many arguments (maximum {co.co_argcount - 1})")
            return
        await func(ctx, *(args[:co.co_argcount-1])) # truncate args to the max we allow

    return caller

class Command(t_cmds.Command):
    def __init__(self, name: str, func: Callable, flag="", **attrs):
        super().__init__(name, func, **attrs)
        self.flag = flag
        self.enabled = True

    async def invoke(self, context: Context, *, index=0):
        if not self.enabled:
            return
        if "m" in self.flag:
            if not context.author.is_mod:
                return
            
        await super().invoke(context, index=index)

def command(name, *aliases, flag="", force_argcount=False):
    def inner(func):
        cmd = Command(name=name, aliases=list(aliases), func=wrapper(func, force_argcount), flag=flag)
        TConn.add_command(cmd)
        return cmd
    return inner

class TwitchConn(t_cmds.Bot):
    async def event_raw_usernotice(self, channel: Channel, tags: dict):
        user = Chatter(tags=tags["badges"], name=tags["user"], channel=channel, bot=self, websocket=self._connection)
        match tags["msg-id"]:
            case "sub" | "resub":
                self.run_event("subscription", user, channel, tags)
            case "subgift" | "anonsubgift" | "submysterygift" | "giftpaidupgrade" | "rewardgift" | "anongiftpaidupgrade":
                self.run_event("gift_sub", user, channel, tags)
            case "raid":
                self.run_event("raid", user, channel, tags)
            case "unraid":
                self.run_event("unraid", user, channel, tags)
            case "ritual":
                self.run_event("ritual", user, channel, tags)
            case "bitsbadgetier":
                self.run_event("bits_badge", user, channel, tags)

TConn = TwitchConn(token=config.oauth, prefix=config.prefix, initial_channels=["faelyka"], case_insensitive=True)
DConn = d_cmds.Bot(config.prefix, case_insensitive=True, owner_ids=config.owners)

_cmds: dict[str, dict[str, list[str] | bool | None]] = {} # internal json

@command("command", flag="m") # TODO: perms
async def command_cmd(ctx: Context, action: str = "", name: str = "", flag: str = "", *args: str):
    """Syntax: command <action> [+<flag>] <name> <output>"""
    if flag.startswith("+"):
        flag = flag[1:]
    else: # no flag
        args = (flag, *args)
        flag = ""
    args = list(args)
    msg = " ".join(args)
    if not action or not name:
        await ctx.channel.send("Missing args")
        return
    name = name.lstrip(config.prefix)
    cmds: dict[str, Command] = TConn.commands
    match action:
        case "add":
            if name in cmds:
                await ctx.channel.send(f"Error: command {name} already exists!")
                return
            async def inner(ctx: Context, *s, msg=msg):
                await ctx.channel.send(msg)
                return
            add_cmd(name, (), "T", flag, msg)
            command(name, flag=flag)(inner)
            await ctx.channel.send(f"Command {name} added!")

        case "edit":
            if name not in cmds:
                await ctx.channel.send(f"Error: command {name} does not exist!")
                return
            if cmds[name].name != name:
                await ctx.channel.send(f"Error: cannot edit alias. Edit {cmds[name].name} instead.")
                return
            if name not in _cmds:
                await ctx.channel.send(f"Error: cannot edit built-in command {name}.")
                return
            _cmds[name]["output"] = msg
            if flag:
                _cmds[name]["flag"] = flag
            _update_db()
            async def inner(ctx: Context, *s, msg=msg):
                await ctx.channel.send(msg)
            cmds[name]._callback = inner
            await ctx.channel.send(f"Command {name} edited successfully!")

        case "remove" | "delete":
            if name not in cmds:
                await ctx.channel.send(f"Error: command {name} does not exist!")
                return
            if cmds[name].name != name:
                await ctx.channel.send(f"Error: cannot delete alias. Use 'unalias {name}' instead.")
                return
            if name not in _cmds:
                await ctx.channel.send(f"Error: cannot delete built-in command {name}.")
                return
            del _cmds[name]
            _update_db()
            TConn.remove_command(name)
            await ctx.channel.send(f"Command {name} has been deleted.")

        case "enable":
            if name not in cmds:
                await ctx.channel.send(f"Error: command {name} does not exist!")
                return
            if cmds[name].enabled:
                await ctx.channel.send(f"Command {name} is already disabled.")
                return
            cmds[name].enabled = True
            _cmds[name]["enabled"] = True
            _update_db()
            with _getfile("disabled", "r") as f:
                disabled = f.readlines()
            disabled.remove(name)
            with _getfile("disabled", "w") as f:
                f.writelines(disabled)
            await ctx.channel.send(f"Command {name} has been enabled")

        case "disable":
            if name not in cmds:
                await ctx.channel.send(f"Error: command {name} does not exist!")
                return
            if cmds[name].name != name:
                await ctx.channel.send(f"Error: cannot disable alias. Use 'unalias {name}' instead.")
                return
            if name not in _cmds:
                await ctx.channel.send(f"Error: cannot disable built-in command {name}.")
                return
            if not cmds[name].enabled:
                await ctx.channel.send(f"Command {name} is already disabled.")
                return
            cmds[name].enabled = False
            _cmds[name]["enabled"] = False
            _update_db()
            with _getfile("disabled", "r") as f:
                disabled = f.readlines()
            disabled.append(name)
            with _getfile("disabled", "w") as f:
                f.writelines(disabled)
            await ctx.channel.send(f"Command {name} has been disabled")

        case "alias":
            if name not in cmds and args[0] in cmds:
                await ctx.channel.send(f"Error: use 'alias {args[0]} {name}'")
                return
            if name not in cmds:
                await ctx.channel.send(f"Error: command {name} does not exist")
                return
            if name not in _cmds:
                await ctx.channel.send("Error: cannot alias built-in commands")
                return
            if flag:
                await ctx.channel.send("Error: cannot specify flag for aliases")
                return
            if set(args) & cmds.keys():
                await ctx.channel.send(f"Error: aliases {set(args) & cmds.keys()} already exist")
                return
            for arg in args:
                TConn._command_aliases[arg] = name
            _cmds[name]["aliases"] = args
            _update_db()

        case "unalias":
            if name not in TConn._command_aliases:
                await ctx.channel.send("Error: not an alias")
                return
            if name not in _cmds:
                await ctx.channel.send("Error: cannot unalias built-in commands")
                return
            if flag:
                await ctx.channel.send("Error: cannot specify flag for aliases")
                return
            fn = TConn._command_aliases.pop(name)
            _cmds[fn]["aliases"].remove(name)
            _update_db()

        case _:
            await ctx.channel.send(f"Unrecognized action {action}.")

@command("kills")
async def kills_cmd(ctx: Context):
    msg = "A20 Heart kills in 2022: Total: {1} - Ironclad: {0[0]} - Silent: {0[1]} - Defect: {0[2]} - Watcher: {0[3]}"
    with _getfile("kills", "r") as f:
        kills = [int(x) for x in f.read().split()]
    await ctx.channel.send(msg.format(kills, sum(kills)))

@command("losses")
async def losses_cmd(ctx: Context):
    msg = "A20 Heart losses in 2022: Total: {1} - Ironclad: {0[0]} - Silent: {0[1]} - Defect: {0[2]} - Watcher: {0[3]}"
    with _getfile("losses", "r") as f:
        losses = [int(x) for x in f.read().split()]
    await ctx.channel.send(msg.format(losses, sum(losses)))

@command("streak")
async def streak_cmd(ctx: Context):
    msg = "Current streak: Rotating: {0[0]} - Ironclad: {0[1]} - Silent: {0[2]} - Defect: {0[3]} - Watcher: {0[4]}"
    with _getfile("streak", "r") as f:
        streak = [int(x) for x in f.read().split()]
    await ctx.channel.send(msg.format(streak))

@command("pb")
async def pb_cmd(ctx: Context):
    msg = "Baalor's PB A20H Streaks | Rotating: {0[0]} - Ironclad: {0[1]} - Silent: {0[2]} - Defect: {0[3]} - Watcher: {0[4]}"
    with _getfile("pb", "r") as f:
        pb = [int(x) for x in f.read().split()]
    await ctx.channel.send(msg.format(pb))

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
        await ctx.channel.send(f"Unrecognized character {arg}")
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
        await ctx.channel.send(f"[NEW PB ATTAINED] Win recorded for the {d[i]}")
    elif add:
        await ctx.channel.send(f"Win recorded for the {d[i]}")
    else:
        await ctx.channel.send(f"Loss recorded for the {d[i]}")

@command("win")
async def win_cmd(ctx: Context, arg: str):
    await edit_counts(ctx, arg, add=True)

@command("loss")
async def loss_cmd(ctx: Context, arg: str):
    await edit_counts(ctx, arg, add=False)

load()

TConn.run()

#async def main():
#    await asyncio.gather(TConn.run(), DConn.start(config.token))

#asyncio.run(main())
