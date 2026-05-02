from aiohttp import ClientSession, ClientError, ServerDisconnectedError

import traceback
import platform
import pathlib
import asyncio
import pickle
import time
import yaml
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
    cur2 = 0
    try:
        with open("last_run") as f:
            last_run = f.read().strip()
    except OSError:
        last_run = ""
    possible = None
    poss_2 = None
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
        # Check if the app is registered, prompt it if not
        try:
            async with session.post("/twitch/check-token", params={"key": cfg.secret}) as resp:
                if resp.ok:
                    text = await resp.text()
                    match text:
                        case "DISABLED":
                            print("\nTwitch connectivity is disabled.")
                        case "NO_CREDENTIALS":
                            print("\nExtended OAuth is not properly set-up. Contact the server owner.")
                        case "WORKING":
                            print("\nExtended OAuth validated.")
                        case a:
                            if a.startswith("NEEDS_CONNECTION"):
                                nc, cl, url = a.partition(":")
                                import webbrowser
                                webbrowser.open_new_tab(url)
                            else:
                                print(f"\nERROR: Unrecognized return value:\n\n{a}")

        except (ClientError, ServerDisconnectedError):
            print("\nServer is offline, cannot confirm OAuth mode.\nYou may safely ignore this if you previously authorized the app.")

        while True:
            try:
                time.sleep(timeout)
                start = time.time()
                timeout = 1
                if possible is None:
                    for file in (cfg.spiredir / "saves").iterdir():
                        if file.name.endswith(".autosave"):
                            if possible is None:
                                possible = file
                            else:
                                print("Error: Multiple savefiles detected.")
                                possible = None
                                raise ValueError("Multiple savefiles detected")

                if possible is not None:
                    try:
                        cur = (spire1_saves / possible).stat().st_mtime
                    except OSError:
                        possible = None

                if poss_2 is None: # TODO: carry over profiles, more save stuff
                    potential: list[pathlib.Path] = []
                    for file in spire2_saves.iterdir():
                        if file.name.startswith("profile"):
                            save2 = file / "saves" / "current_run.save"
                            if save2.exists():
                                potential.append(save2)
                            else:
                                save2_mp = file / "saves" / "current_run_mp.save"
                                if save2_mp.exists():
                                    potential.append(save2_mp)

                    if len(potential) == 1:
                        poss_2 = potential[0]

                if poss_2 is not None:
                    try:
                        cur2 = poss_2.stat().st_mtime
                    except OSError:
                        poss_2 = None

                if use_sd:
                    try:
                        cur_sd = sd_file.stat().st_mtime
                    except OSError:
                        pass
                    else:
                        if cur_sd != last_sd:
                            with sd_file.open() as f:
                                sd_data = f.read()
                            sd_data = sd_data.encode("utf-8", "xmlcharrefreplace")
                            async with session.post("/sync/slice", data={"data": sd_data}, params={"key": cfg.secret}) as resp:
                                if resp.ok:
                                    last_sd = cur_sd
                                    curses = await resp.read()
                                    if curses and cfg.slice_curses:
                                        decoded: list[str] = pickle.loads(curses)
                                        try:
                                            with open(cfg.slice_curses, "w") as f:
                                                f.write("\n".join(decoded))
                                        except OSError:
                                            pass

                to_send: list[tuple[pathlib.Path, list[str], str, str]] = []
                files = []
                if possible is None and poss_2 is None and cfg.sync_runs: # don't check run files during a run
                    # Spire 1
                    for path, folders, _f in (cfg.spiredir / "runs").walk():
                        for folder in folders:
                            profile = "0"
                            if folder[0].isdigit():
                                profile = folder[0]
                            for p1, d1, f1 in (path / folder).walk():
                                for file in f1:
                                    if file > last_run:
                                        to_send.append((p1, file, profile, "1"))
                                        files.append(file)

                    # Spire 2
                    for path, folders, _f in spire2_saves.walk():
                        for folder in folders:
                            profile = folder[-1]
                            runpath = path / folder / "saves" / "history"
                            if not runpath.exists():
                                continue
                            for p2, d2, f2 in runpath.walk():
                                for file in f2:
                                    if file > last_run:
                                        to_send.append((p2, file, profile, "2"))
                                        files.append(file)

                try:
                    if possible is None and poss_2 is None:
                        async with session.get("/playing", params={"key": cfg.secret}) as resp:
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

                    all_sent = True
                    if to_send: # send runs first so savefile can seamlessly transfer its cache
                        for path, file, profile, version in to_send:
                            if file:
                                path /= file
                            with path.open() as f:
                                content = f.read()
                            content = content.encode("utf-8", "xmlcharrefreplace")
                            async with session.post("/sync/run", data={"run": content, "name": file, "profile": profile, "version": version}, params={"key": cfg.secret, "start": start}) as resp:
                                if not resp.ok:
                                    all_sent = False
                        if all_sent:
                            last_run = max(files)
                            with open("last_run", "w") as f:
                                f.write(last_run)

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
                            possible = None
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
                            poss_2 = None
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
