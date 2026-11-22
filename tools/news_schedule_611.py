"""Show the news blackout calendar's status and upcoming releases in Kenya time.

Display only. Times are computed in UTC and shown in Kenya (EAT, UTC+3 all
year), New York and UTC. The verdict comes from the same
NewsCalendar.decide used by the backtests, so a stale or out-of-range
calendar is reported as such. The calendar is research only; it does not
replace the manual news check in Stage C.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from goldbot.research.news_calendar import (
    SOURCES, CalendarError, NewsCalendar, describe_event, display_times,
)


def latest_calendar(root):
    """The newest rebuilt calendar, or the original calendar.json if none."""
    root = Path(root)
    rebuilt = sorted(root.glob("calendar-*.json"))
    return rebuilt[-1] if rebuilt else root / "calendar.json"


def schedule(calendar, moment, days):
    horizon = moment + timedelta(days=days)
    sources, upcoming = {}, []
    report = calendar.coverage_report(moment)
    for source in SOURCES:
        latest = calendar.latest_capture(source, moment)
        if latest is None:
            sources[source] = {"capture": None}
            continue
        captured, digest, events = latest
        limits = report["sources"][source]
        sources[source] = {"captured": display_times(captured), "method": limits["method"],
                           "age_days": round((moment - captured).total_seconds() / 86400, 1),
                           "stale_after": display_times(datetime.fromisoformat(limits["stale_after_utc"])),
                           "listed_until": display_times(datetime.fromisoformat(limits["listed_until_utc"]))}
        for event in events:
            when = datetime.fromisoformat(event["scheduled_utc"])
            if moment - calendar.blackout <= when <= horizon:
                upcoming.append((when, describe_event(event, calendar.blackout)))
    decision = calendar.decide(moment)
    refused_after = report["entries_refused_after_utc"]
    return {"at": display_times(moment), "decision": decision.reason,
            "problems": [{"code": c, "source": s} for c, s in decision.problems],
            "entries_refused_after": None if refused_after is None
            else display_times(datetime.fromisoformat(refused_after)),
            "sources": sources, "upcoming": [row for _, row in sorted(upcoming, key=lambda r: r[0])]}


def render(view):
    lines = [f"At {view['at']['kenya']}  ({view['at']['utc']})",
             f"New entry now: {view['decision']}"]
    lines += [f"  problem: {p['code']} ({p['source']})" for p in view["problems"]]
    for source, info in view["sources"].items():
        if "captured" not in info:
            lines.append(f"  {source:11} no capture")
        else:
            lines.append(f"  {source:11} {info['method']:15} captured {info['captured']['kenya']} "
                         f"({info['age_days']} d) | stale after {info['stale_after']['kenya']} "
                         f"| listed until {info['listed_until']['kenya']}")
    if view["entries_refused_after"]:
        lines.append(f"Without a new capture, entries are refused after "
                     f"{view['entries_refused_after']['kenya']} ({view['entries_refused_after']['utc']})")
    lines.append("Upcoming releases (blackout window in Kenya time):")
    if not view["upcoming"]:
        lines.append("  none listed in range")
    for row in view["upcoming"]:
        lines.append(f"  {row['release']['kenya']}  {row['event']:28} "
                     f"blackout {row['blackout_from']['kenya'][11:16]}-{row['blackout_until']['kenya'][11:16]} EAT"
                     f"   [{row['release']['new_york']}]")
    lines.append("Research only. The Stage C manual news check remains mandatory.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--calendar", type=Path,
                        help="calendar file (default: newest in historical_data/news_calendar)")
    parser.add_argument("--at", help="ISO time with offset, e.g. 2026-03-11T15:00+03:00 (default: now)")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        moment = datetime.now(timezone.utc) if args.at is None else datetime.fromisoformat(args.at)
        if moment.tzinfo is None:
            raise CalendarError("--at needs an explicit offset, e.g. +03:00 for Kenya.")
        path = args.calendar or latest_calendar("historical_data/news_calendar")
        view = dict(schedule(NewsCalendar(json.loads(path.read_bytes())), moment, args.days),
                    calendar_file=str(path))
    except (OSError, ValueError) as error:
        print(f"Schedule unavailable: {error}", file=sys.stderr)
        return 1
    print(json.dumps(view, indent=2) if args.json else render(view))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
