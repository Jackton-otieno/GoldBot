from pathlib import Path

import MetaTrader5 as mt5


SYMBOL = "XAUUSD"
TIMEFRAMES = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}
CANDLE_COUNT = 10_000
MAX_QUOTE_AGE_SECONDS = 60
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
