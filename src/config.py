import collections
import argparse
import pathlib
import yaml

from src import _cfgmap

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

curpath: pathlib.Path = None
config: _cfgmap.Config

parser = argparse.ArgumentParser(__botname__)

parser.add_argument("--config-file", action="append", help="Add a config file to use")
parser.add_argument("--version", action="version", version=f"{__botname__} {__version__}")
parser.add_argument("--no-twitch", action="store_true", help="Disable the Twitch bot")
parser.add_argument("--no-discord", action="store_true", help="Disable the Discord bot")
parser.add_argument("--channel", help="Which Twitch channel to join")

def load_default_config():
    global curpath
    if curpath is None:
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

    return _cfgmap.Config(**conf)

def parse_launch_args(args: argparse.Namespace):
    files: list[pathlib.Path] = []
    override = collections.defaultdict(dict)

    if args.config_file:
        for file in args.config_file:
            file: str
            curfile = curpath / file
            if not curfile.is_file():
                raise RuntimeError(f"Config file {file!r} could not be found.")
            files.append(curfile)

    else: # none specified, use the dev one
        devfile = curpath / "dev-config.yml"

        if not devfile.exists(): # make our own
            with devfile.open("w") as f:
                yaml.dump(DEFAULT_DEV_CONFIG, f)

            print("No dev-config.yml file found.")
            print("A skeleton has been written for you.")

        files.append(devfile)

    if args.channel:
        override["twitch"]["channel"] = args.channel

    if args.no_twitch:
        override["twitch"]["enabled"] = False

    if args.no_discord:
        override["discord"]["enabled"] = False

    return files, override

def load_user_config(conf: _cfgmap.Config, file: pathlib.Path):
    with file.open() as f:
        cf = yaml.safe_load(f)
    conf.update(cf)

def load():
    """Load the full configuration for the program."""
    global config
    config = load_default_config()

    # this is important; both testing and docgen use their own args
    # we should only care about what we actually use
    args, _ = parser.parse_known_args()
    files, override = parse_launch_args(args)

    for file in files:
        load_user_config(config, file)

    config.update(override)
