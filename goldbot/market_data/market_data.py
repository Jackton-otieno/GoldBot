import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from tempfile import NamedTemporaryFile

import MetaTrader5 as mt5

from goldbot.core.config import CANDLE_COUNT, DATA_DIR, MAX_QUOTE_AGE_SECONDS, SYMBOL


CSV_FIELDS = ("mt5_time_epoch", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")


@dataclass(frozen=True)
class Quote:
    time_utc: datetime
    bid: float
    ask: float
    age_seconds: float

    @property
    def spread(self):
        return self.ask - self.bid

    @property
    def status(self):
        if self.age_seconds < 0:
            return "FUTURE TIMESTAMP"
        if self.age_seconds > MAX_QUOTE_AGE_SECONDS:
            return "STALE"
        return "FRESH"


def select_symbol():
    info = mt5.symbol_info(SYMBOL)
    if info is None:
        raise RuntimeError(f"{SYMBOL} is unavailable (MT5 code {mt5.last_error()[0]}).")
    if not info.visible and not mt5.symbol_select(SYMBOL, True):
        raise RuntimeError(f"Could not select {SYMBOL} (MT5 code {mt5.last_error()[0]}).")


def read_quote():
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        raise RuntimeError(f"{SYMBOL} quote unavailable (MT5 code {mt5.last_error()[0]}).")
    if not all(isfinite(price) for price in (tick.bid, tick.ask)) or not 0 < tick.bid <= tick.ask:
        raise ValueError(f"{SYMBOL} quote has invalid bid or ask.")

    timestamp = tick.time_msc / 1000 if tick.time_msc > 0 else tick.time
    if timestamp <= 0:
        raise ValueError(f"{SYMBOL} quote has no valid timestamp.")
    time_utc = datetime.fromtimestamp(timestamp, timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - time_utc).total_seconds()
    return Quote(time_utc, tick.bid, tick.ask, age_seconds)


def read_closed_candles(timeframe):
    # MT5 reserves position zero for its current bar.
    rates = mt5.copy_rates_from_pos(SYMBOL, timeframe, 1, CANDLE_COUNT)
    if rates is None:
        raise RuntimeError(f"History unavailable (MT5 code {mt5.last_error()[0]}).")
    if len(rates) == 0:
        raise RuntimeError(f"MT5 returned 0/{CANDLE_COUNT:,} closed candles.")
    return rates


def validate_candles(rates):
    rows = []
    previous_time = 0
    for index, rate in enumerate(rates, start=1):
        timestamp = int(rate["time"])
        if timestamp <= previous_time:
            raise ValueError(f"Candle {index} has an invalid, duplicate, or out-of-order timestamp.")
        open_price, high, low, close = (float(rate[field]) for field in ("open", "high", "low", "close"))
        if not all(isfinite(price) and price > 0 for price in (open_price, high, low, close)):
            raise ValueError(f"Candle {index} has a non-finite or non-positive OHLC price.")
        if not low <= min(open_price, close) <= max(open_price, close) <= high:
            raise ValueError(f"Candle {index} has inconsistent OHLC prices.")

        rows.append((
            timestamp, open_price, high, low, close,
            int(rate["tick_volume"]), int(rate["spread"]), int(rate["real_volume"]),
        ))
        previous_time = timestamp
    return rows


def export_candles(timeframe_name, rows):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination = DATA_DIR / f"{SYMBOL}_{timeframe_name}.csv"
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=DATA_DIR,
            suffix=".tmp", delete=False,
        ) as temporary:
            temporary_path = DATA_DIR / temporary.name
            writer = csv.writer(temporary)
            writer.writerow(CSV_FIELDS)
            writer.writerows(rows)
        temporary_path.replace(destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return destination
