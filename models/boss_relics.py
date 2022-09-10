#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS bossRelics (
        runId TEXT,
        choiceNum INTEGER,
        option TEXT,
        picked INTEGER,
        PRIMARY KEY (runId, choiceNum, option)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    choiceNum = 0
    for choice in fjson["boss_relics"]:
        choiceNum = choiceNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO bossRelics (
            runId,
            choiceNum,
            option,
            picked
        ) VALUES (
            "{fjson["play_id"]}",
            {choiceNum},
            "{choice["picked"]}",
            1
        );
        """)

        for notPicked in choice["not_picked"]:
            connection.execute(f"""
            INSERT OR IGNORE INTO bossRelics (
                runId,
                choiceNum,
                option,
                picked
            ) VALUES (
                "{fjson["play_id"]}",
                {choiceNum},
                "{notPicked}",
                0
            );
            """)