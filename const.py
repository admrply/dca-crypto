from enum import Enum, unique

@unique
class BinanceCode(Enum):
    INSUFFICIENT_BALANCE = -2010
    AMOUNT_TOO_SMALL = -1013

@unique
class Error(Enum):
    INVALID_INTERVAL_STRING = 1

@unique
class Side(Enum):
    BUY = 0
    SELL = 1

@unique
class TRADE(Enum):
    SUCCESS = 0
    FAILURE = 1
    NO_TRADE_YET = 2