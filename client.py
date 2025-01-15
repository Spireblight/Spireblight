from aiohttp import ClientSession, ClientError, ServerDisconnectedError

import traceback
import asyncio
import pickle
import time
import os

from configuration import config

async def main():
    print("Client running. Will periodically check for the savefile and send it over!\n")
    has_save = True # whether the server has a save file - we lie at first in case we just restarted and it has an old one
    last = 0
    last_slots = 0
    lasp = [0, 0, 0]
    last_sd = 0
    last_mt = 0
    last_bro = 0
    runs_last = {}
    use_sd = False
    use_mt = False
    use_bro = False
    user = None
    try:
        with open("last_run") as f:
            last_run = f.read().strip()
    except OSError:
        last_run = ""
    possible = None
    playing = None
    timeout = 1
    if not config.server.url or not config.server.secret:
        print("Config is not complete")
        time.sleep(3)
        return
    try:
        user = os.environ["USERPROFILE"]
        use_sd = config.slice.enabled
        use_mt = config.mt.enabled
        use_bro = config.brotato.enabled
    except (AttributeError, KeyError):
        use_sd = use_mt = use_bro = False

    print(f"User profile folder: {user}\nFetch Slice & Dice Data: {'YES' if use_sd else 'NO'}\nFetch Monster Train Data: {'YES' if use_mt else 'NO'}")

    if use_mt:
        mt_folder = os.path.join(user, "AppData", "LocalLow", "Shiny Shoe", "MonsterTrain")
        mt_file = os.path.join(mt_folder, "saves", "save-singlePlayer.json")
        print(f"\nFolder: {mt_folder}\nSavefile: {mt_file}")

    if use_bro:
        bro_file = None
        raise NotImplementedError
        # TODO: Determine brotato folder and save location
        # bro_folder = os.path.join()
        # bro_file = os.path.join(bro_folder)
        # print(f"\nFolder: {bro_folder}\nSavefile: {bro_file}")

    async with ClientSession(config.server.url) as session:
        # Check if the app is registered, prompt it if not
        try:
            async with session.post("/twitch/check-token", params={"key": config.server.secret}) as resp:
                if resp.ok:
                    text = await resp.text()
                    match text:
                        case "DISABLED":
                            print("\nTwitch connectivity is disabled.")
                        case "NOT_EXTENDED":
                            print("\nExtended OAuth functionality is not enabled. Some features will be unavailable.")
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
            time.sleep(timeout)
            start = time.time()
            timeout = 1
            if possible is None:
                for file in os.listdir(os.path.join(config.spire.steamdir, "saves")):
                    if file.endswith(".autosave"):
                        if possible is None:
                            possible = file
                        else:
                            print("Error: Multiple savefiles detected.")
                            possible = None
                            break

            if possible is not None:
                try:
                    cur = os.path.getmtime(os.path.join(config.spire.steamdir, "saves", possible))
                except OSError:
                    possible = None

            if use_sd:
                try:
                    cur_sd = os.path.getmtime(os.path.join(user, ".prefs", "slice-and-dice-3"))
                except OSError:
                    pass
                else:
                    if cur_sd != last_sd:
                        with open(os.path.join(user, ".prefs", "slice-and-dice-3")) as f:
                            sd_data = f.read()
                        sd_data = sd_data.encode("utf-8", "xmlcharrefreplace")
                        async with session.post("/sync/slice", data={"data": sd_data}, params={"key": config.server.secret}) as resp:
                            if resp.ok:
                                last_sd = cur_sd
                                curses = await resp.read()
                                if curses and config.slice.curses:
                                    decoded: list[str] = pickle.loads(curses)
                                    try:
                                        with open(config.slice.curses, "w") as f:
                                            f.write("\n".join(decoded))
                                    except OSError:
                                        pass

            to_send = []
            files = []
            if possible is None and config.client.sync_runs: # don't check run files during a run
                for path, folders, _f in os.walk(os.path.join(config.spire.steamdir, "runs")):
                    for folder in folders:
                        profile = "0"
                        if folder[0].isdigit():
                            profile = folder[0]
                        for p1, d1, f1 in os.walk(os.path.join(path, folder)):
                            for file in f1:
                                if file > last_run:
                                    to_send.append((p1, file, profile))
                                    files.append(file)

            try:
                if possible is None:
                    async with session.get("/playing", params={"key": config.server.secret}) as resp:
                        if resp.ok:
                            j = await resp.json()
                            if j and j.get("item"):
                                track = j['item']['name']
                                artists = ", ".join(x['name'] for x in j['item']['artists'])
                                album = j['item']['album']['name']
                                text = f"{track}\n{artists}\n{album}"
                                if playing != text:
                                    try:
                                        with open(config.client.playing, "w") as f:
                                            f.write(text)
                                        playing = text
                                    except OSError:
                                        pass

                            else:
                                playing = None
                                try:
                                    with open(config.client.playing, "w") as f:
                                        pass # make it an empty file
                                except OSError:
                                    pass

                all_sent = True
                if to_send: # send runs first so savefile can seamlessly transfer its cache
                    for path, file, profile in to_send:
                        with open(os.path.join(path, file)) as f:
                            content = f.read()
                        content = content.encode("utf-8", "xmlcharrefreplace")
                        async with session.post("/sync/run", data={"run": content, "name": file, "profile": profile}, params={"key": config.server.secret, "start": start}) as resp:
                            if not resp.ok:
                                all_sent = False
                    if all_sent:
                        last_run = max(files)
                        with open("last_run", "w") as f:
                            f.write(last_run)

                if possible is None and has_save: # server has a save, but we don't (anymore)
                    async with session.post("/sync/save", data={"savefile": b"", "character": b""}, params={"key": config.server.secret, "has_run": str(all_sent).lower(), "start": start}) as resp:
                        if resp.ok:
                            has_save = False

                if use_mt:
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
                            async with session.post("/sync/monster", data=mt_runs, params={"key": config.server.secret}) as resp:
                                if resp.ok:
                                    last_mt = cur_mt
                                    runs_last.update(mt_runs_last)
                                else:
                                    print(f"ERROR: Monster Train data not properly sent:\n{resp.reason}")


                if use_bro:
                    # TODO: Brotato check for save file changes, send to server
                    raise NotImplementedError
                    # try:
                    #     cur_bro = os.path.getmtime(bro_file)
                    # except OSError:
                    #     traceback.print_exc()
                    # if cur_bro != last_bro:
                    #     with open(bro_file, "rb") as f:
                    #         bro_data = f.read()
                    #     bro_runs = {"save": bro_data}
                    #     async with session.post(
                    #         "/sync/brotato",
                    #         data=bro_runs,
                    #         params={"key": config.server.secret},
                    #     ) as resp:
                    #         if resp.ok:
                    #             last_bro = cur_bro
                    #         else:
                    #             print(
                    #                 f"ERROR: Brotato data not properly sent:\n{resp.reason}"
                    #             )

                # update all profiles
                data = {
                    "slots": b"",
                    "0": b"",
                    "1": b"",
                    "2": b"",
                }

                # always send the save slots; it's possible it changed, even during a run (e.g. wall card)
                cur_slots = os.path.getmtime(os.path.join(config.spire.steamdir, "preferences", "STSSaveSlots"))
                if cur_slots != last_slots:
                    with open(os.path.join(config.spire.steamdir, "preferences", "STSSaveSlots")) as f:
                        data["slots"] = f.read().encode("utf-8", "xmlcharrefreplace")
                tobe_lasp = [0, 0, 0]
                for i in range(3):
                    name = "STSPlayer"
                    if i:
                        name = f"{i}_{name}"
                    try:
                        fname = os.path.join(config.spire.steamdir, "preferences", name)
                        tobe_lasp[i] = m = os.path.getmtime(fname)
                        if m == lasp[i]:
                            continue # unchanged, don't bother
                        with open(fname) as f:
                            data[str(i)] = f.read().encode("utf-8", "xmlcharrefreplace")
                    except OSError:
                        continue

                if any(data.values()):
                    async with session.post("/sync/profile", data=data, params={"key": config.server.secret, "start": start}) as resp:
                        if resp.ok:
                            lasp = tobe_lasp
                            last_slots = cur_slots
                        else:
                            print("Warning: Profiles were not successfully updated. Desyncs may occur.")

                if possible is not None and cur != last:
                    content = ""
                    try:
                        with open(os.path.join(config.spire.steamdir, "saves", possible)) as f:
                            content = f.read()
                    except OSError:
                        possible = None
                        continue
                    content = content.encode("utf-8", "xmlcharrefreplace")
                    char = possible[:-9].encode("utf-8", "xmlcharrefreplace")
                    async with session.post("/sync/save", data={"savefile": content, "character": char}, params={"key": config.server.secret, "has_run": "false", "start": start}) as resp:
                        if resp.ok:
                            last = cur
                            has_save = True

            except (ClientError, ServerDisconnectedError):
                timeout = 10 # give it a bit of time
                print("Error: Server is offline! Retrying in 10s")
                continue

if __name__ == "__main__":
    asyncio.run(main())
