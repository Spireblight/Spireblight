from unittest import TestCase
from pathlib import Path

from src import config as _cfgmodule
from src.exceptions import InvalidConfigType

class TestConfigFile(TestCase):
    def setUp(self):
        self.config = _cfgmodule.load_default_config()

    def test_auto_disable(self):
        orig = Path.cwd() / "test" / "static"
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

    def tearDown(self):
        self.config = None
