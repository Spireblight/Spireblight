from unittest import TestCase

from src.nameinternal import _sanitize, query, get

# BEGIN SETUP

import asyncio, src.events as events

asyncio.run(events.invoke("setup_init"))

# END SETUP

class TestSanitize(TestCase):
    def test_lower(self):
        self.assertEqual(_sanitize("SPAM"), "spam")
        self.assertEqual(_sanitize("Eggs"), "eggs")

    def test_symbols(self):
        self.assertEqual(_sanitize("Hello world."), "helloworld")
        self.assertEqual(_sanitize("Something 'Real'"), "somethingreal")
        self.assertEqual(_sanitize("Hello(W-o-R-l-D)"), "helloworld")

class TestQuery(TestCase):
    def test_game_override(self):
        res1 = query("vajra")
        self.assertEqual(res1.v, 2)
        self.assertEqual(res1.cls_name, "relic") # just making sure
        # because it cycles but prioritizes Spire 2, check that it's still correct
        self.assertEqual(query("vajra").v, 2)
        self.assertEqual(query("vajra 1").v, 1)

class TestGet(TestCase):
    def test_basic(self):
        res = get("Gash") # Claw from Spire 1 :3
        self.assertEqual(res.cls_name, "card")
        self.assertEqual(res.name, "Claw")
        self.assertEqual(res.v, 1)

    def test_unknown(self):
        self.assertEqual(get("gibberish that just isn't anything in the game").cls_name, "<unknown>")

    def test_spire2_choice(self):
        res = get("SCROLL_BOXES.title")
        self.assertEqual(res.name, "Scroll Boxes")
        self.assertEqual(res.v, 2)

    def test_spire2_extended(self):
        res = get("CARD.BLIGHT_STRIKE")
        self.assertEqual(res.name, "Blight Strike")
        self.assertEqual(res.v, 2)

        res2 = get("RELIC.LOST_COFFER")
        self.assertEqual(res2.name, "Lost Coffer")
        self.assertEqual(res2.cls_name, "relic")

