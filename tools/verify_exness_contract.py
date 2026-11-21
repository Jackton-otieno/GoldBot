"""Verify an explicitly selected Exness KE demo and calculate XAUUSD probes."""
import argparse
import json
import os
import sys

from goldbot.core.exness_demo import (
    DemoProfile, KE_COMPANY, VerificationError, check_identity, require_running_terminal,
    running_terminals,
)
from goldbot.risk.broker_spec_validator import DiagnosticError, validate


def verify_contract(mt5, profile, discover=running_terminals):
    def identity():
        terminal, account = check_identity(mt5, profile)
        if account.company != KE_COMPANY:
            raise VerificationError("The selected session did not report Exness (KE) Limited.")
        if terminal.trade_allowed is not False:
            raise VerificationError("Terminal Algo Trading must be disabled.")
        if account.leverage != 100:
            raise VerificationError("The selected demo leverage differs from 1:100.")
        return terminal, account

    require_running_terminal(profile.terminal, discover())
    try:
        if not mt5.initialize(str(profile.terminal), timeout=5000):
            raise VerificationError("Read-only MT5 attachment failed.")
        terminal, account = identity()
        symbol = mt5.symbol_info("XAUUSD")
        if getattr(symbol, "name", None) != "XAUUSD" or getattr(symbol, "custom", None) is not False:
            raise VerificationError("The exact non-custom XAUUSD symbol is unavailable.")
        identity()
        connectivity = {
            "server": profile.server, "company": KE_COMPANY, "account_suffix": str(profile.login)[-4:],
            "mode": "demo", "currency": "USD", "balance_usd": account.balance,
            "leverage": account.leverage, "terminal_build": terminal.build,
            "terminal_algo_trading_allowed": terminal.trade_allowed, "symbol": "XAUUSD",
        }
        def probe_identity():
            try:
                identity()
            except VerificationError:
                raise DiagnosticError("PINNED_EXNESS_IDENTITY_CHANGED") from None

        report = validate(mt5, account, expected_server=profile.server, exness_identity=probe_identity)
        return {"connectivity": connectivity, "contract": report}
    finally:
        mt5.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        import MetaTrader5 as mt5

        result = verify_contract(mt5, DemoProfile.from_environment(os.environ))
        print(json.dumps(result, indent=2, allow_nan=False))
        return int(result["contract"]["status"] == "REJECTED")
    except VerificationError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        print("Exness contract verification could not complete.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
