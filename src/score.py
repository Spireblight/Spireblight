from __future__ import annotations

from typing import TYPE_CHECKING

from collections import Counter

from src.nameinternal import get, ScoreBonus

if TYPE_CHECKING:
    from src.save import Savefile

class Score:
    def __init__(self, name: str = "", count: int = 0, score: int = 0, should_show: bool = False):
        self.score_bonus = score
        self.should_show = should_show            
        self._format_string = ""
        if name:
            data: ScoreBonus = get(name)
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
    score = 0
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
            get_champions_bonus(save),
            get_bosses_slain_bonus(save),
            get_perfect_bosses_bonus(save),
            get_overkill_bonus(save),
            get_combo_bonus(save)
        ])
        score = round(bonuses_total * 0.05 * save.ascension_level)
    return Score("Ascension", save.ascension_level, score, should_show=save.ascension_level > 0)

def get_floors_climbed_bonus(save: Savefile) -> Score:
    """Get 5 points for each floor climbed."""
    return Score("Floors Climbed", save.current_floor, 5 * (save.current_floor), should_show=True)

def get_enemies_killed_bonus(save: Savefile) -> Score:
    """Get 2 points for each monster defeated."""
    return Score("Enemies Killed", save.monsters_killed, 2 * save.monsters_killed, should_show=True)

def get_act1_elites_killed_bonus(save: Savefile) -> Score:
    """Get 10 points for each Act 1 elite killed."""
    return Score("Exordium Elites Killed", save.act1_elites_killed, 10 * save.act1_elites_killed, should_show=True)

def get_act2_elites_killed_bonus(save: Savefile) -> Score:
    """Get 20 points for each Act 2 elite killed."""
    return Score("City Elites Killed", save.act2_elites_killed, 20 * save.act2_elites_killed, should_show=save.act_num >= 2)

def get_act3_elites_killed_bonus(save: Savefile) -> Score:
    """Get 30 points for each Act 3 elite killed."""
    return Score("Beyond Elites Killed", save.act3_elites_killed, 30 * save.act3_elites_killed, should_show=save.act_num >= 3)

def get_champions_bonus(save: Savefile) -> Score:
    """Get 25 points for each elite perfected."""
    return Score("Champion", save.perfect_elites, 25 * save.perfect_elites)

def get_bosses_slain_bonus(save: Savefile) -> Score:
    """Get 25 points for each boss killed."""
    boss_nodes = sum(1 for node in save.path if node.room_type == "Boss")
    match boss_nodes:
        case 0:
            score = 0
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
        case _:
            score = 750
    return Score("Bosses Slain", boss_nodes, score, should_show=True)

def get_perfect_bosses_bonus(save: Savefile) -> Score:
    """Get 50 points for each boss perfected, if 3 or more return 200."""
    if save.perfect_bosses >= 3:
        bonus = Score("Beyond Perfect", score=200)
    else:
        bonus = Score("Perfect", save.perfect_bosses, score=50 * save.perfect_bosses)
    return bonus

def get_collector_bonus(save: Savefile) -> Score:
    """Get 25 points for each non-starter card with 4 copies."""
    card_dict = Counter(save.deck_card_ids)
    nonstarter_cards_count = sum(1 for key, value in card_dict.items() if value >= 4 and get(key).rarity != "Basic")
    return Score("Collector", nonstarter_cards_count, 25 * nonstarter_cards_count) 

def get_deck_bonus(save: Savefile) -> Score:
    """Get points depending on how big the deck is."""
    size = len(list(save.cards))
    if size >= 50:
        bonus = Score("Encyclopedian", score=50)
    elif size >= 35:
        bonus = Score("Librarian", score=25)
    else:
        bonus = Score()
    return bonus

def get_overkill_bonus(save: Savefile) -> Score:
    """Deal 99 damage with a single attack."""
    score = 0
    if save.has_overkill:
        score = 25
    return Score("Overkill", score=score)

def get_mystery_machine_bonus(save: Savefile) -> Score:
    """Traveled to 15+ ? rooms."""
    score = 0
    if save.mystery_machine_counter >= 15:
        score = 25
    return Score("Mystery Machine", score=score)

def get_shiny_bonus(save: Savefile) -> Score:
    """Have 25 or more Relics."""
    score = 0
    if len(list(save.relics)) >= 25:
        score = 50
    return Score("Shiny", score=score)

def get_max_hp_bonus(save: Savefile) -> Score:
    """Get points based on how much max HP gained, ignores Ascension 14 penalty."""
    bonus = Score()
    max_hp_dict = {
        "Ironclad": 80,
        "Silent": 70,
        "Defect": 75,
        "Watcher": 72
    }

    if save.character in max_hp_dict:
        max_hp_gain = save.max_health - max_hp_dict[save.character]
        if max_hp_gain >= 30:
            bonus = Score("Stuffed", score=50)
        elif max_hp_gain >= 15:
            bonus = Score("Well Fed", score=25)
    return bonus

def get_gold_bonus(save: Savefile) -> Score:
    """Get points based on how much accrued gold."""
    if save.total_gold_gained >= 3000:
        bonus = Score("I Like Gold", score=75)
    elif save.total_gold_gained >= 2000:
        bonus = Score("Raining Money", score=50)
    elif save.total_gold_gained >= 1000:
        bonus = Score("Money Money", score=25)
    else:
        bonus = Score()
    return bonus

def get_combo_bonus(save: Savefile) -> Score:
    """Play 20 cards in a single turn."""
    score = 0
    if save.has_combo:
        score = 25
    return Score("Combo", score=score)

def get_curses_bonus(save: Savefile) -> Score:
    """Your deck contains 5 curses."""
    score = 0
    curses = [card for card in save.deck_card_ids if get(card).color == "Curse"]
    if len(curses) >= 5:
        score = 100
    return Score("Curses", score=score)

def get_poopy_bonus(save: Savefile) -> Score:
    """Possess Spirit Poop."""
    score = 0
    relics = [relic.name for relic in save.relics]
    if "Spirit Poop" in relics:
        score = -1
    return Score("Poopy", score=score)
