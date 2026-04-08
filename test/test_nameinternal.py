from unittest import TestCase

from src.nameinternal import _sanitize, query

# BEGIN SETUP

import asyncio, src.events as events

asyncio.run(events.invoke("setup_init"))


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
        pass
