"""Bounded Phase 6.9.4.1 diagnostics. Use tools/exness_phase_6941.ps1."""

import json
import socket
import struct
import sys

from goldbot.core.exness_demo import DemoProfile, PROFILE, VerificationError
from tools import diagnose_time as clock
from tools.verify_exness_time_history import SERVER, SUFFIX, collect

NTP_HOST = "162.159.200.1"
NTP_EPOCH = 2208988800
NTP_SCALE = 2**32


def ntp_bounds(reply, sent, before, after):
    if (len(reply) < 48 or reply[0] != 0x24 or not 1 <= reply[1] <= 15
            or reply[24:32] != sent or reply[32:40] == bytes(8)
            or reply[40:48] == bytes(8)):
        raise ValueError("Invalid NTP server response")
    receive, transmit = struct.unpack("!QQ", reply[32:48])
    elapsed = after["monotonic"] - before["monotonic"]
    start, end = (clock.wall(point).timestamp() for point in (before, after))
    # Unfold the NTP era around the local wall clock.
    era = round((start + NTP_EPOCH - transmit / NTP_SCALE) / NTP_SCALE)
    correction = era * NTP_SCALE - NTP_EPOCH
    t2, t3 = receive / NTP_SCALE + correction, transmit / NTP_SCALE + correction
    delay = (end - start) - (t3 - t2)
    if (not 0 <= elapsed <= 2.1 or abs(end - start - elapsed) > clock.WALL_STEP_TOLERANCE
            or not 0 <= t3 - t2 <= elapsed or delay < 0):
        raise ValueError("Invalid NTP timing bracket")
    root_delay, dispersion = struct.unpack("!iI", reply[4:12])
    root_distance = max(0, root_delay / 65536) / 2 + dispersion / 65536
    allowance = root_distance + clock.WALL_STEP_TOLERANCE
    return [t3 - end - allowance, t2 - start + allowance], delay


def ntp_probe():
    report = {"source": "Cloudflare", "address": NTP_HOST, "protocol": "NTPv4 UDP",
              "before": clock.mark()}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as peer:
            peer.settimeout(2)
            peer.connect((NTP_HOST, 123))
            report["before"] = clock.mark()
            start = clock.wall(report["before"]).timestamp()
            sent = struct.pack("!Q", int((start + NTP_EPOCH) * NTP_SCALE) % 2**64)
            peer.send(b"\x23" + bytes(39) + sent)
            reply = peer.recv(512)
        report["after"] = clock.mark()
        bounds, delay = ntp_bounds(reply, sent, report["before"], report["after"])
        report.update(correction_bounds_s=bounds, round_trip_s=delay, stratum=reply[1])
    except (OSError, ValueError) as error:
        report.setdefault("after", clock.mark())
        report["error"] = type(error).__name__
    return report


def local_profile(stream):
    try:
        values = json.loads(stream.readline(8192))
        profile = DemoProfile.from_environment({
            "GOLDBOT_DEMO_PROFILE": PROFILE,
            "GOLDBOT_EXNESS_TERMINAL": values["terminal"],
            "GOLDBOT_EXNESS_DEMO_SERVER": values["server"],
            "GOLDBOT_EXNESS_DEMO_LOGIN": values["login"],
        })
    except (KeyError, TypeError, ValueError):
        raise VerificationError("Local opt-in profile is absent or invalid.") from None
    if profile.server != SERVER or not str(profile.login).endswith(SUFFIX):
        raise VerificationError("The local profile does not match the selected demo route.")
    return profile


def summarize(report):
    history = report.get("history", {})
    for key in ("M1", "M15", "H1"):
        if key in history:
            bars = history[key].get("bars", [])
            history[key]["observed_raw_open_span"] = (
                [bars[0]["raw_open"], bars[-1]["raw_open"]] if bars else None
            )
    for key in ("count_probe", "range_probe"):
        if key in history:
            probe = history[key]
            stamps = [tick["raw_ms"] for tick in probe["ticks"]]
            probe["returned_count"] = len(stamps)
            probe["observed_raw_ms_span"] = [min(stamps), max(stamps)] if stamps else None
            probe["raw_ms_nondecreasing"] = stamps == sorted(stamps) if stamps else None
            probe["valid_tick_count"] = sum(clock.valid_tick(tick) for tick in probe["ticks"])
    if "range_probe" in history:
        probe = history["range_probe"]
        start = probe.pop("requested_inclusive_raw_seconds")[0]
        probe["request_arguments_raw_seconds"] = [start, start + 60]
        probe["reconstruction_interval_raw_seconds_half_open"] = [start, start + 60]
    report["session_diagnostics"] = {
        "evidence": "Observed bar gaps in raw coordinates",
        "account_scoped_quote_and_trade_intervals": "UNVERIFIED",
        "holiday_and_maintenance_overrides": "UNVERIFIED",
    }
    report["risk_day"] = {"approved_boundary": "UNVERIFIED", "opening_equity": "NOT_COLLECTED"}
    report["archive_coverage"] = "UNVERIFIED_BEYOND_BOUNDED_SAMPLES"


def main():
    report = {"status": "UNVERIFIED", "scope": "diagnostic only", "samples": []}
    try:
        profile = local_profile(sys.stdin)
        import MetaTrader5 as mt5

        first = ntp_probe()
        try:
            collect(mt5, profile, report)
        finally:
            last = ntp_probe()
            report["external_clock_probes"] = [first, last]
            report["clock"] = clock.assess_clock(first, last, report["samples"])
    except VerificationError as error:
        report["terminal_failure"] = str(error)
    except Exception as error:
        report["terminal_failure_type"] = type(error).__name__
    report["quote_state"] = clock.quote_state(report["samples"])
    if report.get("clock", {}).get("status") == "UTC_WITHIN_TOLERANCE":
        lower, upper = report["clock"]["correction_bounds_s"]
        for sample in report["samples"]:
            if sample["tick"] and clock.valid_tick(sample["tick"]):
                event = sample["tick"]["raw_ms"] / 1000
                sample["age_s_if_raw_utc"] = [
                    clock.wall(sample["before"]).timestamp() + lower - event,
                    clock.wall(sample["after"]).timestamp() + upper - event,
                ]
    summarize(report)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
