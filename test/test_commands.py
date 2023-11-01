from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock, MagicMock

import server


class TestDiscordCommands(IsolatedAsyncioTestCase):
    async def test_discord_command_card_with_art_error(self):
        # Set up required mocks
        context = AsyncMock()
        context.reply

        # Find command in discord command list
        card_with_art = None
        for cmd in server._to_add_discord:
            if cmd.name == "card":
                card_with_art = cmd

        await card_with_art(context, "Error")

        context.reply.assert_awaited_once_with("Could not find card 'Error'")

    @patch("server.query")
    async def test_discord_command_card_with_art_not_a_card(self, mock_query):
        # Set up required mocks
        context = AsyncMock()
        context.reply
        mock_query.cls_name = "relic"

        # Find command in discord command list
        card_with_art = None
        for cmd in server._to_add_discord:
            if cmd.name == "card":
                card_with_art = cmd

        # Invoke command using mocked context and desired command keywords
        await card_with_art(context, "anchor")

        context.reply.assert_awaited_once_with(
            "Can only find art for cards. Use !info instead."
        )

    @patch("server.query")
    async def test_discord_command_card_with_art_success_sts_clumsy(self, mock_query):
        # Set up required mocks
        context = AsyncMock()
        context.reply
        info = MagicMock(cls_name = "card", mod = None, internal = "Clumsy")
        mock_query.return_value = info

        # Find desired command in discord command list
        card_with_art = None
        for cmd in server._to_add_discord:
            if cmd.name == "card":
                card_with_art = cmd

        # Invoke command using mocked context and desired command keywords
        await card_with_art(context, "clumsy")

        # Validate that ctx.reply was awaited with the expected result
        context.reply.assert_awaited_once_with(
            "You can view this card and the upgrade with the art here: https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/slay%20the%20spire/cards/clumsy.png"
        )

    @patch("server.query")
    async def test_discord_command_card_with_art_success_mod_snapshot(self, mock_query):
        # Set up required mocks
        context = AsyncMock()
        context.reply
        info = MagicMock(cls_name = "card", mod = "Downfall", internal = "hermit:Snapshot")
        mock_query.return_value = info

        # Find command in discord command list
        card_with_art = None
        for cmd in server._to_add_discord:
            if cmd.name == "card":
                card_with_art = cmd

        # Invoke command using mocked context and desired command keywords
        await card_with_art(context, "clumsy")

        # Validate that ctx.reply was awaited with the expected result
        context.reply.assert_awaited_once_with(
            "You can view this card and the upgrade with the art here: https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/downfall/cards/hermit-snapshot.png"
        )
