import datetime

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock, MagicMock

import server


class TestCommandCommand(IsolatedAsyncioTestCase):
    @patch("server.update_db")
    @patch("server.TConn", autospec=True)
    async def test_command_command_add_success(self, TConn, update_db):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()

        # Invoke command using mocked context and desired command keywords
        await server.command_cmd(
            context, "add", "test_in_prod", "We're testing in prod!"
        )

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Command test_in_prod added! Permission: Everyone"
        )

        TConn.add_command.assert_called_once()
        update_db.assert_called_once()

    @patch("server.update_db")
    @patch("server.TConn", autospec=True)
    async def test_command_command_add_success_with_valid_flag(self, TConn, update_db):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()

        # Invoke command using mocked context and desired command keywords
        await server.command_cmd(
            context, "add", "test_in_prod", "+m", "We're testing in prod!"
        )

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Command test_in_prod added! Permission: Moderator"
        )

        TConn.add_command.assert_called_once()
        update_db.assert_called_once()

    @patch("server.update_db")
    @patch("server.TConn")
    async def test_command_command_add_failure_already_added(self, TConn, update_db):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        TConn.commands = {"test_in_prod": ["We're testing in prod!"]}

        # Invoke command using mocked context and desired command keywords
        await server.command_cmd(
            context, "add", "test_in_prod", "We're testing in prod!"
        )

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Error: command test_in_prod already exists!"
        )

        TConn.add_command.assert_not_called()
        update_db.assert_not_called()

    @patch("server.update_db")
    @patch("server.TConn")
    async def test_command_command_add_failure_already_alias(self, TConn, update_db):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        cmd = MagicMock(spec=server.CommandType)
        cmd.name = "tests"
        TConn.commands = {"tests": [cmd]}
        TConn._command_aliases = {"test_in_prod": [{"name": cmd.name}]}

        # Invoke command using mocked context and desired command keywords
        await server.command_cmd(
            context, "add", "test_in_prod", "We're testing in prod!"
        )

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Error: test_in_prod is an alias to tests. Use 'unalias tests test_in_prod' first."
        )

        TConn.add_command.assert_not_called()
        update_db.assert_not_called()

    @patch("server.update_db")
    @patch("server.TConn")
    async def test_command_command_add_failure_unknown_flag(self, TConn, update_db):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        cmd = MagicMock(spec=server.CommandType)
        cmd.name = "tests"
        TConn.commands = {"tests": [cmd]}
        TConn._command_aliases = {"test_in_prod": [{"name": cmd.name}]}

        # Invoke command using mocked context and desired command keywords
        await server.command_cmd(
            context, "add", "flag", "+z", "This isn't a proper flag!"
        )

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with("Error: flag not recognized.")

        TConn.add_command.assert_not_called()
        update_db.assert_not_called()

    @patch("server.update_db")
    @patch("server.TConn")
    async def test_command_command_add_failure_no_output(self, TConn, update_db):
        # Set up required mocks
        context = MagicMock()
        context.reply = AsyncMock()
        cmd = MagicMock(spec=server.CommandType)
        cmd.name = "tests"
        TConn.commands = {"tests": [cmd]}
        TConn._command_aliases = {"test_in_prod": [{"name": cmd.name}]}

        # Invoke command using mocked context and desired command keywords
        await server.command_cmd(context, "add", "flag")

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with("Error: no output provided.")

        TConn.add_command.assert_not_called()
        update_db.assert_not_called()


# TODO: test_command_command_edit_success(self, TConn):
# TODO: test_command_command_edit_success_with_valid_flag(self, TConn):
# TODO: test_command_command_edit_failure_no_output(self, TConn):
# TODO: test_command_command_edit_failure_does_not_exist(self, TConn):
# TODO: test_command_command_edit_failure_built-in_command(self, TConn):
# TODO: test_command_command_edit_failure_alias(self, TConn):
# TODO: test_command_command_edit_failure_unknown_flag(self, TConn):

# TODO: test_command_command_remove(self, TConn):
# TODO: test_command_command_enable(self, TConn):
# TODO: test_command_command_disable(self, TConn):
# TODO: test_command_command_alias(self, TConn):
# TODO: test_command_command_unalias(self, TConn):

# TODO: test_command_command_unknown_action(self, TConn):


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

    @patch("server._update_quotes")
    async def test_quote_add(self, mock_update):
        context = MagicMock()
        context.reply = AsyncMock()

        now = datetime.datetime.now()

        await server.quote_stuff(context, "add", "Meow!", "-", "Faely, not wanting to write these tests")

        context.reply.assert_awaited_once_with("Quote #0 successfully added!")

        context.reply = AsyncMock()

        await server.quote_stuff(context)

        context.reply.assert_awaited_once_with(f'Quote #0: "Meow!" - Faely, not wanting to write these tests, on {now.year}-{now.month:02}-{now.day:02}')

        mock_update.assert_called_once()

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
        info = "calipers"
        mock_query.return_value = info
        mock_save = MagicMock(spec_set=server.Savefile)
        mock_save.relics_bare = [info]

        # Invoke command using mocked context and desired command keywords
        await server.calipers(context, mock_save)

        # Validate that expected calls and awaits were made
        context.reply.assert_awaited_once_with(
            "Calipers ARE good here! baalorCalipers baalorSmug"
        )
