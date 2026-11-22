import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from goldbot.backtesting.historical_replay import ClosedEvent, OpenEvent, Replay
from goldbot.research import news_calendar as nc
from goldbot.strategy.strategy import Signal
from tools import build_news_calendar_611 as builder
from tools import capture_news_calendar_611 as capture
from tools import compare_news_filter_611 as compare


UTC = timezone.utc

BLS_PAGE = """<h2>Schedule</h2><table class="release-list"><thead><tr><th>Reference Month</th>
<th>Release Date</th><th>Release Time</th></tr></thead><tbody>
<tr class="release-list-even-row"><td>October 2025</td><td>Nov. 07, 2025</td><td>08:30 AM</td></tr>
<tr class="release-list-odd-row"><td>May 2025</td><td>Jun. 06, 2025</td><td>08:30 AM</td></tr>
<tr><td>September 2025</td><td>Sept. 05, 2025</td><td>10:00 AM</td></tr>
</tbody></table>"""

FOMC_PAGE = """<h4><a>2025 FOMC Meetings</a></h4>
<div class="row fomc-meeting"><div class="fomc-meeting__month col-xs-5"><strong>January</strong></div>
<div class="fomc-meeting__date col-xs-4">28-29</div></div>
<div class="row fomc-meeting"><div class="fomc-meeting__month col-xs-5"><strong>Apr/May</strong></div>
<div class="fomc-meeting__date col-xs-4">30-1*</div></div>
<div class="row fomc-meeting"><div class="fomc-meeting__month col-xs-5"><strong>August</strong></div>
<div class="fomc-meeting__date col-xs-4">5 (unscheduled)</div></div>
<h4><a>2026 FOMC Meetings</a></h4>
<div class="row fomc-meeting"><div class="fomc-meeting__month col-xs-5"><strong>March</strong></div>
<div class="fomc-meeting__date col-xs-4">17-18*</div></div>"""


def at(*parts):
    return datetime(*parts, tzinfo=UTC)


def calendar(captures, contents):
    return nc.seal({"format": "test", "contents": contents, "captures": captures})


def page(source, *times):
    return {"source": source, "events": [
        {"event": nc.SOURCES[source]["event"], "reference": f"r{i}", "scheduled_utc": t.isoformat(),
         "flags": []} for i, t in enumerate(times)]}


def cap(source, when, digest):
    return {"source": source, "captured_utc": when.isoformat(), "content_sha256": digest, "wayback": "w"}


class ParserTests(unittest.TestCase):
    def test_bls_rows_convert_eastern_time_to_utc(self):
        rows = nc.parse_bls(BLS_PAGE)
        self.assertEqual(rows, [("October 2025", at(2025, 11, 7, 13, 30)),
                                ("May 2025", at(2025, 6, 6, 12, 30)),
                                ("September 2025", at(2025, 9, 5, 14, 0))])
        for bad in ("<p>no table</p>",
                    BLS_PAGE.replace("08:30 AM</td></tr>\n<tr class", "8.30</td></tr>\n<tr class", 1),
                    BLS_PAGE.replace("Nov. 07, 2025", "Smarch 07, 2025"),
                    '<table class="release-list"><tbody></tbody></table>'):
            with self.subTest(bad=bad[:40]), self.assertRaises(nc.CalendarError):
                nc.parse_bls(bad)

    def test_fomc_meetings_spanning_months_and_unscheduled(self):
        events, skipped = nc.parse_fomc(FOMC_PAGE)
        self.assertEqual([(label, when, flags) for label, when, flags in events], [
            ("2025 January 28-29", at(2025, 1, 29, 19, 0), []),
            ("2025 Apr/May 30-1*", at(2025, 5, 1, 18, 0), ["SEP"]),
            ("2026 March 17-18*", at(2026, 3, 18, 18, 0), ["SEP"]),
        ])
        self.assertEqual(skipped, ["2025 August 5 (unscheduled)"])
        with self.assertRaises(nc.CalendarError):
            nc.parse_fomc(FOMC_PAGE.replace("30-1*", "29-30"))
        with self.assertRaises(nc.CalendarError):
            nc.parse_fomc("<p>nothing</p>")


class DecisionTests(unittest.TestCase):
    NFP = at(2025, 11, 7, 13, 30)

    def build(self, extra_captures=(), extra_contents=None):
        contents = {
            "nfp": page("BLS_EMPSIT", self.NFP, at(2025, 12, 5, 13, 30)),
            "cpi": page("BLS_CPI", at(2025, 11, 13, 13, 30), at(2025, 12, 10, 13, 30)),
            "fomc": page("FED_FOMC", at(2025, 12, 10, 19, 0)),
        }
        contents.update(extra_contents or {})
        captures = [cap("BLS_EMPSIT", at(2025, 11, 1), "nfp"), cap("BLS_CPI", at(2025, 11, 1), "cpi"),
                    cap("FED_FOMC", at(2025, 11, 1), "fomc"), *extra_captures]
        return nc.NewsCalendar(calendar(captures, contents))

    def test_blackout_is_inclusive_thirty_minutes_each_side(self):
        news = self.build()
        for moment, allowed in ((self.NFP - timedelta(minutes=31), True),
                                (self.NFP - timedelta(minutes=30), False), (self.NFP, False),
                                (self.NFP + timedelta(minutes=30), False),
                                (self.NFP + timedelta(minutes=30, seconds=1), True)):
            with self.subTest(moment=moment):
                decision = news.decide(moment)
                self.assertEqual(decision.allowed, allowed)
        decision = news.decide(self.NFP)
        self.assertEqual(decision.reason, "NEWS_BLACKOUT")
        (event,) = decision.events
        self.assertEqual((event["event"], event["source"], event["capture_utc"]),
                         ("NFP (Employment Situation)", "BLS_EMPSIT", at(2025, 11, 1).isoformat()))

    def test_missing_stale_and_horizon_block_entries(self):
        news = self.build()
        missing = news.decide(at(2025, 10, 31))
        self.assertEqual((missing.allowed, missing.reason), (False, "CALENDAR_COVERAGE_MISSING"))
        self.assertEqual(len(missing.problems), 3)
        stale = news.decide(at(2025, 12, 6, 12))
        self.assertEqual((stale.allowed, stale.reason), (False, "CALENDAR_STALE"))
        fresh = self.build([cap("BLS_EMPSIT", at(2025, 12, 1), "nfp"), cap("BLS_CPI", at(2025, 12, 1), "cpi"),
                            cap("FED_FOMC", at(2025, 12, 1), "fomc")])
        beyond = fresh.decide(at(2025, 12, 11, 12))
        self.assertEqual((beyond.reason, [p[1] for p in beyond.problems]),
                         ("CALENDAR_HORIZON_EXCEEDED", ["BLS_EMPSIT", "BLS_CPI", "FED_FOMC"]))
        self.assertEqual(fresh.decide(at(2025, 12, 3, 12)).reason, "ALLOWED")

    def test_later_reschedule_is_not_visible_earlier(self):
        moved = at(2025, 11, 20, 13, 30)
        news = self.build([cap("BLS_EMPSIT", at(2025, 11, 15), "nfp2")],
                          {"nfp2": page("BLS_EMPSIT", moved, at(2025, 12, 16, 13, 30))})
        self.assertFalse(news.decide(self.NFP).allowed)
        self.assertTrue(news.decide(at(2025, 11, 19, 13, 30)).allowed)
        self.assertEqual(news.decide(moved).reason, "NEWS_BLACKOUT")

    def test_seal_tamper_and_naive_times_are_refused(self):
        sealed = calendar([cap("BLS_CPI", at(2025, 11, 1), "cpi")], {"cpi": page("BLS_CPI", self.NFP)})
        sealed["captures"][0]["captured_utc"] = at(2025, 1, 1).isoformat()
        with self.assertRaisesRegex(nc.CalendarError, "SHA-256"):
            nc.NewsCalendar(sealed)
        with self.assertRaisesRegex(nc.CalendarError, "unknown content"):
            nc.NewsCalendar(calendar([cap("BLS_CPI", at(2025, 11, 1), "x")], {}))
        with self.assertRaises(nc.CalendarError):
            self.build().decide(datetime(2025, 11, 7, 13, 30))


class BuildAndCaptureTests(unittest.TestCase):
    def test_gzip_encoded_bodies_are_decoded(self):
        import gzip
        self.assertEqual(nc.decode_page(gzip.compress(BLS_PAGE.encode())), BLS_PAGE)
        self.assertEqual(nc.decode_page(BLS_PAGE.encode()), BLS_PAGE)

    def test_build_excludes_unusable_pages_and_verifies_hashes(self):
        import gzip, json, tempfile
        from hashlib import sha256
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pages = {"good": gzip.compress(BLS_PAGE.encode()), "blank": b" " * 762}
            captures = []
            for i, (name, raw) in enumerate(pages.items()):
                path = root / f"{name}.html.gz"
                path.write_bytes(gzip.compress(raw, mtime=0))
                for day, downloaded in ((1, True), (8, False)):
                    captures.append({"source": "BLS_CPI", "captured_utc": at(2025, 10 + i, day).isoformat(),
                                     "content_sha256": sha256(raw).hexdigest(), "file": path.name,
                                     "downloaded": downloaded, "cdx_digest_matches": True, "wayback": "w"})
            manifest = {"range": ["20251001", "20251130"], "captures": captures, "statement_times": []}
            (root / "captures.json").write_text(json.dumps(manifest))
            calendar = builder.build(root)
            self.assertEqual([c["captured_utc"][:10] for c in calendar["captures"]], ["2025-10-01", "2025-10-08"])
            self.assertEqual(len(calendar["excluded_captures"]), 2)
            (unusable,) = calendar["unusable_contents"].values()
            self.assertEqual(unusable["bytes"], 762)
            nc.NewsCalendar(calendar)
            (root / "good.html.gz").write_bytes(gzip.compress(b"tampered", mtime=0))
            with self.assertRaisesRegex(nc.CalendarError, "SHA-256"):
                builder.build(root)

    def test_statement_time_verification(self):
        records = [
            {"meeting": "a", "scheduled_utc": at(2025, 1, 29, 19).isoformat(), "release_time": "02:00 p.m. EST"},
            {"meeting": "b", "scheduled_utc": at(2025, 7, 30, 18).isoformat(), "release_time": "02:00 p.m. EDT"},
            {"meeting": "c", "scheduled_utc": at(2025, 7, 30, 18).isoformat(), "release_time": "02:30 p.m. EDT"},
            {"meeting": "d", "scheduled_utc": at(2025, 1, 29, 19).isoformat(), "error": "HTTP 404"},
        ]
        result = builder.verify_statement_times(records)
        self.assertEqual(result["verified_meetings"], ["a", "b"])
        self.assertEqual(result["mismatches"], [{"meeting": "c", "expected": "02:00 p.m. EDT",
                                                 "found": "02:30 p.m. EDT"}])
        self.assertEqual(result["unavailable"], [{"meeting": "d", "reason": "HTTP 404"}])

    def test_capture_end_to_end_with_simulated_network(self):
        import base64, json, tempfile
        from hashlib import sha1
        from pathlib import Path
        pages = {"empsit": BLS_PAGE.encode(), "cpi": BLS_PAGE.encode(), "fomc": FOMC_PAGE.encode()}

        def digest(raw):
            return base64.b32encode(sha1(raw).digest()).decode()

        def get(url):
            if url.startswith(capture.CDX):
                key = next(k for k in pages if k in url)
                return json.dumps([["timestamp", "digest"], ["20250105000000", digest(pages[key])],
                                   ["20250112000000", digest(pages[key])]]).encode()
            if "/web/" in url:
                return pages[next(k for k in pages if k in url)]
            if url.endswith("monetary20250129a.htm"):
                return b"<p>For release at 2:00 p.m. EST</p>"
            raise OSError("HTTP 404")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "capture"
            with self.assertRaises(ValueError):
                capture.capture(root, "2025-01-01", "20250601", get=get, pause=0, log=lambda *_: None)
            self.assertFalse(root.exists())
            manifest = capture.capture(root, "20250101", "20250601", get=get, pause=0,
                                       log=lambda *_: None, now=at(2025, 6, 1))
            self.assertTrue(all(c["cdx_digest_matches"] for c in manifest["captures"] if c["downloaded"]))
            self.assertEqual([r["meeting"] for r in manifest["statement_times"]],
                             ["2025 January 28-29", "2025 Apr/May 30-1*"])
            calendar = builder.build(root)
            self.assertEqual(calendar["fomc_statement_time"]["verified_meetings"], ["2025 January 28-29"])
            self.assertEqual(len(calendar["fomc_statement_time"]["unavailable"]), 1)
            news = nc.NewsCalendar(calendar)
            self.assertEqual(news.decide(at(2025, 1, 29, 19, 10)).reason, "NEWS_BLACKOUT")
            with self.assertRaises(OSError):
                capture.capture(root, "20250101", "20250601", get=get, pause=0, log=lambda *_: None)

    def test_capture_selection(self):
        bls = [("20250101000000", "A"), ("20250108000000", "A"), ("20250115000000", "B"),
               ("20250122000000", "A")]
        downloads, kept = capture.select("BLS_CPI", bls)
        self.assertEqual((downloads, kept), (["20250101000000", "20250115000000"], bls))
        fomc = [("20250101000000", "x"), ("20250110000000", "y"), ("20250115000000", "z"),
                ("20250120000000", "w")]
        downloads, kept = capture.select("FED_FOMC", fomc)
        self.assertEqual(downloads, ["20250101000000", "20250115000000"])
        self.assertEqual(kept, [fomc[0], fomc[2]])


class FilterTests(unittest.TestCase):
    def replay(self, labels, decisions):
        events = []
        for row, (label, decision) in enumerate(zip(labels, decisions), start=1):
            common = dict(timeframe="H1", source_row=row, raw_server_clock_label=label,
                          raw_label_delta=None if row == 1 else 3600, gap_before=False, open=1.0)
            events.append(OpenEvent(**common))
            events.append(ClosedEvent(**common, high=1.0, low=1.0, close=1.0, tick_volume=1, spread=1,
                                      real_volume=0, indicators=(),
                                      signal=Signal(decision, (f"{decision}_SETUP",))))
        return Replay("H1", "test", "x", True, tuple(events))

    def test_label_to_utc_uses_measured_offsets(self):
        winter = int(at(2025, 11, 7, 15, 0).timestamp())
        summer = int(at(2025, 6, 6, 15, 0).timestamp())
        self.assertEqual(compare.label_to_utc(winter), at(2025, 11, 7, 13, 0))
        self.assertEqual(compare.label_to_utc(summer), at(2025, 6, 6, 12, 0))

    def test_only_blocked_entries_become_hold_and_are_recorded(self):
        news = DecisionTests().build()
        start = int(at(2025, 11, 7, 14, 0).timestamp())  # 12:00 UTC in winter (UTC+2)
        labels = [start + 3600 * i for i in range(4)]     # opens 12:00, 13:00, 14:00, 15:00 UTC
        replay = self.replay(labels, ["BUY", "SELL", "HOLD", "BUY"])
        filtered, blocked, counts = compare.apply_news_filter(replay, news)
        signals = [e.signal for e in filtered.events[1::2]]
        self.assertEqual(signals[0], Signal("HOLD", ("NEWS_BLACKOUT",)))
        self.assertEqual(signals[1], Signal("HOLD", ("NEWS_BLACKOUT",)))
        self.assertEqual(signals[2:], [e.signal for e in replay.events[1::2]][2:])
        self.assertEqual(counts, {"NEWS_BLACKOUT": 2, "TERMINAL_SIGNAL_NOT_EVALUATED": 1})
        self.assertEqual([(b["signal_row"], b["entry_utc"], b["events"][0]["scheduled_utc"]) for b in blocked],
                         [(1, at(2025, 11, 7, 13).isoformat(), DecisionTests.NFP.isoformat()),
                          (2, at(2025, 11, 7, 14).isoformat(), DecisionTests.NFP.isoformat())])
        self.assertEqual(filtered.events[0::2], replay.events[0::2])


class KenyaTimeAndTransitionTests(unittest.TestCase):
    """Kenya time is display only; blackouts stay in UTC. EAT is UTC+3 all year."""

    def test_reviewer_table_new_york_to_kenya(self):
        from datetime import date, time
        cases = (
            (date(2026, 1, 9), time(8, 30), "2026-01-09 13:30 UTC", "2026-01-09 08:30 EST", "2026-01-09 16:30 EAT"),
            (date(2026, 6, 5), time(8, 30), "2026-06-05 12:30 UTC", "2026-06-05 08:30 EDT", "2026-06-05 15:30 EAT"),
            (date(2026, 1, 28), time(14, 0), "2026-01-28 19:00 UTC", "2026-01-28 14:00 EST", "2026-01-28 22:00 EAT"),
            (date(2026, 6, 17), time(14, 0), "2026-06-17 18:00 UTC", "2026-06-17 14:00 EDT", "2026-06-17 21:00 EAT"),
        )
        for day, clock, utc, new_york, kenya in cases:
            with self.subTest(day=day):
                shown = nc.display_times(nc.to_utc(day, clock))
                self.assertEqual((shown["utc"], shown["new_york"], shown["kenya"]), (utc, new_york, kenya))
        with self.assertRaises(nc.CalendarError):
            nc.display_times(datetime(2026, 1, 9, 13, 30))

    def test_blackout_window_display(self):
        row = nc.describe_event({"event": "CPI", "reference": "x", "scheduled_utc": "2026-03-11T12:30:00+00:00"})
        self.assertEqual((row["blackout_from"]["kenya"], row["release"]["kenya"], row["blackout_until"]["kenya"]),
                         ("2026-03-11 15:00 EAT", "2026-03-11 15:30 EAT", "2026-03-11 16:00 EAT"))

    def test_server_label_to_utc_in_us_eu_mismatch_weeks(self):
        """Server labels (Exness, EU rule) and New York change on different dates."""
        cases = (  # (server label wall time, expected UTC, why)
            (at(2026, 3, 6, 15, 30), at(2026, 3, 6, 13, 30), "both on winter time: NFP at 15:30 server"),
            (at(2026, 3, 11, 14, 30), at(2026, 3, 11, 12, 30), "US summer, EU winter: CPI at 14:30 server"),
            (at(2026, 4, 3, 15, 30), at(2026, 4, 3, 12, 30), "both on summer time: NFP at 15:30 server"),
            (at(2026, 10, 28, 20, 0), at(2026, 10, 28, 18, 0), "EU winter, US summer: FOMC at 20:00 server"),
            (at(2026, 11, 6, 15, 30), at(2026, 11, 6, 13, 30), "both on winter time again"),
        )
        for label, utc, why in cases:
            with self.subTest(why=why):
                self.assertEqual(compare.label_to_utc(int(label.timestamp())), utc)

    def test_mismatch_week_blackout_edges_from_server_labels(self):
        cpi = at(2026, 3, 11, 12, 30)
        news = nc.NewsCalendar(calendar(
            [cap(s, at(2026, 3, 1), s) for s in nc.SOURCES],
            {"BLS_EMPSIT": page("BLS_EMPSIT", at(2026, 4, 3, 12, 30)),
             "BLS_CPI": page("BLS_CPI", cpi, at(2026, 4, 10, 12, 30)),
             "FED_FOMC": page("FED_FOMC", at(2026, 4, 29, 18, 0))}))
        for label, blocked in ((at(2026, 3, 11, 13, 59), False), (at(2026, 3, 11, 14, 0), True),
                               (at(2026, 3, 11, 15, 0), True), (at(2026, 3, 11, 15, 1), False)):
            with self.subTest(server_label=label):
                decision = news.decide(compare.label_to_utc(int(label.timestamp())))
                self.assertEqual(not decision.allowed, blocked)

    @unittest.skipUnless(Path(__file__).resolve().parents[1].joinpath(
        "historical_data/news_calendar/calendar.json").exists(), "committed calendar is local data")
    def test_committed_calendar_events_and_kenya_view(self):
        import json
        from tools import news_schedule_611 as viewer
        root = Path(__file__).resolve().parents[1]
        news = nc.NewsCalendar(json.loads((root / "historical_data/news_calendar/calendar.json").read_bytes()))
        expected = {
            ("BLS_EMPSIT", at(2026, 3, 6, 13, 30)): "2026-03-06 16:30 EAT",
            ("BLS_CPI", at(2026, 3, 11, 12, 30)): "2026-03-11 15:30 EAT",
            ("FED_FOMC", at(2026, 3, 18, 18, 0)): "2026-03-18 21:00 EAT",
            ("FED_FOMC", at(2026, 10, 28, 18, 0)): "2026-10-28 21:00 EAT",
            ("BLS_EMPSIT", at(2026, 11, 6, 13, 30)): "2026-11-06 16:30 EAT",
        }
        for (source, when), kenya in expected.items():
            with self.subTest(source=source, when=when):
                decision = news.decide(when)
                self.assertEqual(decision.reason, "NEWS_BLACKOUT")
                self.assertIn(source, {e["source"] for e in decision.events})
                self.assertEqual(nc.display_times(when)["kenya"], kenya)
        view = viewer.schedule(news, at(2026, 3, 9, 6, 0), 7)
        self.assertEqual(view["decision"], "ALLOWED")
        self.assertEqual([(r["event"], r["release"]["kenya"]) for r in view["upcoming"]],
                         [("CPI", "2026-03-11 15:30 EAT")])
        today = viewer.schedule(news, at(2026, 11, 22, 12), 21)
        self.assertEqual(today["decision"], "ALLOWED")
        self.assertEqual([(r["event"], r["release"]["kenya"]) for r in today["upcoming"]],
                         [("NFP (Employment Situation)", "2026-12-04 16:30 EAT"),
                          ("FOMC statement", "2026-12-09 22:00 EAT"), ("CPI", "2026-12-10 16:30 EAT")])
        # Without a new capture, the 9 Nov FOMC capture passes 35 days on 14 Dec.
        later = viewer.schedule(news, at(2026, 12, 15, 12), 7)
        self.assertEqual((later["decision"], later["problems"]),
                         ("CALENDAR_STALE", [{"code": "CALENDAR_STALE", "source": "FED_FOMC"}]))


if __name__ == "__main__":
    unittest.main()
