from aiohttp import ClientSession, ClientError

import asyncio
import time
import os

import config

async def main():
    print("Client running. Will periodically check for the savefile and send it over!")
    has_save = True # whether the server has a save file - we lie at first in case we just restarted and it has an old one
    last = 0
    lasp = [0, 0, 0]
    try:
        with open("last_run") as f:
            last_run = f.read().strip()
    except OSError:
        last_run = ""
    possible = None
    timeout = 1
    if not config.website_url or not config.secret:
        print("Config is not complete")
        time.sleep(3)
        return
    while True:
        time.sleep(timeout)
        start = time.time()
        timeout = 1
        if possible is None:
            for file in os.listdir(os.path.join(config.STS_path, "saves")):
                if file.endswith(".autosave"):
                    if possible is None:
                        possible = file
                    else:
                        print("Error: Multiple savefiles detected.")
                        possible = None
                        break

        if possible is not None:
            try:
                cur = os.path.getmtime(os.path.join(config.STS_path, "saves", possible))
            except OSError:
                possible = None

        to_send = []
        files = []
        for path, folders, _f in os.walk(os.path.join(config.STS_path, "runs")):
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
            all_sent = True
            if to_send: # send runs first so savefile can seamlessly transfer its cache
                async with ClientSession() as session:
                    for path, file, profile in to_send:
                        with open(os.path.join(path, file)) as f:
                            content = f.read()
                        content = content.encode("utf-8", "xmlcharrefreplace")
                        async with session.post(f"{config.website_url}/sync/run", data={"run": content, "name": file, "profile": profile}, params={"key": config.secret, "start": start}) as resp:
                            if not resp.ok:
                                all_sent = False
                if all_sent:
                    last_run = max(files)
                    with open("last_run", "w") as f:
                        f.write(last_run)

            if possible is None and has_save: # server has a save, but we don't (anymore)
                async with ClientSession() as session:
                    async with session.post(f"{config.website_url}/sync/save", data={"savefile": b"", "character": b""}, params={"key": config.secret, "has_run": str(all_sent).lower(), "start": start}) as resp:
                        if resp.ok:
                            has_save = False
                    # update all profiles
                    data = {
                        "slots": b"",
                        "0": b"",
                        "1": b"",
                        "2": b"",
                    }
                    # always send the save slots; it's likely it changed
                    with open(os.path.join(config.STS_path, "preferences", "STSSaveSlots")) as f:
                        data["slots"] = f.read().encode("utf-8", "xmlcharrefreplace")
                    tobe_lasp = [0, 0, 0]
                    for i in range(3):
                        name = "STSPlayer"
                        if i:
                            name = f"{i}_{name}"
                        try:
                            fname = os.path.join(config.STS_path, "preferences", name)
                            tobe_lasp[i] = m = os.path.getmtime(fname)
                            if m == lasp[i]:
                                continue # unchanged, don't bother
                            with open(fname) as f:
                                data[str(i)] = f.read().encode("utf-8", "xmlcharrefreplace")
                        except OSError:
                            continue

                    async with session.post(f"{config.website_url}/sync/profile", data=data, params={"key": config.secret, "start": start}) as resp:
                        if resp.ok:
                            lasp = tobe_lasp
                        else:
                            print("Warning: Profiles were not successfully updated. Desyncs may occur.")

            if possible is not None and cur != last:
                content = ""
                with open(os.path.join(config.STS_path, "saves", possible)) as f:
                    content = f.read()
                content = content.encode("utf-8", "xmlcharrefreplace")
                char = possible[:-9].encode("utf-8", "xmlcharrefreplace")
                async with ClientSession() as session:
                    async with session.post(f"{config.website_url}/sync/save", data={"savefile": content, "character": char}, params={"key": config.secret, "has_run": "false", "start": start}) as resp:
                        if resp.ok:
                            last = cur
                            has_save = True

        except ClientError:
            timeout = 10 # give it a bit of time
            print("Error: Server is offline! Retrying in 10s")
            continue

if __name__ == "__main__":
    asyncio.run(main())
