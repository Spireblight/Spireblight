from config import Config
import os
import tempfile
import unittest

class TestConfig(unittest.TestCase):
    def test_file_missing(self):
        with tempfile.TemporaryDirectory() as tempdir:
            cfg = Config.from_file("this file does not exist")
            self.assertEqual("", cfg.API_key, "properties should be empty")

            
    def test_file_empty(self):
        with tempfile.TemporaryDirectory() as tempdir:
            filename = os.path.join(tempdir, "config.json")
            with open(filename, "w+") as file:
                file.write("{}")

            cfg = Config.from_file(filename)
            self.assertEqual("", cfg.API_key, "properties should be empty")
    
    
    def test_file_full(self):
        with tempfile.TemporaryDirectory() as tempdir:
            filename = os.path.join(tempdir, "config.json")
            with open(filename, "w+") as file:
                file.write("""
                {
                    "token": "token",
                    "oauth": "oauth",
                    "prefix": "prefix",
                    "API_key": "api key",
                    "YT_channel_id": "youtube",
                    "channel": "channel",
                    "editors": [
                        "that one person",
                        "that other person"
                    ],
                    "website_url": "url",
                    "secret": "secret",
                    "json_indent": 1,
                    "cache_timeout": 2,
                    "default_video_id": "video",
                    "STS_path": "/somedir/",
                    "global_interval": 3,
                    "global_commands": [
                        "cmd"
                    ],
                    "sponsored_interval": 4,
                    "sponsored_commands": [
                        "help"
                    ],
                    "discord_servid": "discord",
                    "discord_invite_link": "discord invite",
                    "client_id": "client",
                    "client_secret": "client secret",
                    "webhook_secret": "webhook secret",
                    "moderator_role": "mod",
                    "owners": ["you cant own a discord, man"],
                    "website_bg": "FFFFFF"
                }
                """)

            cfg = Config.from_file(filename)
            self.assertEqual("token", cfg.token, "properties should not be empty")
            self.assertEqual("oauth", cfg.oauth, "properties should not be empty")
            self.assertEqual("prefix", cfg.prefix, "properties should not be empty")
            self.assertEqual("api key", cfg.API_key, "properties should not be empty")
            self.assertEqual("youtube", cfg.YT_channel_id, "properties should not be empty")
            self.assertEqual("channel", cfg.channel, "properties should not be empty")
            self.assertEqual(["that one person","that other person"], cfg.editors, "properties should not be empty")
            self.assertEqual("url", cfg.website_url, "properties should not be empty")
            self.assertEqual("secret", cfg.secret, "properties should not be empty")
            self.assertEqual(1, cfg.json_indent, "properties should not be empty")
            self.assertEqual(2, cfg.cache_timeout, "properties should not be empty")
            self.assertEqual("video", cfg.default_video_id, "properties should not be empty")
            self.assertEqual("/somedir/", cfg.STS_path, "properties should not be empty")
            self.assertEqual(3, cfg.global_interval, "properties should not be empty")
            self.assertEqual(["cmd"], cfg.global_commands, "properties should not be empty")
            self.assertEqual(4, cfg.sponsored_interval, "properties should not be empty")
            self.assertEqual(["help"], cfg.sponsored_commands, "properties should not be empty")
            self.assertEqual("discord", cfg.discord_servid, "properties should not be empty")
            self.assertEqual("discord invite", cfg.discord_invite_link, "properties should not be empty")
            self.assertEqual("client", cfg.client_id, "properties should not be empty")
            self.assertEqual("client secret", cfg.client_secret, "properties should not be empty")
            self.assertEqual("webhook secret", cfg.webhook_secret, "properties should not be empty")
            self.assertEqual("mod", cfg.moderator_role, "properties should not be empty")
            self.assertEqual(["you cant own a discord, man"], cfg.owners, "properties should not be empty")
            self.assertEqual("FFFFFF", cfg.website_bg, "properties should not be empty")

unittest.main()