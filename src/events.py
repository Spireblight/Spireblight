from __future__ import annotations

from typing import Callable, Coroutine
import inspect

EVENTS: dict[str, list[EventListener]] = {}

class EventListener:
    def __init__(self, name: str, func: Coroutine):
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"Listener {self.name} must receive a coroutine")
        self.name = name
        self.callback = func

    # note: this does not handle any of the scheduling machinery
    # it is meant to be passed as-is to the relevant event schedulers
    async def invoke(self, args, kwargs):
        return await self.callback(*args, **kwargs)

def get(name: str) -> list[EventListener]:
    return EVENTS.get(name, [])

def add_listener(name: str):
    def inner(func: Coroutine):
        listener = EventListener(name, func)
        if name not in EVENTS:
            EVENTS[name] = []
        EVENTS[name].append(listener)
        return func
    return inner

async def invoke(name: str, /, *args, **kwargs) -> list:
    rets = []
    for listener in get(name):
        rets.append(await listener.invoke(args, kwargs))
    return rets
