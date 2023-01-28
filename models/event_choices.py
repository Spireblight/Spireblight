#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS eventChoices (
        runId TEXT,
        floor INTEGER,
        damageHealed INTEGER,
        damageTaken INTEGER,
        eventName TEXT,
        goldGain INTEGER,
        goldLoss INTEGER,
        maxHPGain INTEGER,
        maxHPLoss INTEGER,
        playerChoice TEXT,
        PRIMARY KEY (runId, floor)
    ) WITHOUT ROWID;
    """)
    connection.execute("""
    CREATE TABLE IF NOT EXISTS eventRelics (
        runId TEXT,
        floor INTEGER,
        relicNum INTEGER,
        relic TEXT,
        PRIMARY KEY (runId, floor, relicNum)
    ) WITHOUT ROWID;
    """)
    connection.execute("""
    CREATE TABLE IF NOT EXISTS eventCards (
        runId TEXT,
        floor INTEGER,
        cardNum INTEGER,
        card TEXT,
        PRIMARY KEY (runId, floor, cardNum)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    for event in fjson["event_choices"]:
        connection.execute(f"""
        INSERT OR IGNORE INTO eventChoices (
            runId,
            floor,
            damageHealed,
            damageTaken,
            eventName,
            goldGain,
            goldLoss,
            maxHPGain,
            maxHPLoss,
            playerChoice
        ) VALUES (
            "{fjson["play_id"]}",
            {event["floor"]},
            {event["damage_healed"]},
            {event["damage_taken"]},
            "{event["event_name"]}",
            {event["gold_gain"]},
            {event["gold_loss"]},
            {event["max_hp_gain"]},
            {event["max_hp_loss"]},
            "{event["player_choice"]}"
        );
        """)

        cardNum = 0
        for card in [] if "cards_obtained" not in event else event["cards_obtained"]:
            cardNum = cardNum + 1
            
            connection.execute(f"""
            INSERT OR IGNORE INTO eventCards (
                runId,
                floor,
                cardNum,
                card
            ) VALUES (
                "{fjson["play_id"]}",
                {event["floor"]},
                {cardNum},
                "{card}"
            );
            """)

        relicNum = 0
        for relic in [] if "relics_obtained" not in event else event["relics_obtained"]:
            relicNum = relicNum + 1
            
            connection.execute(f"""
            INSERT OR IGNORE INTO eventRelics (
                runId,
                floor,
                relicNum,
                relic
            ) VALUES (
                "{fjson["play_id"]}",
                {event["floor"]},
                {relicNum},
                "{relic}"
            );
            """)