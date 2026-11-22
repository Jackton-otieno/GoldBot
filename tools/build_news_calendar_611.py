"""Build the sealed news-blackout calendar from captured schedule pages.

Reads captures.json and the stored snapshots written by
tools.capture_news_calendar_611, re-verifies every stored file's SHA-256,
parses each distinct page, and checks every fetched FOMC statement release
time against the assumed 2:00 p.m. Eastern time. Any parse failure, hash
mismatch or statement-time mismatch stops the build. The calendar is
research-only.
"""

import argparse
import gzip
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from goldbot.research.news_calendar import (
    BLACKOUT, ET, FOMC_STATEMENT_TIME_ET, MAX_CAPTURE_AGE, SOURCES, CalendarError, decode_page,
    seal, snapshot_events,
)


FORMAT = "goldbot-news-calendar/1"
FORMAT_WITH_REFRESH = "goldbot-news-calendar/2"


def verify_statement_times(records):
    verified, mismatches, unavailable = [], [], []
    for record in records:
        scheduled = datetime.fromisoformat(record["scheduled_utc"]).astimezone(ET)
        zone = "EDT" if scheduled.dst() else "EST"
        expected = f"{FOMC_STATEMENT_TIME_ET:%I:%M} p.m. {zone}"
        found = record.get("release_time")
        if found is None:
            unavailable.append({"meeting": record["meeting"], "reason": record.get("error", "time not found")})
        elif found == expected:
            verified.append(record["meeting"])
        else:
            mismatches.append({"meeting": record["meeting"], "expected": expected, "found": found})
    return {"assumed": f"{FOMC_STATEMENT_TIME_ET:%H:%M} US Eastern on the meeting's last day",
            "verified_meetings": verified, "mismatches": mismatches, "unavailable": unavailable}


def build(directory):
    directory = Path(directory)
    manifest_bytes = (directory / "captures.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    manifests = load_manifests(directory)
    contents, unusable = {}, {}
    for relative, batch_manifest, _ in manifests:
        base = relative.parent
        for capture in batch_manifest["captures"]:
            if not capture["downloaded"]:
                continue
            stored = (base / capture["file"]).as_posix()
            raw = gzip.decompress((directory / stored).read_bytes())
            if sha256(raw).hexdigest() != capture["content_sha256"]:
                raise CalendarError(f"Stored snapshot {stored} fails its SHA-256.")
            try:
                events, skipped = snapshot_events(capture["source"], decode_page(raw))
            except CalendarError as error:
                # An empty or non-schedule page confirms nothing; it is excluded, not guessed.
                unusable[capture["content_sha256"]] = {"file": stored, "bytes": len(raw),
                                                       "reason": str(error)}
                continue
            contents[capture["content_sha256"]] = {"source": capture["source"], "events": events,
                                                   "skipped_unscheduled": skipped}
    captures, excluded, statements = [], [], {}
    for _, batch_manifest, _ in manifests:
        for c in batch_manifest["captures"]:
            if c["content_sha256"] not in contents and c["content_sha256"] not in unusable:
                raise CalendarError(f"Capture refers to content that is not stored: {c['content_sha256'][:12]}.")
            record = {"source": c["source"], "captured_utc": c["captured_utc"],
                      "content_sha256": c["content_sha256"], "cdx_digest_matches": c["cdx_digest_matches"]}
            if c.get("method", "wayback") == "wayback":
                record["wayback"] = c["wayback"]
            else:
                record.update(method=c["method"], url=c["url"], imported_utc=c["imported_utc"],
                              attestation=c["attestation"])
            (excluded if c["content_sha256"] in unusable else captures).append(record)
        for item in batch_manifest.get("statement_times", ()):
            statements.setdefault(item["meeting"], item)
    statement = verify_statement_times(list(statements.values()))
    if statement["mismatches"]:
        raise CalendarError(f"FOMC statement times differ from the assumption: {statement['mismatches']}")
    extra = {}
    if len(manifests) > 1:
        extra = {"format": FORMAT_WITH_REFRESH, "refresh_batches": [
            {"manifest": relative.as_posix(), "sha256": sha256(raw_manifest).hexdigest(),
             "method": m.get("method"), "created_utc": m.get("created_utc")}
            for relative, m, raw_manifest in manifests[1:]]}
    return seal({
        "format": FORMAT,
        "label": "RESEARCH_ONLY",
        "rule": {"blackout_minutes_each_side": int(BLACKOUT.total_seconds() // 60),
                 "inclusive": True,
                 "max_capture_age_days": MAX_CAPTURE_AGE.days,
                 "point_in_time": "latest capture of each source at or before the decision"},
        "sources": SOURCES,
        "captures_manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "capture_range": manifest["range"],
        "contents": contents,
        "captures": captures,
        "unusable_contents": unusable,
        "excluded_captures": excluded,
        "fomc_statement_time": statement,
        **extra,
    })


def load_manifests(root):
    """(path relative to root, manifest, raw bytes): the original capture first,
    then every refresh batch in name (time) order."""
    root = Path(root)
    paths = [Path("captures.json")] + sorted(
        path.relative_to(root) for path in (root / "refresh").glob("*/captures.json"))
    loaded = []
    for relative in paths:
        raw = (root / relative).read_bytes()
        loaded.append((relative, json.loads(raw), raw))
    return loaded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=Path("historical_data/news_calendar"))
    parser.add_argument("--output", type=Path,
                        help="new calendar JSON file (default <input>/calendar-<UTC time>.json)")
    args = parser.parse_args(argv)
    try:
        calendar = build(args.input)
        output = args.output or args.input / f"calendar-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
        with output.open("x", encoding="utf-8", newline="\n") as target:
            json.dump(calendar, target, indent=1, sort_keys=True)
            target.write("\n")
    except (OSError, ValueError, KeyError) as error:
        print(f"Calendar build failed: {error}", file=sys.stderr)
        return 1
    counts = {s: sum(c["source"] == s for c in calendar["captures"]) for s in SOURCES}
    print(json.dumps({"calendar_sha256": calendar["calendar_sha256"], "captures": counts,
                      "distinct_pages": len(calendar["contents"]),
                      "fomc_statement_time": {k: len(v) if isinstance(v, list) else v
                                              for k, v in calendar["fomc_statement_time"].items()}},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
