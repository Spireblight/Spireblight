from trie import Trie
from utils import edit_distance

ACTIVEMODS_KEY = "activemods:active_mods"

class ActiveMods():
    def __init__(self, data):
        self._activemods = {}
        self._trie = Trie()

        if ACTIVEMODS_KEY in data:
            for x in data[ACTIVEMODS_KEY]:
                m = ActiveMod(x)
                self._activemods[m.normalized_name] = m
                self._trie.insert(m.normalized_name)

    @property
    def all_mods(self):
        return self._activemods.values()

    def normalize(self, string):
        return string.lower().replace(" ", "")

    def edit_distance_ratio(self, distance, word):
        return (len(word)-distance)/len(word)
    
    def find_mod(self, mod_name):
        mod_name = self.normalize(mod_name)

        # it's pointless...
        if len(mod_name) == 0:
            return None
        
        # easy, they entered the name correctly
        if mod_name in self._activemods:
            return self._activemods[mod_name]
        
        names = self._trie.search(mod_name)

        # still pretty easy...
        if len(names) == 1:
            return self._activemods[names[0]]

        # getting annoying...
        if len(names) < 3:
            # sort by edit distance
            distances = sorted([(name, edit_distance(name, mod_name)) for name in names], key=lambda x: x[1])

            # and check the first one
            name, distance = distances[0]
            # close enough, i guess
            if self.edit_distance_ratio(distance, name) > 0.9:
                return self._activemods[potential[0]]
            
        # nope, we give up
        return None
        

class ActiveMod():
    def __init__(self, data: dict):
        """
        See https://github.com/drummeur/activemods/blob/master/schema.json for the dict schema.
        A few of the fields are renamed to avoid python keywords
        """

        if "id" in data:
            self.modid = data["id"]
        else:
            self.modid = ""
        
        if "name" in data:
            self.name = data["name"].strip()
        else:
            self.name = ""
            
        if "description" in data:
            self.description = data["description"]
        else:
            self.description = ""

        if "authors" in data:
            self.authors = data["authors"]
        else:
            self.authors = []

        if "credits" in data:
            self.mod_credits = data["credits"]
        else:
            self.mod_credits = ""

        if "mod_version" in data:
            self.mod_version = data["mod_version"]
        else:
            self.mod_version = {
                "version": "unknown",
                "major": 0,
                "minor": 0,
                "patch": 0
            }

        if "dependencies" in data:
            self.dependencies = data["dependencies"]
        else:
            self.dependencies = []

        if "optional_dependencies" in data:
            self.optional_dependencies = data["optional_dependencies"]
        else:
            self.optional_dependencies = []

        if "mod_url" in data:
            self._mod_url = data["mod_url"]
            #self._mod_url = data["mod_url"]
        else:
            self._mod_url = ""
            
        if "is_steam_workshop_mod" in data:
            self.is_steam_workshop_mod = data["is_steam_workshop_mod"]
        else:
            self.is_steam_workshop_mod = None

    def __str__(self):
        return self.name
        
    @property
    def mod_url(self) -> str:
        # infomod is hardcoded until custom URLs are implemented into ActiveMods
        if self.modid == "ojb_infomod2":
            return "https://casey-c.github.io/slaythespire/infomod.html"
        else:
            return self._mod_url

    @property
    def version(self) -> str:
        return self.mod_version["version"]

    def _try_get_int_version(self, field: str) -> int:
        result = 0
        
        try:
            result = int(self.mod_version[version])
        except (ValueError, KeyError):
            pass
        
        return result
    
    @property
    def major_version(self) -> int:
        return self._try_get_int_version("major")

    @property
    def minor_version(self):
        return self._try_get_int_version("minor")

    @property
    def patch_version(self):
        return self._try_get_int_version("patch")

    @property
    def authors_formatted(self):
        if len(self.authors) == 0:
            authors = "An unknown STS modder"
        elif len(self.authors) == 1:
            authors = self.authors[0]
        else:
            authors = ", ".join(self.authors[:-1])
            authors += f", and {self.authors[-1]}"

        return authors

    @property
    def description_formatted(self):
        if len(self.description) == 0:
            desc = "This mod is indescribable (because it has no description...)"
        else:
            desc = self.description

        return desc

    @property
    def normalized_name(self):
        return self.name.lower().replace(" ", "")
