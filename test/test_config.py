from unittest import TestCase

from platform import system
from os.path import expanduser

from configuration import config

class TestConfigFile(TestCase):

    def test_default_spire_steamdir(self):
        system_os = system().lower()
        if system_os == "windows":
            self.assertEqual(config.spire.steamdir, 'C:\Program Files (x86)\Steam\steamapps\common\SlayTheSpire')
        elif system_os == "linux":
            self.assertEqual(config.spire.steamdir, expanduser("~/.steam/steam/steamapps/common/SlayTheSpire"))
        else:
            self.fail(f"No default spire.steamdir set for os: '{system_os}'")
