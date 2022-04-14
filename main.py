# (c) Anilyka Barry, 2022

# TODO: Split cmds into separate module (package?) for easy reload

from __future__ import annotations

import asyncio
import json
import os

from twitchio.ext import commands as t_cmds
from twitchio.ext.commands import Context
from discord.ext import commands as d_cmds
import flask

import config

prefix = "!"

def _getfile(x, mode):
    return open(os.path.join("data", x), mode)

def _update_db():
    with _getfile("data.json", "w") as f:
        json.dump(_cmds, f)

def load():
    with _getfile("data.json", "r") as f:
        _cmds.update(json.load(f))
    for name, d in _cmds.items():
        async def inner(ctx: Context, *s, output=d["output"]):
            await ctx.channel.send(output)
        TConn.command(name=name, aliases=d["aliases"])(inner)

def add_cmd(name: str, aliases: list[str], source: str, output: str):
    _cmds[name] = {"aliases": aliases, "enabled": True, "source": source, "output": output}
    _update_db()

TConn = t_cmds.Bot(token=config.oauth, prefix=prefix, initial_channels=["faelyka"], case_insensitive=True)
DConn = d_cmds.Bot(prefix, case_insensitive=True, owner_ids=config.owners)

_cmds: dict[str, dict[str, list[str] | bool | None]] = {} # internal json

load()

@TConn.command(name="test")
async def testcmd(ctx: Context, *args, **kwargs):
    await ctx.channel.send(f"Received {args}, {kwargs}")

@TConn.command(name="command") # TODO: perms
async def command_cmd(ctx: Context, action: str = "", name: str = "", *args: str):
    if not action or not name:
        await ctx.channel.send("Missing args")
        return
    name = name.lstrip(prefix)
    msg = " ".join(args)
    cmds = TConn.commands
    match action:
        case "add":
            if name in cmds:
                await ctx.channel.send(f"Error: command {name} already exists!")
                return
            async def inner(ctx: Context, *s, msg=msg):
                await ctx.channel.send(msg)
                return
            add_cmd(name, (), "T", msg)
            TConn.command(name=name)(inner)
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
            await ctx.channel.send(f"Command {name} has been disabled")

        case _:
            await ctx.channel.send(f"Unrecognized action {action}.")

#@command("kills", discord=True, twitch=True)
async def kills(arg=None):
    msg = "A20 Heart kills in 2022: Total: {4} - Ironclad: {0} - Silent: {1} - Defect: {2} - Watcher: {3}"
    with _getfile("kills", "r") as f:
        i, s, d, w = (int(x) for x in f.read().split())
    if not arg:
        return msg.format(i, s, d, w, sum(i, s, d, w))
    if arg.lower() in ("ironclad", "ic", "i"):
        i += 1
    if arg.lower() in ("silent", "s"):
        s += 1
    if arg.lower() in ("defect", "d"):
        d += 1
    if arg.lower() in ("watcher", "w"):
        w += 1
    with _getfile("kills", "w") as f:
        f.write(f"{i} {s} {d} {w}")
    return "[Increased] " + msg.format(i, s, d, w, sum(i, s, d, w))

TConn.run()

async def main():
    await asyncio.gather(TConn.run(), DConn.start(config.token))

asyncio.run(main())
