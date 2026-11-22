"""Capture dated copies of the official release schedules for the news blackout.

Sources: BLS Employment Situation and CPI schedules, and the Federal Reserve
FOMC calendar, as archived by the Internet Archive's Wayback Machine. Each
capture carries the archive's own timestamp, which is what makes the
calendar point-in-time. BLS refuses automated requests to its own site, so
only archived copies are used for BLS.

- BLS pages: one download per distinct archived content. Every capture is
  kept as a confirmation that the schedule was unchanged at that time.
- FOMC page: the first capture in each 14-day bucket. The page changes
  often for unrelated reasons (new minutes links).
- FOMC statement press releases for past meetings, fetched from
  federalreserve.gov, to verify the release time rather than assume it.

Every download is checked against the archive's SHA-1 content digest and
stored gzip-compressed with its SHA-256. The output directory must be new.
"""

import argparse
import base64
import gzip
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from hashlib import sha1, sha256
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from goldbot.research.news_calendar import SOURCES, decode_page, parse_fomc


CDX = "http://web.archive.org/cdx/search/cdx"
USER_AGENT = "schedule-archive-client/1.0"
FOMC_BUCKET = timedelta(days=14)
PRESS_RELEASE = "https://www.federalreserve.gov/newsevents/pressreleases/monetary{:%Y%m%d}a.htm"
RELEASE_TIME = re.compile(r"For release at (\d{1,2}):(\d{2}) ([ap])\.m\. (EST|EDT)", re.I)


def _get(url, *, attempts=4, pause=5.0):
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=90) as response:
                if response.status != 200:
                    raise OSError(f"HTTP {response.status}")
                return response.read()
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(pause * attempt)


def cdx_captures(url, start, end, get=None):
    query = urlencode({"url": url, "from": start, "to": end, "output": "json",
                       "filter": "statuscode:200", "fl": "timestamp,digest"})
    rows = json.loads((get or _get)(f"{CDX}?{query}"))
    return [(ts, digest) for ts, digest in rows[1:]]


def _day(text):
    return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)


def _utc(timestamp):
    return datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def select(source, captures):
    """Return (download timestamps, kept captures)."""
    if source == "FED_FOMC":
        chosen, bucket_end = [], None
        for ts, digest in captures:
            if bucket_end is None or _utc(ts) >= bucket_end:
                chosen.append((ts, digest))
                bucket_end = _utc(ts) + FOMC_BUCKET
        return [ts for ts, _ in chosen], chosen
    first = {}
    for ts, digest in captures:
        first.setdefault(digest, ts)
    return sorted(first.values()), captures


def capture(output, start, end, log=print, get=None, pause=1.0, now=None):
    """Validate everything that can be checked offline before the first request."""
    get = get or _get
    first, last = _day(start), _day(end)
    if last < first:
        raise ValueError("--to must not precede --from.")
    now = now or datetime.now(timezone.utc)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise OSError("Output directory must be new or empty.")
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "range": [start, end],
                "captures": [], "statement_times": []}
    latest_fomc = None
    for source, info in SOURCES.items():
        url = info["url"]
        captures = cdx_captures(url, start, end, get)
        downloads, kept = select(source, captures)
        log(f"{source}: {len(captures)} captures, {len(downloads)} downloads")
        content_by_digest = {}
        digests = dict(captures)
        folder = output / "snapshots" / source
        folder.mkdir(parents=True, exist_ok=True)
        for ts in downloads:
            digest = digests[ts]
            wayback = f"http://web.archive.org/web/{ts}id_/{url}"
            raw = get(wayback)
            name = f"{ts}.html.gz"
            (folder / name).write_bytes(gzip.compress(raw, mtime=0))
            content_by_digest[digest] = {
                "content_sha256": sha256(raw).hexdigest(), "file": f"snapshots/{source}/{name}",
                "cdx_digest_matches": base64.b32encode(sha1(raw).digest()).decode() == digest,
            }
            if source == "FED_FOMC" and "FOMC Meetings" in decode_page(raw):
                latest_fomc = raw
            time.sleep(pause)
        for ts, digest in kept:
            content = content_by_digest[digest]
            manifest["captures"].append({
                "source": source, "wayback_timestamp": ts, "captured_utc": _utc(ts).isoformat(),
                "cdx_digest": digest, "wayback": f"http://web.archive.org/web/{ts}/{url}",
                "downloaded": ts in downloads, **content,
            })
    if latest_fomc is not None:
        events, _ = parse_fomc(decode_page(latest_fomc))
        folder = output / "press_releases"
        folder.mkdir(parents=True, exist_ok=True)
        for label, when, _ in events:
            if not first <= when <= now:
                continue
            url = PRESS_RELEASE.format(when.astimezone(timezone.utc).date())
            record = {"meeting": label, "scheduled_utc": when.isoformat(), "url": url,
                      "fetched_utc": datetime.now(timezone.utc).isoformat()}
            try:
                raw = get(url)
            except OSError as error:
                record.update(error=str(error))
            else:
                name = f"{when:%Y%m%d}.html.gz"
                (folder / name).write_bytes(gzip.compress(raw, mtime=0))
                text = re.sub(r"<[^>]+>", " ", decode_page(raw))
                found = RELEASE_TIME.search(text)
                record.update(content_sha256=sha256(raw).hexdigest(), file=f"press_releases/{name}",
                              release_time=None if not found else
                              f"{int(found[1]):02d}:{found[2]} {found[3].lower()}.m. {found[4].upper()}")
            manifest["statement_times"].append(record)
            time.sleep(pause / 2)
    (output / "captures.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8", newline="\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--from", dest="start", default="20241101", help="YYYYMMDD")
    parser.add_argument("--to", dest="end", default=f"{date.today():%Y%m%d}", help="YYYYMMDD")
    args = parser.parse_args(argv)
    try:
        manifest = capture(args.output, args.start, args.end)
    except (OSError, ValueError) as error:
        print(f"Capture failed: {error}", file=sys.stderr)
        return 1
    mismatched = [c for c in manifest["captures"] if c["downloaded"] and not c["cdx_digest_matches"]]
    print(f"{len(manifest['captures'])} captures, {len(mismatched)} digest mismatches, "
          f"{len(manifest['statement_times'])} statement pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
