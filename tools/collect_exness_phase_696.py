"""Run the existing guarded collector into a separate Phase 6.9.6 journal."""

import argparse
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from tools import collect_exness_phase_695 as collector

DATABASE = Path("reports/phase_6_9_6/boundary.sqlite3")
PHASE_SCOPE = dict(collector.SCOPE, phase="6.9.6")
DEADLINE_SECONDS = 75
POLL_INTERVAL_SECONDS = 6


def worker():
    pin = collector.local_profile(sys.stdin)
    trusted = collector.local_profile(sys.stdin)
    if pin != trusted or pin.server != collector.SERVER:
        raise collector.VerificationError("Independent pin did not match.")
    import MetaTrader5 as mt5

    with collector.exclusive(DATABASE):
        DATABASE.touch(exist_ok=False)
        with closing(sqlite3.connect(DATABASE, timeout=0)) as connection:
            journal = collector.Journal(connection, scope=PHASE_SCOPE)
            status = collector.collect(
                journal, collector.Reader(mt5, pin, collector.running_terminals),
                poll_interval=POLL_INTERVAL_SECONDS,
            )
            print(collector.encode(dict(journal.manifest(), status=status)))
    return 0 if status == "COMPLETE_BOUNDED_DIAGNOSTIC" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker:
            return worker()
        profile_lines = sys.stdin.readline(8192) + sys.stdin.readline(8192)
        return subprocess.run(
            [sys.executable, "-B", "-m", "tools.collect_exness_phase_696", "--worker"],
            input=profile_lines, text=True, timeout=DEADLINE_SECONDS, check=False,
        ).returncode
    except subprocess.TimeoutExpired:
        print("The 75-second watchdog stopped the one-shot diagnostic.", file=sys.stderr)
    except Exception as error:
        print(f"Diagnostic stopped ({type(error).__name__}).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
