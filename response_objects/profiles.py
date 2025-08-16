from src.sts_profile import Profile


class ProfilesResponse:
    def __init__(self, profiles: list[Profile]):
        self.profiles = profiles
