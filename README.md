# TwitchCordBot

This is a program meant as a Twitch-Discord hybrid bot that also is a website.
Made for [Baalorlord on Twitch](https://twitch.tv/baalorlord), so quite a few
things are hardcoded currently. If interest picks up and people want to use it
elsewhere, I will move the stuff out of the repo.

## Installation

This needs Python 3.10. To set up the project, you should only need create a
virtualenv and install the requirements:

```bash
python3.10 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

The data folder has a bunch of stuff to make the bot run. data.json contains
most of the commands

## Running and configuring the server

```bash
python ./main.py
```

When you run it for the first time, a file called `dev-config.yml` will be
created, in which you can put authentication tokens and other configuration. The
configuration defaults and documentation for all the variables can be found in
[default-config.yml](default-config.yml).

## Running the client

The client side should run `client.py`. Client only needs the `aiohttp` library.
The client configuration needs the following to be set:

- `spire.steamdir`
- `server.url`
- `server.secret`

## Contributing

For any issues, feel free to open an issue or submit a PR.

Development discord: https://discord.gg/RHYrs3Nsve
