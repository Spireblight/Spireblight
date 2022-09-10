#!/usr/bin/env python3

idToName = {
    "Adaption": "Rush Down",
    "Auto Shields": "Auto-Shields",
    "BootSequence": "Boot Sequence",
    "ClearTheMind": "Tranquility",
    "Conserve Battery": "Charge Battery",
    "Crippling Poison": "Crippling Cloud",
    "Defend_B": "Defend",
    "Defend_G": "Defend",
    "Defend_P": "Defend",
    "Defend_R": "Defend",
    "Fasting2": "Fasting",
    "Gash": "Claw",
    "Ghostly": "Apparition",
    "Lockon": "Bullseye",
    "Night Terror": "Nightmare",
    "PathToVictory": "Pressure Points",
    "Redo": "Recursion",
    "Steam Power": "Overclock",
    "Steam": "Steam Barrier",
    "Strike_B": "Strike",
    "Strike_G": "Strike",
    "Strike_P": "Strike",
    "Strike_R": "Strike",
    "Underhanded Strike": "Sneaky Strike",
    "Venomology": "Alechemize",
    "Wireheading": "Foresight",
    "Wraith Form v2": "Wraith Form",
}

def to_modern(card):
    cardParts = card.split("+")

    cardName = cardParts[0]
    if cardName in idToName:
        cardName = idToName[cardName]
    
    if len(cardParts) == 2:
        cardName = cardName + "+" + cardParts[1]

    return cardName