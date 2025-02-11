

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

        # temporarily making mod_url a property to take care of the InfoMod url
        # make sure to change this back to "mod_url" when fixing ActiveMods, too

        if "steam_workshop_url" in data:
            self._mod_url = data["steam_workshop_url"]
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
        if self.modid == "obj_infomod2":
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
