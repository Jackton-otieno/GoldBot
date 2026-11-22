"""Read-only reconciliation of manually placed Exness demo XAUUSD trades.

The operator places the trades by hand (docs/evidence/manual-demo-trades.md).
This tool only reads: identity, symbol economics, deal and order history from
--from (minus one day) to the present, nearby ticks and the account snapshot.
MT5 is wrapped in an allowlist proxy, so any trading or position function
raises before it can reach the terminal.

Requires the same opt-in environment as tools.verify_exness_demo.
"""

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal
from hashlib import sha256
from pathlib import Path

from goldbot.core import server_clock
from goldbot.core.exness_demo import (
    SYMBOL, DemoProfile, VerificationError, check_identity, require_running_terminal,
    running_terminals,
)
from goldbot.research import exposure_log
from goldbot.risk.booked_pnl import DEAL_BUY, DEAL_SELL, balance_at, protocol_check, reconcile


DEAL_BALANCE = 2


READ_ONLY = frozenset({
    "initialize", "shutdown", "last_error", "terminal_info", "account_info", "symbol_info",
    "history_deals_get", "history_orders_get", "copy_ticks_range",
    "ACCOUNT_TRADE_MODE_DEMO", "COPY_TICKS_ALL",
})
DEAL_FIELDS = ("ticket", "order", "time", "time_msc", "type", "entry", "position_id", "reason",
               "volume", "price", "commission", "swap", "profit", "fee", "symbol")
ORDER_FIELDS = ("ticket", "time_setup_msc", "time_done_msc", "type", "state", "type_filling",
                "type_time", "reason", "volume_initial", "volume_current", "price_open", "sl", "tp",
                "price_current", "position_id", "symbol")
ACCOUNT_FIELDS = ("currency", "balance", "credit", "equity", "margin", "margin_free", "leverage")
SYMBOL_FIELDS = ("digits", "point", "trade_tick_size", "trade_tick_value", "trade_tick_value_profit",
                 "trade_tick_value_loss", "trade_contract_size", "volume_min", "volume_step",
                 "volume_max", "trade_stops_level", "trade_freeze_level", "trade_calc_mode",
                 "trade_exemode", "swap_mode", "swap_long", "swap_short", "swap_rollover3days",
                 "margin_initial", "margin_maintenance", "spread", "spread_float")
QUOTE_LOOKBACK_MS = 10_000
MAX_QUOTE_AGE_MS = 2_000
HISTORY_MARGIN = timedelta(days=1)


class ReadOnlyMT5:
    def __init__(self, module):
        self._module = module

    def __getattr__(self, name):
        if name not in READ_ONLY:
            raise PermissionError(f"MT5 function {name!r} is not permitted by this read-only tool.")
        return getattr(self._module, name)


def _record(row, fields):
    if hasattr(row, "_asdict"):
        data = row._asdict()
    elif isinstance(row, Mapping):
        data = row
    else:
        data = vars(row)
    return {key: data.get(key) for key in fields}


def _quote_before(mt5, time_msc):
    start = datetime.fromtimestamp((time_msc - QUOTE_LOOKBACK_MS) / 1000, timezone.utc)
    end = datetime.fromtimestamp(time_msc / 1000 + 1, timezone.utc)
    ticks = mt5.copy_ticks_range(SYMBOL, start, end, mt5.COPY_TICKS_ALL)
    best = None
    for tick in ticks if ticks is not None else ():
        stamp, bid, ask = int(tick["time_msc"]), float(tick["bid"]), float(tick["ask"])
        if stamp <= time_msc and 0 < bid <= ask:
            best = (stamp, bid, ask)
    return best


def _boundaries(values, offset_hours=None):
    """Return (utc_text, server_label_ms, offset_record) per boundary. Without an
    explicit offset, the measured Phase 6.11 rule is used and recorded as such."""
    labels = []
    for value in values or ():
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise VerificationError("Boundaries must carry an explicit UTC offset.")
        measured = server_clock.offset_hours(moment)
        hours = measured if offset_hours is None else offset_hours
        utc_ms = int(moment.timestamp() * 1000)
        labels.append((moment.astimezone(timezone.utc).isoformat(), utc_ms + hours * 3_600_000, {
            "offset_hours": hours,
            "offset_source": "measured_rule" if offset_hours is None else "explicit",
            "measured_rule_offset_hours": measured,
            "matches_measured_rule": hours == measured,
        }))
    return labels


MT5_SUCCESS = 1
# Planned protective stops from docs/evidence/manual-demo-trades.md:
# (trades, volume, stop distance in price, loss cap in USD).
PLANNED_STOPS = (
    ("1-6", "0.01", "2.50", "3"), ("7", "0.02", "1.20", "3"), ("8", "0.03", "0.70", "3"),
    ("9", "0.01", "1.00", "3"), ("10-11", "0.01", "4.50", "5"),
)
MAX_ENTRY_SPREAD = Decimal("0.60")


def _history(mt5, query, start, end):
    """MT5 may report an empty history as None with a success code; any other
    None is a failed read."""
    rows = query(start, end)
    if rows is not None:
        return rows
    code = mt5.last_error()
    if code and code[0] == MT5_SUCCESS:
        return ()
    raise VerificationError("MT5 history request failed.")


def planned_stop_check(economics):
    """Check each planned stop against MT5 order mechanics at the current spread.

    The stop distance is measured from the entry price: the ask for a BUY,
    the bid for a SELL. A BUY's stop triggers when the bid reaches it, and a
    SELL's when the ask does, so the exit-side price must move
    ``distance - spread`` to trigger. The broker minimum applies to that
    trigger distance. The loss at an exact stop fill is
    ``distance * contract * volume``, because the spread was already paid at
    entry. Slippage adds to it, and a gap or fast market can exceed it.
    """
    try:
        point = Decimal(str(economics["point"]))
        contract = Decimal(str(economics["trade_contract_size"]))
        minimum = int(economics["trade_stops_level"]) * point
        spread = int(economics["spread"]) * point
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return {"status": "UNKNOWN_SPECIFICATION", "trades": []}
    rows = []
    for trades, volume, distance, cap in PLANNED_STOPS:
        distance, volume, cap = Decimal(distance), Decimal(volume), Decimal(cap)
        trigger = distance - spread
        loss = (distance * contract * volume).quantize(Decimal("0.01"), ROUND_CEILING)
        reasons = [code for code, failed in (
            ("TRIGGER_NOT_BEYOND_SPREAD", trigger <= 0),
            ("BELOW_BROKER_MINIMUM_STOP", trigger < minimum),
            ("EXCEEDS_LOSS_CAP", loss > cap),
            ("SPREAD_ABOVE_ENTRY_LIMIT", spread > MAX_ENTRY_SPREAD),
        ) if failed]
        rows.append({"trades": trades, "volume": str(volume),
                     "stop_distance_from_entry": str(distance),
                     "exit_side_trigger_distance": str(trigger),
                     "loss_at_exact_stop_fill_usd": str(loss), "loss_cap_usd": str(cap),
                     "slippage_allowance_usd": str(cap - loss),
                     "ok": not reasons, "reasons": reasons})
    return {"status": "OK" if all(r["ok"] for r in rows) else "ATTENTION",
            "broker_minimum_stop_distance": str(minimum), "current_spread": str(spread),
            "trades": rows,
            "note": "Read-time estimate. Losses exclude slippage; a stop does not guarantee its "
                    "price in a gap or fast market."}


DEAL_CORRECTION = 5
ARCHIVED_DEALS_COMMENT = "Archived deals"
AMOUNT_FIELDS = ("profit", "commission", "swap", "fee")
ARCHIVED_DEALS_WARNING = (
    "An Exness 'Archived deals' correction is present. Its recorded amounts are zero, but "
    "historical completeness cannot be independently established from the MT5 ledger alone: "
    "archived history may be absent from what the terminal returns."
)


def archived_deals_entry(deal, comment):
    """Describe a type-5 correction whose comment is exactly 'Archived deals'.

    Returns None for any other deal. ``accepted`` is true only when every
    amount field is exactly zero. Only this exact comment is ever exported.
    """
    if deal.get("type") != DEAL_CORRECTION or comment != ARCHIVED_DEALS_COMMENT:
        return None
    amounts = {k: str(Decimal(str(deal.get(k) if deal.get(k) is not None else 0)))
               for k in AMOUNT_FIELDS}
    zero = all(Decimal(v) == 0 for v in amounts.values())
    return {"ticket": deal.get("ticket"), "time_msc": deal.get("time_msc"),
            "type": DEAL_CORRECTION, "comment": comment, "amounts": amounts,
            "accepted": zero, "reason": None if zero else "NONZERO_AMOUNT"}


def _opening_equity(boundary, issues, account, deals, ledger_reconciled, archived=()):
    """Fail closed. UNRESOLVED if anything could make equity differ from the
    reconstructed balance. CONDITIONAL if the only remaining concern is an
    accepted 'Archived deals' correction. SUPPORTED otherwise."""
    accepted = {e["ticket"] for e in archived if e["accepted"]}
    reasons = []
    if boundary["positions_open_across_boundary"]:
        reasons.append("POSITION_OPEN_ACROSS_BOUNDARY")
    if any(i["issue"] in ("MISSING_ENTRY", "UNSUPPORTED_POSITION_SHAPE") for i in issues):
        reasons.append("INCOMPLETE_POSITION_HISTORY")
    if any(d["type"] not in (DEAL_BUY, DEAL_SELL, DEAL_BALANCE) and d["ticket"] not in accepted
           for d in deals):
        reasons.append("UNVERIFIED_LEDGER_ENTRY_TYPE")
    if not ledger_reconciled:
        reasons.append("LEDGER_DOES_NOT_SUM_TO_BALANCE")
    if getattr(account, "margin", None) != 0:
        reasons.append("POSITIONS_OPEN_AT_COLLECTION")
    if getattr(account, "credit", None) not in (0, 0.0):
        reasons.append("NONZERO_OR_UNKNOWN_CREDIT")
    conditions = ["ARCHIVED_DEALS_CORRECTION_PRESENT"] if accepted else []
    if reasons:
        status = "UNRESOLVED"
    elif conditions:
        status = "CONDITIONAL"
    else:
        status = "SUPPORTED"
    return {"status": status, "reasons": reasons, "conditions": conditions,
            "warnings": [ARCHIVED_DEALS_WARNING] if accepted else []}


def collect(mt5, profile, *, start, boundaries=(), quotes=True, discover=running_terminals,
            clock=lambda: datetime.now(timezone.utc)):
    """Read every deal and order from ``start`` (minus a margin) to the present."""
    window_start = start - HISTORY_MARGIN
    first_label_ms = int(window_start.timestamp() * 1000)
    if any(label < first_label_ms for _, label, _ in boundaries):
        raise VerificationError("A risk-day boundary precedes the history window; move --from earlier.")
    mt5 = ReadOnlyMT5(mt5)
    try:
        require_running_terminal(profile.terminal, discover())
        try:
            if not mt5.initialize(str(profile.terminal), timeout=5000):
                raise VerificationError("Read-only MT5 attachment failed.")
            observed = clock()
            _, account = check_identity(mt5, profile)
            symbol = mt5.symbol_info(SYMBOL)
            if getattr(symbol, "name", None) != SYMBOL or getattr(symbol, "custom", None) is not False:
                raise VerificationError("The exact non-custom XAUUSD symbol is unavailable.")
            window_end = observed + HISTORY_MARGIN
            deals, archived = [], []
            for row in _history(mt5, mt5.history_deals_get, window_start, window_end):
                deal = _record(row, DEAL_FIELDS)
                deals.append(deal)
                entry = archived_deals_entry(deal, _record(row, ("comment",))["comment"])
                if entry is not None:
                    archived.append(entry)
            orders = {o["ticket"]: o for o in (
                _record(row, ORDER_FIELDS)
                for row in _history(mt5, mt5.history_orders_get, window_start, window_end)
            )}
            nearby = {}
            if quotes:
                for deal in deals:
                    if deal["type"] in (DEAL_BUY, DEAL_SELL) and deal["symbol"] == SYMBOL:
                        found = _quote_before(mt5, deal["time_msc"])
                        if found is not None:
                            nearby[deal["ticket"]] = (deal["time_msc"],) + found
            _, final = check_identity(mt5, profile)
            if final.login != account.login:
                raise VerificationError("The account changed during collection.")
            if (getattr(final, "balance", None), getattr(final, "credit", None)) != (
                    account.balance, getattr(account, "credit", None)):
                raise VerificationError("Balance or credit changed during collection; "
                                        "read again with no trading activity.")
        finally:
            mt5.shutdown()
    except VerificationError:
        raise
    except Exception:
        raise VerificationError("MT5 read failed while inspecting the selected session.") from None

    economics = _record(symbol, SYMBOL_FIELDS)
    start_offset = server_clock.offset_hours(start)
    start_label_ms = int(start.timestamp() * 1000) + start_offset * 3_600_000
    fresh ={k: (b, a) for k, (fill, t, b, a) in nearby.items() if fill - t <= MAX_QUOTE_AGE_MS}
    result = reconcile(deals, contract_size=economics["trade_contract_size"],
                       tick_size=economics["trade_tick_size"], quotes=fresh)
    timing = {}
    for deal in deals:
        if deal["type"] not in (DEAL_BUY, DEAL_SELL):
            continue
        order = orders.get(deal["order"])
        quote = nearby.get(deal["ticket"])
        timing[str(deal["ticket"])] = {
            "order_ticket": deal["order"],
            "order_found": order is not None,
            "order_time_setup_msc": order and order["time_setup_msc"],
            "order_price_open": order and order["price_open"],
            "deal_time_msc": deal["time_msc"],
            "request_to_execution_ms": order and deal["time_msc"] - order["time_setup_msc"],
            "prior_quote": None if quote is None else {
                "tick_time_msc": quote[1], "bid": quote[2], "ask": quote[3],
                "age_ms": quote[0] - quote[1], "used": deal["ticket"] in fresh,
                "side_compared": "ask" if deal["type"] == DEAL_BUY else "bid",
            },
        }
    window_sum = sum((_amount(d) for d in deals), Decimal(0))
    reconciled = window_sum == Decimal(str(account.balance))
    return {
        "observed_utc": observed.isoformat(),
        "server": profile.server,
        "company": account.company,
        "mode": "demo",
        "symbol": SYMBOL,
        "history_window_labels": [window_start.isoformat(), window_end.isoformat()],
        "account_snapshot": {k: getattr(account, k, None) for k in ACCOUNT_FIELDS},
        "ledger_check": {
            "sum_of_window_deals": str(window_sum),
            "account_balance": str(Decimal(str(account.balance))),
            "sums_to_current_balance": reconciled,
            "note": "True means the window's deals sum exactly to the current balance, so there is "
                    "no aggregate discrepancy. It cannot prove every historical entry is present: "
                    "omitted entries whose effects cancel leave the sum unchanged.",
        },
        "symbol_economics": economics,
        "planned_stop_check": planned_stop_check(economics),
        "deal_count": len(deals),
        "deals": deals,
        "orders": list(orders.values()),
        "archived_deals_corrections": archived,
        "fill_timing": timing,
        "max_quote_age_ms": MAX_QUOTE_AGE_MS,
        "reconciliation": result,
        "protocol_check": dict(
            protocol_check(deals, orders, start_msc=start_label_ms,
                           now_msc=int(observed.timestamp() * 1000) + start_offset * 3_600_000,
                           contract_size=economics["trade_contract_size"]),
            experiment_start_label_ms=start_label_ms, limits_source="docs/evidence/manual-demo-trades.md"),
        "risk_day_boundaries": [
            dict(boundary, boundary_utc=utc, offset=offset,
                 opening_equity=_opening_equity(boundary, result["issues"], account, deals,
                                                reconciled, archived))
            for utc, label, offset in boundaries
            for boundary in (balance_at(deals, label, current_balance=account.balance),)
        ],
        "time_note": "Deal, order and tick times are raw server-clock labels. Use the archive "
                     "clock-offset result to map them to UTC.",
    }


def _amount(deal):
    return sum(Decimal(str(deal.get(k) or 0)) for k in ("profit", "commission", "swap", "fee"))


def _day(text):
    return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="start", type=_day, required=True,
                        help="YYYY-MM-DD; history is read from one day earlier to the present")
    parser.add_argument("--output", type=Path, required=True, help="new JSON file")
    parser.add_argument("--boundary-utc", action="append",
                        help="risk-day boundary such as 2026-11-24T00:00:00Z (repeatable)")
    parser.add_argument("--server-offset-hours", type=int,
                        help="override the measured offset rule (server label minus UTC); "
                             "the output records whether it matches the rule")
    parser.add_argument("--no-quotes", action="store_true")
    parser.add_argument("--exposure-log", type=Path, default=exposure_log.DEFAULT_LOG)
    args = parser.parse_args(argv)
    try:
        exposure_log.verify(args.exposure_log)
        boundaries = _boundaries(args.boundary_utc, args.server_offset_hours)
        profile = DemoProfile.from_environment(os.environ)
        import MetaTrader5 as mt5

        evidence = collect(mt5, profile, start=args.start, boundaries=boundaries,
                           quotes=not args.no_quotes)
        payload = (json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
        with args.output.open("xb") as output:
            output.write(payload)
        exposure_log.append(
            path=args.exposure_log, source=f"Exness MT5 demo deal history ({evidence['server']})",
            sha256_digest=sha256(payload).hexdigest(),
            coverage_utc=[evidence["history_window_labels"][0], evidence["observed_utc"]],
            purpose="Manual demo experiment ledger read", tool="tools.read_demo_deals_611")
    except (VerificationError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps({"reconciliation": evidence["reconciliation"]["summary"],
                      "protocol_compliant": evidence["protocol_check"]["compliant"],
                      "violations": evidence["protocol_check"]["violations"]},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
