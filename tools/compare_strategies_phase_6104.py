"""Compare frozen entry signals under the same offline OHLC assumptions."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from goldbot.backtesting.historical_replay import ClosedEvent, ORIGINAL_DIGESTS, load_replay
from goldbot.backtesting.research_phase_6_8_5 import _simulate, _spec, _summary
from goldbot.backtesting.sensitivity_analysis import SCENARIOS
from goldbot.strategy.strategy import Signal


LEDGER_SHA256 = "2e5d0a7230beaa3839babbf47acdb8fd3f43d603ed9af6700a961bc1e470c60e"
ROOT = Path(__file__).resolve().parents[1]
BASELINE_REPORT = ROOT / "reports/research_phase_6_8_5/results.json"


def candidate_replay(replay, rows, candidate):
    events = iter(replay.events)
    projected = []
    for row in rows:
        opening, close = next(events), next(events)
        if (not isinstance(close, ClosedEvent)
                or (row["row"], row["raw_label"], row["raw_label_delta"], row["gap_before"])
                != (close.source_row, close.raw_server_clock_label,
                    close.raw_label_delta, close.gap_before)):
            raise ValueError("Candidate ledger row does not match replay")
        status = row["decisions"][candidate]
        decision = status if status in ("BUY", "SELL") else "HOLD"
        reason = f"{decision}_SETUP" if decision in ("BUY", "SELL") else status
        projected.extend((opening, replace(close, signal=Signal(decision, (reason,)))))
    if next(events, None) is not None:
        raise ValueError("Candidate ledger ended early")
    return replace(replay, events=tuple(projected))


def build(ledger_path):
    source = ledger_path.read_bytes()
    if sha256(source).hexdigest() != LEDGER_SHA256:
        raise ValueError("Phase 6.10.3 ledger digest mismatch")
    ledger = json.loads(source)
    archive = BASELINE_REPORT.read_bytes()
    baseline = json.loads(archive)["timeframes"]
    results = {}
    for frame, digest in ORIGINAL_DIGESTS.items():
        replay = load_replay(ROOT / f"data/XAUUSD_{frame}.csv", frame,
                             expected_sha256=digest, expected_rows=10000)
        frame_ledger = ledger["timeframes"][frame]
        results[frame] = {}
        variants = {"baseline": replay}
        for candidate in frame_ledger["counts"]:
            variants[candidate] = candidate_replay(replay, frame_ledger["rows"], candidate)
        for candidate, variant in variants.items():
            signals = Counter(event.signal.decision for event in variant.events[1::2])
            summaries = {}
            for scenario, _ in SCENARIOS:
                result = _simulate(variant, _spec(scenario, frame))
                summary = _summary(result)
                if "INVALID_SIGNAL" in summary["entry_rejections"]:
                    raise ValueError(f"Invalid replay signal for {frame}/{candidate}/{scenario}")
                if candidate == "baseline":
                    actual = json.loads(json.dumps(summary, default=str))
                    if actual != baseline[frame][scenario]:
                        raise ValueError(f"Frozen baseline diverged for {frame}/{scenario}")
                summaries[scenario] = summary
            results[frame][candidate] = dict(signals=dict(signals), scenarios=summaries)
    return dict(mode="RETROSPECTIVE_RESEARCH", readiness_decision="NO-GO",
                ledger_sha256=LEDGER_SHA256, baseline_sha256=sha256(archive).hexdigest(),
                timeframes=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.dumps(build(args.ledger), default=str, sort_keys=True,
                         indent=2, allow_nan=False)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(payload + "\n")


if __name__ == "__main__":
    main()
