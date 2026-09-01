from aiohttp import ClientSession, ClientError, ServerDisconnectedError

import traceback
import platform
import pathlib
import asyncio
import pickle
import json
import time
import yaml
import sys
import os

class Config:
    playing_file = ""
    sync_runs = False
    modded = False
    spiredir = ""
    server_url = ""
    secret = ""
    use_mt = False
    use_slice = False
    slice_curses = ""
    steam_id = ""
    user_profile = ""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

        self.server_url = self.server_url.rstrip("/")

        # If spiredir is not being set via configs, detect the OS and
        # use the OS appropriate default spire steamdir:
        if not self.spiredir:
            system_os = platform.system().lower()
            if system_os == "windows":
                self.spiredir = r'C:\Program Files (x86)\Steam\steamapps\common\SlayTheSpire'
            elif system_os == "linux":
                self.spiredir = "~/.steam/steam/steamapps/common/SlayTheSpire"
            elif kwargs: # Other Operating systems do not have defaults set; only error if any data was set
                raise NotImplementedError(f"No default spiredir set for os: '{system_os}'\nSet spiredir manually in config file.")

        self.spiredir = pathlib.Path(self.spiredir)

        if not self.steam_id:
            raise NotImplementedError("Please enter your Steam ID.")

        if not self.user_profile:
            try:
                self.user_profile = os.environ["USERPROFILE"]
            except KeyError:
                raise ValueError("Please set user_profile in the config (typically << C:/Users/[USERNAME] >> on Windows).")

        self.user_profile = pathlib.Path(self.user_profile)

        if self.slice_curses:
            self.slice_curses = pathlib.Path(self.slice_curses)

    def export(self):
        return {
            "playing_file": self.playing_file,
            "sync_runs": self.sync_runs,
            "spiredir": self.spiredir,
            "server_url": self.server_url,
            "secret": self.secret,
            "use_mt": self.use_mt,
            "use_slice": self.use_slice,
            "slice_curses": self.slice_curses,
            "steam_id": self.steam_id,
            "user_profile": self.user_profile,
        }

class Main:
    def __init__(self):
        print("Client running. Will periodically check for the savefile and send it over!\n")
        if not cfg.server_url or not cfg.secret:
            print("Config is not complete. Please open 'client-config.yml' and edit it with your preferences.")
            time.sleep(3)
            return

        self.session = None
        self.last_exception: Exception | None = None

        self.spire1_saves = cfg.spiredir / "saves"
        self.spire2_saves = cfg.user_profile / "AppData" / "Roaming" / "SlayTheSpire2" / "steam" / cfg.steam_id
        if cfg.modded:
            self.spire2_saves /= "modded"

        self.last_sent = { # last save timestamp, or time.time() if no save
            "save_sts1": None,
            "save_sts2": None,
        }

        self.all_sent = {
            "save_sts1": False,
            "save_sts2": False,
            "runs_sts1": False,
            "runs_sts2": False,
        }

        self.timestamps = {
            "last_modified": None,
            "last_committed": None,
        }

        self.last_modified = { # some of these are int, some are str
            "save_sts1": None,
            "save_sts2": None,
            "runs_sts1": None,
            "runs_sts2": None,
            "slice_dice": None,
        }

        self.last_modified_file = pathlib.Path(".") / "last_modified.json"

        self.load_last_modified()

    def is_exception_recurring(self) -> bool:
        """Check if the ongoing exception keeps re-ocurring.

        :raises RuntimeError: If there is no active exception.
        :return: True if the exception is the same as the previous one, False otherwise.
        :rtype: bool
        """
        exc = sys.exception()
        if exc is None:
            raise RuntimeError("no exception ongoing")

        ret = False # if there was no prior exception, it is new
        if self.last_exception is not None:
            ret = (
                type(exc) is type(self.last_exception) and
                exc.args == self.last_exception.args # exceptions are never equal, so args is second best bet
            )

        self.last_exception = exc
        return ret

    def load_last_modified(self):
        """Load last-modified information, to save on network transfers."""
        try:
            with self.last_modified_file.open() as f:
                data: dict[str, int | str] = json.load(f)
        except FileNotFoundError:
            print("last_modified.json not found, will send everything to server.")
        except PermissionError:
            print("last_modified.json is not readable, check permissions.")
        except OSError:
            print("Could not load data from last_modified.json")
        else:
            for key, value in data.items():
                if key not in self.last_modified:
                    # it's unlikely to happen, and we store it anyway, just in case
                    print(f"Unrecognized key {key!r} in last_modified.json, will have no effect")
                lasval = self.last_modified.get(key)
                if lasval and value > lasval:
                    self.last_modified[key] = value

            self.timestamps["last_modified"] = self.timestamps["last_committed"] = time.time()

    def modified(self, key: str, value: str | int | float):
        """Keep track of what was modified, to only update when needed."""
        if key not in self.last_modified:
            raise KeyError(f"Could not find key {key!r} for last modified")

        self.last_modified[key] = value
        self.timestamps["last_modified"] = time.time()

    def save_last_modified(self, *, force=False):
        """Save last-modified information, for cross-session persistence.
        
        :param force: Whether to force a commit to disk.
        :type force: bool, default False"""

        ts = self.timestamps
        if not force and ts["last_modified"] == ts["last_committed"]: # nothing changed
            return
        try:
            with self.last_modified_file.open("w") as f:
                json.dump(self.last_modified, f)
        except PermissionError:
            print("last_modified.json is not writable, check permissions.")
        except OSError:
            print("Could not write data to last_modified.json")
        else:
            ts["last_modified"] = ts["last_committed"] = time.time()

    async def run(self):
        has_save = True # whether the server has a save file - we lie at first in case we just restarted and it has an old one
        last = 0
        last_slots = 0
        lasp = [0, 0, 0]
        lasp2 = [None, 0, 0, 0] # this is 1-indexed, so use None as filler
        last_mt = 0
        last_mt2 = 0
        runs_last = {}
        use_mt = cfg.use_mt
        playing = None
        timeout = 1

        print(
            f"User profile folder: {cfg.user_profile}",
            f"Fetch Slice & Dice Data: {'YES' if cfg.use_slice else 'NO'}",
            f"Fetch Monster Train Data: {'YES' if cfg.use_mt else 'NO'}",
            sep="\n"
        )

        if use_mt:
            mt_folder = cfg.user_profile / "AppData" / "LocalLow" / "Shiny Shoe" / "MonsterTrain"
            mt_file = mt_folder / "saves" / "save-singlePlayer.json"
            print(f"\nFolder-1: {mt_folder}\nSavefile-1: {mt_file}")

            mt2_folder = cfg.user_profile / "AppData" / "LocalLow" / "Shiny Shoe" / "MonsterTrain2"
            mt2_file = mt2_folder / "saves" / "save-singlePlayer.json"
            print(f"\nFolder-2: {mt2_folder}\nSavefile-2: {mt2_file}")

        self.session = ClientSession(cfg.server_url)

        await self.check_twitch_credentials()

        while True:
            try:
                await asyncio.sleep(timeout)
                timeout = 1

                await self.sync_slice_dice_data()

                sts1_save = self.get_savefile_sts1()
                sts2_save = self.get_savefile_sts2()

                if sts1_save is None and sts2_save is None:
                    if cfg.sync_runs:
                        await self.sync_runfiles_sts1()
                        await self.sync_runfiles_sts2()

                    await self.get_now_playing()

                self.save_last_modified()

            except (ClientError, ServerDisconnectedError):
                timeout = 10 # give it a bit of time
                print("Error: Server is offline! Retrying in 10s")
                continue
            except Exception:
                # since the loop is every second, don't spam the report feature
                if self.is_exception_recurring():
                    continue
                text = traceback.format_exc()
                try:
                    async with self.session.post("/report", data={"traceback": text}, params={"key": cfg.secret}) as resp:
                        if not resp.ok:
                            print(text)
                except Exception:
                    print(text)

    async def check_twitch_credentials(self):
        """Check if the app is registered, prompt it if not."""
        needs_restart = False
        try:
            for ttype in ("broadcaster", "bot"):
                if ttype == "broadcaster":
                    print("Verifying channel access permissions . . .")
                else:
                    print("Verifying Twitch bot permissions . . .")
                async with self.session.post(f"/twitch/check-token/{ttype}", params={"key": cfg.secret}) as resp:
                    if resp.ok:
                        text = await resp.text()
                        match text:
                            case "DISABLED":
                                print("\nTwitch connectivity is disabled.")
                                break
                            case "NO_CREDENTIALS":
                                print("\nExtended OAuth is not properly set-up. Contact the server owner.")
                                break
                            case "WORKING":
                                print("\nExtended OAuth validated.")
                            case "UNKNOWN_TYPE":
                                print(f"Type {ttype!r} unrecognized (this is a bug).")
                            case a:
                                if a.startswith("NEEDS_CONNECTION"):
                                    needs_restart = True
                                    nc, cl, url = a.partition(":")
                                    ob = True # do we open a browser window?
                                    if ttype == "bot":
                                        val = input(
                                            "--==-- Twitch bot access required --==--\n"
                                            "Please login to your Twitch bot account.\n\n"
                                            "Then press Enter, and make sure to authorize to the bot account!\n"
                                            "If this doesn't work for whatever reason, type in 'Link' then Enter. "
                                            )
                                        if val: # anything at all, really
                                            ob = False
                                            print(f"Please copy-paste the following in your browser:\n\n{url}")
                                    if ob:
                                        import webbrowser
                                        webbrowser.open_new_tab(url)
                                    input("\nPress Enter if the handshake is successful.")
                                else:
                                    print(f"\nERROR: Unrecognized return value:\n\n{a}")

        except (ClientError, ServerDisconnectedError):
            print("\nServer is offline, cannot confirm OAuth mode.\nYou may safely ignore this if you previously authorized the app.")

        if needs_restart:
            input("Please wait for the server to reboot, then restart this.")
            exit()

    def get_savefile_sts1(self) -> pathlib.Path | None:
        """Find and return the current run save file, or None if no run is ongoing.

        :raises ValueError: If multiple possible saves are detected.
        :return: Slay the Spire current run save file.
        :rtype: pathlib.Path | None
        """
        possible = None
        for file in (cfg.spiredir / "saves").iterdir():
            if file.name.endswith(".autosave"):
                if possible is None:
                    possible = file
                else:
                    print("Error: Multiple savefiles detected.")
                    possible = None
                    raise ValueError("Multiple savefiles detected")

        # fun fact: and/or binary operators always return one of their operands
        # if the first operand ('possible') is false, it always returns it
        # otherwise, it returns whatever the second one is, without even checking it
        # or is the same, but returns the first if it's true instead
        return possible and self.spire1_saves / possible

        # make sure caller does this where needed
        if possible is not None:
            try:
                cur = (self.spire1_saves / possible).stat().st_mtime
            except OSError:
                possible = None

    async def sync_savefile_sts1(self, savefile: pathlib.Path | None):
        if savefile is None: # no save locally, check if we must inform
            if not self.all_sent["save_sts1"] or self.last_sent["save_sts1"]: # idk if this is correct, im too stoned and stopping here
                pass

    def get_savefile_sts2(self) -> pathlib.Path | None:
        """Find and return the current run save file, or None if no run is ongoing.

        :raises ValueError: If multiple possible saves are detected.
        :return: Slay the Spire 2 current run save file.
        :rtype: pathlib.Path | None
        """
        potential: list[pathlib.Path] = []
        for file in self.spire2_saves.iterdir():
            if file.name.startswith("profile"):
                save2 = file / "saves" / "current_run.save"
                if save2.exists():
                    potential.append(save2)
                else:
                    save2_mp = file / "saves" / "current_run_mp.save"
                    if save2_mp.exists():
                        potential.append(save2_mp)

        if len(potential) == 1:
            return potential[0]

        print("Error: Multiple savefiles detected.")
        raise ValueError("Multiple savefiles detected")

        if poss_2 is not None:
            try:
                cur2 = poss_2.stat().st_mtime
            except OSError:
                poss_2 = None

    async def sync_runfiles_sts1(self):
        """Fetch and sync the Spire 1 run files."""
        last_sent = ""
        update = True
        last = self.last_modified.get("runs_sts1", "")
        for path, folders, _f in (cfg.spiredir / "runs").walk():
            for folder in folders:
                profile = "0"
                if folder[0].isdigit():
                    profile = folder[0]
                for p1, d1, f1 in (path / folder).walk():
                    for file in f1:
                        if file > last:
                            with (p1 / file).open() as f:
                                content = f.read()
                            data = {
                                "run": content.encode("utf-8", "xmlcharrefreplace"),
                                "name": file,
                                "profile": profile,
                                "version": "1",
                            }
                            async with self.session.post("/sync/run", data=data, params={"key": cfg.secret}) as resp:
                                if not resp.ok:
                                    update = False
                                elif update:
                                    last_sent = max(last_sent, file)

        self.modified("runs_sts1", last_sent)
        self.all_sent["runs_sts1"] = update

    async def sync_runfiles_sts2(self):
        """Fetch and sync the Spire 2 run files."""
        last_sent = ""
        update = True
        last = self.last_modified.get("runs_sts2", "")
        for path, folders, _f in self.spire2_saves.walk():
            for folder in folders:
                profile = folder[-1]
                runpath = path / folder / "saves" / "history"
                if not runpath.exists():
                    continue
                for p2, d2, f2 in runpath.walk():
                    for file in f2:
                        if file > last:
                            with (p2 / file).open() as f:
                                content = f.read()
                            data = {
                                "run": content.encode("utf-8", "xmlcharrefreplace"),
                                "name": file,
                                "profile": profile,
                                "version": "2",
                            }
                            async with self.session.post("/sync/run", data=data, params={"key": cfg.secret}) as resp:
                                if not resp.ok:
                                    update = False
                                elif update:
                                    last_sent = max(last_sent, file)

        self.modified("runs_sts2", last_sent)
        self.all_sent["runs_sts2"] = update

    async def sync_slice_dice_data(self): # XXX Server side is not updated for S&D 3.x
        if not cfg.use_slice:
            return

        file = cfg.user_profile / ".prefs" / "slice-and-dice-3"
        try:
            cur = file.stat().st_mtime
        except OSError:
            return

        if cur == self.last_modified["slice_dice"]: # not changed, don't do anything
            return

        with file.open() as f:
            sd_data = f.read()
        sd_data = sd_data.encode("utf-8", "xmlcharrefreplace")

        async with self.session.post("/sync/slice", data={"data": sd_data}, params={"key": cfg.secret}) as resp:
            if resp.ok:
                self.last_modified["slice_dice"] = cur
                curses = await resp.read()
                if curses and cfg.slice_curses:
                    decoded: list[str] = pickle.loads(curses)
                    try:
                        with cfg.slice_curses.open("w") as f:
                            f.write("\n".join(decoded))
                    except OSError:
                        pass
                    else:
                        self.modified("slice_dice", time.time())

    async def get_now_playing(self):
        async with self.session.get("/playing", params={"key": cfg.secret}) as resp:
            if resp.ok:
                j = await resp.json()
                if j and j.get("item"):
                    track = j['item']['name']
                    artists = ", ".join(x['name'] for x in j['item']['artists'])
                    album = j['item']['album']['name']
                    text = f"{track}\n{artists}\n{album}"
                    if playing != text:
                        try:
                            with open(cfg.playing_file, "w") as f:
                                f.write(text)
                            playing = text
                        except OSError:
                            pass

                else:
                    playing = None
                    try:
                        with open(cfg.playing_file, "w") as f:
                            pass # make it an empty file
                    except OSError:
                        pass

async def main():
    print("Client running. Will periodically check for the savefile and send it over!\n")
    has_save = True # whether the server has a save file - we lie at first in case we just restarted and it has an old one
    last = 0
    last_slots = 0
    lasp = [0, 0, 0]
    lasp2 = [None, 0, 0, 0] # this is 1-indexed, so use None as filler
    last_sd = 0
    last_mt = 0
    last_mt2 = 0
    runs_last = {}
    use_sd = cfg.use_slice
    use_mt = cfg.use_mt
    last_exc = None
    s2_save = True
    last2 = 0
    try:
        with open("last_run") as f:
            last_run = f.read().strip()
    except OSError:
        last_run = ""
    playing = None
    timeout = 1
    if not cfg.server_url or not cfg.secret:
        print("Config is not complete. Please open 'client-config.yml' and edit it with your preferences.")
        time.sleep(3)
        return

    print(f"User profile folder: {cfg.user_profile}\nFetch Slice & Dice Data: {'YES' if use_sd else 'NO'}\nFetch Monster Train Data: {'YES' if use_mt else 'NO'}")

    if use_mt:
        mt_folder = cfg.user_profile / "AppData" / "LocalLow" / "Shiny Shoe" / "MonsterTrain"
        mt_file = mt_folder / "saves" / "save-singlePlayer.json"
        print(f"\nFolder-1: {mt_folder}\nSavefile-1: {mt_file}")

        mt2_folder = cfg.user_profile / "AppData" / "LocalLow" / "Shiny Shoe" / "MonsterTrain2"
        mt2_file = mt2_folder / "saves" / "save-singlePlayer.json"
        print(f"\nFolder-2: {mt2_folder}\nSavefile-2: {mt2_file}")

    if use_sd:
        sd_file = cfg.user_profile / ".prefs" / "slice-and-dice-3"

    spire1_saves = cfg.spiredir / "saves"
    spire2_saves = cfg.user_profile / "AppData" / "Roaming" / "SlayTheSpire2" / "steam" / cfg.steam_id
    if cfg.modded:
        spire2_saves /= "modded"

    async with ClientSession(cfg.server_url) as session:
        while True:
            try:
                time.sleep(timeout)
                start = time.time()
                timeout = 1
                try:
                    # XXX: consolidate into one endpoint
                    if possible is None and has_save: # server has a save, but we don't (anymore)
                        async with session.post("/sync/save", data={"savefile": b"", "character": b""}, params={"key": cfg.secret, "has_run": str(all_sent).lower(), "start": start}) as resp:
                            if resp.ok:
                                has_save = False

                    if poss_2 is None and s2_save: # server has a save, but we don't (anymore)
                        async with session.post("/sync/save-2", data={"savefile": b"", "character": b""}, params={"key": cfg.secret, "has_run": str(all_sent).lower(), "start": start}) as resp:
                            if resp.ok:
                                s2_save = False

                    if use_mt:
                        ## MT1
                        try:
                            cur_mt = os.path.getmtime(mt_file)
                        except OSError:
                            traceback.print_exc()
                        else:
                            if cur_mt != last_mt:
                                with open(mt_file, "rb") as f:
                                    mt_data = f.read()
                                mt_runs = {"save": mt_data}
                                mt_runs_last = {}
                                for file in os.listdir(os.path.join(mt_folder, "run-history")):
                                    break # otherwise, it might exceed the data limit. let's not.
                                    if not file.endswith(".db"):
                                        continue
                                    if file == "runHistory.db": # main one
                                        key = "main"
                                    elif file.startswith("runHistoryData"): # something like runHistoryData00.db
                                        key = file[14:16]
                                    else:
                                        key = file # just in case
                                    last = os.path.getmtime(os.path.join(mt_folder, "run-history", file))
                                    if runs_last.get(key) != last:
                                        with open(os.path.join(mt_folder, "run-history", file), "rb") as f:
                                            mt_runs[key] = f.read()
                                            mt_runs_last[key] = last
                                async with session.post("/sync/monster", data=mt_runs, params={"key": cfg.secret}) as resp:
                                    if resp.ok:
                                        last_mt = cur_mt
                                        runs_last.update(mt_runs_last)
                                    else:
                                        print(f"ERROR: Monster Train data not properly sent:\n{resp.reason}")

                        ## MT2

                        try:
                            cur_mt2 = os.path.getmtime(mt2_file)
                        except OSError:
                            traceback.print_exc()
                        else:
                            if cur_mt2 != last_mt2:
                                with open(mt2_file, "rb") as f:
                                    mt2_data = f.read()
                                mt2_runs = {"save": mt2_data}
                                mt2_runs_last = {}
                                for file in os.listdir(os.path.join(mt2_folder, "run-history")):
                                    break # otherwise, it might exceed the data limit. let's not.
                                    if not file.endswith(".db"):
                                        continue
                                    if file == "runHistory.db": # main one
                                        key = "main"
                                    elif file.startswith("runHistoryData"): # something like runHistoryData00.db
                                        key = file[14:16]
                                    else:
                                        key = file # just in case
                                    last = os.path.getmtime(os.path.join(mt_folder, "run-history", file))
                                    if runs_last.get(key) != last:
                                        with open(os.path.join(mt_folder, "run-history", file), "rb") as f:
                                            mt_runs[key] = f.read()
                                            mt_runs_last[key] = last
                                async with session.post("/sync/monster-2", data=mt2_runs, params={"key": cfg.secret}) as resp:
                                    if resp.ok:
                                        last_mt2 = cur_mt2
                                        runs_last.update(mt2_runs_last)
                                    else:
                                        print(f"ERROR: Monster Train 2 data not properly sent:\n{resp.reason}")

                    # update all profiles
                    data = {
                        "slots": b"",
                        "0": b"",
                        "1": b"",
                        "2": b"",
                        "11": b"",
                        "12": b"",
                        "13": b"",
                    }

                    # always send the save slots; it's possible it changed, even during a run (e.g. wall card)
                    cur_slots = (cfg.spiredir / "preferences" / "STSSaveSlots").stat().st_mtime
                    if cur_slots != last_slots:
                        with (cfg.spiredir / "preferences" / "STSSaveSlots").open() as f:
                            data["slots"] = f.read().encode("utf-8", "xmlcharrefreplace")
                    tobe_lasp = [0, 0, 0]
                    for i in range(3):
                        name = "STSPlayer"
                        if i:
                            name = f"{i}_{name}"
                        try:
                            fname = cfg.spiredir / "preferences" / name
                            tobe_lasp[i] = m = fname.stat().st_mtime
                            if m == lasp[i]:
                                continue # unchanged, don't bother
                            with fname.open() as f:
                                data[str(i)] = f.read().encode("utf-8", "xmlcharrefreplace")
                        except OSError:
                            continue

                    tobe_lasp2 = [None, 0, 0, 0]
                    for i in range(3):
                        i += 1
                        name = f"profile{i}"
                        try:
                            fname = spire2_saves / name / "saves" / "progress.save"
                            tobe_lasp2[i] = m = fname.stat().st_mtime
                            if m == lasp2[i]:
                                continue # unchanged
                            with fname.open() as f:
                                data[str(i+10)] = f.read().encode("utf-8", "xmlcharrefreplace")
                        except OSError:
                            continue

                    if any(data.values()):
                        async with session.post("/sync/profile", data=data, params={"key": cfg.secret, "start": start}) as resp:
                            if resp.ok:
                                lasp = tobe_lasp
                                lasp2 = tobe_lasp2
                                last_slots = cur_slots
                            else:
                                print("Warning: Profiles were not successfully updated. Desyncs may occur.")

                    if possible is not None and cur != last:
                        content = ""
                        try:
                            with possible.open() as f:
                                content = f.read()
                        except OSError:
                            pass#possible = None
                        else:
                            content = content.encode("utf-8", "xmlcharrefreplace")
                            char = possible.name[:-9].encode("utf-8", "xmlcharrefreplace")
                            async with session.post("/sync/save", data={"savefile": content, "character": char}, params={"key": cfg.secret, "has_run": "false", "start": start}) as resp:
                                if resp.ok:
                                    last = cur
                                    has_save = True

                    if poss_2 is not None and cur2 != last2:
                        content = ""
                        try:
                            with poss_2.open() as f:
                                content = f.read()
                        except OSError:
                            pass#poss_2 = None
                        else:
                            content = content.encode("utf-8", "xmlcharrefreplace")
                            async with session.post("/sync/save-2", data={"savefile": content}, params={"key": cfg.secret, "start": start}) as resp:
                                if resp.ok:
                                    last2 = cur2
                                    s2_save = True

                except (ClientError, ServerDisconnectedError):
                    timeout = 10 # give it a bit of time
                    print("Error: Server is offline! Retrying in 10s")
                    continue
            except Exception as e:
                # since the loop is every second, don't spam the report feature
                if type(e) is type(last_exc) and e.args == last_exc.args: # exceptions are never equal, so check args
                    continue
                last_exc = e
                text = traceback.format_exc()
                try:
                    async with session.post("/report", data={"traceback": text}, params={"key": cfg.secret}) as resp:
                        if not resp.ok:
                            print(text)
                except Exception:
                    print(text)


if __name__ == "__main__":
    try:
        with open("client-config.yml") as f:
            cfg = Config(**yaml.safe_load(f))
    except FileNotFoundError:
        cfg = Config()
        with open("client-config.yml", "w") as f:
            yaml.safe_dump(cfg.export(), f)
    asyncio.run(main())
