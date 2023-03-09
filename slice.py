import xml.etree.ElementTree
import json
import os

from aiohttp.web import Request, Response

parsed_data = {}
curses = {}
items = {}

class CurrentRun:
    def __init__(self, data):
        self._data = data["d"]

    @property
    def curses(self):
        ret = []
        for curse in self._data["m"]:
            ret.append(f"{curse} [{curses[curse]['tier']}] ({curses[curse]['description']})")

        return f"We are running Classic on {self._data['c']} with {'; '.join(ret)}."

    @property
    def items(self):
        ret = []
        for item in self._data["e"]:
            ret.append(f"{item} [{items[item]['tier']}] ({items[item]['description']})")

        if ret:
            return f"The unequipped items are {'; '.join(ret)}."
        return "We have no unequipped items."

def get_current_run():
    if "classic" in parsed_data:
        return CurrentRun(parsed_data["classic"])

try:
    from webpage import router
    from utils import get_req_data

    @router.post("/sync/slice")
    async def receive_slice(req: Request):
        data = await get_req_data(req, "data")
        with open(os.path.join("data", "slice-data"), "w") as f:
            f.write(data[0])
        populate(os.path.join("data", "slice-data"))
        return Response()

except ModuleNotFoundError: # running as stand-alone module
    pass

def populate(path=None) -> bool:
    """Decode the savefile and populate the variables.

    Return True if decoding was successful, False otherwise."""

    if path is None:
        try:
            user = os.environ["USERPROFILE"]
        except KeyError:
            return False

        path = os.path.join(user, ".prefs", "slice-and-dice-2")

    try:
        decoded = xml.etree.ElementTree.parse(path)
    except OSError:
        return False

    root = decoded.getroot()

    for child in root:
        key = child.attrib["key"]
        data = child.text
        if key == "run_history":
            # TODO: non-standard JSON; keys and values aren't quoted
            continue
        parsed_data[key] = json.loads(data)

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
