"""Refresh the news blackout calendar without overwriting anything.

Two routes, each writing a new batch folder under <root>/refresh/:

  archive   Primary. Fetch Wayback Machine captures of the official BLS and
            Federal Reserve schedule pages taken after the newest capture
            already held, plus Fed statement pages for meetings held since
            the last verified one.
  import    Fallback. Record an official schedule page the operator saved
            from a browser. Its capture time is operator-stated, so it is
            labelled as such. It is rejected if the URL is not the official
            page, the page does not parse, it lists no release after its
            capture time, or it shows an older schedule than one already
            held for that source.

Existing captures, batches and calendars are never modified. Rebuild with
tools.build_news_calendar_611 to produce a new calendar file. Research only.
"""

import argparse
import base64
import gzip
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from hashlib import sha1, sha256
from pathlib import Path

from goldbot.research.news_calendar import (
    SOURCES, CalendarError, decode_page, parse_fomc, snapshot_events,
)
from tools.build_news_calendar_611 import load_manifests
from tools.capture_news_calendar_611 import FOMC_BUCKET, PRESS_RELEASE, RELEASE_TIME, _get, cdx_captures


MAX_IMPORT_BYTES = 5 * 1024 * 1024
FUTURE_TOLERANCE = timedelta(minutes=5)


class RefreshError(ValueError):
    pass


def _stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _new_batch(root, method, now):
    batch = Path(root) / "refresh" / f"{_stamp(now)}-{method}"
    batch.mkdir(parents=True, exist_ok=False)  # never reuse or overwrite a batch
    return batch


def _write_manifest(batch, manifest):
    with (batch / "captures.json").open("x", encoding="utf-8", newline="\n") as target:
        json.dump(manifest, target, indent=2, sort_keys=True)
        target.write("\n")


def known_state(root):
    """Every capture already held, with stored file paths relative to root."""
    captures, statements = [], []
    for relative, manifest, _ in load_manifests(root):
        base = relative.parent
        for capture in manifest["captures"]:
            record = dict(capture)
            if capture.get("file"):
                record["path"] = str((base / capture["file"]).as_posix())
            captures.append(record)
        statements.extend(manifest.get("statement_times", ()))
    return captures, statements


def _events_of(root, capture, cache):
    """Parsed events of a held capture's content, or None if unusable."""
    digest = capture["content_sha256"]
    if digest not in cache:
        cache[digest] = None
        if capture.get("path"):
            raw = gzip.decompress((Path(root) / capture["path"]).read_bytes())
            try:
                cache[digest] = snapshot_events(capture["source"], decode_page(raw))[0]
            except CalendarError:
                pass
    return cache[digest]


def _store(batch, source, name, raw):
    folder = batch / "snapshots" / source
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(gzip.compress(raw, mtime=0))
    return f"snapshots/{source}/{name}"


def refresh_archive(root, *, get=None, now=None, pause=1.0, log=print):
    get = get or _get
    now = now or datetime.now(timezone.utc)
    held, statements = known_state(root)
    plans = {}
    for source, info in SOURCES.items():
        mine = [c for c in held if c["source"] == source and c.get("method", "wayback") == "wayback"]
        last = max(c["wayback_timestamp"] for c in mine) if mine else "20241101000000"
        by_digest = {c["cdx_digest"]: c for c in mine if c.get("path")}
        fresh = [(ts, d) for ts, d in cdx_captures(info["url"], last, f"{now:%Y%m%d%H%M%S}", get) if ts > last]
        plans[source] = (info["url"], last, by_digest, fresh)
    if not any(plan[3] for plan in plans.values()):
        log("No archive captures newer than those held; nothing written.")
        return None
    batch = _new_batch(root, "wayback", now)
    manifest = {"method": "wayback", "created_utc": now.isoformat(), "captures": [], "statement_times": []}
    latest_fomc = None
    for source, (url, last, by_digest, fresh) in plans.items():
        bucket_end = datetime.strptime(last, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc) + FOMC_BUCKET
        downloaded = {}
        for ts, digest in fresh:
            captured = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            record = {"source": source, "method": "wayback", "wayback_timestamp": ts,
                      "captured_utc": captured.isoformat(), "cdx_digest": digest,
                      "wayback": f"http://web.archive.org/web/{ts}/{url}"}
            if source == "FED_FOMC":
                if captured < bucket_end:
                    continue
                bucket_end = captured + FOMC_BUCKET
            existing = downloaded.get(digest) or by_digest.get(digest)
            if existing is not None and source != "FED_FOMC":
                # Same archived bytes as content already held: a confirmation, not a new page.
                record.update(downloaded=False, content_sha256=existing["content_sha256"],
                              cdx_digest_matches=existing.get("cdx_digest_matches"))
            else:
                raw = get(f"http://web.archive.org/web/{ts}id_/{url}")
                file = _store(batch, source, f"{ts}.html.gz", raw)
                record.update(downloaded=True, content_sha256=sha256(raw).hexdigest(), file=file,
                              cdx_digest_matches=base64.b32encode(sha1(raw).digest()).decode() == digest)
                downloaded[digest] = dict(record, path=(batch.relative_to(root) / file).as_posix())
                if source == "FED_FOMC" and "FOMC Meetings" in decode_page(raw):
                    latest_fomc = raw
                time.sleep(pause)
            manifest["captures"].append(record)
        log(f"{source}: {len(fresh)} new captures")
    verified_until = max((datetime.fromisoformat(s["scheduled_utc"]) for s in statements
                          if s.get("release_time")), default=None)
    if latest_fomc is not None:
        for label, when, _ in parse_fomc(decode_page(latest_fomc))[0]:
            if (verified_until is None or when > verified_until) and when <= now:
                url = PRESS_RELEASE.format(when.date())
                record = {"meeting": label, "scheduled_utc": when.isoformat(), "url": url,
                          "fetched_utc": now.isoformat()}
                try:
                    raw = get(url)
                except OSError as error:
                    record.update(error=str(error))
                else:
                    found = RELEASE_TIME.search(re.sub(r"<[^>]+>", " ", decode_page(raw)))
                    name = f"{when:%Y%m%d}.html.gz"
                    folder = batch / "press_releases"
                    folder.mkdir(exist_ok=True)
                    (folder / name).write_bytes(gzip.compress(raw, mtime=0))
                    record.update(content_sha256=sha256(raw).hexdigest(), file=f"press_releases/{name}",
                                  release_time=None if not found else
                                  f"{int(found[1]):02d}:{found[2]} {found[3].lower()}.m. {found[4].upper()}")
                manifest["statement_times"].append(record)
    _write_manifest(batch, manifest)
    return batch


def import_page(root, *, source, file, captured_utc, url, now=None):
    """Validate and record one operator-saved official schedule page."""
    now = now or datetime.now(timezone.utc)
    if source not in SOURCES:
        raise RefreshError(f"Unknown source {source!r}.")
    if url != SOURCES[source]["url"]:
        raise RefreshError(f"URL must be the official page {SOURCES[source]['url']}.")
    captured = datetime.fromisoformat(captured_utc.replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise RefreshError("--captured-utc needs an explicit offset.")
    captured = captured.astimezone(timezone.utc)
    if captured > now + FUTURE_TOLERANCE:
        raise RefreshError("The stated capture time is in the future.")
    raw = Path(file).read_bytes()
    if not raw or len(raw) > MAX_IMPORT_BYTES:
        raise RefreshError("Saved page is empty or larger than 5 MB.")
    try:
        events, skipped = snapshot_events(source, decode_page(raw))
    except CalendarError as error:
        raise RefreshError(f"Page does not parse as the {source} schedule: {error}") from None
    times = [datetime.fromisoformat(e["scheduled_utc"]) for e in events]
    if not any(when > captured for when in times):
        raise RefreshError("Page lists no release after its capture time; it cannot extend coverage.")
    held, _ = known_state(root)
    same = [c for c in held if c["source"] == source]
    if any(c["captured_utc"] == captured.isoformat() for c in same):
        raise RefreshError("A capture of this source at that exact time is already recorded.")
    earlier = [c for c in same if datetime.fromisoformat(c["captured_utc"]) <= captured]
    cache = {}
    for capture in sorted(earlier, key=lambda c: c["captured_utc"], reverse=True):
        known = _events_of(root, capture, cache)
        if known:
            if max(times) < max(datetime.fromisoformat(e["scheduled_utc"]) for e in known):
                raise RefreshError("Page shows an older schedule than one already held for this source.")
            break
    batch = _new_batch(root, "operator_import", now)
    stored = _store(batch, source, f"{_stamp(captured)}-operator.html.gz", raw)
    record = {"source": source, "method": "operator_import", "url": url,
              "captured_utc": captured.isoformat(), "imported_utc": now.isoformat(),
              "attestation": "capture time stated by the operator", "downloaded": True,
              "content_sha256": sha256(raw).hexdigest(), "file": stored, "cdx_digest_matches": None,
              "original_filename": Path(file).name, "events": events, "skipped_unscheduled": skipped}
    _write_manifest(batch, {"method": "operator_import", "created_utc": now.isoformat(),
                            "captures": [record], "statement_times": []})
    return batch, record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("historical_data/news_calendar"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("archive")
    manual = commands.add_parser("import")
    manual.add_argument("--source", required=True, choices=sorted(SOURCES))
    manual.add_argument("--file", type=Path, required=True)
    manual.add_argument("--captured-utc", required=True,
                        help="when you saved the page, e.g. 2026-12-10T09:15:00+03:00")
    manual.add_argument("--url", required=True, help="the official page URL you saved")
    args = parser.parse_args(argv)
    try:
        if args.command == "archive":
            batch = refresh_archive(args.root)
            print("No new batch." if batch is None else f"New batch: {batch}")
        else:
            batch, record = import_page(args.root, source=args.source, file=args.file,
                                        captured_utc=args.captured_utc, url=args.url)
            print(f"Imported {len(record['events'])} releases into {batch}")
    except (OSError, ValueError) as error:
        print(f"Refresh refused: {error}", file=sys.stderr)
        return 1
    print("Rebuild the calendar with tools.build_news_calendar_611 to use the new captures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
