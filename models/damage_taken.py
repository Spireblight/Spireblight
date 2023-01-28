#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS damageTaken (
        runId TEXT,
        floor INTEGER,
        damage INTEGER,
        turns INTEGER,
        enemies TEXT,
        PRIMARY KEY (runId, floor)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    for damage in fjson["damage_taken"]:
        connection.execute(f"""
        INSERT OR IGNORE INTO damageTaken (
            runId,
            floor,
            damage,
            turns,
            enemies
        ) VALUES (
            "{fjson["play_id"]}",
            {damage["floor"]},
            {damage["damage"]},
            {damage["turns"]},
            "{damage["enemies"]}"
        );
        """)