from __future__ import annotations
from cache.cache_helpers import RunLinkedListNode

from gamedata import FileParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runs import RunParser

class RunResponse:
    def __init__(self, parser: FileParser, run_linked_node: RunLinkedListNode = None, *, autorefresh: bool, redirect: bool, extend_base: bool):
        self.run = parser
        self.linked_runs = run_linked_node
        self.autorefresh = autorefresh
        self.redirect = redirect
        self.extend_base = extend_base
