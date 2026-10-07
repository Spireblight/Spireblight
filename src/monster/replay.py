import base64

def number(x: int):
    x += 1
    match x:
        case 1:
            return "1st"
        case 2:
            return "2nd"
        case 3:
            return "3rd"
        case a:
            return f"{a}th"

def floor(x: int):
    match x:
        case 0:
            return "on the bottom floor"
        case 1:
            return "on the middle floor"
        case 2:
            return "on the top floor"
        case 3:
            return "in the Pyre room"

def parse(value: str):
    """Parse a replay entry into a human-readable format."""
    decoded = base64.b64decode(value.encode())
    match tuple(decoded):
        case (1, ring, side, index):
            ring += 1 # it's 0-indexed
            side = side and "right" or "left"
            if ring == 1:
                return f"Take the {number(index)} reward from ring {ring}"
            if side == 255:
                return f"Take the shared reward from ring {ring}"
            return f"Take the {number(index)} reward from the {side} side of ring {ring}"
        case (2, a):
            return f"Begin Fight {a}"
        case (3, a):
            return f"End fight with {a} turns remaining"
        case (5, a):
            if a == 0:
                return "Skip trial"
            return "Take trial"
        case (6,):
            return "End turn"
        case (7, hand, fnum, c, index, id): # we have card index / target team
            # hand in the position in hand of the card before playing it
            # index is the position of the card played, starting at the center of the room(?)
            # I believe c is the card type, but that doesn't seem correct
            return f"Play the {number(hand)} card from hand {floor(fnum)}, targeting the {number(index)} position"
        case (8, fnum, index, c, d, e):
            return f"Activate ability of the {number(index)} unit {floor(fnum)}"
        case (9, i, id):
            if i == 255:
                return "Skip unit reward"
            return f"Acquire unit at position {i} (id #{id})"
        case (10, i, id):
            if i == 255:
                return "Skip relic reward"
            return f"Select relic at position {i} (id #{id})"
        case (11, i, id):
            if i == 255:
                return "Skip Champion upgrade"
            return f"Pick Champion upgrade at position {i} (id #{id})"
        case (16, i, id):
            return f"Buy shop item #{i} (id #{id})"
        case (19, i, id):
            return f"Apply upgrade to card at position {i} (id #{id})"
        case (22, a, b, c):
            return "Pick option from event (more details unknown yet)"
        case (28, 0):
            return "Enter event node"
        case (38, 0):
            return "Begin run"
        case a:
            return f"Unrecognized action {a}"
