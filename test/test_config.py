from unittest import TestCase

from src import config as _cfgmodule

class TestConfigFile(TestCase):
    def setUp(self):
        self.config = _cfgmodule.load_default_config()

    def tearDown(self):
        self.config = None
