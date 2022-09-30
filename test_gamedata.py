import pytest

from gamedata import FileParser

class TestFileParser:
    def test_plain_init(self):
        empty = FileParser({})
        assert empty.done is False
