#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS currentHPPerFloor (
        runId TEXT,
        floor INTEGER,
        hp INTEGER,
        PRIMARY KEY (runId, floor)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    floorNum = 0
    for hp in fjson["current_hp_per_floor"]:
        floorNum = floorNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO currentHPPerFloor (
            runId,
            floor,
            hp
        ) VALUES (
            "{fjson["play_id"]}",
            {floorNum},
            {hp}
        );
        """)