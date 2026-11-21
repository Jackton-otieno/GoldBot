"""Exness public tick archive: bounded fetch, streamed audit and UTC bid candles.

The archive is Exness-published bid/ask history from its real-server pricing
(https://www.exness.com/tick-history/). Rows carry a trailing ``Z`` and are
read as UTC. Prices are held as integer thousandths, so no binary floating
point enters the audit. Sub-millisecond digits, if present, are truncated.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import datetime, timezone
from hashlib import file_digest, sha256
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile


HOST = "https://ticks.ex2archive.com"
SYMBOLS = frozenset({"XAUUSD", "XAUUSDm"})
HEADER = ("Exness", "Symbol", "Timestamp", "Bid", "Ask")
PRICE_SCALE = 1000
MAX_ZIP_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
GAP_MS = 5 * 60 * 1000
WEEKEND_MS = 24 * 3600 * 1000
TIMEFRAMES = {"M15": 900_000, "H1": 3_600_000}
USER_AGENT = "tick-archive-client/1.0"

_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z")
_PRICE = re.compile(r"(\d{1,7})(?:\.(\d{1,3}))?")


class ArchiveError(ValueError):
    pass


def parse_month(text):
    match = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", text or "")
    if not match:
        raise ArchiveError("Expected a YYYY-MM month.")
    return int(match[1]), int(match[2])


def _check(symbol, year, month):
    if symbol not in SYMBOLS:
        raise ArchiveError(f"Unsupported archive symbol; expected one of {sorted(SYMBOLS)}.")
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise ArchiveError("Archive month out of range.")


def archive_url(symbol, year, month):
    _check(symbol, year, month)
    return f"{HOST}/ticks/{symbol}/{year}/{month:02d}/Exness_{symbol}_{year}_{month:02d}.zip"


def member_name(symbol, year, month):
    _check(symbol, year, month)
    return f"Exness_{symbol}_{year}_{month:02d}.csv"


def month_bounds_ms(year, month):
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()) * 1000, int(end.timestamp()) * 1000


def utc_text(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds")


def price_text(thousandths):
    return f"{thousandths // PRICE_SCALE}.{thousandths % PRICE_SCALE:03d}"


def _now():
    return datetime.now(timezone.utc)


def fetch(symbol, year, month, destination, *, opener=urlopen, clock=_now):
    """Download one monthly ZIP to a new file and return its provenance record."""
    url = archive_url(symbol, year, month)
    destination = Path(destination)
    before = clock()
    digest, size = sha256(), 0
    created = False
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=60) as response:
            status = getattr(response, "status", None)
            if status != 200:
                raise ArchiveError(f"Archive request returned HTTP {status}.")
            headers = response.headers
            with destination.open("xb") as output:
                created = True
                while chunk := response.read(1 << 20):
                    size += len(chunk)
                    if size > MAX_ZIP_BYTES:
                        raise ArchiveError("Archive exceeds the one-month size cap.")
                    digest.update(chunk)
                    output.write(chunk)
        if not size:
            raise ArchiveError("Archive response was empty.")
        member = _member(destination, symbol, year, month)
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return {
        "source": "Exness public tick archive",
        "url": url,
        "symbol": symbol,
        "month": f"{year}-{month:02d}",
        "http_status": 200,
        "last_modified": headers.get("Last-Modified"),
        "byte_count": size,
        "sha256": digest.hexdigest(),
        "zip_member": member.filename,
        "member_bytes": member.file_size,
        "acquired_utc_bracket": [before.isoformat(), clock().isoformat()],
    }


def _member(path, symbol, year, month):
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
    except BadZipFile:
        raise ArchiveError("Archive is not a readable ZIP file.") from None
    expected = member_name(symbol, year, month)
    if (len(infos) != 1 or infos[0].filename != expected
            or not 0 < infos[0].file_size <= MAX_MEMBER_BYTES):
        raise ArchiveError(f"Expected exactly one bounded member named {expected}.")
    return infos[0]


def _timestamp(text, days):
    match = _STAMP.fullmatch(text)
    if not match:
        raise ArchiveError(f"Malformed timestamp {text!r}.")
    day = days.get(match[1])
    if day is None:
        parsed = datetime.strptime(match[1], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        day = days[match[1]] = int(parsed.timestamp()) * 1000
    hour, minute, second = int(match[2]), int(match[3]), int(match[4])
    if hour > 23 or minute > 59 or second > 59:
        raise ArchiveError(f"Invalid clock time {text!r}.")
    millis = int(((match[5] or "") + "000")[:3])
    return day + ((hour * 60 + minute) * 60 + second) * 1000 + millis


def parse_price(text):
    match = _PRICE.fullmatch(text)
    if not match:
        raise ArchiveError(f"Malformed or over-precise price {text!r}.")
    value = int(match[1]) * PRICE_SCALE + int((match[2] or "").ljust(3, "0"))
    if value <= 0:
        raise ArchiveError("Prices must be positive.")
    return value


def iter_ticks(path, symbol, year, month, expected_sha256):
    """Yield (utc_ms, bid, ask) in source order after verifying the pinned digest."""
    path = Path(path)
    with path.open("rb") as source:
        if file_digest(source, "sha256").hexdigest() != expected_sha256:
            raise ArchiveError("Archive fails its pinned SHA-256.")
    info = _member(path, symbol, year, month)
    start, end = month_bounds_ms(year, month)
    days = {}
    with ZipFile(path) as archive, archive.open(info) as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding="ascii", newline=""))
        if tuple(next(reader, ())) != HEADER:
            raise ArchiveError("Unexpected archive header.")
        for line, row in enumerate(reader, start=2):
            if len(row) != 5 or row[0].casefold() != "exness" or row[1] != symbol:
                raise ArchiveError(f"Line {line}: unexpected source or symbol.")
            ms = _timestamp(row[2], days)
            bid, ask = parse_price(row[3]), parse_price(row[4])
            if not start <= ms < end:
                raise ArchiveError(f"Line {line}: timestamp outside {year}-{month:02d}.")
            if ask < bid:
                raise ArchiveError(f"Line {line}: crossed quote.")
            yield ms, bid, ask


def _percentile(counter, fraction):
    total = sum(counter.values())
    if not total:
        return None
    target = fraction * (total - 1)
    seen = 0
    for value in sorted(counter):
        seen += counter[value]
        if seen > target:
            return value
    return max(counter)


class MonthAudit:
    """Single-pass audit: ordering, gaps, spread distribution and bid candles."""

    def __init__(self):
        self.count = 0
        self.first = self.last = None
        self.same_ms = 0
        self.zero_spread = 0
        self.gaps = []
        self.spreads = Counter()
        self.hourly = [Counter() for _ in range(24)]
        self.candles = {name: {} for name in TIMEFRAMES}

    def add(self, ms, bid, ask):
        if self.last is not None:
            if ms < self.last:
                raise ArchiveError(f"Tick {self.count + 1} is out of order.")
            if ms == self.last:
                self.same_ms += 1
            elif ms - self.last >= GAP_MS:
                self.gaps.append((self.last, ms))
        else:
            self.first = ms
        self.last = ms
        self.count += 1
        spread = ask - bid
        if not spread:
            self.zero_spread += 1
        self.spreads[spread] += 1
        self.hourly[ms // 3_600_000 % 24][spread] += 1
        for name, width in TIMEFRAMES.items():
            bins = self.candles[name]
            start = ms - ms % width
            bar = bins.get(start)
            if bar is None:
                bins[start] = [bid, bid, bid, bid, ask, 1, spread, spread]
            else:
                if bid > bar[1]:
                    bar[1] = bid
                if bid < bar[2]:
                    bar[2] = bid
                bar[3] = bid
                bar[4] = ask
                bar[5] += 1
                bar[6] += spread
                if spread > bar[7]:
                    bar[7] = spread

    def candle_rows(self, name):
        for start, (o, h, l, c, ask, ticks, total, widest) in sorted(self.candles[name].items()):
            yield {
                "utc_start": utc_text(start),
                "epoch_s": start // 1000,
                "open": price_text(o), "high": price_text(h),
                "low": price_text(l), "close": price_text(c),
                "ask_close": price_text(ask), "ticks": ticks,
                "spread_mean": f"{total / ticks / PRICE_SCALE:.4f}",
                "spread_max": price_text(widest),
            }

    def report(self):
        if not self.count:
            raise ArchiveError("Archive contained no ticks.")
        weekend, breaks = [], Counter()
        listed = []
        for before, after in self.gaps:
            minutes = (after - before) / 60_000
            item = {"last_tick_utc": utc_text(before), "next_tick_utc": utc_text(after),
                    "minutes": round(minutes, 2)}
            listed.append(item)
            if after - before >= WEEKEND_MS:
                weekend.append(item)
            else:
                key = (utc_text(before)[11:16], utc_text(after)[11:16])
                breaks[key] += 1
        spread = {
            "unit": "price (USD per oz); USD cost per 0.01 lot equals this value",
            "p50": price_text(_percentile(self.spreads, .5)),
            "p90": price_text(_percentile(self.spreads, .9)),
            "p99": price_text(_percentile(self.spreads, .99)),
            "max": price_text(max(self.spreads)),
            "mean": f"{sum(k * v for k, v in self.spreads.items()) / self.count / PRICE_SCALE:.4f}",
            "by_utc_hour": {
                f"{hour:02d}": {"ticks": sum(c.values()),
                                "p50": price_text(_percentile(c, .5)) if c else None,
                                "p95": price_text(_percentile(c, .95)) if c else None}
                for hour, c in enumerate(self.hourly)
            },
        }
        return {
            "ticks": self.count,
            "first_tick_utc": utc_text(self.first),
            "last_tick_utc": utc_text(self.last),
            "same_millisecond_ticks": self.same_ms,
            "zero_spread_ticks": self.zero_spread,
            "spread": spread,
            "gap_threshold_minutes": GAP_MS // 60_000,
            "weekend_closures": weekend,
            "intraday_breaks_by_utc_minute": [
                {"last_tick_hhmm": a, "next_tick_hhmm": b, "days": n}
                for (a, b), n in sorted(breaks.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            "all_gaps": listed,
            "candle_counts": {name: len(bins) for name, bins in self.candles.items()},
        }


def audit(path, symbol, year, month, expected_sha256):
    result = MonthAudit()
    for tick in iter_ticks(path, symbol, year, month, expected_sha256):
        result.add(*tick)
    return result
