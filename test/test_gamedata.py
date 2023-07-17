from unittest import TestCase

import datetime
import json
import os

from save import _savefile as s
from runs import RunParser

with open(os.path.join("test", "static", "dummy_savefile.json")) as f:
    s.update_data(json.load(f), "THE_SILENT", "false")

with open(os.path.join("test", "static", "watcher.json")) as f:
    wa = RunParser("watcher.json", 0, json.load(f))

with open(os.path.join("test", "static", "slay_the_streamer.json")) as f:
    streamer = RunParser("slay_the_streamer.json", 2, json.load(f))

class TestSavefile(TestCase):
    def test_timestamp(self):
        ts = s.timestamp
        self.assertEqual(ts, datetime.datetime(2022, 5, 3, 20, 14, 30, 317000))

    def test_timedelta(self):
        self.assertEqual(s.timedelta.seconds, 3379)

    def test_character(self):
        self.assertEqual(s.character, "Silent")

    def test_display_name(self):
        self.assertEqual(s.display_name, "Current Silent run")

    def test_modded(self):
        self.assertFalse(s.modded)

    def test_keys(self):
        k = s.keys
        self.assertTrue(k.ruby_key_obtained)
        self.assertTrue(k.emerald_key_obtained)
        self.assertTrue(k.sapphire_key_obtained)

        self.assertEqual(k.ruby_key_floor, 42)
        self.assertEqual(k.sapphire_key_floor, 43)

    def test_seed(self):
        self.assertEqual(s.seed, "57Z3V6XL40NZS")

    def test_seeded(self):
        self.assertFalse(s.is_seeded)

class TestPath(TestCase):
    def test_length(self):
        self.assertEqual(len(s.path), 45)
        self.assertEqual(len(wa.path), 57)
        self.assertEqual(len(streamer.path), 50)

