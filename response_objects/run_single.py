from __future__ import annotations
from cache.cache_helpers import RunLinkedListNode

from gamedata import FileParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runs import RunParser

class RunResponse:
    def __init__(self, parser: FileParser, prev_char: RunParser = None, next_char: RunParser = None, *, autorefresh: bool, redirect: bool):
        self.run = parser
        if prev_char is not None or next_char is not None:
            self.characters = RunLinkedListNode()
            self.characters.prev_char = prev_char
            self.characters.next_char = next_char
        self.autorefresh = autorefresh
        self.redirect = redirect
