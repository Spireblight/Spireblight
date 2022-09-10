#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS neowBonus (
        runId TEXT,
        bonus TEXT,
        cost TEXT,
        PRIMARY KEY (runId)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    connection.execute(f"""
    INSERT OR IGNORE INTO neowBonus (
        runId,
        bonus,
        cost
    ) VALUES (
        "{fjson["play_id"]}",
        "{fjson["neow_bonus"]}",
        "{fjson["neow_cost"]}"
    );
    """)