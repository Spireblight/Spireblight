from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock, MagicMock

import server


# Test non-game specific commands
class TestDiscordCommands(IsolatedAsyncioTestCase):
    @patch("server.query")
    async def test_command_card_with_art_error(self, mock_query):
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
    async def test_command_card_with_art_not_a_card(self, mock_query):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
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
    async def test_command_card_with_art_success_sts_clumsy(self, mock_query):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
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
    async def test_command_card_with_art_success_mod_snapshot(self, mock_query):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        info = MagicMock(cls_name="card", mod="Downfall", internal="hermit:Snapshot")
        mock_query.return_value = info

        # Invoke command using mocked context and desired command keywords
        await server.card_with_art(context, "snapshot")

        # Validate that expected calls and awaits were made
        mock_query.assert_called_once_with("snapshot")
        context.reply.assert_awaited_once_with(
            "You can view this card and the upgrade with the art here: https://raw.githubusercontent.com/OceanUwU/slaytabase/main/docs/downfall/cards/hermit-snapshot.png"
        )

    # Game specific commands

    # Slay the Spire:

    # !cwbgh (Calipers would be good here)
    # "Calipers would be good here baalorCalipers baalorSmug"

    async def test_command_cwbgh_without_save(self):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()

        # Invoke command using mocked context and desired command keywords
        await server.calipers(context, None)

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Calipers would be good here baalorCalipers baalorSmug"
        )

    @patch("server.query")
    async def test_command_cwbgh_with_save_no_calipers(self, mock_query):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        info = MagicMock(cls_name="relic", name="calipers")
        mock_query.return_value = info
        mock_save = MagicMock(spec_set=server.Savefile)

        # Invoke command using mocked context and desired command keywords
        await server.calipers(context, mock_save)

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Calipers would be good here baalorCalipers baalorSmug"
        )

    @patch("server.query")
    async def test_command_cwbgh_with_save_has_calipers(self, mock_query):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        info = "Calipers"
        mock_query.return_value = info
        mock_save = MagicMock(spec_set=server.Savefile)
        mock_save.relics_bare = [info]

        # Invoke command using mocked context and desired command keywords
        await server.calipers(context, mock_save)

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Calipers ARE good here! baalorCalipers baalorSmug"
        )
