#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS itemPurges (
        runId TEXT,
        floor INTEGER,
        itemPurgeNum INTEGER,
        item TEXT,
        PRIMARY KEY (runId, floor, itemPurgeNum)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    itemPurgeNum = 0
    for floor in fjson["items_purged_floors"]:
        item = fjson["items_purged"][itemPurgeNum]
        itemPurgeNum = itemPurgeNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO itemPurges (
            runId,
            floor,
            itemPurgeNum,
            item
        ) VALUES (
            "{fjson["play_id"]}",
            {floor},
            {itemPurgeNum},
            "{item}"
        );
        """)