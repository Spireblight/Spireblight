import argparse
import pathlib
import yaml

import _cfgmap

__version__ = "0.7"
__author__ = "Anilyka Barry"
__github__ = "https://github.com/Spireblight/Spireblight"
__botname__ = "Spireblight"

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

parser = argparse.ArgumentParser(__botname__)

parser.add_argument("--config-file", "-f", action="append")
parser.add_argument("--version", "-v", action="version", version=f"{__botname__} {__version__}")
parser.add_argument("--no-twitch", action="store_true")
parser.add_argument("--no-discord", action="store_true")
parser.add_argument("--channel", "-c")

def load_config(args: argparse.Namespace):
    curpath = pathlib.Path(".")
    conf = None
    for i in range(3):
        f = None
        try:
            f = (curpath / "default-config.yml").open()
        except (FileNotFoundError, PermissionError, IsADirectoryError): # you never know
            curpath = curpath / ".."
        else:
            conf = yaml.safe_load(f)
            break # this will break out of the loop, but finally always happens :>
        finally:
            if f is not None:
                f.close()

    if conf is None:
        raise RuntimeError("No default config could be found.")

    conf = _cfgmap.Config(**conf)

    if args.config_file:
        for file in args.config_file:
            file: str
            curfile = curpath / file
            if not curfile.is_file():
                raise RuntimeError(f"Config file {file!r} could not be found.")
            with curfile.open() as f:
                cf = yaml.safe_load(f)
            conf.update(cf)

    else: # none specified, use the dev one
        devfile = curpath / "dev-config.yml"

        if not devfile.exists(): # make our own
            with devfile.open("w") as f:
                yaml.dump(DEFAULT_DEV_CONFIG, f)

            print("No dev-config.yml file found.")
            print("A skeleton has been written for you.")

        with devfile.open() as f:
            cf = yaml.safe_load(f)
        conf.update(cf)
