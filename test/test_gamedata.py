from unittest import TestCase

from datetime import datetime
import json
import os

from save import _savefile as s
from runs import RunParser

# TODO: make profiles work for testing

with open(os.path.join("test", "static", "dummy_savefile.json")) as f:
    s.update_data(json.load(f), "THE_SILENT", "false")

with open(os.path.join("test", "static", "watcher.json")) as f:
    wa = RunParser("watcher.json", 0, json.load(f))

with open(os.path.join("test", "static", "slay_the_streamer.json")) as f:
    streamer = RunParser("slay_the_streamer.json", 2, json.load(f))

class TestFileParser(TestCase):
    def test_character(self):
        self.assertEqual(s.character, "Silent")

    def test_modded(self):
        self.assertFalse(s.modded)

    def test_seed(self):
        self.assertEqual(s.seed, "57Z3V6XL40NZS")

    def test_seeded(self):
        self.assertFalse(s.is_seeded)

    def test_timestamp(self):
        self.assertEqual(s.timestamp, datetime(2022, 5, 3, 20, 14, 30, 317000))
        self.assertEqual(wa.timestamp, datetime(2023, 6, 16, 20, 34, 58))
        self.assertEqual(streamer.timestamp, datetime(2023, 7, 12, 20, 9, 44))

class TestSavefile(TestCase):
    def test_timedelta(self):
        self.assertEqual(s.timedelta.seconds, 3379)

    def test_display_name(self):
        self.assertEqual(s.display_name, "Current Silent run")

    def test_in_game(self):
        self.assertTrue(s.in_game)

    def test_keys(self):
        k = s.keys
        self.assertTrue(k.ruby_key_obtained)
        self.assertTrue(k.emerald_key_obtained)
        self.assertTrue(k.sapphire_key_obtained)

        self.assertEqual(k.ruby_key_floor, 42)
        self.assertEqual(k.sapphire_key_floor, 43)

    def test_current_health(self):
        self.assertEqual(s.current_health, 32)

    def test_max_health(self):
        self.assertEqual(s.max_health, 70)

    def test_gold(self):
        self.assertEqual(s.current_gold, 85)

class TestRunParser(TestCase):
    def test_won(self):
        self.assertTrue(wa.won)
        self.assertFalse(streamer.won)

    def test_keys(self):
        k = wa.keys
        self.assertTrue(k.ruby_key_obtained)
        self.assertTrue(k.emerald_key_obtained)
        self.assertTrue(k.sapphire_key_obtained)

        self.assertEqual(k.ruby_key_floor, 41)
        self.assertEqual(k.emerald_key_floor, 10)
        self.assertEqual(k.sapphire_key_floor, 26)

class TestNeow(TestCase):
    pass

class TestPath(TestCase):
    def test_length(self):
        self.assertEqual(len(s.path), 45)
        self.assertEqual(len(wa.path), 57)
        self.assertEqual(len(streamer.path), 50)

    def test_streamer(self):
        # Slay the Streamer has a weird thing after the chest
        self.assertEqual(streamer.path[8].floor, 9)
        self.assertEqual(streamer.path[9].floor, 11)

    def test_current_hp(self):
        self.assertEqual([x.current_hp for x in s.path], s.current_hp_counts[1:])
        self.assertEqual([x.current_hp for x in wa.path][:-1], wa.current_hp_counts[1:])
        # slay the streamer kinda breaks this

    def test_max_hp(self):
        self.assertEqual([x.max_hp for x in s.path], s.max_hp_counts[1:])
        self.assertEqual([x.max_hp for x in wa.path][:-1], wa.max_hp_counts[1:])

    def test_gold(self):
        self.assertEqual([x.gold for x in s.path], s.gold_counts[1:])
        self.assertEqual([x.gold for x in wa.path][:-1], wa.gold_counts[1:])
