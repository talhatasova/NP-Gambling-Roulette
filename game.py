import requests
import uuid

class Results():
    GREEN = "GREEN"
    RED = "RED"
    BLACK = "BLACK"

RED_MULTIPLIER = 2
BLACK_MULTIPLIER = 2
GREEN_MULTIPLIER = 14

BETTING_DURATION = 10
def getBetDuration():
    return BETTING_DURATION
def setBetDuration(value:int):
    global BETTING_DURATION
    BETTING_DURATION = value

ANIMATION_DURATION = 10
FRAME_RATE = 5
TOTAL_FRAMES = ANIMATION_DURATION * FRAME_RATE
SLEEP_DURATION = 1 / FRAME_RATE

GREEN_INTERVAL = [0]
RED_INTERVAL = [1, 2, 3, 4, 5, 6, 7]
BLACK_INTERVAL = [8, 9, 10, 11, 12, 13, 14]
ROULETTE_SEQUENCE = [1, 14, 2, 13, 3, 12, 4, 0, 11, 5, 10, 6, 9, 7, 8]

NUMBER_COLOR_MAPPING = {
    0:Results.GREEN,
    1:Results.RED,
    2:Results.RED,
    3:Results.RED,
    4:Results.RED,
    5:Results.RED,
    6:Results.RED,
    7:Results.RED,
    8:Results.BLACK,
    9:Results.BLACK,
    10:Results.BLACK,
    11:Results.BLACK,
    12:Results.BLACK,
    13:Results.BLACK,
    14:Results.BLACK,
}

def getNewRoundResult() -> int:
    try:
        response = requests.get("https://csrng.net/csrng/csrng.php?min=1&max=1500000").json()
        result = response[0].get("random")
        result = result % 15
        return result
    except Exception:
        return None
    
def getNewRoundID() -> str:
    return str(uuid.uuid4())

def set_sequence(midpoint:int) -> list[str]:
    if midpoint not in ROULETTE_SEQUENCE:
        raise ValueError(f"{midpoint} does not exist in roulette.")
    
    last_result_index = ROULETTE_SEQUENCE.index(midpoint)
    sequence_length = len(ROULETTE_SEQUENCE)
    half_window = 7
    start_index = (last_result_index - half_window) % sequence_length
    end_index = (last_result_index + half_window + 1) % sequence_length
    if start_index < end_index:
        sequence = ROULETTE_SEQUENCE[start_index:end_index]
    else:
        sequence = ROULETTE_SEQUENCE[start_index:] + ROULETTE_SEQUENCE[:end_index]
    
    return sequence