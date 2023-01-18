import logging
import random
import json
import yaml
import sys
import os

from dotmap import DotMap

# This is the minimal development config needed.
DEFAULT_DEV_CONFIG = {
    "twitch": {
        "enabled": False,
        "oauth_token": "<Get one at https://twitchapps.com/tmi/>",
        "channel": "baalorlord",
    },
    "discord": {
        "enabled": False,
        "oauth_token": "<token unset>"
    },
    "server": {"debug": False, "secret": "<i-haven't-set-a-secret>"},
}

def load_file(filename: str) -> DotMap:
    with open(filename, 'r') as stream:
        # With _dynamic=False, any access on something we hadn't yet
        # set will raise an exception. With _dynamic=True (the default) it
        # would instead return None. This lets us know when we access things
        # that aren't set.
        conf = DotMap(yaml.safe_load(stream), _dynamic=False)
        return conf

# Load the default configuration file
config = load_file("./default-config.yml")

# Expand filepaths for *nix systems ('~/' becomes '/home/$USER').  Has no effect otherwise.
config.spire.steamdir = os.path.expanduser(config.spire.steamdir) 

# Determine which extra file to load values from.
if len(sys.argv) >= 2:
    # If we have specified a configuration file on the command line, use that.
    extra_file = sys.argv[1]
else:
    # Otherwise, use the development one.
    extra_file = "./dev-config.yml"

    # But if it doesn't exist yet, be nice and make one for the user.
    if not os.path.exists(extra_file):
        with open(extra_file, 'w') as f:
            f.write(yaml.dump(DEFAULT_DEV_CONFIG))

        print("No ./dev-config.yml file found.")
        print("A skeleton has been written for you.")

extra = load_file(extra_file)

# This is a little hack to update each of the sections with the values from
# the extra file. A simple `config = config | extra` dict merge would be nice,
# but that completely overrides _all_ the values of things specified in the
# extra files, not just the ones that have been added. So, if the only thing
# we change under "server" would be to add "debug: true", then all the other
# keys would be missing.
for key in extra:
    config[key].update(extra[key])

config.filename = extra_file
print("Configuration loaded:", json.dumps(config, indent=config.server.json_indent))
