from nameinternal import get_card_metadata, get_score_bonus
from collections import Counter, namedtuple
from save import Savefile

class ScoreBonus():
    def __init__(self, name: str):
        self.name = ""
        self.format_string = ""
        self.description = ""
        self.score_bonus = 0

        if name:
            data = get_score_bonus(name)
            self.name = data["NAME"]
            if data["DESCRIPTIONS"]:
                self.description = data["DESCRIPTIONS"][0]

    def get_format_string(self) -> str:
        if self.format_string:
            return self.format_string
        else:
            return f'{self.name}: {self.score_bonus}'

def get_ascension_score_bonus(save: Savefile) -> ScoreBonus:
    bonus = ScoreBonus("Ascension")
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
        bonuses_total = 0
        bonuses_total += get_floors_climbed_bonus(save).score_bonus
        bonuses_total += get_enemies_killed_bonus(save).score_bonus
        bonuses_total += get_act1_elites_killed_bonus(save).score_bonus
        bonuses_total += get_act2_elites_killed_bonus(save).score_bonus
        bonuses_total += get_act3_elites_killed_bonus(save).score_bonus
        bonuses_total += get_bosses_slain_bonus(save).score_bonus
        bonuses_total += get_champions_bonus(save).score_bonus
        bonuses_total += get_perfect_bosses_bonus(save).score_bonus
        bonuses_total += get_overkill_bonus(save).score_bonus
        bonuses_total += get_combo_bonus(save).score_bonus
        score = round(bonuses_total * 0.05 * save.ascension_level)
        bonus.format_string = f'Ascension ({save.ascension_level}): {score}'
        bonus.score_bonus = score
    return bonus

def get_floors_climbed_bonus(save: Savefile) -> ScoreBonus:
    bonus = ScoreBonus()
    bonus.name = "Floors Climbed"
    bonus.description = "Five points for each Floor you reached"
    score = 5 * (save.current_floor - 1) # will need to do more testing if this is current-1 or just current
    bonus.format_string = f'Floors Climbed ({save.current_floor - 1}): {score}'
    bonus.score_bonus = score
    return bonus

def get_enemies_killed_bonus(save: Savefile) -> ScoreBonus:
    bonus = ScoreBonus()
    bonus.name = "Enemies Killed"
    bonus.description = "Two points for each Monster encounter defeated"
    score = 2 * save.monsters_killed
    bonus.format_string = f'Enemies Slain ({save.monsters_killed}): {score}'
    bonus.score_bonus = score
    return bonus

def get_act1_elites_killed_bonus(save: Savefile) -> ScoreBonus:
    """Get 10 points for each elite killed."""
    bonus = ScoreBonus("Exordium Elites Killed")
    score = 10 * save.act1_elites_killed
    bonus.format_string = f'Exordium Elites Killed ({save.act1_elites_killed}): {score}'
    bonus.score_bonus = score
    return bonus

def get_act2_elites_killed_bonus(save: Savefile) -> ScoreBonus:
    """Get 20 points for each elite killed."""
    bonus = ScoreBonus("City Elites Killed")
    score = 20 * save.act2_elites_killed
    bonus.format_string = f'City Elites Killed ({save.act2_elites_killed}): {score}'
    bonus.score_bonus = score
    return bonus

def get_act3_elites_killed_bonus(save: Savefile) -> ScoreBonus:
    """Get 30 points for each elite killed."""
    bonus = ScoreBonus("Beyond Elites Killed")
    score = 30 * save.act3_elites_killed
    bonus.format_string = f'Beyond Elites Killed ({save.act3_elites_killed}): {score}'
    bonus.score_bonus = score
    return bonus

def get_champions_bonus(save: Savefile) -> ScoreBonus:
    """Get 25 points for each elite perfected."""
    bonus = ScoreBonus("Champion")
    score = 25 * save.perfect_elites
    bonus.format_string = f'Champion ({save.perfect_elites}): {score}'
    bonus.score_bonus = score
    return bonus

def get_bosses_slain_bonus(save: Savefile) -> ScoreBonus:
    """Get 25 points for each boss killed."""
    bonus = ScoreBonus("Bosses Slain")
    boss_nodes = sum(1 for node in save.path if node.room_type == "Boss")
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
    bonus.format_string = f'Bosses Slain ({boss_nodes}): {score}'
    bonus.score_bonus = score
    return bonus

def get_perfect_bosses_bonus(save: Savefile) -> ScoreBonus:
    """Get 50 points for each boss perfected, if 3 or more return 200."""
    if save.perfect_bosses >= 3:
        bonus = ScoreBonus("Beyond Perfect")
        score = 200
        bonus.format_string = f'Beyond Perfect: {score}'
    else:
        bonus = ScoreBonus("Perfect")
        score = 50 * save.perfect_bosses
        bonus.format_string = f'Perfect ({save.perfect_bosses}): {score}'

    bonus.score_bonus = score
    return bonus

def get_collector_bonus(save: Savefile) -> ScoreBonus:
    """Get 25 points for each non-starter card with 4 copies."""
    bonus = ScoreBonus("Collector")
    card_dict = dict(Counter(save.cards))
    nonstarter_cards = [key for key, value in card_dict.items() if value >= 4 and get_card_metadata(key)["RARITY"] != "Starter"]
    score = 25 * len(nonstarter_cards)
    bonus.format_string = f'Collector ({len(nonstarter_cards)}): {score}'
    bonus.score_bonus = score
    return bonus

def get_deck_bonus(save: Savefile) -> ScoreBonus:
    """Get points depending on how big the deck is."""
    size = len(list(save.cards))
    if size >= 50:
        bonus = ScoreBonus("Encyclopedian")
        bonus.score_bonus = 50
    elif size >= 35:
        bonus = ScoreBonus("Librarian")
        bonus.score_bonus = 25
    else:
        bonus = ScoreBonus()
    return bonus

def get_overkill_bonus(save: Savefile) -> ScoreBonus:
    """Deal 99 damage with a single attack."""
    bonus = ScoreBonus("Overkill")
    score = 0
    if save.has_overkill:
        score = 25
    bonus.score_bonus = score
    return bonus

def get_mystery_machine_bonus(save: Savefile) -> ScoreBonus:
    """Traveled to 15+ ? rooms."""
    bonus = ScoreBonus("Mystery Machine")
    score = 0
    if save.mystery_machine_counter >= 15:
        score = 25
    bonus.score_bonus = score
    return bonus

def get_shiny_bonus(save: Savefile) -> ScoreBonus:
    """Have 25 or more Relics."""
    bonus = ScoreBonus("Shiny")
    score = 0
    if len(list(save.relics)) >= 25:
        score = 50
    bonus.score_bonus = score
    return bonus

def get_max_hp_bonus(save: Savefile) -> ScoreBonus:
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
        bonus = ScoreBonus("Stuffed")
        bonus.score_bonus = 50
    elif max_hp_gain >= 15:
        bonus = ScoreBonus("Well Fed")
        bonus.score_bonus = 25
    else:
        bonus = ScoreBonus()
    return bonus

def get_gold_bonus(save: Savefile) -> ScoreBonus:
    """Get points based on how much accrued gold."""
    if save.total_gold_gained >= 3000:
        bonus = ScoreBonus("I Like Gold")
        bonus.score_bonus = 75
    elif save.total_gold_gained >= 2000:
        bonus = ScoreBonus("Raining Money")
        bonus.score_bonus = 50
    elif save.total_gold_gained >= 1000:
        bonus = ScoreBonus("Money Money")
        bonus.score_bonus = 25
    else:
        bonus = ScoreBonus()
    return bonus

def get_combo_bonus(save: Savefile) -> ScoreBonus:
    """Play 20 cards in a single turn."""
    bonus = ScoreBonus("Combo")
    score = 0
    if save.has_combo:
        score = 25
    bonus.score_bonus = score
    return bonus

def get_pauper_bonus(save: Savefile) -> ScoreBonus:
    """Have 0 rare cards."""
    bonus = ScoreBonus("Pauper")
    score = 0
    rare_cards = [card for card in save.cards if get_card_metadata(card)["RARITY"] == "Rare"]
    if not rare_cards:
        score = 50
    bonus.score_bonus = score
    return bonus

def get_curses_bonus(save: Savefile) -> ScoreBonus:
    """Your deck contains 5 curses."""
    bonus = ScoreBonus("Curses")
    score = 0
    curses = [card for card in save.cards if get_card_metadata(card)["CHARACTER"] == "Curse"]
    if len(curses) >= 5:
        score = 100
    bonus.score_bonus = score
    return bonus

def get_highlander_bonus(save: Savefile) -> ScoreBonus:
    """Your deck contains no duplicates."""
    bonus = ScoreBonus("Highlander")
    score = 0
    card_dict = dict(Counter(save.cards))
    multiple_copies = [key for key, value in card_dict.items() if value > 1 and get_card_metadata(key)["RARITY"] != "Starter"]
    if not multiple_copies:
        score = 100
    bonus.score_bonus = score
    return bonus

def get_poopy_bonus(save: Savefile) -> ScoreBonus:
    """Possess Spirit Poop."""
    bonus = ScoreBonus("Poopy")
    score = 0
    relics = [relic.name for relic in save.relics]
    if "Spirit Poop" in relics:
        score = -1
    bonus.score_bonus = score
    return bonus
    