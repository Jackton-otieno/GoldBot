"""Fetch and analyze one month of the Exness public XAUUSD tick archive.

fetch    downloads one monthly ZIP to a new file and writes <file>.manifest.json.
analyze  verifies the pinned digest, audits every tick, writes UTC bid candles,
         and optionally infers the MT5 server-label offset from local exports.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from goldbot.market_data.archive_comparison import infer_offsets, load_mt5_candles, summarize
from goldbot.market_data.exness_archive import (
    ArchiveError, SYMBOLS, TIMEFRAMES, audit, fetch, parse_month,
)
from goldbot.research import exposure_log


def _new_directory(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ArchiveError("Output directory must be new or empty.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def run_fetch(args):
    year, month = parse_month(args.month)
    manifest = fetch(args.symbol, year, month, args.output)
    _write_json(f"{args.output}.manifest.json", manifest)
    return manifest


def run_analyze(args):
    year, month = parse_month(args.month)
    exposure_log.verify(args.exposure_log)
    output = _new_directory(args.output)
    result = audit(args.file, args.symbol, year, month, args.sha256)
    summary = dict(result.report(), symbol=args.symbol, month=args.month,
                   source_sha256=args.sha256, source_file=Path(args.file).name)
    for name in TIMEFRAMES:
        with (output / f"{args.symbol}_{name}_utc_bid.csv").open("x", newline="", encoding="ascii") as target:
            rows = result.candle_rows(name)
            first = next(rows)
            writer = csv.DictWriter(target, fieldnames=list(first), lineterminator="\n")
            writer.writeheader()
            writer.writerow(first)
            writer.writerows(rows)
    comparisons = {}
    for name, path in (("M15", args.mt5_m15), ("H1", args.mt5_h1)):
        if path is None:
            continue
        width = TIMEFRAMES[name] // 1000
        archive = {start // 1000: tuple(bar[:4]) for start, bar in result.candles[name].items()}
        mt5 = load_mt5_candles(path)
        days = infer_offsets(archive, mt5)
        comparisons[name] = {"mt5_export": Path(path).name, "bar_seconds": width,
                             "summary": summarize(days, archive, mt5), "days": days}
    _write_json(output / "summary.json", summary)
    if comparisons:
        _write_json(output / "clock-offset.json", comparisons)
    exposure_log.append(
        path=args.exposure_log, source=f"Exness public tick archive {args.symbol} {args.month}",
        sha256_digest=args.sha256,
        coverage_utc=[summary["first_tick_utc"], summary["last_tick_utc"]],
        purpose="Archive audit" + (" and MT5 clock-offset comparison" if comparisons else ""),
        tool="tools.exness_archive_611 analyze")
    brief = {k: summary[k] for k in ("ticks", "first_tick_utc", "last_tick_utc")}
    brief["spread_p50"] = summary["spread"]["p50"]
    brief["offsets"] = {k: v["summary"]["offset_hours_by_day_count"] for k, v in comparisons.items()}
    return brief


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    get = commands.add_parser("fetch")
    get.add_argument("--symbol", default="XAUUSD", choices=sorted(SYMBOLS))
    get.add_argument("--month", required=True, help="YYYY-MM")
    get.add_argument("--output", type=Path, required=True, help="new .zip path")
    check = commands.add_parser("analyze")
    check.add_argument("--file", type=Path, required=True)
    check.add_argument("--sha256", required=True)
    check.add_argument("--symbol", default="XAUUSD", choices=sorted(SYMBOLS))
    check.add_argument("--month", required=True, help="YYYY-MM")
    check.add_argument("--output", type=Path, required=True, help="new or empty directory")
    check.add_argument("--mt5-m15", type=Path)
    check.add_argument("--mt5-h1", type=Path)
    check.add_argument("--exposure-log", type=Path, default=exposure_log.DEFAULT_LOG,
                       help="append-only record of examined data (default docs/evidence/exposure-log.jsonl)")
    args = parser.parse_args(argv)
    try:
        result = run_fetch(args) if args.command == "fetch" else run_analyze(args)
    except (ArchiveError, exposure_log.ExposureLogError, OSError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
