"""Inspect read-only session metadata availability for the expected MT5 demo."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import MetaTrader5 as mt5

from goldbot.core.config import SYMBOL
from goldbot.core.connection import demo_connection
from tools.diagnose_time import EXPECTED_SERVER


def capture():
    report = {
        "captured_host_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "package_version": mt5.__version__,
        "demo_scope_confirmed": False,
        "python_session_functions": {
            name: callable(getattr(mt5, name, None))
            for name in ("symbol_info_session_quote", "symbol_info_session_trade",
                         "SymbolInfoSessionQuote", "SymbolInfoSessionTrade")
        },
        "quote_session": "UNVERIFIED",
        "trade_session": "UNVERIFIED",
        "quote_freshness": "UNVERIFIED",
        "server_time_conversion": "UNVERIFIED",
        "risk_day": "UNVERIFIED",
    }
    try:
        with demo_connection() as account:
            if account.server != EXPECTED_SERVER:
                report["connection_status"] = "UNEXPECTED_DEMO_SERVER"
                return report
            report["demo_scope_confirmed"] = True
            info = mt5.symbol_info(SYMBOL)
            if info is None:
                report["symbol_info_error_code"] = mt5.last_error()[0]
                return report
            fields = info._asdict()
            report["symbol_fields"] = sorted(fields)
            report["session_named_fields"] = sorted(
                name for name in fields if "session" in name.lower()
            )
            report["symbol_status"] = {
                "exact_name_match": info.name == SYMBOL,
                "visible": info.visible,
                "trade_mode": info.trade_mode,
                "custom": info.custom,
            }
            terminal = mt5.terminal_info()
            report["terminal_connected_after"] = terminal is not None and terminal.connected
            report["connection_status"] = "METADATA_READ"
    except RuntimeError as error:
        report["connection_status"] = "DEMO_CONNECTION_REJECTED"
        report["connection_detail"] = str(error)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New file for the JSON evidence.")
    args = parser.parse_args()
    payload = json.dumps(capture(), indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(payload)
    else:
        print(payload, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
