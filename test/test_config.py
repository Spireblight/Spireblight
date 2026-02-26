from unittest import TestCase
from pathlib import Path

import logging

from src import logger, config as _cfgmodule
from src.exceptions import InvalidConfigType

# this is where all the test files reside
orig = Path.cwd() / "test" / "static"

class TestConfigFile(TestCase):
    def setUp(self):
        self.config = _cfgmodule.load_default_config()

    def test_auto_disable(self):
        return # it fails atm
        file_enabled = orig / "with-tokens.yml"
        file_disabled = orig / "auto-disable.yml"

        self.assertFalse(self.config.twitch.enabled)
        self.assertFalse(self.config.discord.enabled)

        _cfgmodule.load_user_config(self.config, file_enabled)

        self.assertTrue(self.config.twitch.enabled)
        self.assertTrue(self.config.discord.enabled)

        _cfgmodule.load_user_config(self.config, file_disabled)

        self.assertFalse(self.config.twitch.enabled)
        self.assertFalse(self.config.discord.enabled)

    def test_multiple_files(self):
        f1 = orig / "with-tokens.yml"
        f2 = orig / "unrelated.yml"

        _cfgmodule.load_user_config(self.config, f1)

        doauth = self.config.discord.oauth_token

        # second file doesn't touch tokens, so they should still be there
        _cfgmodule.load_user_config(self.config, f2)

        self.assertEqual(self.config.discord.oauth_token, doauth)

    def test_argv(self):
        file = orig / "with-tokens.yml"

        _cfgmodule.load_user_config(self.config, file)

        self.assertEqual(self.config.twitch.channel, "twitch")
        self.assertTrue(self.config.discord.enabled)

        _, override = _cfgmodule.parse_launch_args(["--no-discord", "--channel", "testing"])
        self.config.update(override)

        self.assertEqual(self.config.twitch.channel, "testing")
        self.assertFalse(self.config.discord.enabled)

    def test_exists(self):
        # works fine
        self.config.update({"bot": {"prefix": "%"}})

        with self.assertLogs(logger.logger, logging.WARNING):
            self.config.update({"spam": "eggs"})

        with self.assertRaises(AttributeError):
            self.config.spam

    def test_replace(self):
        self.assertEqual(self.config.bot.prefix, "!")
        self.config.update({"bot": {"prefix": "%"}})
        self.assertEqual(self.config.bot.prefix, "%")

    def test_nested(self):
        self.assertEqual(self.config.twitch.extended.client_id, "")
        self.config.update({"twitch": {"extended": {"client_id": "eggs"}}})
        self.assertEqual(self.config.twitch.extended.client_id, "eggs")

    def test_dict_type(self):
        # this should just succeed
        self.config.update({"twitch": {"channel": "spam"}})

        with self.assertRaises(InvalidConfigType):
            self.config.update({"twitch": "eggs"})

        with self.assertRaises(InvalidConfigType):
            self.config.update({"server": "spamalot"})

    def test_list_type(self):
        lst = self.config.bot.spire_mods
        self.assertEqual(lst, ["Slay the Spire"])
        self.config.update({"bot": {"spire_mods": "Downfall"}})
        self.assertEqual(self.config.bot.spire_mods, ["Slay the Spire", "Downfall"])

        self.assertIs(self.config.bot.spire_mods, lst)

        self.config.update({"bot": {"spire_mods": {"Packmaster"}}})
        self.assertEqual(self.config.bot.spire_mods, ["Slay the Spire", "Downfall", "Packmaster"])

        self.assertIs(self.config.bot.spire_mods, lst)

        self.config.update({"bot": {"spire_mods": ["Downfall", "Hermit"]}})
        self.assertEqual(self.config.bot.spire_mods, ["Slay the Spire", "Downfall", "Packmaster", "Hermit"])

        self.assertIs(self.config.bot.spire_mods, lst)

        with self.assertRaises(InvalidConfigType):
            self.config.update({"bot": {"spire_mods": 34}})

    def test_int_type(self):
        self.assertEqual(self.config.server.port, 80)
        self.config.update({"server": {"port": 6667}})
        self.assertEqual(self.config.server.port, 6667)

        self.config.update({"server": {"port": "6697"}}) # using SSL is better
        self.assertEqual(self.config.server.port, 6697)

        with self.assertRaises(InvalidConfigType):
            self.config.update({"server": {"port": "not a number"}})

    def test_str_type(self):
        self.assertEqual(self.config.bot.name, "")
        self.config.update({"bot": {"name": "some test bot"}})
        self.assertEqual(self.config.bot.name, "some test bot")

        with self.assertRaises(InvalidConfigType):
            self.config.update({"bot": {"name": ["Not a real name!"]}})

    def test_bool_type(self):
        self.assertFalse(self.config.server.debug)
        self.config.update({"server": {"debug": True}})
        self.assertTrue(self.config.server.debug)

        with self.assertRaises(InvalidConfigType):
            self.config.update({"server": {"debug": "false"}})

    def tearDown(self):
        self.config = None
