"""Bounded XAUUSD diagnostics. Launch through the Windows opt-in runner."""

import hashlib
import json
import math
import msvcrt
import sqlite3
import subprocess
import sys
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from goldbot.core.exness_demo import (
    KE_COMPANY, SYMBOL, VerificationError, check_identity, require_running_terminal,
    running_terminals,
)
from tools.verify_exness_phase_6941 import local_profile, ntp_probe
from tools.verify_exness_time_history import SERVER
from tools.diagnose_time import assess_clock

POLLS = 8
ATTEMPTS = 2
DEADLINE = 55
MAX_EVENTS = 8192
MAX_RUN_EVENTS = 40
MAX_EVENT_BYTES = 16384
FRAMES = {"M15": 900, "H1": 3600}
QUOTE_FIELDS = ("time", "time_msc", "bid", "ask", "last", "volume", "flags", "volume_real")
BAR_FIELDS = ("time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
PRICE_FIELDS = {"open", "high", "low", "close"}
SCOPE = {"phase": "6.9.5", "diagnostic_only": True, "exposed": True,
         "holdout_eligible": False, "coverage": "UNKNOWN_NON_EXHAUSTIVE",
         "production_utc_mapping": "UNVERIFIED"}
DATABASE = Path("reports/phase_6_9_5/diagnostic.sqlite3")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def stamp():
    before = time.monotonic_ns()
    utc = time.time_ns()
    return {"host_utc_unix_ns": utc, "monotonic_before_ns": before,
            "monotonic_after_ns": time.monotonic_ns()}


@contextmanager
def exclusive(path):
    with path.with_suffix(".lock").open("a+b") as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


class Journal:
    def __init__(self, connection, read_only=False, *, scope=None):
        self.db = connection
        self.scope = dict(SCOPE if scope is None else scope)
        self.seq = 0
        self.head = "0" * 64
        self.active = None
        self.payloads = set()
        if not read_only:
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA max_page_count=65536")
        if self.db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise VerificationError("Storage integrity check failed.")
        if not read_only:
            with self.db:
                self.db.execute(
                    "CREATE TABLE IF NOT EXISTS events("
                    "seq INTEGER PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL)"
                )
        for seq, body, checksum in self.db.execute(
                "SELECT seq, body, sha256 FROM events ORDER BY seq"):
            if (seq != self.seq + 1 or seq > MAX_EVENTS or len(body) > MAX_EVENT_BYTES
                    or digest(body) != checksum):
                raise VerificationError("Storage manifest is invalid.")
            event = json.loads(body)
            if event["seq"] != seq or event["previous"] != self.head or event["scope"] != self.scope:
                raise VerificationError("Storage chain is invalid.")
            self.validate_event(event)
            self.seq, self.head = seq, checksum

    def validate_event(self, event):
        kind = event["kind"]
        run = event["run"]
        if kind == "start":
            if self.active is not None:
                raise VerificationError("Overlapping diagnostic runs.")
            self.active = run
        elif self.active is None or run != self.active:
            raise VerificationError("Event outside its diagnostic run.")
        elif kind in {"finish", "interrupted"}:
            self.active = None
        for item in event["data"].get("objects", []):
            key = item["sha256"]
            if "raw" in item:
                if key in self.payloads or digest(encode(item["raw"])) != key:
                    raise VerificationError("Storage payload hash is invalid.")
                self.payloads.add(key)
            elif key not in self.payloads:
                raise VerificationError("Storage payload reference is missing.")

    def append(self, run, kind, data, objects=()):
        references = []
        pending = set()
        for raw in objects:
            key = digest(encode(raw))
            item = {"sha256": key}
            if key not in self.payloads and key not in pending:
                item["raw"] = raw
                pending.add(key)
            references.append(item)
        event = {"seq": self.seq + 1, "previous": self.head, "run": run, "kind": kind,
                 "scope": self.scope, "recorded": stamp(), "data": dict(data, objects=references)}
        body = encode(event)
        if len(body) > MAX_EVENT_BYTES or self.seq >= MAX_EVENTS:
            raise VerificationError("Storage bound exceeded.")
        checksum = digest(body)
        with self.db:
            self.db.execute("INSERT INTO events VALUES (?, ?, ?)", (event["seq"], body, checksum))
        self.validate_event(event)
        self.seq, self.head = event["seq"], checksum

    def manifest(self):
        return {"scope": self.scope, "event_count": self.seq, "chain_head_sha256": self.head,
                "unique_payloads": len(self.payloads), "interrupted_run_pending": self.active is not None}


class RetryableRead(VerificationError):
    def __init__(self, reason, error_code):
        super().__init__(reason)
        self.error_code = error_code


class Reader:
    def __init__(self, api, pin, discover):
        self.api = api
        self.pin = pin
        self.discover = discover

    def identity(self):
        terminal = self.api.terminal_info()
        if terminal is None or not getattr(terminal, "connected", False):
            raise RetryableRead("terminal_disconnected", None)
        terminal, account = check_identity(self.api, self.pin)
        if account.company != KE_COMPANY or terminal.trade_allowed is not False:
            raise VerificationError("Strict entity or Algo Trading check failed.")
        return terminal

    def attach(self):
        require_running_terminal(self.pin.terminal, self.discover())
        if not self.api.initialize(str(self.pin.terminal), timeout=5000):
            raise RetryableRead("attachment_failed", int(self.api.last_error()[0]))
        terminal = self.identity()
        symbol, _ = self.read(self.api.symbol_info, SYMBOL)
        if getattr(symbol, "name", None) != SYMBOL or getattr(symbol, "custom", None) is not False:
            raise VerificationError("Exact non-custom XAUUSD is unavailable.")
        return {"terminal_build": int(terminal.build), "entity": KE_COMPANY,
                "server": SERVER, "suffix": "9498", "mode": "demo", "currency": "USD",
                "algo_trading": False, "symbol": SYMBOL}

    def read(self, method, *args):
        self.identity()
        before = stamp()
        result = method(*args)
        after = stamp()
        error_code = self.api.last_error()[0] if result is None else None
        self.identity()
        if result is None:
            raise RetryableRead("null_market_data_response", int(error_code))
        wall_delta = after["host_utc_unix_ns"] - before["host_utc_unix_ns"]
        mono_delta = after["monotonic_before_ns"] - before["monotonic_before_ns"]
        return result, {"before": before, "after": after, "error_code": error_code,
                        "possible_wall_step": abs(wall_delta - mono_delta) > 100_000_000}


def quote_raw(tick):
    raw = {key: getattr(tick, key) for key in QUOTE_FIELDS}
    if (not all(math.isfinite(value) for value in raw.values())
            or raw["time"] <= 0 or raw["time_msc"] // 1000 != raw["time"]
            or not 0 < raw["bid"] <= raw["ask"]):
        raise VerificationError("Invalid quote snapshot.")
    return raw


def closed_bars(rows, period, anchor):
    if len(rows) > 2:
        raise VerificationError("Closed-bar response exceeded requested count.")
    bars = [{key: float(row[key]) if key in PRICE_FIELDS
             else int(row[key]) for key in BAR_FIELDS} for row in rows]
    previous = 0
    for row in bars:
        label = row["time"]
        prices = [row[key] for key in ("low", "open", "close", "high")]
        if (label <= previous or label % period or label + period > anchor
                or not all(math.isfinite(price) and price > 0 for price in prices)
                or not prices[0] <= min(prices[1:3]) <= max(prices[1:3]) <= prices[3]):
            raise VerificationError("Invalid closed bar in raw coordinates.")
        previous = label
    return bars


def clock_sample(timing):
    return {key: {
        "monotonic": timing[key]["monotonic_before_ns"] / 1e9,
        "wall_utc": datetime.fromtimestamp(
            timing[key]["host_utc_unix_ns"] / 1e9, timezone.utc).isoformat(),
    } for key in ("before", "after")}


def collect(journal, reader, probe=ntp_probe, pause=time.sleep, *, poll_interval=1):
    if journal.active is not None:
        journal.append(journal.active, "interrupted", {"reason": "prior_run_without_finish",
                       "coverage": "UNKNOWN_SINCE_LAST_DURABLE_EVENT"})
    if journal.seq + MAX_RUN_EVENTS > MAX_EVENTS:
        raise VerificationError("Diagnostic store is full.")
    run = uuid4().hex
    journal.append(run, "start", {"clock": "host UTC and process monotonic",
                   "inter_run_coverage": "UNKNOWN", "quote_method": "polling_snapshot",
                   "bar_method": "closed_positions_1_and_2", "poll_limit": POLLS})
    state = {}
    admitted_labels = {frame: set() for frame in FRAMES}
    last_quote = None
    samples = []
    poll = 0
    status = "FAILED_CLOSED"
    first = probe()
    try:
        journal.append(run, "external_clock", {"position": "before", "probe": first})
        for attempt in range(1, ATTEMPTS + 1):
            admission_floor = None
            journal.append(run, "attach_attempt", {"attempt": attempt, "coverage": "UNKNOWN"})
            try:
                identity = reader.attach()
                journal.append(run, "attached", identity)
                while poll < POLLS:
                    poll += 1
                    tick, timing = reader.read(reader.api.symbol_info_tick, SYMBOL)
                    samples.append(clock_sample(timing))
                    quote = quote_raw(tick)
                    if admission_floor is None:
                        admission_floor = quote["time"]
                    regressed = last_quote is not None and quote["time_msc"] < last_quote
                    journal.append(run, "quote_snapshot", dict(
                        timing, poll=poll, raw_label_regressed=regressed,
                        between_poll_coverage="UNKNOWN"), [{"type": "snapshot", "fields": quote}])
                    if regressed:
                        raise VerificationError("Raw quote label regressed.")
                    last_quote = quote["time_msc"]
                    for frame, period in FRAMES.items():
                        rows, timing = reader.read(
                            reader.api.copy_rates_from_pos, SYMBOL,
                            getattr(reader.api, "TIMEFRAME_" + frame), 1, 2)
                        samples.append(clock_sample(timing))
                        bars = closed_bars(rows, period, quote["time"])
                        high = state.get(frame)
                        seen = admitted_labels[frame]
                        admitted = []
                        gaps = []
                        for bar in bars:
                            label = bar["time"]
                            if label not in seen and label + period <= admission_floor:
                                continue
                            if high is not None and label > high + period:
                                gaps.append([high + period, label])
                            if high is None and label > admission_floor // period * period:
                                gaps.append([admission_floor // period * period, label])
                            high = label if high is None else max(high, label)
                            seen.add(label)
                            admitted.append({"type": "closed_bar", "frame": frame, "fields": bar})
                        state[frame] = high
                        first_open = admission_floor // period * period
                        closed_through = quote["time"] // period * period
                        next_open = first_open if high is None else max(first_open, high + period)
                        if next_open < closed_through:
                            gaps.append([next_open, closed_through])
                        journal.append(run, "bars", dict(
                            timing, poll=poll, frame=frame, returned=len(bars),
                            admission_floor_raw_seconds=admission_floor,
                            excluded_pre_attachment_close_count=len(bars) - len(admitted),
                            raw_missing_open_ranges_half_open=gaps, coverage="UNKNOWN"), admitted)
                    if poll < POLLS:
                        pause(poll_interval)
                status = "COMPLETE_BOUNDED_DIAGNOSTIC"
                break
            except RetryableRead as error:
                journal.append(run, "coverage_gap", {"attempt": attempt, "poll": poll,
                               "reason": str(error), "api_error_code": error.error_code,
                               "coverage": "UNKNOWN"})
                if poll >= POLLS or attempt == ATTEMPTS:
                    break
                pause(1)
            finally:
                reader.api.shutdown()
    except VerificationError as error:
        journal.append(run, "coverage_gap", {"poll": poll, "reason": str(error),
                       "coverage": "UNKNOWN"})
    except Exception as error:
        journal.append(run, "coverage_gap", {"poll": poll, "reason": type(error).__name__,
                       "coverage": "UNKNOWN"})
    last = probe()
    journal.append(run, "external_clock", {"position": "after", "probe": last})
    journal.append(run, "finish", {"status": status, "poll_attempts": poll,
                   "tail_coverage": "UNKNOWN", "external_clock_authenticated": False,
                   "host_clock_assessment": assess_clock(first, last, samples)})
    return status


def worker():
    # The runner sends the current opt-in and independent pin on separate stdin lines.
    pin = local_profile(sys.stdin)
    trusted = local_profile(sys.stdin)
    if pin != trusted or pin.server != SERVER:
        raise VerificationError("Independent pin did not match.")
    import MetaTrader5 as mt5

    with exclusive(DATABASE), closing(sqlite3.connect(DATABASE, timeout=0)) as connection:
        journal = Journal(connection)
        status = collect(journal, Reader(mt5, pin, running_terminals))
        print(encode(dict(journal.manifest(), status=status)))
    return 0 if status == "COMPLETE_BOUNDED_DIAGNOSTIC" else 1


def main():
    try:
        if sys.argv[1:] == ["--worker"]:
            return worker()
        if sys.argv[1:] == ["--verify"]:
            with exclusive(DATABASE), closing(sqlite3.connect(
                    DATABASE.resolve().as_uri() + "?mode=ro", uri=True, timeout=0)) as connection:
                print(encode(Journal(connection, read_only=True).manifest()))
            return 0
        profile_lines = sys.stdin.readline(8192) + sys.stdin.readline(8192)
        return subprocess.run(
            [sys.executable, "-B", "-m", "tools.collect_exness_phase_695", "--worker"],
            input=profile_lines, text=True, timeout=DEADLINE, check=False,
        ).returncode
    except subprocess.TimeoutExpired:
        print("Watchdog stopped the diagnostic. The next authorized run records the interruption.",
              file=sys.stderr)
    except Exception as error:
        print(f"Diagnostic stopped ({type(error).__name__}).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
