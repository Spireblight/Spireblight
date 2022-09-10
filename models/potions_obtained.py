#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS potionsObtained (
        runId TEXT,
        potionNum INTEGER,
        floor INTEGER,
        key TEXT,
        PRIMARY KEY (runId, potionNum)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    potionNum = 0
    for potion in fjson["potions_obtained"]:
        potionNum = potionNum + 1
        connection.execute(f"""
        INSERT OR IGNORE INTO potionsObtained (
            runId,
            potionNum,
            floor,
            key
        ) VALUES (
            "{fjson["play_id"]}",
            {potionNum},
            {potion["floor"]},
            "{potion["key"]}"
        );
        """)