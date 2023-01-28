#!/usr/bin/env python3

import cards

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS cardChoices (
        runId TEXT,
        choiceNum INTEGER,
        floor INTEGER,
        option TEXT,
        picked INTEGER,
        PRIMARY KEY (runId, choiceNum)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    choiceNum = 0
    for choice in fjson["card_choices"]:
        choiceNum = choiceNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO cardChoices (
            runId,
            choiceNum,
            floor,
            option,
            picked
        ) VALUES (
            "{fjson["play_id"]}",
            {choiceNum},
            {choice["floor"]},
            "{cards.to_modern(choice["picked"])}",
            1
        );
        """)

        for notPicked in choice["not_picked"]:
            connection.execute(f"""
            INSERT OR IGNORE INTO cardChoices (
                runId,
                choiceNum,
                floor,
                option,
                picked
            ) VALUES (
                "{fjson["play_id"]}",
                {choiceNum},
                {choice["floor"]},
                "{cards.to_modern(notPicked)}",
                0
            );
            """)