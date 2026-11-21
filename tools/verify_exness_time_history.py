"""Bounded read-only timestamp and history diagnostics for the pinned Exness demo."""

import json
import math
import os
import time
from collections import Counter
from types import SimpleNamespace

from goldbot.core.exness_demo import (
    DemoProfile, KE_COMPANY, SYMBOL, VerificationError, check_identity,
    require_running_terminal, running_terminals,
)
from tools import diagnose_time as clock

SERVER = "ExnessKE-MT5Trial9"
SUFFIX = "9498"
TICK_FIELDS = ("time", "time_msc", "bid", "ask", "flags")
PRICE_FIELDS = ("open", "high", "low", "close")


def bars_evidence(rows, period, raw_anchor):
    bars = [{"raw_open": int(row["time"]),
             **{name: float(row[name]) if math.isfinite(row[name]) else None
                for name in PRICE_FIELDS}} for row in rows]
    labels = [bar["raw_open"] for bar in bars]
    steps = [right - left for left, right in zip(labels, labels[1:])]
    return {
        "bars": bars, "ordered": all(step > 0 for step in steps),
        "aligned": all(label > 0 and label % period == 0 for label in labels),
        "relative_close": all(label + period <= raw_anchor for label in labels),
        "gap_seconds": dict(Counter(step for step in steps if step > period)),
        "ohlc_valid": all(
            all(bar[name] is not None and bar[name] > 0 for name in PRICE_FIELDS)
            and bar["low"] <= min(bar["open"], bar["close"])
            <= max(bar["open"], bar["close"]) <= bar["high"] for bar in bars
        ),
    }


def tick_rows(rows):
    return [clock.tick_fields(SimpleNamespace(**{key: row[key] for key in TICK_FIELDS}))
            for row in rows]


def quote_basis(rows, bar, saturated):
    if not rows or saturated or any(not clock.valid_tick(row) for row in rows):
        return []
    stamps = [row["raw_ms"] for row in rows]
    start = bar["raw_open"] * 1000
    if stamps != sorted(stamps) or not all(start <= stamp < start + 60000 for stamp in stamps):
        return []
    actual = tuple(bar[name] for name in PRICE_FIELDS)
    matches = []
    for side in ("bid", "ask"):
        prices = [row[side] for row in rows]
        if actual == (prices[0], max(prices), min(prices), prices[-1]):
            matches.append(side)
    return matches


def collect(mt5, profile, evidence):
    if profile.server != SERVER or not str(profile.login).endswith(SUFFIX):
        raise VerificationError("The exact pinned demo profile is required.")
    require_running_terminal(profile.terminal, running_terminals())

    def identity():
        terminal, account = check_identity(mt5, profile)
        if account.company != KE_COMPANY or terminal.trade_allowed is not False:
            raise VerificationError("Expected KE entity and disabled Algo Trading.")
        return terminal

    def read(method, *args, limit=None):
        identity()
        result = method(*args)
        error = mt5.last_error()[0] if result is None else None
        identity()
        if limit is not None and result is not None and len(result) > limit:
            raise VerificationError("History response exceeded diagnostic row limit.")
        return result, error

    try:
        if not mt5.initialize(str(profile.terminal), timeout=5000):
            raise VerificationError("Pinned read-only attachment failed.")
        terminal = identity()
        symbol, _ = read(mt5.symbol_info, SYMBOL)
        if getattr(symbol, "name", None) != SYMBOL or getattr(symbol, "custom", None) is not False:
            raise VerificationError("Exact non-custom XAUUSD is unavailable.")
        evidence["identity"] = {"entity": KE_COMPANY, "server": SERVER, "suffix": SUFFIX,
                                "currency": "USD", "mode": "demo", "algo_trading": False,
                                "terminal_build": terminal.build, "chart_mode": symbol.chart_mode}
        for index in range(8):
            before = clock.mark()
            tick, error = read(mt5.symbol_info_tick, SYMBOL)
            evidence["samples"].append({
                "before": before, "after": clock.mark(), "tick": clock.tick_fields(tick) if tick else None,
                "error_code": error, "connected_before": True, "connected_after": True,
            })
            if index < 7:
                time.sleep(1)
        tick = evidence["samples"][-1]["tick"]
        if not tick or not clock.valid_tick(tick):
            return
        anchor = tick["raw_s"]
        history = evidence["history"] = {}
        for name, period in (("M1", 60), ("M15", 900), ("H1", 3600)):
            rows, error = read(mt5.copy_rates_from_pos, SYMBOL, getattr(mt5, "TIMEFRAME_" + name),
                               0 if name == "M1" else 1, 12, limit=12)
            history[name] = {"count": None if rows is None else len(rows), "error_code": error}
            if rows is not None:
                history[name].update(bars_evidence(rows, period, anchor))
        history["M1"]["matching_quote_minute"] = any(
            0 <= anchor - bar["raw_open"] < 60 for bar in history["M1"].get("bars", [])
        )
        rows, error = read(mt5.copy_ticks_from, SYMBOL, anchor, 128, mt5.COPY_TICKS_ALL, limit=128)
        ticks = [] if rows is None else tick_rows(rows)
        history["count_probe"] = {"ticks": ticks, "error_code": error,
                                  "saturated": len(ticks) == 128, "exact_quote_match": tick in ticks}
        closed = [bar for bar in history["M1"].get("bars", []) if bar["raw_open"] + 60 <= anchor]
        if closed:
            bar = closed[-1]
            start = bar["raw_open"]
            rows, error = read(mt5.copy_ticks_range, SYMBOL, start, start + 60,
                               mt5.COPY_TICKS_ALL, limit=4096)
            ticks = [] if rows is None else tick_rows(rows)
            history["range_probe"] = {
                "requested_inclusive_raw_seconds": [start, start + 59], "ticks": ticks, "error_code": error,
                "matching_sample_bases": quote_basis([row for row in ticks if row["raw_s"] < start + 60],
                                                     bar, len(ticks) == 4096),
            }
    finally:
        mt5.shutdown()


def main():
    report = {"status": "UNVERIFIED", "scope": "diagnostic only", "samples": []}
    first = clock.clock_probe()
    try:
        profile = DemoProfile.from_environment(os.environ)
        import MetaTrader5 as mt5
        collect(mt5, profile, report)
    except VerificationError as error:
        report["terminal_failure"] = str(error)
    except Exception as error:
        report["terminal_failure_type"] = type(error).__name__
    last = clock.clock_probe()
    report["external_clock_probes"] = [first, last]
    report["clock"] = clock.assess_clock(first, last, report["samples"])
    report["quote_state"] = clock.quote_state(report["samples"])
    if report["clock"]["status"] == "UTC_WITHIN_TOLERANCE":
        lower, upper = report["clock"]["correction_bounds_s"]
        for sample in report["samples"]:
            if sample["tick"] and clock.valid_tick(sample["tick"]):
                event = sample["tick"]["raw_ms"] / 1000
                sample["age_s_if_raw_utc"] = [
                    clock.wall(sample["before"]).timestamp() + lower - event,
                    clock.wall(sample["after"]).timestamp() + upper - event,
                ]
    print(json.dumps(report, indent=2, allow_nan=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
