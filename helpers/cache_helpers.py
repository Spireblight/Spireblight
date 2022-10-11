class Statistic:
    def __init__(self, set_default: bool = False):
        self.all_character_count = None
        self.ironclad_count = None
        self.silent_count = None
        self.defect_count = None
        self.watcher_count = None
        if set_default:
            self.all_character_count = 0
            self.ironclad_count = 0
            self.silent_count = 0
            self.defect_count = 0
            self.watcher_count = 0

    @property
    def is_loaded(self):
        return self.all_character_count is not None and self.ironclad_count is not None and self.silent_count is not None and self.defect_count is not None and self.watcher_count is not None 

class RunStats:
    def __init__(self):
        self.wins = Statistic(True)
        self.losses = Statistic(True)
        self.streaks = Statistic()

    def add_win(self, char: str):
        self._increment_stat(self.wins, char)

    def add_loss(self, char: str):
        self._increment_stat(self.losses, char)

    def _increment_stat(self, stat: Statistic, char: str):
        match char:
            case "Ironclad":
                stat.ironclad_count += 1
            case "Silent":
                stat.silent_count += 1
            case "Defect":
                stat.defect_count += 1
            case "Watcher":
                stat.watcher_count += 1
        stat.all_character_count += 1
