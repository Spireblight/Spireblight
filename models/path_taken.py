#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS pathTaken (
        runId TEXT,
        floor INTEGER,
        node TEXT,
        PRIMARY KEY (runId, floor)
    ) WITHOUT ROWID;
    """)

def switch(nodeRaw):
    if nodeRaw == "M":
        return "combat"
    if nodeRaw == "$":
        return "shop"
    if nodeRaw == "R":
        return "campfire"
    if nodeRaw == "?":
        return "event"
    if nodeRaw == "E":
        return "elite"
    if nodeRaw == "BOSS":
        return "boss"

def insert(connection, fjson):
    floorNum = 0
    for nodeRaw in fjson["path_taken"]:
        floorNum = floorNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO pathTaken (
            runId,
            floor,
            node
        ) VALUES (
            "{fjson["play_id"]}",
            {floorNum},
            "{switch(nodeRaw)}"
        );
        """)