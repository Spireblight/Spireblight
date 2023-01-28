#!/usr/bin/env python3

import apsw
import glob
import json

import boss_relics
import campfire_choices
import card_choices
import current_hp_per_floor
import current_gold_per_floor
import damage_taken
import deck_cards
import event_choices
import item_purchases
import item_purges
import max_hp_per_floor
import neow_bonus
import path_taken
import potions_obtained
import relics
import runs

pkgs = [
    boss_relics, 
    campfire_choices,
    card_choices,
    current_hp_per_floor,
    current_gold_per_floor,
    damage_taken,
    deck_cards,
    event_choices,
    item_purchases,
    item_purges,
    max_hp_per_floor,
    neow_bonus,
    path_taken,
    potions_obtained,
    relics,
    runs
]

def create_or_open(dbName):
    return apsw.Connection(dbName)

def create_tables_if_not_exists(connection):
    for pkg in pkgs:
        pkg.create(connection)

def import_files_if_not_imported(connection, pathBase):
    for filename in glob.iglob(pathBase + '/**/*.run', recursive=True):
        import_file_if_not_imported(connection, filename)


def import_file_if_not_imported(connection, filename):
    with open(filename) as file:
            fraw = file.read()
            fjson = json.loads(fraw)
            for pkg in pkgs:
                pkg.insert(connection, fjson)