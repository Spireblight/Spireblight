from collections import Counter, namedtuple

from nameinternal import get_card_metadata, get_score_bonus
from save import Savefile

class Score:
    def __init__(self, name: str, count: int, should_show: bool):
        self.score_bonus = 0
        self.should_show = should_show or False # use this to override showing if the score > 0
        if name:
            data = get_score_bonus(name)
            if data:
                self._name = data.name
                self._description = data.description
                self._format_string = data.format_string.format(count = count)
            else:
                raise ValueError("Invalid score bonus name")

    @property
    def full_display(self) -> str:
        return f'{self._format_string}: {self.score_bonus}'


def get_ascension_score_bonus(save: Savefile) -> Score:
    asc_bonus = Score("Ascension", save.ascension_level, should_show=save.ascension_level > 0)
    if save.ascension_level > 0:
        # Only applies to the score from the following bonuses:
        # Floors Climbed
        # Enemies Killed
        # Elites Killed
        # Bosses Slain
        # Champion
        # Perfect
        # Beyond Perfect
        # Overkill
        # C-c-c-combo.
        bonuses_total = sum(bonus.score_bonus for bonus in [
            get_floors_climbed_bonus(save),
            get_enemies_killed_bonus(save),
            get_act1_elites_killed_bonus(save),
            get_act2_elites_killed_bonus(save),
            get_act3_elites_killed_bonus(save),
            get_bosses_slain_bonus(save),
            get_champions_bonus(save),
            get_overkill_bonus(save),
            get_combo_bonus(save)
        ])
        asc_bonus.score_bonus = round(bonuses_total * 0.05 * save.ascension_level)
    return asc_bonus

def get_floors_climbed_bonus(save: Savefile) -> Score:
    """Get 5 points for each floor climbed."""
    bonus = Score("Floors Climbed", save.current_floor - 1, should_show=True)
    bonus.score_bonus = 5 * (save.current_floor - 1) # will need to do more testing if this is current-1 or just current
    return bonus

def get_enemies_killed_bonus(save: Savefile) -> Score:
    """Get 2 points for each monster defeated."""
    bonus = Score("Enemies Killed", save.monsters_killed, should_show=True)
    bonus.score_bonus = 2 * save.monsters_killed
    return bonus

def get_act1_elites_killed_bonus(save: Savefile) -> Score:
    """Get 10 points for each Act 1 elite killed."""
    bonus = Score("Exordium Elites Killed", save.act1_elites_killed, should_show=True)
    bonus.score_bonus = 10 * save.act1_elites_killed
    return bonus

def get_act2_elites_killed_bonus(save: Savefile) -> Score:
    """Get 20 points for each Act 2 elite killed."""
    bonus = Score("City Elites Killed", save.act2_elites_killed, should_show=save.act_num >= 2)
    bonus.score_bonus = 20 * save.act2_elites_killed
    return bonus

def get_act3_elites_killed_bonus(save: Savefile) -> Score:
    """Get 30 points for each Act 3 elite killed."""
    bonus = Score("Beyond Elites Killed", save.act3_elites_killed, should_show=save.act_num >= 3)
    bonus.score_bonus = 30 * save.act3_elites_killed
    return bonus

def get_champions_bonus(save: Savefile) -> Score:
    """Get 25 points for each elite perfected."""
    bonus = Score("Champion", save.perfect_elites)
    bonus.score_bonus = 25 * save.perfect_elites
    return bonus

def get_bosses_slain_bonus(save: Savefile) -> Score:
    """Get 25 points for each boss killed."""
    boss_nodes = sum(1 for node in save.path if node.room_type == "Boss")
    bonus = Score("Bosses Slain", boss_nodes, should_show=True)
    score = 0
    match boss_nodes:
        case 1:
            score = 50
        case 2:
            score = 150
        case 3:
            score = 300
        case 4:
            score = 500
        case 5:
            score = 750
    bonus.score_bonus = score
    return bonus

def get_perfect_bosses_bonus(save: Savefile) -> Score:
    """Get 50 points for each boss perfected, if 3 or more return 200."""
    score = 0
    if save.perfect_bosses >= 3:
        bonus = Score("Beyond Perfect")
        score = 200
    else:
        bonus = Score("Perfect", save.perfect_bosses)
        score = 50 * save.perfect_bosses

    bonus.score_bonus = score
    return bonus

def get_collector_bonus(save: Savefile) -> Score:
    """Get 25 points for each non-starter card with 4 copies."""
    card_dict = dict(Counter(save.cards))
    nonstarter_cards_count = sum(1 for key, value in card_dict.items() if value >= 4 and get_card_metadata(key)["RARITY"] != "Starter")
    bonus = Score("Collector", nonstarter_cards_count)    
    bonus.score_bonus = 25 * nonstarter_cards_count
    return bonus

def get_deck_bonus(save: Savefile) -> Score:
    """Get points depending on how big the deck is."""
    size = len(list(save.cards))
    if size >= 50:
        bonus = Score("Encyclopedian")
        bonus.score_bonus = 50
    elif size >= 35:
        bonus = Score("Librarian")
        bonus.score_bonus = 25
    else:
        bonus = Score()
    return bonus

def get_overkill_bonus(save: Savefile) -> Score:
    """Deal 99 damage with a single attack."""
    bonus = Score("Overkill")
    score = 0
    if save.has_overkill:
        score = 25
    bonus.score_bonus = score
    return bonus

def get_mystery_machine_bonus(save: Savefile) -> Score:
    """Traveled to 15+ ? rooms."""
    bonus = Score("Mystery Machine")
    score = 0
    if save.mystery_machine_counter >= 15:
        score = 25
    bonus.score_bonus = score
    return bonus

def get_shiny_bonus(save: Savefile) -> Score:
    """Have 25 or more Relics."""
    bonus = Score("Shiny")
    score = 0
    if len(list(save.relics)) >= 25:
        score = 50
    bonus.score_bonus = score
    return bonus

def get_max_hp_bonus(save: Savefile) -> Score:
    """Get points based on how much max HP gained"""
    max_hp_tuple = namedtuple("MaxHP", ["base_max_hp", "asc_max_hp_loss"])
    max_hp_dict = {
        "Ironclad": max_hp_tuple(80, 5),
        "Silent": max_hp_tuple(70, 4),
        "Defect": max_hp_tuple(75, 4),
        "Watcher": max_hp_tuple(72, 4)
    }

    character_starting_max_hp = max_hp_dict[save.character].base_max_hp
    if save.ascension_level >= 14:
        character_starting_max_hp -= max_hp_dict[save.character].asc_max_hp_loss

    max_hp_gain = save.max_health - character_starting_max_hp
    if max_hp_gain >= 30:
        bonus = Score("Stuffed")
        bonus.score_bonus = 50
    elif max_hp_gain >= 15:
        bonus = Score("Well Fed")
        bonus.score_bonus = 25
    else:
        bonus = Score()
    return bonus

def get_gold_bonus(save: Savefile) -> Score:
    """Get points based on how much accrued gold."""
    if save.total_gold_gained >= 3000:
        bonus = Score("I Like Gold")
        bonus.score_bonus = 75
    elif save.total_gold_gained >= 2000:
        bonus = Score("Raining Money")
        bonus.score_bonus = 50
    elif save.total_gold_gained >= 1000:
        bonus = Score("Money Money")
        bonus.score_bonus = 25
    else:
        bonus = Score()
    return bonus

def get_combo_bonus(save: Savefile) -> Score:
    """Play 20 cards in a single turn."""
    bonus = Score("Combo")
    score = 0
    if save.has_combo:
        score = 25
    bonus.score_bonus = score
    return bonus

def get_pauper_bonus(save: Savefile) -> Score:
    """Have 0 rare cards."""
    bonus = Score("Pauper")
    score = 0
    rare_cards = [card for card in save.cards if get_card_metadata(card)["RARITY"] == "Rare"]
    if not rare_cards:
        score = 50
    bonus.score_bonus = score
    return bonus

def get_curses_bonus(save: Savefile) -> Score:
    """Your deck contains 5 curses."""
    bonus = Score("Curses")
    score = 0
    curses = [card for card in save.cards if get_card_metadata(card)["CHARACTER"] == "Curse"]
    if len(curses) >= 5:
        score = 100
    bonus.score_bonus = score
    return bonus

def get_highlander_bonus(save: Savefile) -> Score:
    """Your deck contains no duplicates."""
    bonus = Score("Highlander")
    score = 0
    card_dict = dict(Counter(save.cards))
    multiple_copies = [key for key, value in card_dict.items() if value > 1 and get_card_metadata(key)["RARITY"] != "Starter"]
    if not multiple_copies:
        score = 100
    bonus.score_bonus = score
    return bonus

def get_poopy_bonus(save: Savefile) -> Score:
    """Possess Spirit Poop."""
    bonus = Score("Poopy")
    score = 0
    relics = [relic.name for relic in save.relics]
    if "Spirit Poop" in relics:
        score = -1
    bonus.score_bonus = score
    return bonus
