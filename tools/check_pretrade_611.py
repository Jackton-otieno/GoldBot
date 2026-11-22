"""Compare a trade-day read with the accepted 22 Nov 2026 Stage B baseline.

The scoped Stage B exception (docs/evidence/stage-b-baseline-2026-11-22.md)
covers one baseline only. This check is pinned to that file's SHA-256 and
passes only if nothing has changed since: the same account and
specification, the same deals, the same single accepted "Archived deals"
entry, no exposure, feasible stops, and a fresh read. It reads files only;
it never attaches to MT5. Passing it does not approve Stage C.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from goldbot.research import exposure_log


ACCEPTED_BASELINE_SHA256 = "0dc6e9c4f67f24026893bbf5d45eb1f5ba0240572acba84e81e8d5ed5183d95f"
MAX_READ_AGE = timedelta(minutes=30)
SPEC_FIELDS = ("digits", "trade_tick_size", "trade_contract_size", "trade_stops_level",
               "volume_min", "volume_step")
CONDITION = "ARCHIVED_DEALS_CORRECTION_PRESENT"
MANUAL_CHECKS = (
    "Specification window: the current time is inside today's TRADE session (screenshot)",
    "Displayed spread <= 0.60 at the moment of the order",
    "Not within 30 min of the daily quote break or a high-impact US release; not after 18:00 UTC Friday",
    "Algo Trading off; no open positions or pending orders on screen",
    "Stage C approved in manual-demo-trades.md",
)


def _time(text):
    return datetime.fromisoformat(text)


def _accepted_archived(evidence):
    return sorted(e["ticket"] for e in evidence.get("archived_deals_corrections", ()) if e.get("accepted"))


def evaluate(baseline, read, *, baseline_sha256, read_sha256, logged_digests, now):
    """Return [(check, passed, detail)] for a trade-day read against the baseline."""
    checks = []

    def add(name, passed, detail):
        checks.append((name, bool(passed), detail))

    add("baseline_is_the_accepted_one", baseline_sha256 == ACCEPTED_BASELINE_SHA256,
        f"baseline SHA-256 {baseline_sha256[:12]}...")
    same = all(read.get(k) == baseline.get(k) for k in ("server", "company", "mode", "symbol"))
    add("same_account_and_symbol",
        same and read["account_snapshot"].get("currency") == "USD" and read.get("mode") == "demo",
        f"{read.get('company')} / {read.get('server')} / {read.get('mode')} / {read.get('symbol')}")
    observed = _time(read["observed_utc"])
    add("fresh_read", timedelta(0) <= now - observed <= MAX_READ_AGE
        and observed > _time(baseline["observed_utc"]),
        f"read {observed.isoformat()}, age {int((now - observed).total_seconds() // 60)} min")
    account = read["account_snapshot"]
    add("no_exposure", account.get("margin") == 0 and account.get("credit") == 0,
        f"margin {account.get('margin')}, credit {account.get('credit')}")
    add("ledger_unchanged",
        read["ledger_check"].get("sums_to_current_balance") is True
        and account.get("balance") == baseline["account_snapshot"].get("balance"),
        f"balance {account.get('balance')} vs baseline {baseline['account_snapshot'].get('balance')}")
    tickets = sorted(d["ticket"] for d in read["deals"])
    add("no_new_account_activity",
        tickets == sorted(d["ticket"] for d in baseline["deals"]) and not read.get("orders"),
        f"{len(tickets)} deals, {len(read.get('orders') or ())} orders")
    add("no_reconciliation_issues", not read["reconciliation"]["issues"],
        f"{len(read['reconciliation']['issues'])} issues")
    boundaries = read.get("risk_day_boundaries") or []
    equity = boundaries[0]["opening_equity"] if boundaries else {}
    add("opening_equity_matches_accepted_condition",
        len(boundaries) == 1
        and _time(boundaries[0]["boundary_utc"]).date() == observed.date()
        and equity.get("status") == "CONDITIONAL" and not equity.get("reasons")
        and equity.get("conditions") == [CONDITION]
        and _accepted_archived(read) == _accepted_archived(baseline)
        and len(_accepted_archived(baseline)) == 1,
        f"status {equity.get('status')}, reasons {equity.get('reasons')}, "
        f"archived {_accepted_archived(read)}")
    add("specification_unchanged",
        all(read["symbol_economics"].get(k) == baseline["symbol_economics"].get(k) for k in SPEC_FIELDS),
        ", ".join(f"{k}={read['symbol_economics'].get(k)}" for k in SPEC_FIELDS))
    stops = read.get("planned_stop_check", {})
    add("stops_feasible", stops.get("status") == "OK",
        f"status {stops.get('status')}, spread {stops.get('current_spread')}")
    add("protocol_compliant", read.get("protocol_check", {}).get("compliant") is True,
        f"violations {read.get('protocol_check', {}).get('violations')}")
    add("read_recorded_in_exposure_log", read_sha256 in logged_digests, f"read SHA-256 {read_sha256[:12]}...")
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", type=Path, default=Path("reports/phase_6_11/demo-baseline-2.json"))
    parser.add_argument("--read", type=Path, required=True, help="trade-day output of tools.read_demo_deals_611")
    parser.add_argument("--exposure-log", type=Path, default=exposure_log.DEFAULT_LOG)
    args = parser.parse_args(argv)
    try:
        baseline_bytes, read_bytes = args.baseline.read_bytes(), args.read.read_bytes()
        checks = evaluate(
            json.loads(baseline_bytes), json.loads(read_bytes),
            baseline_sha256=sha256(baseline_bytes).hexdigest(),
            read_sha256=sha256(read_bytes).hexdigest(),
            logged_digests={e["sha256"] for e in exposure_log.verify(args.exposure_log)},
            now=datetime.now(timezone.utc))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Pre-trade check could not run: {error}", file=sys.stderr)
        return 1
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name:42} {detail}")
    passed = all(ok for _, ok, _ in checks)
    print(f"\nAutomated pre-trade checks: {'PASS' if passed else 'FAIL'}")
    print("Still to confirm by hand before any order:")
    for item in MANUAL_CHECKS:
        print(f"  [ ] {item}")
    print("Passing does not approve Stage C. GoldBot remains NO-GO for automated trading.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
