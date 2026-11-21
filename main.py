import sys

from goldbot.core.config import CANDLE_COUNT, MAX_QUOTE_AGE_SECONDS, SYMBOL, TIMEFRAMES
from goldbot.core.connection import demo_connection
from goldbot.market_data.market_data import export_candles, read_closed_candles, read_quote, select_symbol, validate_candles


def collect_market_data():
    select_symbol()
    has_error = False
    try:
        quote = read_quote()
        print(
            f"{SYMBOL} quote {quote.status} at {quote.time_utc.isoformat()} | "
            f"age {quote.age_seconds:.2f}s (limit {MAX_QUOTE_AGE_SECONDS}s) | "
            f"bid {quote.bid:g} | ask {quote.ask:g} | spread {quote.spread:.8f} USD"
        )
        has_error = quote.status == "FUTURE TIMESTAMP"
    except (RuntimeError, ValueError, OverflowError, OSError) as error:
        print(f"Quote check failed: {error}", file=sys.stderr)
        has_error = True

    for name, timeframe in TIMEFRAMES.items():
        try:
            rates = read_closed_candles(timeframe)
            shortfall = " (partial history)" if len(rates) < CANDLE_COUNT else ""
            print(f"{SYMBOL} {name}: received {len(rates):,}/{CANDLE_COUNT:,} closed candles{shortfall}.")
            path = export_candles(name, validate_candles(rates))
            print(f"Saved {path}")
        except (RuntimeError, ValueError, OverflowError, OSError) as error:
            print(f"{SYMBOL} {name} collection failed: {error}", file=sys.stderr)
            has_error = True
    return int(has_error)


def main():
    print("Starting GoldBot...")
    try:
        with demo_connection() as account:
            print("Connected to an MT5 demo account.")
            print("Broker:", account.company)
            print("Server:", account.server)
            print("Balance:", account.balance)
            print("Equity:", account.equity)
            print("Currency:", account.currency)
            print("Leverage:", account.leverage)
            return collect_market_data()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
