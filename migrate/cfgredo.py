FROM = "0.6"
TO = "0.7"

def migrate(*, automatic: bool):
    import pathlib, yaml
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

            redone = {}

            for key, value in contents:
                match key:
                    case "mt":
                        if "enabled" in value:
                            client_cfg["use_mt"] = value["enabled"]
                    case "baalorbot":
                        redone["bot"] = {}
                        if "prefix" in value:
                            redone["bot"]["prefix"] = value["prefix"]
                        redone["bot"]["name"] = "<undefined>"
                    case _:
                        redone[key] = value

            file.rename(file.parent / f"unconverted-{file.name}")

            with file.open("x") as f:
                yaml.safe_dump(redone, f)

    print("Your config files have been converted. Your old config files have been renamed to 'unconverted-***.yml'.")

if __name__ == "__main__":
    migrate(automatic=False) # we don't check return values here
