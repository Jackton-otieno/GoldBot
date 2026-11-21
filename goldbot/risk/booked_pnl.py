"""Reconcile broker-booked deal P/L against XAUUSD contract arithmetic.

Input rows are MT5 deal records as plain mappings (``deal._asdict()``).
Every value is converted through ``str`` into ``Decimal`` so the comparison
uses the exact decimal values the terminal reported.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from goldbot.risk.risk_config import SYMBOL


D = Decimal
CENT = D("0.01")
DEAL_BUY, DEAL_SELL = 0, 1
ENTRY_IN, ENTRY_OUT, ENTRY_INOUT, ENTRY_OUT_BY = 0, 1, 2, 3
ROUNDINGS = {
    "half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN,
    "floor": ROUND_FLOOR, "ceiling": ROUND_CEILING, "truncate": ROUND_DOWN,
}


def _d(value):
    result = D(str(value))
    if not result.is_finite():
        raise ValueError("non-finite deal value")
    return result


def _models(direction, entry, exit_, contract, volume):
    exact = direction * (exit_ - entry) * contract * volume
    models = {"exact": exact}
    models.update({name: exact.quantize(CENT, rule) for name, rule in ROUNDINGS.items()})
    entry_notional = (entry * contract * volume).quantize(CENT, ROUND_HALF_UP)
    exit_notional = (exit_ * contract * volume).quantize(CENT, ROUND_HALF_UP)
    models["cent_rounded_notionals"] = direction * (exit_notional - entry_notional)
    return exact, models


def _fill_slippage(deal_type, price, quote):
    """Fill minus the same-side quote last observed before it (ask for buys, bid
    for sells). Positive is adverse. This is a quote comparison, not proof of
    the price the server received the request at. quote is (bid, ask)."""
    if quote is None:
        return None
    bid, ask = map(_d, quote)
    return price - ask if deal_type == DEAL_BUY else bid - price


def reconcile(deals, *, contract_size, tick_size, quotes=None, symbol=SYMBOL):
    """Return per-exit reconciliation rows, non-trading ledger rows and issues."""
    contract, tick = _d(contract_size), _d(tick_size)
    if contract <= 0 or tick <= 0:
        raise ValueError("contract and tick size must be positive")
    quotes = quotes or {}
    positions = defaultdict(list)
    ledger, issues = [], []
    for row in deals:
        if not isinstance(row, Mapping):
            raise ValueError("deal rows must be mappings")
        if row.get("type") not in (DEAL_BUY, DEAL_SELL):
            ledger.append({"ticket": row.get("ticket"), "type": row.get("type"),
                           "time_msc": row.get("time_msc"), "amount": str(_d(row.get("profit", 0)))})
            continue
        if row.get("symbol") != symbol:
            issues.append({"ticket": row.get("ticket"), "issue": "OTHER_SYMBOL"})
            continue
        positions[row.get("position_id")].append(row)

    exits = []
    for position_id, rows in sorted(positions.items(), key=lambda kv: min(r["time_msc"] for r in kv[1])):
        rows = sorted(rows, key=lambda r: (r["time_msc"], r["ticket"]))
        entries = [r for r in rows if r.get("entry") == ENTRY_IN]
        outs = [r for r in rows if r.get("entry") == ENTRY_OUT]
        other = [r for r in rows if r.get("entry") not in (ENTRY_IN, ENTRY_OUT)]
        if not entries and outs and not other:
            # The opening deal precedes the queried window, so the ledger is incomplete here.
            issues.append({"position_id": position_id, "issue": "MISSING_ENTRY"})
            continue
        if len(entries) != 1 or other:
            issues.append({"position_id": position_id, "issue": "UNSUPPORTED_POSITION_SHAPE"})
            continue
        opening = entries[0]
        direction = 1 if opening["type"] == DEAL_BUY else -1
        entry_price, open_volume = _d(opening["price"]), _d(opening["volume"])
        closed = sum((_d(r["volume"]) for r in outs), D(0))
        if closed > open_volume:
            issues.append({"position_id": position_id, "issue": "OVERCLOSED"})
            continue
        for out in outs:
            if out["type"] == opening["type"]:
                issues.append({"position_id": position_id, "issue": "EXIT_SAME_SIDE"})
                continue
            exit_price, volume = _d(out["price"]), _d(out["volume"])
            exact, models = _models(direction, entry_price, exit_price, contract, volume)
            booked = _d(out["profit"])
            ticks = abs(exit_price - entry_price) / tick
            exits.append({
                "position_id": position_id,
                "side": "BUY" if direction == 1 else "SELL",
                "entry_ticket": opening["ticket"], "exit_ticket": out["ticket"],
                "entry_time_msc": opening["time_msc"], "exit_time_msc": out["time_msc"],
                "entry_price": str(entry_price), "exit_price": str(exit_price),
                "volume": str(volume), "entry_volume": str(open_volume),
                "partial": volume != open_volume,
                "price_ticks": str(ticks.normalize()),
                "exact_usd": str(exact), "booked_usd": str(booked),
                "booked_minus_exact": str(booked - exact),
                "matching_models": sorted(name for name, value in models.items() if value == booked),
                "implied_usd_per_tick_per_lot": (
                    str((abs(booked) / (ticks * volume)).normalize()) if ticks and booked else None),
                "entry_commission": str(_d(opening.get("commission", 0))),
                "exit_commission": str(_d(out.get("commission", 0))),
                "entry_fee": str(_d(opening.get("fee", 0))),
                "exit_fee": str(_d(out.get("fee", 0))),
                "swap": str(_d(out.get("swap", 0))),
                "entry_vs_prior_quote": _str(_fill_slippage(opening["type"], entry_price,
                                                            quotes.get(opening["ticket"]))),
                "exit_vs_prior_quote": _str(_fill_slippage(out["type"], exit_price,
                                                           quotes.get(out["ticket"]))),
            })
        if closed < open_volume:
            issues.append({"position_id": position_id, "issue": "STILL_OPEN",
                           "open_volume": str(open_volume - closed)})
    return {"exits": exits, "ledger": ledger, "issues": issues, "summary": summarize(exits)}


def _str(value):
    return None if value is None else str(value)


def summarize(exits):
    models = Counter(name for e in exits for name in e["matching_models"])
    per_deal = {}
    for e in exits:
        per_deal[e["entry_ticket"]] = (_d(e["entry_commission"]), _d(e["entry_volume"]))
        per_deal[e["exit_ticket"]] = (_d(e["exit_commission"]), _d(e["volume"]))
    commissions = Counter(str((c / v).normalize()) for c, v in per_deal.values() if v)
    slips = [_d(e[k]) for e in exits for k in ("entry_vs_prior_quote", "exit_vs_prior_quote")
             if e[k] is not None]
    return {
        "exits": len(exits),
        "partial_exits": sum(e["partial"] for e in exits),
        "models_matching_every_exit": sorted(n for n, c in models.items() if c == len(exits)) if exits else [],
        "model_match_counts": dict(sorted(models.items())),
        "implied_usd_per_tick_per_lot": sorted({e["implied_usd_per_tick_per_lot"] for e in exits} - {None}),
        "commission_per_lot_by_deal": dict(sorted(commissions.items())),
        "nonzero_swaps": [{"position_id": e["position_id"], "swap": e["swap"]}
                          for e in exits if _d(e["swap"])],
        "fees_total": str(sum((_d(e["entry_fee"]) + _d(e["exit_fee"]) for e in exits), D(0))),
        "sample_note": "Describes these exits only; it does not establish behaviour outside them.",
        "fill_vs_prior_quote": None if not slips else {
            "basis": "fill minus same-side quote last observed before the fill; positive is adverse",
            "fills": len(slips), "adverse_max": str(max(slips)), "favorable_max": str(min(slips)),
            "mean": str((sum(slips) / len(slips)).quantize(D("0.0001"))),
            "zero": sum(s == 0 for s in slips),
        },
    }


def _amount(row):
    return sum(_d(row.get(k, 0)) for k in ("profit", "commission", "swap", "fee"))


@dataclass(frozen=True)
class ProtocolLimits:
    """Limits from docs/evidence/manual-demo-trades.md."""
    max_concurrent: int = 1
    max_volume: Decimal = D("0.03")
    short_trade_cap: Decimal = D("3")
    overnight_cap: Decimal = D("5")
    overnight_after_ms: int = 6 * 3_600_000
    experiment_cap: Decimal = D("15")


def _held_over_saturday(open_ms, close_ms):
    day = datetime.fromtimestamp(open_ms // 1000, timezone.utc).date()
    last = datetime.fromtimestamp(close_ms // 1000, timezone.utc).date()
    while day <= last:
        if day.weekday() == 5:
            return True
        day += timedelta(days=1)
    return False


def protocol_check(deals, orders, *, start_msc, now_msc, limits=ProtocolLimits(), symbol=SYMBOL):
    """Check positions opened at or after ``start_msc`` against the experiment limits.

    Times are raw server labels. ``orders`` maps order ticket to its record;
    an entry without a recorded stop, or whose order is missing, is flagged.
    """
    positions = defaultdict(list)
    for row in deals:
        if row.get("type") in (DEAL_BUY, DEAL_SELL) and row.get("symbol") == symbol:
            positions[row.get("position_id")].append(row)
    rows, violations = [], []
    for position_id, group in positions.items():
        group.sort(key=lambda r: (r["time_msc"], r["ticket"]))
        entries = [r for r in group if r.get("entry") == ENTRY_IN]
        if len(entries) != 1 or entries[0]["time_msc"] < start_msc:
            continue
        entry = entries[0]
        volume = _d(entry["volume"])
        closed = sum((_d(r["volume"]) for r in group if r.get("entry") == ENTRY_OUT), D(0))
        close_ms = group[-1]["time_msc"] if closed >= volume else None
        held_until = close_ms if close_ms is not None else now_msc
        order = orders.get(entry.get("order"))
        stop = None if order is None else order.get("sl")
        net = sum((_amount(r) for r in group), D(0))
        overnight = held_until - entry["time_msc"] >= limits.overnight_after_ms
        cap = limits.overnight_cap if overnight else limits.short_trade_cap
        rows.append({
            "position_id": position_id, "open_msc": entry["time_msc"], "close_msc": close_ms,
            "volume": str(volume), "stop_at_entry": stop, "order_found": order is not None,
            "net_usd": str(net) if close_ms is not None else None, "overnight": overnight,
            "loss_cap_usd": str(cap),
            "weekend_hold": _held_over_saturday(entry["time_msc"], held_until),
        })
    rows.sort(key=lambda r: r["open_msc"])

    events = sorted([(r["open_msc"], 1) for r in rows]
                    + [(r["close_msc"], -1) for r in rows if r["close_msc"] is not None],
                    key=lambda e: (e[0], e[1]))
    concurrent = peak = 0
    for _, step in events:
        concurrent += step
        peak = max(peak, concurrent)

    running, low, cap_time = D(0), D(0), None
    for row in sorted((r for r in rows if r["close_msc"] is not None), key=lambda r: r["close_msc"]):
        running += _d(row["net_usd"])
        low = min(low, running)
        if cap_time is None and running <= -limits.experiment_cap:
            cap_time = row["close_msc"]
    after_cap = [r["position_id"] for r in rows if cap_time is not None and r["open_msc"] > cap_time]

    def flag(code, items):
        if items:
            violations.append({"code": code, "positions": items})

    if peak > limits.max_concurrent:
        violations.append({"code": "CONCURRENT_POSITIONS", "peak": peak})
    flag("VOLUME_LIMIT", [r["position_id"] for r in rows if _d(r["volume"]) > limits.max_volume])
    flag("STOP_UNVERIFIED", [r["position_id"] for r in rows if not r["order_found"]])
    flag("ENTRY_WITHOUT_STOP", [r["position_id"] for r in rows if r["order_found"] and not r["stop_at_entry"]])
    flag("WEEKEND_HOLD", [r["position_id"] for r in rows if r["weekend_hold"]])
    flag("PER_TRADE_CAP_EXCEEDED", [r["position_id"] for r in rows if r["net_usd"] is not None
                                    and _d(r["net_usd"]) < -_d(r["loss_cap_usd"])])
    flag("TRADED_AFTER_LOSS_CAP", after_cap)
    return {
        "positions": rows,
        "max_concurrent_positions": peak,
        "cumulative_net_usd": str(running),
        "lowest_cumulative_net_usd": str(low),
        "experiment_cap_reached": cap_time is not None,
        "still_open": [r["position_id"] for r in rows if r["close_msc"] is None],
        "violations": violations,
        "compliant": not violations,
    }


def balance_at(deals, boundary_msc, *, current_balance=None):
    """Balance at a raw boundary and whether any position was open across it.

    With ``current_balance`` (read at collection time from a window that runs
    to the present), the result is that balance minus every later deal, which
    needs no history before the boundary. Without it, the result is the sum of
    the supplied deals before the boundary and is only correct when they start
    at the account's first deposit. Equity equals balance only when no position
    was open across the boundary; callers must not treat it as opening equity
    otherwise.
    """
    ordered = sorted(deals, key=lambda r: (r["time_msc"], r["ticket"]))
    before = sum((_amount(r) for r in ordered if r["time_msc"] < boundary_msc), D(0))
    after = sum((_amount(r) for r in ordered if r["time_msc"] >= boundary_msc), D(0))
    volume = defaultdict(D)
    for row in ordered:
        if row["time_msc"] >= boundary_msc:
            break
        if row.get("type") in (DEAL_BUY, DEAL_SELL):
            sign = 1 if row.get("entry") == ENTRY_IN else -1
            volume[row.get("position_id")] += sign * _d(row["volume"])
    open_positions = sorted(str(p) for p, v in volume.items() if v > 0)
    if current_balance is None:
        balance, method = before, "sum_of_supplied_deals_before_boundary"
    else:
        balance, method = _d(current_balance) - after, "current_balance_minus_later_deals"
    return {"boundary_time_msc": boundary_msc, "balance": str(balance), "method": method,
            "positions_open_across_boundary": open_positions,
            "equity_equals_balance": not open_positions}
