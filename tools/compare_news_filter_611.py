"""Compare the frozen Phase 6.10.4 runs with a news-filtered research variant.

Inputs are unchanged: the same validated M15/H1 candles, the same Phase
6.10.3 entry signals, the same four cost scenarios and the same sizing,
stops and exits. The only difference in the filtered variant is that a
directional signal whose entry (the next candle's open, converted from
server labels to UTC) is refused by the point-in-time news calendar becomes
HOLD. Signals only ever open positions, so existing positions keep their
normal stops and targets. The unfiltered runs are recomputed and must equal
the archived Phase 6.10.4 results exactly, or the comparison stops.

Research only. Self-tested, not independently validated. It changes no
frozen strategy and grants no trading authority.
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from goldbot.backtesting.historical_replay import ClosedEvent, ORIGINAL_DIGESTS, OpenEvent, load_replay
from goldbot.backtesting.research_phase_6_8_5 import _simulate, _spec, _summary
from goldbot.backtesting.sensitivity_analysis import SCENARIOS
from goldbot.core import server_clock
from goldbot.research.news_calendar import NewsCalendar
from goldbot.strategy.strategy import Signal
from tools.compare_strategies_phase_6104 import LEDGER_SHA256, candidate_replay


ROOT = Path(__file__).resolve().parents[1]
ARCHIVED_6104 = ROOT / "reports/phase_6_10_4/comparison.json"
ARCHIVED_6104_SHA256 = "4829ae1bb824ac289a3328b92ad2bccb99c78d2b883a548fb24d9e08064dc5df"


def label_to_utc(label_seconds):
    """Server label (seconds) to UTC using the measured offset rule."""
    for hours in (3, 2):
        moment = datetime.fromtimestamp(label_seconds - hours * 3600, timezone.utc)
        if server_clock.offset_hours(moment) == hours:
            return moment
    raise ValueError(f"Label {label_seconds} has no consistent server offset.")


def apply_news_filter(replay, calendar):
    """Return (filtered replay, blocked-entry records, decision counts)."""
    events = list(replay.events)
    blocked, counts = [], Counter()
    for index in range(1, len(events), 2):
        close = events[index]
        if not isinstance(close, ClosedEvent) or close.signal.decision not in ("BUY", "SELL"):
            continue
        if index + 1 >= len(events):
            counts["TERMINAL_SIGNAL_NOT_EVALUATED"] += 1
            continue
        entry = events[index + 1]
        if not isinstance(entry, OpenEvent):
            raise ValueError("Replay events must alternate open and close.")
        moment = label_to_utc(entry.raw_server_clock_label)
        decision = calendar.decide(moment)
        counts[decision.reason] += 1
        if decision.allowed:
            continue
        events[index] = replace(close, signal=Signal("HOLD", (decision.reason,)))
        blocked.append({
            "signal_row": close.source_row, "entry_row": entry.source_row,
            "entry_server_label": entry.raw_server_clock_label, "entry_utc": moment.isoformat(),
            "side": close.signal.decision, "reason": decision.reason,
            "events": [{k: e[k] for k in ("event", "reference", "scheduled_utc", "source", "capture_utc")}
                       for e in decision.events],
            "calendar_problems": [{"code": c, "source": s} for c, s in decision.problems],
        })
    return replace(replay, events=tuple(events)), blocked, dict(counts)


def _key(summary):
    return {
        "terminal_marked_pnl": str(summary["terminal_marked_pnl"]),
        "entries": summary["entries"],
        "closed_trades": len(summary["closed_trades"]),
        "exit_reasons": summary["exit_reasons"],
        "max_drawdown_usd": str(summary["max_drawdown"]["drawdown"]["value"]),
        "entry_rejections": summary["entry_rejections"],
    }


def build(ledger_path, calendar_path):
    source = Path(ledger_path).read_bytes()
    if sha256(source).hexdigest() != LEDGER_SHA256:
        raise ValueError("Phase 6.10.3 ledger digest mismatch.")
    archived_bytes = ARCHIVED_6104.read_bytes()
    if sha256(archived_bytes).hexdigest() != ARCHIVED_6104_SHA256:
        raise ValueError("Archived Phase 6.10.4 comparison digest mismatch.")
    archived = json.loads(archived_bytes)["timeframes"]
    calendar_bytes = Path(calendar_path).read_bytes()
    calendar = NewsCalendar(json.loads(calendar_bytes))
    ledger = json.loads(source)
    results = {}
    for frame, digest in ORIGINAL_DIGESTS.items():
        replay = load_replay(ROOT / f"data/XAUUSD_{frame}.csv", frame,
                             expected_sha256=digest, expected_rows=10000)
        frame_ledger = ledger["timeframes"][frame]
        variants = {"baseline": replay}
        for candidate in frame_ledger["counts"]:
            variants[candidate] = candidate_replay(replay, frame_ledger["rows"], candidate)
        results[frame] = {}
        for candidate, variant in variants.items():
            filtered, blocked, decisions = apply_news_filter(variant, calendar)
            scenarios = {}
            for scenario, _ in SCENARIOS:
                spec = _spec(scenario, frame)
                plain = json.loads(json.dumps(_summary(_simulate(variant, spec)), default=str))
                if plain != archived[frame][candidate]["scenarios"][scenario]:
                    raise ValueError(f"Unfiltered run diverged from Phase 6.10.4 for {frame}/{candidate}/{scenario}.")
                news = json.loads(json.dumps(_summary(_simulate(filtered, spec)), default=str))
                if "INVALID_SIGNAL" in news["entry_rejections"]:
                    raise ValueError(f"Invalid filtered signal for {frame}/{candidate}/{scenario}.")
                scenarios[scenario] = {"unfiltered": _key(plain), "news_filtered": _key(news),
                                       "news_filtered_full": news}
            results[frame][candidate] = {
                "directional_signals_evaluated": sum(decisions.values()),
                "calendar_decisions": decisions,
                "blocked_entries": blocked,
                "scenarios": scenarios,
            }
    return {
        "mode": "RETROSPECTIVE_RESEARCH_NEWS_FILTER",
        "label": "Self-tested, not independently validated",
        "readiness_decision": "NO-GO",
        "frozen_strategies_changed": False,
        "inputs": {"ledger_sha256": LEDGER_SHA256, "archived_6104_sha256": ARCHIVED_6104_SHA256,
                   "calendar_sha256": calendar.sha256, "candle_sha256": ORIGINAL_DIGESTS},
        "unfiltered_matches_phase_6104": True,
        "server_time_rule": server_clock.RULE,
        "timeframes": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger", type=Path, default=ROOT / "reports/phase_6_10_3/candidate-signals.json")
    parser.add_argument("--calendar", type=Path, default=ROOT / "historical_data/news_calendar/calendar.json")
    parser.add_argument("--output", type=Path, required=True, help="new JSON file")
    args = parser.parse_args(argv)
    try:
        report = build(args.ledger, args.calendar)
        with args.output.open("x", encoding="utf-8", newline="\n") as target:
            json.dump(report, target, indent=2, sort_keys=True, allow_nan=False)
            target.write("\n")
    except (OSError, ValueError, KeyError) as error:
        print(f"Comparison failed: {error}", file=sys.stderr)
        return 1
    for frame, candidates in report["timeframes"].items():
        for name, data in candidates.items():
            row = data["scenarios"]["baseline"]
            print(f"{frame:3} {name:30} decisions {data['calendar_decisions']}  "
                  f"P/L {row['unfiltered']['terminal_marked_pnl']} -> {row['news_filtered']['terminal_marked_pnl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
