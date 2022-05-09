# (c) Anilyka Barry, 2022

# TODO: Split cmds into separate module (package?) for easy reload

from __future__ import annotations

from typing import Callable
import datetime
import asyncio
import random
import base64
import json
import os

from twitchio.ext.commands import Context, Bot, Command, Cooldown, Bucket
from twitchio.channel import Channel
from twitchio.chatter import Chatter
from twitchio.errors import HTTPException
from twitchio.models import Stream
#from discord.ext import commands as d_cmds
#import flask

import config

_DEFAULT_BURST = 2
_DEFAULT_RATE  = 5.0

_json_indent = 4

_consts = {
    "discord": "https://discord.gg/9XYVCSY",
}

_perms = {
    "": "Everyone",
    "m": "Moderator",
}

_defaults = {
    "aliases": [],
    "flag": "",
    "burst": _DEFAULT_BURST,
    "rate": _DEFAULT_RATE,
    "source": "T",
    "enabled": True,
    "output": "<UNDEFINED>",
}

def _check_json():
    changed = False
    with _getfile("data.json", "r") as f:
        d = json.load(f)
    for key in d:
        for name in _defaults:
            if name not in d[key]:
                d[key][name] = _defaults[name]
                changed = True

    if changed:
        with _getfile("data.json", "w") as f:
            json.dump(d, f, indent=_json_indent)

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
        return json.loads(arr)

def _getfile(x: str, mode: str):
    return open(os.path.join("data", x), mode)

def _update_db():
    with _getfile("data.json", "w") as f:
        json.dump(_cmds, f, indent=_json_indent)

def _create_cmd(output):
    async def inner(ctx: Context, *s, output: str=output):
        await ctx.send(output.format(user=ctx.author.display_name, text=" ".join(s), words=s, **_consts))
    return inner

def load():
    _cmds.clear()
    with _getfile("data.json", "r") as f:
        _cmds.update(json.load(f))
    for name, d in _cmds.items():
        c = command(name, *d["aliases"], flag=d["flag"], burst=d["burst"], rate=d["rate"])(_create_cmd(d["output"]))
        c.enabled = d["enabled"]
    with _getfile("disabled", "r") as f:
        for disabled in f.readlines():
            TConn.commands[disabled].enabled = False

def add_cmd(name: str, aliases: list[str], source: str, flag: str, burst: int, rate: float, output: str):
    _cmds[name] = {"aliases": aliases, "enabled": True, "source": source, "flag": flag, "burst": burst, "rate": rate, "output": output}
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
                await ctx.send(f"Error: Missing required argument {names[0]!r}")
                return
            else:
                await ctx.send(f"Error: Missing required arguments {names!r}")
                return
        if co.co_flags & 0x04: # function supports *args, don't check further
            await func(ctx, *args)
            return
        if (len(args) + 1) > co.co_argcount and force_argcount: # too many args and we enforce it
            await ctx.send(f"Error: too many arguments (maximum {co.co_argcount - 1})")
            return
        await func(ctx, *(args[:co.co_argcount-1])) # truncate args to the max we allow

    return caller

class Command(Command):
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

def command(name: str, *aliases: str, flag: str = "", force_argcount: bool = False, burst: int = _DEFAULT_BURST, rate: float = _DEFAULT_RATE):
    def inner(func):
        wrapped = wrapper(func, force_argcount)
        wrapped.__cooldowns__ = [Cooldown(burst, rate, Bucket.default)]
        cmd = Command(name=name, aliases=list(aliases), func=wrapped, flag=flag)
        TConn.add_command(cmd)
        return cmd
    return inner

class TwitchConn(Bot):
    async def event_raw_usernotice(self, channel: Channel, tags: dict):
        user = Chatter(tags=tags["badges"], name=tags["login"], channel=channel, bot=self, websocket=self._connection)
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

TConn = TwitchConn(token=config.oauth, prefix=config.prefix, initial_channels=[config.channel], case_insensitive=True)
#DConn = d_cmds.Bot(config.prefix, case_insensitive=True, owner_ids=config.owners)

_cmds: dict[str, dict[str, list[str] | bool | None]] = {} # internal json

@command("command", flag="m") # TODO: perms
async def command_cmd(ctx: Context, action: str = "", name: str = "", *args: str):
    """Syntax: command <action> <name> [+<flag>] <output>"""
    args = list(args)
    msg = " ".join(args)
    if not action or not name:
        await ctx.send("Missing args.")
        return
    name = name.lstrip(config.prefix)
    cmds: dict[str, Command] = TConn.commands
    aliases = ctx.bot._command_aliases
    match action:
        case "add":
            if not args:
                await ctx.send("Error: no output provided.")
                return
            if name in aliases:
                await ctx.send(f"Error: {name} is an alias to {aliases[name]}. Use 'unalias {aliases[name]} {name}' first.")
                return
            if name in cmds:
                await ctx.send(f"Error: command {name} already exists!")
                return
            flag = ""
            if args[0].startswith("+"):
                flag, *args = args
            if flag not in _perms:
                await ctx.send("Error: flag not recognized.")
                return
            add_cmd(name, (), "T", flag, _DEFAULT_BURST, _DEFAULT_RATE, msg)
            command(name, flag=flag)(_create_cmd(msg))
            await ctx.send(f"Command {name} added! Permission: {_perms[flag]}")

        case "edit":
            if not args:
                await ctx.send("Error: no output provided.")
                return
            if name in aliases:
                await ctx.send(f"Error: cannot edit alias. Use 'edit {aliases[name]}' instead.")
                return
            if name not in cmds:
                await ctx.send(f"Error: command {name} does not exist!")
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
            if name in aliases:
                await ctx.send(f"Error: cannot delete alias. Use 'remove {aliases[name]}' or 'unalias {aliases[name]} {name}' instead.")
                return
            if name not in cmds:
                await ctx.send(f"Error: command {name} does not exist!")
                return
            if name not in _cmds:
                await ctx.send(f"Error: cannot delete built-in command {name}.")
                return
            del _cmds[name]
            _update_db()
            TConn.remove_command(name)
            await ctx.send(f"Command {name} has been deleted.")

        case "enable":
            if name in aliases:
                await ctx.send(f"Error: cannot enable alias. Use 'enable {aliases[name]}' instead.")
                return
            if name not in cmds:
                await ctx.send(f"Error: command {name} does not exist!")
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
            if name in aliases:
                await ctx.send(f"Error: cannot disable alias. Use 'disable {aliases[name]}' or 'unalias {aliases[name]} {name}' instead.")
                return
            if name not in cmds:
                await ctx.send(f"Error: command {name} does not exist!")
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

        case "alias":
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
            if name not in cmds:
                await ctx.send(f"Error: command {name} does not exist.")
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

        case _:
            await ctx.send(f"Unrecognized action {action}.")

@command("support", "so")
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

    if "BlueKeyRelicSkippedLog" not in j:
        await ctx.send("RunHistoryPlus is not running; cannot get data.")
        return

    await ctx.send(f"We skipped {j['BlueKeyRelicSkippedLog']['relicID']} on floor {j['BlueKeyRelicSkippedLog']['floor']+1} for the Sapphire key.")

@command("neow", "neowbonus")
async def neowbonus(ctx: Context):
    j = await _get_savefile_as_json(ctx)
    if j is None:
        return

    if "NeowBonusLog" not in j:
        await ctx.send("RunHistoryPlus is not running; cannot get data.")
        return

    d = j["NeowBonusLog"]

    if d["cardsUpgraded"]:
        pos = f"upgraded {' and '.join(d['cardsUpgraded'])}"

    elif d["cardsRemoved"]:
        pos = f"removed {' and '.join(d['cardsRemoved'])}"

    elif d["cardsObtained"]:
        if d["cardsTransformed"]:
            pos = f"transformed {' and '.join(d['cardsTransformed'])} into {' and '.join(d['cardsObtained'])}"
        else:
            pos = f"obtained {' and '.join(d['cardsObtained'])}"

    elif d["relicsObtained"]:
        if j["neow_bonus"] == "BOSS_RELIC":
            pos = f"swapped our Starter relic for {d['relicsObtained'][0]}"
        else:
            pos = f"obtained {d['relicsObtained'][0]}"

    elif d["maxHpGained"]:
        pos = f"gained {d['maxHpGained']} max HP"

    elif d["goldGained"]:
        pos = f"gained {d['goldGained']} gold"

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
    j = _get_savefile_as_json(ctx)
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

    await ctx.send(f"Current seed: {''.join(s)}")

@command("shopremoval", "cardremoval", "removal")
async def shop_removal_cost(ctx: Context):
    j = _get_savefile_as_json(ctx)
    if j is None:
        return

    await ctx.send(f"Current card removal cost: {j['purgeCost']}")

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

@command("dig")
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
        streak = [int(x) for x in f.read().split()]
    await ctx.send(msg.format(streak))

@command("pb")
async def pb_cmd(ctx: Context):
    msg = "Baalor's PB A20H Streaks | Rotating: {0[0]} - Ironclad: {0[1]} - Silent: {0[2]} - Defect: {0[3]} - Watcher: {0[4]}"
    with _getfile("pb", "r") as f:
        pb = [int(x) for x in f.read().split()]
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
        await ctx.send(f"[NEW PB ATTAINED] Win recorded for the {d[i]}")
    elif add:
        await ctx.send(f"Win recorded for the {d[i]}")
    else:
        await ctx.send(f"Loss recorded for the {d[i]}")

@command("win", flag="m") # TODO: add a manual time check for "this was last updated by X n seconds ago, do you wish to do this"
async def win_cmd(ctx: Context, arg: str):
    await edit_counts(ctx, arg, add=True)

@command("loss", flag="m")
async def loss_cmd(ctx: Context, arg: str):
    await edit_counts(ctx, arg, add=False)

_check_json()

load()

TConn.run()

#async def main():
#    await asyncio.gather(TConn.run(), DConn.start(config.token))

#asyncio.run(main())
