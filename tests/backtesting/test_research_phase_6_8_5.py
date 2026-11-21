"""Offline regressions for the Phase 6.8.5 research runner."""

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from goldbot.backtesting.execution_data_validator import (
    DatasetEvidence, EffectiveSchedule, verify_execution_data,
)
from goldbot.backtesting.historical_replay import Replay, load_replay
from goldbot.backtesting.portfolio_coordinator import RiskBoundary, RiskSchedule
from goldbot.backtesting.research_phase_6_8_5 import ROOT, _simulate, _spec, build_reports
from goldbot.backtesting.strategy_validation import canonical_bytes, sha256
from goldbot.market_data.session_verification import MarketScope, UTCInterval
from goldbot.risk.risk_day_verification import RiskDayScope
from tests.backtesting.test_execution_simulator import candle


def fixture(*pairs):
    return Replay("M15", "fixture", "", False, tuple(event for pair in pairs for event in pair))


class ResearchTests(unittest.TestCase):
    def test_prefix_indicators_and_signals_do_not_use_future_rows(self):
        source = ROOT / "data/XAUUSD_M15.csv"
        full = load_replay(source, "M15")
        with tempfile.TemporaryDirectory() as folder:
            prefix = Path(folder) / "prefix.csv"
            prefix.write_bytes(b"".join(source.read_bytes().splitlines(keepends=True)[:501]))
            short = load_replay(prefix, "M15")
        self.assertEqual(short.events, full.events[:1000])
        spec = _spec("baseline", "M15")
        self.assertEqual(_simulate(short, spec).events, _simulate(full, spec).events[:1000])

    def test_next_open_gap_and_stop_first(self):
        spec = _spec("baseline", "M15")
        first = candle(1, decision="BUY")
        result = _simulate(fixture(first, candle(2, low=90, high=110)), spec)
        self.assertIsNone(result.events[1].entry)
        entry = result.events[2].entry
        self.assertEqual((entry.signal_row, entry.entry_row), (1, 2))
        self.assertEqual(result.events[3].exit.reason, "STOP")
        self.assertTrue(result.events[3].exit.both_touched)
        gap = _simulate(fixture(first, candle(2, gap=True)), spec)
        self.assertEqual(gap.events[2].entry_status, "GAP_ENTRY")
        self.assertIsNone(gap.events[2].entry)
        self.assertEqual(_simulate(fixture(first), spec).terminal.terminal_signal_row, 1)

    def test_gap_stop_latches_for_the_rest_of_run(self):
        spec = _spec("baseline", "M15")
        later = (
            replace(event, raw_server_clock_label=event.raw_server_clock_label + 900)
            for event in candle(4, opening=90)
        )
        result = _simulate(fixture(candle(1, decision="BUY"), candle(2),
                                   candle(3, opening=90, gap=True, decision="BUY"),
                                   tuple(later)), spec)
        gap = result.events[4]
        self.assertEqual(gap.exit.reason, "OPEN_STOP")
        self.assertIn("DAILY_LOSS_LIMIT", gap.flags)
        self.assertEqual(result.events[6].entry_status, "DAILY_LOSS_LIMIT")
        self.assertEqual([event.row for event in result.events if event.boundary], [1])

    def test_missing_label_is_rejected(self):
        opening, closed = candle(1)
        with self.assertRaisesRegex(ValueError, "expected next replay open"):
            _simulate(fixture((replace(opening, raw_server_clock_label=None), closed)),
                      _spec("baseline", "M15"))

    def test_research_inputs_do_not_satisfy_verified_readiness(self):
        source = (ROOT / "data/XAUUSD_M15.csv").read_bytes()
        spec = _spec("baseline", "M15")
        scope = RiskDayScope(MarketScope("fixture", "XAUUSD"), "fixture", "policy")
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        interval = UTCInterval(start, start + timedelta(hours=1))
        schedule = RiskSchedule("M15", spec.evidence, (RiskBoundary(1, "research-full-run"),))

        result = verify_execution_data(
            scope, interval, candle_bytes=source,
            dataset=DatasetEvidence(scope, "M15", sha256(source), "mid", spec.evidence),
            days=(schedule,)
        )
        self.assertFalse(result.ready)
        findings = {(finding.code, finding.subject) for finding in result.findings}
        self.assertIn(("PROVENANCE_UNVERIFIED", "candles"), findings)
        self.assertIn(("COVERAGE_HOLE", "contract_and_tick_economics"), findings)
        self.assertIn(("COVERAGE_HOLE", "policy_risk_days"), findings)

    def test_full_reports_are_deterministic_and_research_scoped(self):
        encode = lambda records: json.dumps(records, default=str, sort_keys=True, allow_nan=False)
        reports = build_reports()
        self.assertEqual(encode(reports), encode(build_reports()))
        assumptions, results = reports["assumptions.json"], reports["results.json"]
        self.assertEqual(sha256(canonical_bytes(assumptions["manifest"])),
                         results["assumptions_sha256"])
        self.assertFalse(assumptions["manifest"]["phase_6_8_4_readiness_snapshot"]["ready"])
        for report in reports.values():
            self.assertEqual(report["mode"], "RESEARCH")
            self.assertFalse(report["verified_historical_execution"])
        for frame, cases in results["timeframes"].items():
            self.assertEqual(set(cases), {"ideal", "low", "baseline", "stress"})
            self.assertEqual(assumptions["manifest"]["sources"][frame]["rows"], 10000)
            for case in cases.values():
                self.assertEqual(case["account"]["starting_balance"], 3000)
                for fill in case["closed_trades"]:
                    position = fill["position"]
                    self.assertEqual(position["entry_row"], position["signal_row"] + 1)
