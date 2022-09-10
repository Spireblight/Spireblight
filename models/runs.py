#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        runId TEXT,
        user TEXT,
        profile INTEGER,
        ascensionLevel INTEGER,
        buildVersion TEXT,
        campfireRested INTEGER,
        campfireUpgraded INTEGER,
        characterChosen TEXT,
        choseSeed INTEGER,
        circletCount INTEGER,
        floorReached INTEGER,
        gold INTEGER,
        isBeta INTEGER,
        isDaily INTEGER,
        isEndless INTEGER,
        isProd INTEGER,
        isTrial INTEGER,
        localTime TEXT,
        playerExperience INTEGER,
        playtime INTEGER,
        purchasedPurges INTEGER,
        score INTEGER,
        seedPlayed INTEGER,
        seedSourceTimestamp TEXT,
        victory INTEGER,
        PRIMARY KEY (runId)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    # TODO: Stop hardcoding the user and profile values.
    connection.execute(f"""
    INSERT OR IGNORE INTO runs (
        runId,
        user,
        profile,
        ascensionLevel,
        buildVersion,
        campfireRested,
        campfireUpgraded,
        characterChosen,
        choseSeed,
        circletCount,
        floorReached,
        gold,
        isBeta,
        isDaily,
        isEndless,
        isProd,
        isTrial,
        localTime,
        playerExperience,
        playtime,
        purchasedPurges,
        score,
        seedPlayed,
        seedSourceTimestamp,
        victory
    ) VALUES (
        "{fjson["play_id"]}",
        "Baalorlord",
        0,
        {fjson["ascension_level"]},
        "{fjson["build_version"]}",
        {fjson["campfire_rested"]},
        {fjson["campfire_upgraded"]},
        "{fjson["character_chosen"]}",
        {1 if fjson["chose_seed"] else 0},
        {fjson["circlet_count"]},
        {fjson["floor_reached"]},
        {fjson["gold"]},
        {1 if fjson["is_beta"] else 0},
        {1 if fjson["is_daily"] else 0},
        {1 if fjson["is_endless"] else 0},
        {1 if fjson["is_prod"] else 0},
        {1 if fjson["is_trial"] else 0},
        "{fjson["local_time"]}",
        {fjson["player_experience"]},
        {fjson["playtime"]},
        {fjson["purchased_purges"]},
        {fjson["score"]},
        {fjson["seed_played"]},
        "{fjson["seed_source_timestamp"]}",
        {1 if fjson["victory"] else 0}
    );
    """)