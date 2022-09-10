#!/usr/bin/env python3

def create(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS itemPurchases (
        runId TEXT,
        floor INTEGER,
        itemPurchaseNum INTEGER,
        item TEXT,
        PRIMARY KEY (runId, floor, itemPurchaseNum)
    ) WITHOUT ROWID;
    """)

def insert(connection, fjson):
    itemPurchaseNum = 0
    for floor in fjson["item_purchase_floors"]:
        item = fjson["items_purchased"][itemPurchaseNum]
        itemPurchaseNum = itemPurchaseNum + 1

        connection.execute(f"""
        INSERT OR IGNORE INTO itemPurchases (
            runId,
            floor,
            itemPurchaseNum,
            item
        ) VALUES (
            "{fjson["play_id"]}",
            {floor},
            {itemPurchaseNum},
            "{item}"
        );
        """)