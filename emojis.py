class Emoji():
    ZERO = "<:R0:1322626863884926977>"
    ONE = "<:R1:1322626947020357774>"
    TWO = "<:R2:1322626984261582880>"
    THREE = "<:R3:1322626986622976060>"
    FOUR = "<:R4:1322626988858540053>"
    FIVE = "<:R5:1322626990410432624>"
    SIX = "<:R6:1322626991907803308>"
    SEVEN = "<:R7:1322626993606492171>"
    EIGHT = "<:R8:1322627058412683414>"
    NINE = "<:R9:1322627059977027584>"
    TEN = "<:R10:1322627061621329920>"
    ELEVEN = "<:R11:1322627063567483001>"
    TWELVE = "<:R12:1322627064934961175>"
    THIRTEEN = "<:R13:1322627066050383954>"
    FOURTEEN = "<:R14:1322627067866517574>"
    
    roulette_values = {
        0 : ZERO,
        1 : ONE,
        2 : TWO,
        3 : THREE,
        4 : FOUR,
        5 : FIVE,
        6 : SIX,
        7 : SEVEN,
        8 : EIGHT,
        9 : NINE,
        10 : TEN,
        11 : ELEVEN,
        12 : TWELVE,
        13 : THIRTEEN,
        14 : FOURTEEN,
    }

    class PROGRESS_BAR():
        START = "🍌"
        BEHIND_EDGE = "🟰"
        FRONT_EDGE = "➖"
        EDGE = "💦"
        BEFORE_END = "🫅🏿"
        AFTER_END = "🫄🏿"
    class BET_TYPES():
        GREEN = "<:Green:1322677313434947625>"
        RED = "<:Red:1322677314965868544>"
        BLACK = "<:Black:1322677312101154826>"
        ALL = [RED, GREEN, BLACK]

    class ID():
        BET_GREEN = 1322677313434947625
        BET_RED = 1322677314965868544
        BET_BLACK = 1322677312101154826