import xml.etree.ElementTree
import pickle
import json
import os
import re

from aiohttp.web import Request, Response

parsed_data = {}

_NULL = 1 << 16
_colors = {"o": "Orange", "y": "Yellow", "g": "Grey", "b": "Blue", "r": "Red", "n": "Green"}
_gen_re = re.compile(r"^[oygbrn]\d\.[0-9a-f]{3}$")

class Hero:
    def __init__(self, word: str):
        self.name, *rest = word.split("~")
        self.color = ""
        self.items = []
        self.dead = False
        if _gen_re.match(self.name): # generated hero. otherwise idfk
            self.color = _colors[self.name[0]]
        for x in rest:
            if x == "D":
                self.dead = True
            else:
                self.items.append(x)

    def __repr__(self) -> str:
        final = [self.name]
        if self.color:
            final.append(f"({self.color})")
        if self.dead:
            final.append("[Died last fight]")
        if self.items:
            final.append(f"Equipped: {', '.join(self.items)}")

        return " ".join(final)

class CurrentRun:
    def __init__(self, data):
        self._data = data

    @property
    def difficulty(self) -> str:
        return self._data["d"]["c"]

    @property
    def modifiers(self) -> list[str]:
        return self._data["d"]["m"]

    @property
    def items(self) -> list[str]:
        return self._data["d"]["p"]["e"]

    @property
    def heroes(self) -> list[Hero]:
        return [Hero(x) for x in self._data["d"]["p"]["h"]]

    @property
    def preset(self) -> str:
        return self._data["d"]["p"]["plt"]

def get_runs() -> dict[str, CurrentRun]:
    d = {}
    for key, data in parsed_data.items():
        if key in ("stats", "settings", "run_history"):
            continue
        d[key] = CurrentRun(data)
    return d

try:
    from src.webpage import router
    from src.events import add_listener
    from src.utils import get_req_data
except ModuleNotFoundError: # running as stand-alone module
    pass
else:
    @router.post("/sync/slice")
    async def receive_slice(req: Request):
        data = await get_req_data(req, "data")
        with open(os.path.join("data", "slice-data"), "w") as f:
            f.write(data[0])
        populate(os.path.join("data", "slice-data"))
        # This is to allow the client to display curses
        # We don't have easy access to the actual content currently
        # So it's disabled for the time being
        #run = get_current_run()
        #if run is not None:
        #    return Response(body=pickle.dumps(run.curses))
        return Response()

    @add_listener("setup_init")
    async def _load():
        load()

def decode(s: str) -> str:
    return "".join(
        chr(ord(c) - 50 + i % 50)
        for i, c in enumerate(s)
    )

def deserialize(s: str) -> dict:
    return {} # TODO

def populate(path=None) -> bool:
    """Decode the savefile and populate the variables.

    Return True if decoding was successful, False otherwise."""

    if path is None:
        try:
            user = os.environ["USERPROFILE"]
        except KeyError:
            return False

        path = os.path.join(user, ".prefs", "slice-and-dice-3")

    try:
        decoded = xml.etree.ElementTree.parse(path)
    except OSError:
        return False

    root = decoded.getroot()

    for child in root:
        key = child.attrib["key"]
        data = decode(child.text)
        fn = json.loads
        if key == "run_history":
            fn = deserialize
        parsed_data[key] = fn(data)

    return True

def load():
    populate(os.path.join("data", "slice-data"))
    return # Temporary (ha! ha!) fix until we have proper info again
    for file, var in (("curses", curses), ("items", items)):
        with open(f"{file}.txt") as f:
            cont = False
            for line in f.readlines():
                line = line.replace("\t\t", "\t")[:-1] # remove trailing newline
                if cont:
                    if line.endswith('"'):
                        line = line[:-1]
                        cont = False
                    desc = f"{desc} {line}"
                else:
                    name, tier, desc = line.split("\t")
                    if desc.startswith('"'):
                        desc = desc[1:]
                        cont = True
                if not cont:
                    var[name] = {"tier": tier, "description": desc}
