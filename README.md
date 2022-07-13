# TwitchCordBot

This is a program meant as a Twitch-Discord hybrid bot that also is a website. Made for Baalorlord on Twitch, so quite a few things are hardcoded currently. If interest picks up and people want to use it elsewhere, I will move the stuff out of the repo.

This needs Python 3.10 and the following libraries:

- twitchio
- discord
- aiohttp
- aiohttp_jinja2
- matplotlib
- mpld3

The data folder has a bunch of stuff to make the bot run. data.json contains most of the commands

Run main.py for the server. Server-side should have config.py with the following variables:

- token (Discord bot OAuth token)
- oauth (Twitch bot OAuth token)
- prefix (the command prefix; shared between Twitch and Discord)
- API_key (Google API key for YouTube search)
- YT_channel_id (the YouTube channel UID that should be searched for)
- channel (the Twitch channel to connect to)
- editors (a list of the usernames of all people who should be able to edit the bot)
- website_url (the URL out of which the website runs)
- secret (a unique API key for sending over the savefile from the client. if empty, that feature is disabled)
- json_indent (an int of how big should the indent be for dumped json files)
- cache_timeout (an int of how long to wait before clearing cache; mostly used for YouTube API calls. should probably not be lower than 3600)
- default_video_id (the default YouTube video ID to use if API calls fail)
- global_interval (int; the timer interval for global Twitch timers)
- global_commands (list of command names; commands should be present in data/data.json and will be sent periodically according to global_interval)
- sponsored_interval (int; like global_interval but for sponsored content)
- sponsored_commands (list of commands names; like global_commands but with sponsored_interval instead)

The client side should run client.py. Client only needs the aiohttp library. Config should have the following:

- STS_path (the absolute path to the Slay the Spire directory, where the main executable is)
- website_url (should be the same as the server's website_url - this is where the savefile will be sent)
- secret (needs to be identical to the server's secret for savefile syncing to work)

For any issues, feel free to open an issue or submit a PR.
