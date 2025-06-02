from unittest import TestCase

from datetime import datetime
import json
import os

from save import _savefile as s
from runs import RunParser

# TODO: make profiles work for testing

# BEGIN SETUP

import asyncio, events

asyncio.run(events.invoke("setup_init"))

wa = streamer = None

with open(os.path.join("test", "static", "dummy_savefile.json")) as f:
    s.update_data(json.load(f), "THE_SILENT", "false")

with open(os.path.join("test", "static", "watcher.json")) as f:
    wa = RunParser("watcher.json", 0, json.load(f))

with open(os.path.join("test", "static", "slay_the_streamer.json")) as f:
    streamer = RunParser("slay_the_streamer.json", 2, json.load(f))

assert wa is not None and streamer is not None, "could not load test run files"

# END SETUP

_rooms_mapping = {
    "Enemy": "M",
    "Unknown (Enemy)": "m",
    "Treasure": "T",
    "Unknown (Treasure)": "t",
    "Elite": "E",
    "Unknown (Elite)": "e",
    "Unknown": "?",
    "Unknown (Bugged)": "?",
    "Unknown (Ambiguous)": "?",
    "Merchant": "$",
    "Unknown (Merchant)": "S",
    "Rest Site": "R",
    "Boss": "B",
    "Boss Chest": "C",
    "Transition into Act 4": "4",
    "Victory!": "V",
}

class _save_contents:
    rooms = [
    "M",
    "M",
    "$",
    "M",
    "?",
    "R",
    "E",
    "R",
    "T",
    "R",
    "E",
    "M",
    "m",
    "M",
    "R",
    "B",
    "C",
    "M",
    "M",
    "?",
    "?",
    "m",
    "R",
    "?",
    "R",
    "T",
    "E",
    "R",
    "$",
    "E",
    "?",
    "R",
    "B",
    "C",
    "M",
    "?",
    "S",
    "M",
    "$",
    "R",
    "E",
    "R",
    "T",
    "R",
    "?"
    ]
    current_hp = [
    58,
    54,
    54,
    47,
    47,
    47,
    35,
    35,
    35,
    35,
    18,
    18,
    18,
    18,
    18,
    18,
    50,
    40,
    40,
    40,
    70,
    61,
    61,
    56,
    56,
    56,
    54,
    54,
    54,
    51,
    46,
    46,
    19,
    57,
    56,
    56,
    56,
    56,
    56,
    56,
    32,
    32,
    32,
    32,
    32
    ]
    max_hp = [
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    60,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70,
    70
    ]
    gold = [
    360,
    379,
    1,
    14,
    14,
    14,
    46,
    46,
    101,
    101,
    132,
    151,
    164,
    183,
    183,
    262,
    262,
    240,
    255,
    255,
    255,
    271,
    271,
    304,
    304,
    327,
    355,
    355,
    12,
    37,
    157,
    157,
    232,
    232,
    252,
    252,
    103,
    117,
    54,
    54,
    85,
    85,
    85,
    85,
    85
    ]

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

class TestRelicData(TestCase):
    def test_save(self):
        template = "Obtained on floor {}"
        it = iter(s.relics)
        relic = next(it)
        self.assertEqual(relic.name, "Ring of the Snake")

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

class TestNodeSave(TestCase):
    def test_room_type(self):
        path = zip(s.path, _save_contents.rooms)
        for node, short in path:
            self.assertEqual(_rooms_mapping[node.room_type], short)

    def test_current_hp(self):
        path = zip(s.path, _save_contents.current_hp)
        for node, hp in path:
            self.assertEqual(node.current_hp, hp)

    def test_max_hp(self):
        path = zip(s.path, _save_contents.max_hp)
        for node, hp in path:
            self.assertEqual(node.max_hp, hp)

    def test_gold(self):
        path = zip(s.path, _save_contents.gold)
        for node, gold in path:
            self.assertEqual(node.gold, gold)

    def test_floor(self):
        self.assertEqual(s.neow_bonus.floor, 0)
        floor = 1
        for node in s.path:
            self.assertEqual(node.floor, floor)
            floor += 1
        self.assertEqual(floor, 46)
