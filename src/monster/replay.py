import base64

__all__ = ["GameState"]

_floors = ("on the bottom floor", "on the middle floor", "on the top floor", "in the Pyre room")

def number(x: int):
    match x:
        case 0:
            return "1st"
        case 1:
            return "2nd"
        case 2:
            return "3rd"
        case a:
            return f"{a+1}th"

class GameState:
    """Keep track of the current game state."""
    def __init__(self, data: list[str] | None = None):
        self.actions = []
        self._data = None
        self.reset_state()
        if data is not None:
            self.update_replay_data(data)

    def reset_state(self):
        """Reset the game state."""
        self.actions.clear()
        self.in_fight = False
        self.fight_num = 0
        self.is_player_turn = False
        self.cur_turns = 0
        self.total_turns = 0

    def get_current_state(self):
        """Keep a snapshot of the state at this given action."""
        return {
            "in_fight": self.in_fight,
            "fight_num": self.fight_num,
            "is_player_turn": self.is_player_turn,
            "cur_turns": self.cur_turns,
            "total_turns": self.total_turns,
        }

    def _asdict(self):
        d = self.get_current_state()
        d["actions"] = self.actions
        return d

    def update_replay_data(self, data: list[str]):
        if len(data) < len(self.actions): # new run, reset state
            self.reset_state()
        data = data[len(self.actions):]

        for value in data:
            opcode, *args = base64.b64decode(value.encode())
            cls = _actions_mapping.get(opcode, Unknown)
            if cls is Unknown:
                action = cls(opcode, *args)
            else:
                action = cls(*args)
            action.state = self.get_current_state()
            if not action.update_state(self):
                break # updating went wrong, try again next time
            self.actions.append(action)

class Action:
    """Store information for one action. Subclasses define behaviour."""
    opcode: int
    state: dict[str, int | bool]
    text: str

    def __init_subclass__(cls):
        if cls.__name__ == "Unknown":
            return # allow it for unknown ones
        if cls.opcode in _actions_mapping:
            raise RuntimeError(f"Error: Opcode {cls.opcode} is registered more than once.")
        _actions_mapping[cls.opcode] = cls

    def _get_args(self) -> dict[str, int | str | bool]:
        return {}

    def __str__(self):
        args = [f"{x}={y!r}" for x, y in self._get_args().items()]
        return f"{self.__class__.__name__}({', '.join(args)})"

    def update_state(self, state: GameState):
        """Update the known game state from this action.

        :param state: The game state we're a part of.
        :type state: GameState
        :return: True if state was successfully updated, False if not.
        :rtype: bool
        """
        return True

class Unknown(Action):
    def __init__(self, opcode: int, *data: int):
        self._data = data
        self.opcode = opcode
        self.text = f"Unknown action with opcode {opcode}"

    def _get_args(self):
        d = {"opcode": self.opcode}
        for i, x in enumerate(self._data):
            d[f"<{i}>"] = x
        return d

_actions_mapping: dict[int, Action] = {}

class SelectNode(Action):
    """Enter a specific node on the map."""
    opcode = 1

    def __init__(self, ring: int, side: int, index: int):
        self.ring = ring # 0-indexed
        self.index = index
        if not side:
            self.side = "left"
        elif side == 1:
            self.side = "right"
        elif side == 0xff:
            self.side = "shared"
        else:
            raise ValueError(f"Could not parse side {side}")

    def _get_args(self):
        return {"ring": self.ring, "side": self.side, "index": self.index}

    @property
    def text(self) -> str:
        if not self.ring:
            return f"Take the {number(self.index)} reward from ring 1."
        if self.side == "shared":
            return f"Take the shared reward from ring {self.ring+1}."
        return f"Take the {number(self.index)} reward from the {self.side} side of ring {self.ring+1}."

class FightBegin(Action):
    """Enter a fight."""
    opcode = 2

    def __init__(self, num: int):
        self.num = num
        self.text = f"Begin Fight {num}"

    def _get_args(self):
        return {"num": self.num}

    def update_state(self, state: GameState):
        state.in_fight = True
        state.fight_num = self.num
        state.is_player_turn = True
        state.cur_turns = 1 # first turn, though it hasn't started yet
        state.total_turns += 1
        return True

class FightEnd(Action):
    """Terminate fight."""
    opcode = 3

    def __init__(self, num: int):
        self.num = num
        self.text = f"End fight with {num} turns remaining"

    def _get_args(self):
        return {"turns": self.num}

    def update_state(self, state: GameState):
        state.in_fight = False
        if not state.is_player_turn:
            # we increment turns taken on turn end for the *next* turn
            # so if the fight ends during combat (e.g. Relentless), we'll be off by 1
            state.cur_turns -= 1
            state.total_turns -= 1
        return True

class TakeTrial(Action):
    """Whether we take a trial."""
    opcode = 5

    def __init__(self, taken: int):
        self.taken = bool(taken)
        if taken:
            self.text = "Take trial"
        else:
            self.text = "Skip trial"

    def _get_args(self):
        return {"taken": self.taken}

class EndTurn(Action):
    """Ending a turn."""
    opcode = 6

    def update_state(self, state: GameState):
        state.cur_turns += 1
        state.total_turns += 1
        state.is_player_turn = False
        return True

class PlayCard(Action):
    """Playing a single card."""
    opcode = 7

    def __init__(self, hand_pos: int, floor_num: int, a: int, index: int, crc: int):
        # we have card index / target team
        # hand in the position in hand of the card before playing it
        # index is the position of the card played, starting at the center of the room(?)
        # I believe c is the card type, but that doesn't seem correct
        self.hand_pos = hand_pos
        self.floor = _floors[floor_num]
        self.index = index
        self._a = a
        self.crc = crc
        self.text = f"Play the {number(hand_pos)} card from hand {self.floor}, targeting the {number(index)} position."

    def _get_args(self):
        return {"hand_pos": self.hand_pos, "floor": self.floor, "<a>": self._a, "index": self.index}

    def update_state(self, state: GameState):
        state.is_player_turn = True
        return True

class ActivateAbility(Action):
    """Activating an ability."""
    opcode = 8

    def __init__(self, floor_num: int, index: int, a: int, b: int, c: int):
        self.floor = _floors[floor_num]
        self.index = index
        self._a = a
        self._b = b
        self._c = c
        self.text = f"Activate ability of the {number(index)} unit {self.floor}."

    def _get_args(self):
        return {"floor": self.floor, "index": self.index, "<a>": self._a, "<b>": self._b, "<c>": self._c}

    def update_state(self, state: GameState):
        state.is_player_turn = True
        return True

class CardReward(Action):
    """Picking a card reward, including Banners."""
    opcode = 9

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        if index == 0xff:
            self.text = "Skip card reward."
        else:
            self.text = f"Acquire card at position {index}."

    def _get_args(self):
        if self.index == 0xff:
            return {"reward": "skipped"}
        return {"reward": "picked", "index": self.index}

class ArtifactReward(Action):
    """Pick an artifact from some reward."""
    opcode = 10

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        if index == 0xff:
            self.text = "Skip artifact reward."
        else:
            self.text = f"Acquire artifact at position {index}."

    def _get_args(self):
        if self.index == 0xff:
            return {"reward": "skipped"}
        return {"reward": "picked", "index": self.index}

class ChampionUpgrade(Action):
    """Upgrade your Champion."""
    opcode = 11

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        if not index:
            self.text = "Pick the left Champion upgrade."
        elif index == 1:
            self.text = "Pick the right Champion upgrade."
        elif index == 0xff:
            self.text = "Skip Champion upgrade."
        else:
            raise ValueError(f"Unrecognized index {index}")

    def _get_args(self):
        if self.index == 0xff:
            return {"reward": "skipped"}
        return {"reward": "picked", "index": self.index}

class BuyPurge(Action):
    """Buy a Purge Card option."""
    opcode = 13

class RerollShop(Action):
    """Reroll the shop's options."""
    opcode = 14

class BuyShopItem(Action):
    """Buy a single upgrade from the Merchants of Steel or Magic."""
    opcode = 16

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Buy shop upgrade at position {index}."

    def _get_args(self):
        return {"index": self.index}

class BuyRoomOrEquipment(Action):
    """Buy a Room or Equipment from the Merchant of Arms."""
    opcode = 17

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Buy room or equipment at position {index}."

    def _get_args(self):
        return {"index": self.index}

class ApplyUpgrade(Action):
    """Apply a single upgrade to a card."""
    opcode = 19

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Apply upgrade to card at position {index}."

    def _get_args(self):
        return {"index": self.index}

class PurgeCard(Action):
    """Remove a specific card from the deck."""
    opcode = 20

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Purge card at index {index}."

    def _get_args(self):
        return {"index": self.index}

class DuplicateCard(Action):
    """Duplicate a single card."""
    opcode = 21

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Duplicate card at index {index}."

    def _get_args(self):
        return {"index": self.index}

class EventOption(Action):
    """Choose an event option."""
    opcode = 22

    def __init__(self, a: int, b: int, c: int):
        self._a = a
        self._b = b
        self._c = c
        self.text = "Pick option from event (more details unknown yet)"

    def _get_args(self):
        return {"<a>": self._a, "<b>": self._b, "<c>": self._c}

class ReformUnit(Action):
    """Reform a unit."""
    opcode = 25

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Reform unit at index {index}."

    def _get_args(self):
        return {"index": self.index}

class EnterEvent(Action):
    """Enter the Celestial Alcove."""
    opcode = 28

    def __init__(self, a: int): # a is always 0, I think
        self.text = "Enter event node"

class PickDarkShard(Action):
    """Select a Darkshard to use."""
    opcode =  29

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Select Darkshard at position {index}"

    def _get_args(self):
        return {"index": self.index}

class BuyArtifact(Action):
    """Buy an Artifact from the Merchant of Trinkets."""
    opcode = 31

    def __init__(self, index: int, crc: int):
        self.index = index
        self.crc = crc
        self.text = f"Buy artifact at position {index}."

    def _get_args(self):
        return {"index": self.index}

class Deployable(Action):
    """Buy the Deployable upgrade."""
    opcode = 37

class BeginRun(Action):
    """Begin the run."""
    opcode = 38

    def __init__(self, a: int): # a is always 0, I think
        self.text = "Begin run"

class MonolithDiscard(Action):
    """Discard a card to increase the Devotion."""
    opcode = 49

    def __init__(self, floor: int):
        self.text = "Discard a card with the Monolith"
        self.floor = _floors[floor]

    def _get_args(self):
        return {"floor": self.floor}
