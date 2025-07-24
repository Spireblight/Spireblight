from __future__ import annotations
from cache.cache_helpers import RunLinkedListNode

from src.gamedata import FileParser
from typing import TYPE_CHECKING

class RunResponse:
    def __init__(self, parser: FileParser, run_linked_node: RunLinkedListNode = None, *, autorefresh: bool, redirect: bool):
        self.run = parser
        self.linked_runs = run_linked_node
        self.autorefresh = autorefresh
        self.redirect = redirect
