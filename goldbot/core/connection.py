from contextlib import contextmanager

import MetaTrader5 as mt5


@contextmanager
def demo_connection():
    try:
        if not mt5.initialize():
            raise RuntimeError(f"MT5 connection failed (code {mt5.last_error()[0]}).")

        terminal = mt5.terminal_info()
        if terminal is None or not terminal.connected:
            raise RuntimeError("MT5 is disconnected or terminal information is unavailable.")

        account = mt5.account_info()
        if account is None:
            raise RuntimeError(f"MT5 account information unavailable (code {mt5.last_error()[0]}).")
        if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            raise RuntimeError("Only demo accounts are allowed.")

        yield account
    finally:
        mt5.shutdown()
