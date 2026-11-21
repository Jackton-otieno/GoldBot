"""Summarize hash-chained diagnostic events without connecting to MT5."""

import json
import sqlite3
from collections import Counter
from contextlib import closing

from tools import collect_exness_phase_695 as collector


def summarize(path, scope):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        manifest = collector.Journal(db, read_only=True, scope=scope).manifest()
        events = [json.loads(row[0]) for row in db.execute(
            "SELECT body FROM events ORDER BY seq"
        )]
    counts = Counter(event["kind"] for event in events)
    contents = {}
    quotes = []
    bars = {frame: {"reads": 0, "returned": 0, "excluded_pre_attachment": 0,
                    "admitted_observations": 0, "raw_boundaries": set(), "payload_hashes": set()}
            for frame in collector.FRAMES}
    clock = {}
    finish = None
    for event in events:
        data = event["data"]
        objects = data["objects"]
        for item in objects:
            if "raw" in item:
                contents[item["sha256"]] = item["raw"]
        kind = event["kind"]
        if kind == "quote_snapshot":
            quotes.append(contents[objects[0]["sha256"]]["fields"]["time"])
        elif kind == "bars":
            frame = data["frame"]
            entry = bars[frame]
            entry["reads"] += 1
            entry["returned"] += data["returned"]
            entry["excluded_pre_attachment"] += data["excluded_pre_attachment_close_count"]
            entry["admitted_observations"] += len(objects)
            for item in objects:
                entry["payload_hashes"].add(item["sha256"])
                raw = contents[item["sha256"]]
                close = raw["fields"]["time"] + collector.FRAMES[frame]
                if data["admission_floor_raw_seconds"] < close <= quotes[-1]:
                    entry["raw_boundaries"].add(close)
        elif kind == "external_clock":
            clock[data["position"]] = data["probe"].get("error", "SAMPLE_RETURNED")
        elif kind == "finish":
            finish = data
    for entry in bars.values():
        entry["raw_boundaries"] = sorted(entry["raw_boundaries"])
        entry["unique_payloads"] = len(entry.pop("payload_hashes"))
    return {
        "manifest": manifest,
        "event_kinds": dict(counts),
        "quote_snapshots": len(quotes),
        "quote_raw_seconds_bounds": [min(quotes), max(quotes)] if quotes else None,
        "between_poll_tick_coverage": "UNKNOWN",
        "bars": bars,
        "clock_probe_results": clock,
        "host_clock_assessment": finish["host_clock_assessment"] if finish else None,
        "collector_status": finish["status"] if finish else None,
    }


def archived_smoke(root, sha_sources):
    from goldbot.reporting.readiness_696 import CHAIN, JOURNAL, SMOKE

    if any(sha_sources[name].issue for name in (CHAIN, JOURNAL, SMOKE)):
        return {"status": "SOURCE_INTEGRITY_FAILURE"}
    summary = summarize(root / JOURNAL, collector.SCOPE)
    archived = json.loads((root / SMOKE).read_text(encoding="utf-8-sig"))
    expected = json.loads((root / CHAIN).read_text(encoding="utf-8-sig"))
    matched = (summary["manifest"] == expected
               and summary["event_kinds"] == archived["event_kinds"]
               and summary["quote_snapshots"] == archived["quote_snapshots"]
               and summary["clock_probe_results"]["before"] == archived["external_clock"][0]["error"]
               and summary["host_clock_assessment"] == archived["finish"]["host_clock_assessment"]
               and all(value == archived["bars"][frame][key]
                       for frame, bars in summary["bars"].items()
                       for key, value in bars.items() if key in archived["bars"][frame]))
    return dict(summary, status="RECONCILED" if matched else "CONFLICTING")
