#!/usr/bin/env python3

import json

idToName = {
    "Boot": "The Boot",
    "Cables": "Gold Plated Cables",
    "DataDisk": "Data Disk",
    "Dodecahedron": "Runic Dodecahedron",
    "Frozen Egg 2": "Frozen Egg",
    "Lee's Waffle": "Waffle",
    "Molten Egg 2": "Molten Egg",
    "NeowsBlessing": "Neows Lament",
    "Self Forming Clay": "Self-Forming Clay",
    "Snake Skull": "Snecko Skull",
    "Toxic Egg 2": "Toxic Egg",
    "Yang": "Duality",
}

def to_modern(card):
    cardParts = card.split("+")

    cardName = cardParts[0]
    if cardName in idToName:
        cardName = idToName[cardName]
    
    if len(cardParts) == 2:
        cardName = cardName + "+" + cardParts[1]

    return cardName

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS relics (
        runId TEXT,
        relicNum INTEGER,
        relic TEXT,
        floorObtained INTEGER,
        stats TEXT,
        PRIMARY KEY (runId, relicNum)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    relicStats = {} if "relic_stats" not in fjson else fjson["relic_stats"]
    relicNum = 0
    for relic in fjson["relics"]:
        relicNum = relicNum + 1
        floorObtained = 0
        for relicFloor in fjson["relics_obtained"]:
            if relic == relicFloor["key"]:
                floorObtained = relicFloor["floor"]

        connection.execute(f"""
        INSERT OR IGNORE INTO relics (
            runId,
            relicNum,
            relic,
            floorObtained,
            stats
        ) VALUES (
            "{fjson["play_id"]}",
            {relicNum},
            "{to_modern(relic)}",
            {floorObtained},
            json('{"{}" if relic not in relicStats else json.dumps(relicStats[relic])}')
        );
        """)