"""Collect a bounded, read-only clock and position-zero/one snapshot."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

from goldbot.core.exness_demo import VerificationError, running_terminals
from tools import diagnose_time as clock
from tools.collect_exness_phase_695 import Reader, clock_sample
from tools.verify_exness_phase_6941 import ntp_probe
from tools.verify_exness_precision_phase_61051 import INSTALLATION, confirmed_profile
from tools.verify_exness_time_history import SERVER, SUFFIX, SYMBOL, bars_evidence


ROOT = Path(__file__).resolve().parents[1]
PERIODS = {"M1": 60, "M15": 900, "H1": 3600}
SOURCES = (
    "docs/phases/phase-6-8-2.md",
    "docs/phases/phase-6-8-3.md",
    "reports/phase_6_9_4/verification.md",
    "reports/phase_6_9_4_1/diagnostic.json",
    "reports/phase_6_9_5/live-summary.json",
    "reports/phase_6_9_6/assessment.json",
    "reports/phase_6_10_5_1/precision-validation.json",
)


def head_evidence(rows, period, before, after):
    if len(rows) > 2:
        raise VerificationError("Bar response exceeded the requested count.")
    evidence = bars_evidence(rows, period, before)
    result = dict(rows=evidence["bars"], status="INSUFFICIENT_BARS")
    if not all(evidence[key] for key in ("ordered", "aligned", "ohlc_valid")):
        return dict(result, status="INVALID_RAW_BARS")
    if len(rows) != 2:
        return result
    closed, current = (bar["raw_open"] for bar in evidence["bars"])
    return dict(result, status="RAW_COORDINATES_ONLY",
                closed_nominal_raw=closed + period,
                closed_by_first_quote=closed + period <= before,
                current_contains_both_quotes=current <= before <= after < current + period,
                raw_label_gap_seconds=current - closed - period)


def sample_quote(reader):
    tick, timing = reader.read(reader.api.symbol_info_tick, SYMBOL)
    return dict(clock_sample(timing), tick=clock.tick_fields(tick),
                connected_before=True, connected_after=True)


def capture(reader, profile, report, pause=time.sleep):
    if (profile.server != SERVER or str(profile.login)[-4:] != SUFFIX
            or profile.terminal.resolve() != INSTALLATION.resolve()):
        raise VerificationError("Expected the exact independently pinned Exness installation and demo.")
    try:
        report["identity"] = reader.attach()
        for index in range(3):
            before = sample_quote(reader)
            report["samples"].append(before)
            captures = {name: reader.read(reader.api.copy_rates_from_pos, SYMBOL,
                                         getattr(reader.api, "TIMEFRAME_" + name), 0, 2)[0]
                        for name in PERIODS}
            after = sample_quote(reader)
            report["samples"].append(after)
            if all(clock.valid_tick(sample["tick"]) for sample in (before, after)):
                first, last = (sample["tick"]["raw_s"] for sample in (before, after))
                report["head_polls"].append({
                    "quote_raw_bracket_s": [first, last],
                    "timeframes": {name: head_evidence(captures[name], period, first, last)
                                   for name, period in PERIODS.items()},
                })
            if index < 2:
                pause(1)
    finally:
        reader.api.shutdown()


def finish(report, first, last):
    samples = report["samples"]
    report["external_clock_probes"] = [first, last]
    report["clock"] = clock.assess_clock(first, last, samples)
    report["quote_state"] = clock.quote_state(samples)
    if report["clock"]["status"] == "UTC_WITHIN_TOLERANCE":
        lower, upper = report["clock"]["correction_bounds_s"]
        for sample in samples:
            tick = sample["tick"]
            if clock.valid_tick(tick):
                raw = tick["raw_ms"] / 1000
                sample["age_s_if_raw_utc"] = [
                    clock.wall(sample["before"]).timestamp() + lower - raw,
                    clock.wall(sample["after"]).timestamp() + upper - raw,
                ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = dict(engineering="COMPLETED", technical_acceptance="BLOCKED", readiness="NO-GO",
                  production_mapping="UNVERIFIED", samples=[], head_polls=[],
                  source_sha256={name: sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in SOURCES})
    profile = None
    try:
        profile = confirmed_profile(sys.stdin)
    except VerificationError as error:
        report["terminal_stop"] = str(error)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        first = ntp_probe()
        try:
            if profile is not None:
                import MetaTrader5 as mt5
                capture(Reader(mt5, profile, running_terminals), profile, report)
        except VerificationError as error:
            report["terminal_stop"] = str(error)
        finally:
            finish(report, first, ntp_probe())
            json.dump(report, output, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")


if __name__ == "__main__":
    main()
