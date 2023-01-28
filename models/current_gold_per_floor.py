#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS currentGoldPerFloor (
        runId TEXT,
        floor INTEGER,
        gold INTEGER,
        PRIMARY KEY (runId, floor)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    floorNum = 0
    for gold in fjson["gold_per_floor"]:
        floorNum = floorNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO currentGoldPerFloor (
            runId,
            floor,
            gold
        ) VALUES (
            "{fjson["play_id"]}",
            {floorNum},
            {gold}
        );
        """)