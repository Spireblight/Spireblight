#!/usr/bin/env python3

import cards

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS deckCards (
        runId TEXT,
        cardNum INTEGER,
        card TEXT,
        PRIMARY KEY (runId, cardNum)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    cardNum = 0
    for card in fjson["master_deck"]:
        cardNum = cardNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO deckCards (
            runId,
            cardNum,
            card
        ) VALUES (
            "{fjson["play_id"]}",
            {cardNum},
            "{cards.to_modern(card)}"
        );
        """)