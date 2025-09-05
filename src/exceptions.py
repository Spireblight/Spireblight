from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src._cfgmap import _ConfigMapping

class InvalidConfigType(TypeError):
    def __init__(self, inst: _ConfigMapping, key: str, expected: type):
        if (n := inst.__class__.__name__) != "Config":
            if n.startswith("_"):
                n = f"<{n.lstrip("_")}>"
            else:
                n = n.lower()
            key = f"{n}.{key}"
        super().__init__(f"Key {key} is not the right type (should be {expected.__name__} instead).")
