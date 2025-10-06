FROM = "0.6"
TO = "0.7"

def migrate(*, automatic: bool):
    import collections, pathlib, yaml
    path = pathlib.Path(".")
    if not automatic: # one path up
        path = path / ".."

    client_cfg = {}

    for file in path.iterdir():
        if file.name.endswith("-config.yml") and file.name != "default-config.yml": # config file
            contents = None
            with file.open() as f:
                contents: dict = yaml.safe_load(f)
            if not contents:
                return False

            redone = collections.defaultdict(dict)

            for key, value in contents:
                match key:
                    case "mt":
                        if "enabled" in value:
                            client_cfg["use_mt"] = value["enabled"]
                    case "slice":
                        if "enabled" in value:
                            client_cfg["use_slice"] = value["enabled"]
                        if "curses" in value:
                            client_cfg["slice_curses"] = value["curses"]
                    case "baalorbot":
                        if "prefix" in value:
                            redone["bot"]["prefix"] = value["prefix"]
                        if "owners" in value:
                            redone["discord"]["owners"] = value["owners"]
                        if "editors" in value:
                            redone["twitch"]["editors"] = value["editors"]
                        redone["bot"]["name"] = "<undefined>"
                    case "spire":
                        if "enabled_mods" in value:
                            redone["bot"]["spire_mods"] = value["enabled_mods"]
                        if "steamdir" in value:
                            client_cfg["spiredir"] = value["steamdir"]
                    case "client":
                        if "playing" in value:
                            client_cfg["playing_file"] = value["playing"]
                        if "sync_runs" in value:
                            client_cfg["sync_runs"] = value["sync_runs"]
                    case _:
                        if key == "server":
                            if "url" in value:
                                client_cfg["server_url"] = value["url"]
                            if "secret" in value:
                                client_cfg["secret"] = value["secret"]
                        if key not in redone:
                            redone[key] = {}
                        redone[key].update(value)

            file.rename(file.parent / f"unconverted-{file.name}")

            with file.open("x") as f:
                yaml.safe_dump(redone, f)

    try:
        with open("client-config.yml", "x") as f:
            yaml.safe_dump(client_cfg, f)
    except FileExistsError:
        yaml.safe_dump(client_cfg) # will go to stdout
    print("Your config files have been converted. Your old config files have been renamed to 'unconverted-***.yml'.")

if __name__ == "__main__":
    migrate(automatic=False) # we don't check return values here
