"""Acquire and audit one public Dukascopy XAU/USD hour at a time."""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import lzma
from math import isfinite
from pathlib import Path
from struct import Struct
from time import monotonic
from urllib.request import HTTPRedirectHandler, build_opener

from goldbot.market_data.tick_data import spread


HOST = "https://datafeed.dukascopy.com/datafeed/XAUUSD"
RECORD = Struct(">IIIff")
MAX_COMPRESSED = 1024 * 1024
MAX_ROWS = 100_000
HOUR_MS = 3_600_000
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
PERIODS = {"M1": 60_000, "M15": 900_000, "H1": HOUR_MS}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def bounded_response(response, maximum, deadline):
    length = response.headers.get("Content-Length")
    if length is not None and int(length) > maximum:
        raise ValueError("HTTP response exceeds the byte cap.")
    chunks = bytearray()
    while True:
        if monotonic() >= deadline:
            raise TimeoutError("HTTP sample exceeded its time budget.")
        chunk = response.read1(min(64 * 1024, maximum - len(chunks) + 1))
        if not chunk:
            return chunks
        chunks.extend(chunk)
        if len(chunks) > maximum:
            raise ValueError("HTTP response exceeds the byte cap.")


def hour(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(0) or parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("Supply the UTC start of one whole hour.")
    return parsed.astimezone(timezone.utc)


def source_url(start):
    return (f"{HOST}/{start.year:04}/{start.month - 1:02}/{start.day:02}/"
            f"{start.hour:02}h_ticks.bi5")


def acquire(start, path):
    url = source_url(start)
    before = datetime.now(timezone.utc)
    with build_opener(NoRedirect()).open(url, timeout=10) as response:
        raw = bounded_response(response, MAX_COMPRESSED, monotonic() + 30)
        if response.status != 200 or not raw or len(raw) > MAX_COMPRESSED:
            raise ValueError("Archive response was missing or exceeded the sample bound.")
        headers = {name: response.headers[name] for name in ("Last-Modified", "ETag")
                   if name in response.headers}
    after = datetime.now(timezone.utc)
    with path.open("xb") as output:
        output.write(raw)
    return dict(url=url, byte_count=len(raw), sha256=sha256(raw).hexdigest(),
                acquired_utc_bracket=[before.isoformat(), after.isoformat()],
                http_status=200, http_headers=headers)


def decode(raw):
    if not raw or len(raw) > MAX_COMPRESSED:
        raise ValueError("Missing or oversized compressed hour.")
    decoder = lzma.LZMADecompressor(memlimit=32 * 1024 * 1024)
    data = decoder.decompress(raw, max_length=MAX_ROWS * RECORD.size + 1)
    if (not decoder.eof or decoder.unused_data or not data
            or len(data) > MAX_ROWS * RECORD.size or len(data) % RECORD.size):
        raise ValueError("Truncated, empty, oversized or malformed tick stream.")
    return RECORD.iter_unpack(data)


def audit(rows, start, price_unit="0.001"):
    base_ms = (start - EPOCH) // timedelta(milliseconds=1)
    if start.utcoffset() != timedelta(0) or base_ms % HOUR_MS or start.microsecond:
        raise ValueError("Expected a whole UTC hour.")
    stats = Counter()
    seen = set()
    previous = first = None
    min_spread = max_spread = None
    active, bars = {}, {name: [] for name in PERIODS}
    for offset, ask, bid, ask_size, bid_size in rows:
        if stats["ticks"] >= MAX_ROWS:
            raise ValueError("Hour exceeded the tick limit.")
        if not 0 <= offset < HOUR_MS or (previous is not None and offset < previous):
            raise ValueError("Tick outside the hour or out of source order.")
        raw_spread = spread({"bid": bid, "ask": ask})
        if raw_spread is None or any(not isfinite(size) or size < 0 for size in (ask_size, bid_size)):
            raise ValueError("Invalid bid, ask, or quote size.")
        stats["ticks"] += 1
        if first is None:
            first = offset
        if offset != previous:
            seen.clear()
        else:
            stats["shared_timestamp_rows"] += 1
        signature = (ask, bid, ask_size, bid_size)
        stats["repeated_payload_rows"] += signature in seen
        seen.add(signature)
        if previous is not None:
            gap = offset - previous
            stats["largest_intertick_spacing_ms"] = max(stats["largest_intertick_spacing_ms"], gap)
            stats["intertick_spacings_over_60s"] += gap > 60_000
        previous = offset
        width = int(raw_spread)
        stats["zero_spread_rows"] += width == 0
        min_spread = width if min_spread is None else min(min_spread, width)
        max_spread = width if max_spread is None else max(max_spread, width)
        for name, period in PERIODS.items():
            opened = base_ms + offset // period * period
            candle = active.get(name)
            if candle is None or opened != candle["open_utc_ms"]:
                if candle is not None:
                    bars[name].append(candle)
                active[name] = dict(open_utc_ms=opened, available_at_utc_ms=opened + period,
                                    bid_ohlc=[bid] * 4, ask_ohlc=[ask] * 4, ticks=1)
                continue
            for side, price in (("bid_ohlc", bid), ("ask_ohlc", ask)):
                values = candle[side]
                values[1:] = [max(values[1], price), min(values[2], price), price]
            candle["ticks"] += 1
    if first is None:
        raise ValueError("Expected at least one tick.")
    for name, candle in active.items():
        bars[name].append(candle)
    return dict(first_tick_utc_ms=base_ms + first, last_tick_utc_ms=base_ms + previous,
                leading_silence_ms=first, trailing_silence_ms=HOUR_MS - previous,
                tick_counts=dict(stats), spread_price_units=[min_spread, max_spread],
                price_unit_usd_per_troy_ounce=price_unit,
                empty_intervals={name: HOUR_MS // period - len(bars[name])
                                 for name, period in PERIODS.items()},
                coverage="OBSERVED_ONLY", bars=bars)


def validate(start, path, expected):
    with path.open("rb") as source:
        raw = source.read(MAX_COMPRESSED + 1)
    if sha256(raw).hexdigest() != expected:
        raise ValueError("Source SHA-256 mismatch.")
    return audit(decode(raw), start)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "audit"))
    parser.add_argument("--hour", type=hour, required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.action == "fetch":
        result = acquire(args.hour, args.file)
    elif args.sha256:
        result = validate(args.hour, args.file, args.sha256)
    else:
        parser.error("--sha256 is required for audit")
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
