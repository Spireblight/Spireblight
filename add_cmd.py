import json
import time
import os

import config

name = input("Please enter the name of the command: ")
cmd = input("Please input the message for the command (right-click to paste): ")

with open(os.path.join("data", "data.json"), "r") as f:
    data = json.load(f)

name = name.lower().lstrip(config.prefix)

if name in data:
    print(f"Error: another command named {name!r} already exists.\nExiting . . .")
    time.sleep(4)
    quit()

data[name] = {"output": cmd}

with open(os.path.join("data", "data.json"), "w") as f:
    json.dump(data, f, indent=config.json_indent)

input(f"Command {name!r} successfully added! Don't forget to restart the bot for it to take effect.\nPress Enter to exit.")
