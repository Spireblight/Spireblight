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

    def tearDown(self):
        self.config = None
