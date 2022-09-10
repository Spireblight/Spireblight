#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS campfireChoices (
        runId TEXT,
        floor INTEGER,
        key TEXT,
        data TEXT,
        PRIMARY KEY (runId, floor, key)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    for choice in fjson["campfire_choices"]:
        connection.execute(f"""
        INSERT OR IGNORE INTO campfireChoices (
            runId,
            floor,
            key,
            data
        ) VALUES (
            "{fjson["play_id"]}",
            {choice["floor"]},
            "{choice["key"]}",
            {"NULL" if "data" not in choice else f'"{choice["data"]}"'}
        );
        """)