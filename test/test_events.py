from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
import asyncio

from src import events

class TestEvents(IsolatedAsyncioTestCase):
    async def test_setup_unique(self):
        amock = AsyncMock()
        events.add_listener("fake_setup")(amock)
        await events.invoke("fake_setup")
        await events.invoke("fake_setup")
        amock.assert_called_once()
        self.assertNotIn("fake_setup", events.EVENTS)
