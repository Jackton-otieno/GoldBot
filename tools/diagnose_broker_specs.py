"""Print a sanitized, read-only XAUUSD demo diagnostic as JSON."""
import argparse
from datetime import datetime, timezone
import json

from goldbot.risk.broker_spec_validator import api_code, validate
from goldbot.risk.risk_config import SYMBOL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-server", default="MetaQuotes-Demo")
    args = parser.parse_args()
    try:
        from goldbot.core.connection import demo_connection, mt5
        try:
            with demo_connection() as account:
                report = validate(mt5, account, expected_server=args.expected_server)
        except RuntimeError as error:
            report = {"status": "REJECTED", "errors": [{"reason": "MT5_SESSION_UNAVAILABLE", "api_code": api_code(mt5)}]}
        except Exception as error:
            report = {"status": "REJECTED",
                      "errors": [{"reason": "MT5_ERROR", "exception_type": type(error).__name__,
                                  "api_code": api_code(mt5)}]}
    except ImportError:
        report = {"status": "REJECTED", "errors": [{"reason": "MT5_IMPORT_UNAVAILABLE"}]}
    report.setdefault("symbol", SYMBOL)
    report.setdefault("observed_at_utc", datetime.now(timezone.utc).isoformat())
    report.setdefault("historical_applicability", "UNVERIFIED")
    print(json.dumps(report, indent=2, allow_nan=False))
    return int(report["status"] != "CURRENT_DEMO_PROBES_CONSISTENT")


if __name__ == "__main__":
    raise SystemExit(main())


