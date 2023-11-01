from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock, MagicMock

import server


class TestDiscordCommands(IsolatedAsyncioTestCase):
    @patch("server.query")
    async def test_discord_command_card_with_art_error(self, mock_query):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        mock_query.return_value = None

        # Invoke command using mocked context and desired command keywords
        await server.card_with_art(context, "Error")

        # Validate that expected calls and awaits were made
        mock_query.assert_called_once_with("Error")
        context.reply.assert_awaited_once_with("Could not find card 'Error'")
    

    @patch("server.query")
    async def test_discord_command_card_with_art_not_a_card(self, mock_query):
        # Set up required mocks
        context = AsyncMock()
        context.reply
        info = MagicMock(cls_name="relic")
        mock_query.return_value = info

        # Invoke command using mocked context and desired command keywords
        await server.card_with_art(context, "anchor")

        # Validate that expected calls and awaits were made
        mock_query.assert_called_once_with("anchor")
        context.reply.assert_awaited_once_with(
            "Can only find art for cards. Use !info instead."
        )

    @patch("server.query")
    async def test_discord_command_card_with_art_success_sts_clumsy(self, mock_query):
        # Set up required mocks
        context = AsyncMock()
        context.reply
        info = MagicMock(cls_name="card", mod=None, internal="Clumsy")
        mock_query.return_value = info

        # Invoke command using mocked context and desired command keywords
        await server.card_with_art(context, "clumsy")

        # Validate that expected calls and awaits were made
        mock_query.assert_called_once_with("clumsy")
        context.reply.assert_awaited_once_with(
            "You can view this card and the upgrade with the art here: https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/slay%20the%20spire/cards/clumsy.png"
        )

    @patch("server.query")
    async def test_discord_command_card_with_art_success_mod_snapshot(self, mock_query):
        # Set up required mocks
        context = AsyncMock()
        context.reply
        info = MagicMock(cls_name="card", mod="Downfall", internal="hermit:Snapshot")
        mock_query.return_value = info

        # Invoke command using mocked context and desired command keywords
        await server.card_with_art(context, "snapshot")

        # Validate that expected calls and awaits were made
        mock_query.assert_called_once_with("snapshot")
        context.reply.assert_awaited_once_with(
            "You can view this card and the upgrade with the art here: https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/downfall/cards/hermit-snapshot.png"
        )
