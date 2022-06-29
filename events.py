from __future__ import annotations

from typing import Callable, Coroutine
import inspect

from logger import logger

EVENTS: dict[str, EventListener] = {}

class EventListener:
    def __init__(self, name: str):
        self.name = name
        self._callback: Callable | Coroutine | None = None
        self.is_async = True

    def __call__(self, func: Coroutine):
        if self._callback is not None:
            raise ValueError(f"Listener {self.name} is already set-up")
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"Listener {self.name} must receive a coroutine")
        self._callback = func
        return self

    # note: this does not handle any of the scheduling machinery
    # it is meant to be passed as-is to the relevant event schedulers
    async def invoke(self, /, *args, **kwargs):
        if self._callback is None:
            raise RuntimeError(f"Listener {self.name} has not been set-up yet.")
        if self.is_async:
            return await self._callback(*args, **kwargs)
        return self._callback(*args, **kwargs)

    @classmethod
    def from_callable(cls, name: str, func: Callable | Coroutine):
        self = cls(name)
        if inspect.iscoroutinefunction(func):
            self._callback = func
        elif callable(func):
            self._callback = func
            self.is_async = False
        else:
            raise TypeError(f"from_callable({name!r}, obj): obj is not callable")
        return self

    @property
    def callback(self) -> Coroutine | None:
        if self.is_async:
            return self._callback
        return None

    @property
    def function(self) -> Callable | None:
        if not self.is_async:
            return self._callback
        return None

def get(name: str) -> EventListener | None:
    return EVENTS.get(name)
