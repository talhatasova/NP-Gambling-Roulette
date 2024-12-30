class InsufficientBalanceException(Exception):
    def __init__(self, *args):
        super().__init__(*args)

class NoGamblerException(Exception):
    def __init__(self, *args):
        super().__init__(*args)