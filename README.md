# TwitchCordBot

This is a program meant as a Twitch-Discord hybrid bot that also is a website.
Made for [Baalorlord on Twitch](https://twitch.tv/baalorlord), so quite a few
things are hardcoded currently. If interest picks up and people want to use it
elsewhere, I will move the stuff out of the repo.

## Installation

This needs Python 3.11 or higher. To set up the project, you should only need create a
virtualenv and install the requirements:

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

If you want to change dependencies, be it upgrading or changing for a
different library, make sure to do a search-all for `DEPCHECK`. Those pieces of
code are likely to need attention during dependency upgrades, as they may rely
on private or unstable APIs. Conversely, they may implement a feature that is
present in later versions, and would benefit from changing it.

The data folder has a bunch of stuff to make the bot run. `data.json` contains
most of the commands

## Documentation

The documentation [lives here](https://spireblight.github.io), with the Sphinx
source [in the Docs repo](https://github.com/Spireblight/Docs).

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

## Syncing Run Data

There will be no runs on the client initially. In order to sync your runs, while both the server and client from above are running, you'll need to complete a run in Slay the Spire. This can include just starting a run and abandoning it immediately. The synced runs can be found in the `data` folder in the root.

## Contributing

For any issues, feel free to open an issue or submit a PR.

Development discord: https://discord.gg/RHYrs3Nsve

---

# Step-by-step guide to get minimum functionality up and running (mostly) locally

## Local server and client:
1. Clone repo from github
2. Create virtual environment and install dependancies:
    1. Create env:
        ```bash
        python3.11 -m venv env
        ```
    2.  Start virtual environment:
        ```bash
        source env/bin/activate
        ```
    3.  Install requirements:
        ```bash
        pip install -r requirements.txt
        ```
3. Run `python ./main.py` to start the server
    * At this step the website should be accessible at `localhost:8080`
4. Run `python ./client.py` once to create a skeleton `dev-config.yml` file
5. Check `default-config.yml` and `dev-config.yml` settings and validate:
    1. that there is a secret set for the server and,
    2. that the Spire path matches your OS
6. Stop and restart the server (`ctrl-c` to stop, then `python ./main.py`)
7. Stop and restart the client (`ctrl-c` to stop, then `python ./client.py`)
    * Any Spire runs in your save file should now be visible on the website.

## If you want to test bot commands, you'll also need a bot of some kind:
### Discord Bot
1. Go to the discord developer site at `https://discord.com/developers/applications`
2. Create a new application and give it a name (accept terms if necessary)
3. Within this new app, click on the bot tab and create a new bot
    * You'll need to record the token for this bot in order to hook it into the server - if you lose it, you'll need to generate a new one.
    * Disabling the "Public Bot" setting prevents random people from adding your bot to servers
4. Create an OAuth2 link to add your bot to a server using the OAuth2 URL Generator
    * Select relevant permissions/scope, then click copy and paste this into a browser and complete prompts.
5. Give your new bot permissions appropriate Privileged Gateway Intents (If these are not set correctly, the discord integration will fail and crash the rest of the app)
6. Add the bot token to your `dev-config.yml` file and set `Discord.enabled: true`
7. Restart the server (`python ./main.py`)
8. Validate functionality by using commands in discord and checking for command list on site

### Twitch Chat commands
Twitch chat messages can be tested without setting up a full Twitch developer account.  All that is required is an oath login token for your account and a chat channel to test commands in.
1. Go to `https://twitchapps.com/tmi/` while logged in as the account you wish to use to test and copy the oath token
2. In the `dev-config.yml`, update the `twitch:` configs:
    * Paste the oath token into the `oauth_token:` line
    * Choose a channel use to test commands and put that in the `channel:` line - Every twitch accout has an associated channel, so you can put your twitch username here and use that if nothing else comes to mind.
    * Set `enabled:` to `true`
3. Restart the server (`python ./main.py`)
4. Navigate to the twitch channel you used and then the chat page
5. Validate functionality by using commands in chat and checking for command list on site

### Local Testing
To run all unit tests locally, run this command from within the spireblight directory:
`python -m unittest discover -v -s test -t .`