"""Preserve one HistData XAU/USD archive and audit one bounded UTC hour."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import file_digest, sha256
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from zipfile import ZipFile

from tools.dukascopy_sample import NoRedirect, audit, bounded_response, hour


HOST = "https://www.histdata.com"
EST = timezone(timedelta(hours=-5))
MAX_ZIP = 32 * 1024 * 1024
MAX_MEMBER = 320 * 1024 * 1024
PRICE_UNIT = Decimal(".000001")


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.active = attrs.get("id") == "file_down" and attrs.get("action") == "/get.php"
        if self.active and tag == "input" and attrs.get("type") == "hidden":
            self.fields[attrs["name"]] = attrs["value"]

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = False


def acquire(month, path):
    if not re.fullmatch(r"\d{4}(0[1-9]|1[0-2])", month):
        raise ValueError("Expected YYYYMM archive month.")
    url = f"{HOST}/download-free-forex-historical-data/?/ascii/tick-data-quotes/xauusd/{month[:4]}/{month[4:]}"
    opener = build_opener(NoRedirect())
    before = datetime.now(timezone.utc)
    with opener.open(url, timeout=15) as response:
        page = bounded_response(response, 512_000, monotonic() + 20)
    form = DownloadForm()
    form.feed(page.decode("utf-8"))
    expected = dict(fxpair="XAUUSD", platform="ASCII", timeframe="T",
                    date=month[:4], datemonth=month)
    if not form.fields.get("tk") or any(form.fields.get(k) != v for k, v in expected.items()):
        raise ValueError("Official download form did not identify the expected XAUUSD month.")
    request = Request(f"{HOST}/get.php", data=urlencode(form.fields).encode(),
                      headers={"Referer": url})
    with opener.open(request, timeout=20) as response:
        raw = bounded_response(response, MAX_ZIP, monotonic() + 90)
        if response.status != 200 or not raw or len(raw) > MAX_ZIP:
            raise ValueError("Archive response unavailable or exceeds the one-month size cap.")
    after = datetime.now(timezone.utc)
    with ZipFile(BytesIO(raw)) as archive:
        member = expected_member(archive, month)
    with path.open("xb") as output:
        output.write(raw)
    return dict(listing_url=url, download_url=request.full_url, byte_count=len(raw),
                zip_member=member.filename, sha256=sha256(raw).hexdigest(), http_status=200,
                acquired_utc_bracket=[before.isoformat(), after.isoformat()])


def expected_member(archive, month):
    matches = [info for info in archive.infolist()
               if info.filename == f"DAT_ASCII_XAUUSD_T_{month}.csv"]
    if len(matches) != 1 or not 0 < matches[0].file_size <= MAX_MEMBER:
        raise ValueError("Expected one bounded, provider-named XAUUSD tick member.")
    return matches[0]


def price(value):
    scaled = Decimal(value) / PRICE_UNIT
    if not scaled.is_finite() or scaled != scaled.to_integral_value():
        raise ValueError("Unusable HistData quote precision.")
    return int(scaled)


def rows_for_hour(source, start, month):
    local = start.astimezone(EST)
    first = local.strftime("%Y%m%d %H%M%S") + "000"
    last = (local + timedelta(hours=1)).strftime("%Y%m%d %H%M%S") + "000"
    previous = None
    while line := source.readline(257):
        if len(line) > 256:
            raise ValueError("Oversized HistData line.")
        stamp, bid, ask, volume = line.decode("ascii").strip().split(",")
        if (not re.fullmatch(r"\d{8} \d{9}", stamp) or stamp[:6] != month
                or (previous is not None and stamp < previous)):
            raise ValueError("Malformed or out-of-order HistData timestamp.")
        previous = stamp
        if first <= stamp < last:
            parsed = datetime.strptime(stamp, "%Y%m%d %H%M%S%f").replace(tzinfo=EST)
            offset = (parsed - start) // timedelta(milliseconds=1)
            yield offset, price(ask), price(bid), float(volume), 0


def validate(start, path, expected):
    month = start.astimezone(EST).strftime("%Y%m")
    with path.open("rb") as source:
        if path.stat().st_size > MAX_ZIP or file_digest(source, "sha256").hexdigest() != expected:
            raise ValueError("Source exceeds the cap or fails its pinned SHA-256.")
        source.seek(0)
        with ZipFile(source) as archive, archive.open(expected_member(archive, month)) as member:
            return audit(rows_for_hour(member, start, month), start, str(PRICE_UNIT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--month")
    parser.add_argument("--hour", type=hour)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.month and not args.hour and not args.sha256:
        result = acquire(args.month, args.file)
    elif args.hour and args.sha256 and not args.month:
        result = validate(args.hour, args.file, args.sha256)
    else:
        parser.error("Use --month to fetch, or --hour and --sha256 to audit.")
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
