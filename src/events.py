"""Lightweight event system to support plug-in modules.

Modules with listeners must be imported for the
listeners to be active.

Any event with `setup` in the name is guaranteed to never
be called more than once (which could be not at all)."""

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
    if "setup" in name: # make sure this only ever gets called once
        EVENTS.pop(name, None)
    return rets
