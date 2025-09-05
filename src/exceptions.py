from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src._cfgmap import _ConfigMapping

class InvalidConfigType(TypeError):
    def __init__(self, inst: _ConfigMapping, key: str, expected: type):
        """Raised when the user config has an invalid value type.

        :param inst: The class which is handling the assignment.
        :type inst: _ConfigMapping
        :param key: The key with an invalid type.
        :type key: str
        :param expected: Which type we expect to receive.
        :type expected: type
        """
        if (n := inst.__class__.__name__) != "Config":
            if n.startswith("_"):
                n = f"<{n.lstrip('_')}>"
            else:
                n = n.lower()
            key = f"{n}.{key}"
        super().__init__(f"Key {key} is not the right type (should be {expected.__name__} instead).")
