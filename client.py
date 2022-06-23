from aiohttp import ClientSession, ClientError

import asyncio
import time
import os

import config

async def main():
    has_save = False # whether the server has a save file
    last = 0
    possible = None
    timeout = 1
    while True:
        time.sleep(timeout)
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

        try:
            if possible is None and has_save: # server has a save, but we don't (anymore)
                async with ClientSession() as session:
                    async with session.post(f"{config.website_url}/sync/save", data={"savefile": b""}, params={"key": config.secret}) as resp:
                        if resp.ok:
                            has_save = False

            if possible is not None and cur != last:
                content = ""
                with open(os.path.join(config.STS_path, "saves", possible)) as f:
                    content = f.read()
                content = content.encode("utf-8", "xmlcharrefreplace")
                async with ClientSession() as session:
                    async with session.post(f"{config.website_url}/sync/save", data={"savefile": content}, params={"key": config.secret}) as resp:
                        if resp.ok:
                            last = cur
                            has_save = True
        except ClientError:
            timeout = 10 # give it a bit of time
            continue

if __name__ == "__main__":
    asyncio.run(main())
