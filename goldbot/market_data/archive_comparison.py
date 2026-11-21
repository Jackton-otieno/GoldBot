"""Infer the MT5 server-label offset by matching UTC archive candles to MT5 candles.

MT5 returns bar times as raw server-clock labels. If the server clock runs
at UTC+h, the bar starting at UTC instant t carries label t + h hours. For
each UTC day this module tries every candidate h and keeps the one whose
matched bars agree best on OHLC. A day-by-day result exposes any daylight
saving or other offset transition directly from the data.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from goldbot.market_data.exness_archive import PRICE_SCALE, parse_price, price_text


CANDIDATE_HOURS = tuple(range(-4, 5))
MIN_COVERAGE = 0.5


def load_mt5_candles(path):
    """Return {raw_label_seconds: (open, high, low, close)} in thousandths."""
    with Path(path).open(newline="", encoding="ascii") as source:
        reader = csv.DictReader(source)
        if not {"mt5_time_epoch", "open", "high", "low", "close"} <= set(reader.fieldnames or ()):
            raise ValueError("Unexpected MT5 candle export header.")
        return {
            int(row["mt5_time_epoch"]): tuple(parse_price(row[k]) for k in ("open", "high", "low", "close"))
            for row in reader
        }


def _distance(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / 4


def infer_offsets(archive, mt5, *, candidates=CANDIDATE_HOURS):
    """archive: {utc_start_seconds: (o, h, l, c)}; mt5: {label_seconds: (o, h, l, c)}."""
    by_day = defaultdict(list)
    for start in archive:
        by_day[datetime.fromtimestamp(start, timezone.utc).date().isoformat()].append(start)
    days = []
    for day, starts in sorted(by_day.items()):
        scored = []
        for hours in candidates:
            pairs = [(archive[s], mt5[s + hours * 3600]) for s in starts if s + hours * 3600 in mt5]
            if len(pairs) >= MIN_COVERAGE * len(starts):
                scored.append((median(_distance(a, m) for a, m in pairs), hours, len(pairs)))
        if not scored:
            days.append({"utc_date": day, "archive_bars": len(starts), "best_offset_hours": None})
            continue
        scored.sort()
        best, hours, matched = scored[0]
        days.append({
            "utc_date": day,
            "archive_bars": len(starts),
            "matched_bars": matched,
            "best_offset_hours": hours,
            "best_median_ohlc_gap": price_text(round(best)),
            "runner_up_median_ohlc_gap": price_text(round(scored[1][0])) if len(scored) > 1 else None,
        })
    return days


def agreement(archive, mt5, days):
    """Close-price differences using each UTC day's inferred offset, in price units."""
    offsets = {d["utc_date"]: d["best_offset_hours"] for d in days}
    diffs = Counter()
    exact = 0
    for start, bar in archive.items():
        hours = offsets.get(datetime.fromtimestamp(start, timezone.utc).date().isoformat())
        other = None if hours is None else mt5.get(start + hours * 3600)
        if other is None:
            continue
        diffs[abs(bar[3] - other[3])] += 1
        rounded = (bar[3] + 5) // 10 * 10
        exact += rounded == other[3]
    total = sum(diffs.values())
    if not total:
        return {"matched_bars": 0}
    ordered = sorted(diffs.elements())
    return {
        "offset_rule": "each UTC day's best offset",
        "matched_bars": total,
        "close_gap_p50": price_text(ordered[total // 2]),
        "close_gap_p90": price_text(ordered[int(total * .9)]),
        "close_gap_max": price_text(ordered[-1]),
        "share_close_equal_after_rounding_archive_to_cents": round(exact / total, 4),
    }


def summarize(days, archive, mt5):
    offsets = Counter(d["best_offset_hours"] for d in days if d["best_offset_hours"] is not None)
    transitions = []
    previous = None
    for day in days:
        hours = day["best_offset_hours"]
        if hours is None:
            continue
        if previous is not None and hours != previous["best_offset_hours"]:
            transitions.append({"from_date": previous["utc_date"], "to_date": day["utc_date"],
                                "from_hours": previous["best_offset_hours"], "to_hours": hours})
        previous = day
    dominant = offsets.most_common(1)[0][0] if offsets else None
    return {
        "days_with_offset": sum(offsets.values()),
        "days_without_overlap": sum(d["best_offset_hours"] is None for d in days),
        "offset_hours_by_day_count": {str(k): v for k, v in sorted(offsets.items())},
        "transitions": transitions,
        "single_constant_offset": len(offsets) == 1,
        "dominant_offset_hours": dominant,
        "price_agreement": agreement(archive, mt5, days),
        "price_unit_note": f"Archive prices are scaled by {PRICE_SCALE}; MT5 exports carry two decimals.",
    }
