import time
import os

path = ""
# Uncomment the following with your Spire path
#path = r"C:\Program Files (x86)\Steam\steamapps\common\SlayTheSpire"

last = 0
possible = None
exists = False

while True:
    time.sleep(1)
    if not exists:
        possible = None
        for file in os.listdir(os.path.join(path, "saves")):
            if file.endswith(".autosave"):
                if possible is None:
                    possible = file
                else:
                    print("Error: Multiple savefiles detected.")
                    possible = None
                    break

        if possible is not None:
            exists = True

    if possible is None:
        continue

    try:
        cur = os.path.getmtime(os.path.join(path, "saves", possible))
    except OSError:
        exists = False
        continue

    if cur != last:
        # XXX: send it via HTTP to the server here
        last = cur
