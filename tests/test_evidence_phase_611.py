import copy
import io
import json
import tempfile
import unittest
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

from goldbot.core import server_clock
from goldbot.core.exness_demo import PROFILE, DemoProfile, VerificationError
from goldbot.market_data import exness_archive as ea
from goldbot.market_data.archive_comparison import infer_offsets, load_mt5_candles, summarize
from goldbot.research import exposure_log
from goldbot.risk.booked_pnl import balance_at, protocol_check, reconcile
from tools import exness_archive_611 as archive_tool
from tools import read_demo_deals_611 as reader


HEADER = '"Exness","Symbol","Timestamp","Bid","Ask"\n'


def row(stamp, bid, ask, symbol="XAUUSD"):
    return f'"exness","{symbol}","{stamp}",{bid},{ask}\n'


class ArchiveFixture(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def archive(self, body, *, header=HEADER, name="Exness_XAUUSD_2026_10.csv"):
        path = self.root / f"{len(list(self.root.iterdir()))}.zip"
        with ZipFile(path, "w") as target:
            target.writestr(name, header + body)
        return path, sha256(path.read_bytes()).hexdigest()

    def ticks(self, body, **kwargs):
        path, digest = self.archive(body, **kwargs)
        return list(ea.iter_ticks(path, "XAUUSD", 2026, 10, digest))


class ArchiveParsingTests(ArchiveFixture):
    def test_url_and_member(self):
        self.assertEqual(
            ea.archive_url("XAUUSD", 2026, 10),
            "https://ticks.ex2archive.com/ticks/XAUUSD/2026/10/Exness_XAUUSD_2026_10.zip",
        )
        self.assertEqual(ea.member_name("XAUUSDm", 2026, 1), "Exness_XAUUSDm_2026_01.csv")
        for symbol in ("EURUSD", "xauusd", "XAUUSD/../x"):
            with self.subTest(symbol=symbol), self.assertRaises(ea.ArchiveError):
                ea.archive_url(symbol, 2026, 10)
        self.assertEqual(ea.parse_month("2026-10"), (2026, 10))
        for text in ("2026-13", "202610", "", None):
            with self.subTest(text=text), self.assertRaises(ea.ArchiveError):
                ea.parse_month(text)

    def test_ticks_are_utc_milliseconds_and_integer_thousandths(self):
        ticks = self.ticks(row("2026-10-01 00:00:00.048Z", "4156.107", "4156.275")
                           + row("2026-10-01 00:00:01Z", "4156.1", "4156.27"))
        start = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()) * 1000
        self.assertEqual(ticks, [(start + 48, 4156107, 4156275), (start + 1000, 4156100, 4156270)])

    def test_digest_header_symbol_month_and_quote_checks(self):
        path, _ = self.archive(row("2026-10-01 00:00:00.048Z", "1", "2"))
        with self.assertRaisesRegex(ea.ArchiveError, "SHA-256"):
            list(ea.iter_ticks(path, "XAUUSD", 2026, 10, "0" * 64))
        bad = {
            "header": dict(body=row("2026-10-01 00:00:00.048Z", "1", "2"),
                           header='"Symbol","Timestamp","Bid","Ask"\n'),
            "symbol": dict(body=row("2026-10-01 00:00:00.048Z", "1", "2", symbol="XAUUSDm")),
            "month": dict(body=row("2026-11-01 00:00:00.048Z", "1", "2")),
            "crossed": dict(body=row("2026-10-01 00:00:00.048Z", "2", "1")),
            "precision": dict(body=row("2026-10-01 00:00:00.048Z", "1.0001", "2")),
            "stamp": dict(body=row("2026-10-01T00:00:00.048Z", "1", "2")),
            "clock": dict(body=row("2026-10-01 24:00:00.000Z", "1", "2")),
            "zero": dict(body=row("2026-10-01 00:00:00.048Z", "0", "2")),
        }
        for name, kwargs in bad.items():
            with self.subTest(name=name), self.assertRaises(ea.ArchiveError):
                self.ticks(**kwargs)
        with self.assertRaises(ea.ArchiveError):
            self.ticks("", name="other.csv")

    def test_audit_orders_gaps_spreads_and_candles(self):
        body = "".join([
            row("2026-10-02 20:45:00.000Z", "10.000", "10.100"),
            row("2026-10-02 20:49:00.000Z", "10.500", "10.600"),
            row("2026-10-02 20:49:00.000Z", "9.500", "9.700"),
            row("2026-10-02 20:53:00.000Z", "10.100", "10.200"),
            row("2026-10-02 20:57:59.000Z", "10.200", "10.300"),
            row("2026-10-04 22:01:30.000Z", "11.000", "11.100"),
        ])
        path, digest = self.archive(body)
        result = ea.audit(path, "XAUUSD", 2026, 10, digest)
        report = result.report()
        self.assertEqual(report["ticks"], 6)
        self.assertEqual(report["same_millisecond_ticks"], 1)
        self.assertEqual(report["spread"]["p50"], "0.100")
        self.assertEqual(report["spread"]["max"], "0.200")
        self.assertEqual(len(report["weekend_closures"]), 1)
        self.assertEqual(report["intraday_breaks_by_utc_minute"], [])
        self.assertEqual(report["all_gaps"][0]["minutes"], 2943.52)
        weekday = ea.MonthAudit()
        day = int(datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()) * 1000
        for hhmm in ((20, 55), (20, 57), (22, 0), (22, 3)):
            weekday.add(day + (hhmm[0] * 60 + hhmm[1]) * 60_000, 1000, 1100)
        self.assertEqual(weekday.report()["intraday_breaks_by_utc_minute"],
                         [{"last_tick_hhmm": "20:57", "next_tick_hhmm": "22:00", "days": 1}])
        bars = list(result.candle_rows("M15"))
        self.assertEqual(bars[0]["utc_start"], "2026-10-02T20:45:00.000+00:00")
        self.assertEqual((bars[0]["open"], bars[0]["high"], bars[0]["low"], bars[0]["close"]),
                         ("10.000", "10.500", "9.500", "10.200"))
        self.assertEqual((bars[0]["ticks"], bars[0]["ask_close"], bars[0]["spread_max"]),
                         (5, "10.300", "0.200"))
        late = ea.MonthAudit()
        late.add(2_000, 1, 2)
        with self.assertRaisesRegex(ea.ArchiveError, "out of order"):
            late.add(1_000, 1, 2)
        with self.assertRaises(ea.ArchiveError):
            ea.MonthAudit().report()


class Response(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(payload)
        self.status = status
        self.headers = {"Last-Modified": "Sat, 31 Oct 2026 01:41:18 GMT"}


class FetchTests(ArchiveFixture):
    def payload(self):
        path, _ = self.archive(row("2026-10-01 00:00:00.048Z", "1", "2"))
        return path.read_bytes()

    def test_fetch_records_provenance_without_overwriting(self):
        payload = self.payload()
        requests = []

        def opener(request, timeout):
            requests.append(request)
            return Response(payload)

        target = self.root / "out.zip"
        manifest = ea.fetch("XAUUSD", 2026, 10, target, opener=opener)
        self.assertEqual(manifest["sha256"], sha256(payload).hexdigest())
        self.assertEqual(manifest["byte_count"], len(payload))
        self.assertEqual(target.read_bytes(), payload)
        self.assertEqual(requests[0].full_url, ea.archive_url("XAUUSD", 2026, 10))
        self.assertEqual(requests[0].get_header("User-agent"), ea.USER_AGENT)
        with self.assertRaises(FileExistsError):
            ea.fetch("XAUUSD", 2026, 10, target, opener=opener)
        self.assertEqual(target.read_bytes(), payload)

    def test_failed_fetch_leaves_no_partial_file(self):
        payload = self.payload()
        target = self.root / "out.zip"
        with patch.object(ea, "MAX_ZIP_BYTES", 10), self.assertRaises(ea.ArchiveError):
            ea.fetch("XAUUSD", 2026, 10, target, opener=lambda r, timeout: Response(payload))
        self.assertFalse(target.exists())
        with self.assertRaises(ea.ArchiveError):
            ea.fetch("XAUUSD", 2026, 10, target, opener=lambda r, timeout: Response(b"not a zip"))
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(ea.ArchiveError, "HTTP 404"):
            ea.fetch("XAUUSD", 2026, 10, target, opener=lambda r, timeout: Response(b"", 404))
        self.assertFalse(target.exists())


class OffsetTests(unittest.TestCase):
    def test_day_by_day_offset_and_transition(self):
        day1 = int(datetime(2026, 10, 23, 10, tzinfo=timezone.utc).timestamp())
        day2 = int(datetime(2026, 10, 26, 10, tzinfo=timezone.utc).timestamp())
        archive, mt5 = {}, {}
        for base, hours in ((day1, 3), (day2, 2)):
            for i in range(8):
                start = base + i * 900
                price = 4_000_000 + (base // 900 + i) * 7919 % 5_000 * 10
                archive[start] = (price, price + 500, price - 500, price + 120)
                mt5[start + hours * 3600] = (price + 10, price + 510, price - 490, price + 120)
                mt5[start - 3600 * 5] = (1, 1, 1, 1)
        days = infer_offsets(archive, mt5)
        self.assertEqual([d["best_offset_hours"] for d in days], [3, 2])
        self.assertEqual(days[0]["best_median_ohlc_gap"], "0.008")
        summary = summarize(days, archive, mt5)
        self.assertFalse(summary["single_constant_offset"])
        self.assertEqual(summary["transitions"][0]["to_hours"], 2)
        self.assertEqual(summary["price_agreement"]["matched_bars"], 16)
        self.assertEqual(summary["price_agreement"]["close_gap_max"], "0.000")
        self.assertEqual(summary["price_agreement"]["share_close_equal_after_rounding_archive_to_cents"], 1.0)

    def test_no_overlap_is_reported_not_guessed(self):
        start = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
        days = infer_offsets({start: (1, 1, 1, 1)}, {})
        self.assertIsNone(days[0]["best_offset_hours"])

    def test_mt5_export_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m15.csv"
            path.write_text("mt5_time_epoch,open,high,low,close,tick_volume,spread,real_volume\n"
                            "1781128800,4101.57,4102.11,4087.21,4088.93,7279,4,0\n")
            self.assertEqual(load_mt5_candles(path),
                             {1781128800: (4101570, 4102110, 4087210, 4088930)})
            path.write_text("time,close\n1,2\n")
            with self.assertRaises(ValueError):
                load_mt5_candles(path)


def deal(ticket, position, kind, entry, volume, price, profit=0.0, *, time_msc=None,
         commission=0.0, swap=0.0, fee=0.0, symbol="XAUUSD"):
    return dict(ticket=ticket, order=ticket, time=0, time_msc=time_msc or ticket * 1000,
                type=kind, entry=entry, position_id=position, reason=0, volume=volume,
                price=price, commission=commission, swap=swap, profit=profit, fee=fee,
                symbol=symbol)


class BookedPnlTests(unittest.TestCase):
    def reconcile(self, deals, **kwargs):
        return reconcile(deals, contract_size=100.0, tick_size=0.01, **kwargs)

    def test_contract_math_matches_booked_cents(self):
        result = self.reconcile([
            deal(1, 7, 0, 0, 0.01, 3808.93), deal(2, 7, 1, 1, 0.01, 3809.03, 0.1),
            deal(3, 8, 1, 0, 0.10, 3847.64), deal(4, 8, 0, 1, 0.10, 3848.64, -10.0, swap=-0.5),
        ])
        first, second = result["exits"]
        self.assertEqual((first["exact_usd"], first["booked_usd"]), ("0.10000", "0.1"))
        self.assertIn("exact", first["matching_models"])
        self.assertEqual(first["implied_usd_per_tick_per_lot"], "1")
        self.assertEqual(second["side"], "SELL")
        self.assertEqual(second["implied_usd_per_tick_per_lot"], "1")
        summary = result["summary"]
        self.assertIn("exact", summary["models_matching_every_exit"])
        self.assertEqual(summary["implied_usd_per_tick_per_lot"], ["1"])
        self.assertEqual(summary["nonzero_swaps"], [{"position_id": 8, "swap": "-0.5"}])
        self.assertEqual(result["issues"], [])

    def test_metadata_tick_value_would_not_match(self):
        result = self.reconcile([deal(1, 7, 0, 0, 0.01, 3808.93), deal(2, 7, 1, 1, 0.01, 3808.94, 0.001)])
        self.assertEqual(result["exits"][0]["matching_models"], [])
        self.assertEqual(result["summary"]["models_matching_every_exit"], [])

    def test_sub_cent_rounding_models(self):
        result = self.reconcile([deal(1, 7, 0, 0, 0.01, 4156.107), deal(2, 7, 1, 1, 0.01, 4156.113, 0.01)])
        self.assertEqual(result["exits"][0]["matching_models"], ["ceiling", "half_even", "half_up"])
        result = self.reconcile([deal(1, 7, 0, 0, 0.01, 4156.107), deal(2, 7, 1, 1, 0.01, 4156.113, 0.0)])
        self.assertEqual(result["exits"][0]["matching_models"],
                         ["cent_rounded_notionals", "floor", "truncate"])

    def test_partial_close_commission_and_slippage(self):
        deals = [
            deal(1, 9, 0, 0, 0.03, 3800.00, commission=-0.21),
            deal(2, 9, 1, 1, 0.01, 3801.00, 1.0, commission=-0.07),
            deal(3, 9, 1, 1, 0.02, 3799.00, -2.0, commission=-0.14),
        ]
        quotes = {1: (3799.80, 3799.98), 2: (3801.00, 3801.20), 3: (3799.05, 3799.25)}
        result = self.reconcile(deals, quotes=quotes)
        self.assertEqual([e["partial"] for e in result["exits"]], [True, True])
        self.assertEqual(result["exits"][0]["entry_vs_prior_quote"], "0.02")
        self.assertEqual(result["exits"][0]["exit_vs_prior_quote"], "0.0")
        self.assertEqual(result["exits"][1]["exit_vs_prior_quote"], "0.05")
        summary = result["summary"]
        self.assertEqual(summary["partial_exits"], 2)
        self.assertEqual(summary["commission_per_lot_by_deal"], {"-7": 3})
        self.assertEqual(summary["fill_vs_prior_quote"]["adverse_max"], "0.05")
        self.assertIn("same-side quote", summary["fill_vs_prior_quote"]["basis"])

    def test_ledger_issues_and_balance_boundary(self):
        deals = [
            deal(1, 0, 2, 0, 0, 0, 3000.0, time_msc=100),
            deal(2, 5, 0, 0, 0.01, 3800.00, time_msc=200),
            deal(3, 5, 1, 1, 0.01, 3801.00, 1.0, time_msc=300, commission=-0.07),
            deal(4, 6, 0, 0, 0.02, 3800.00, time_msc=400),
            deal(5, 7, 0, 0, 0.01, 1.0, symbol="EURUSD", time_msc=500),
            deal(6, 8, 0, 2, 0.01, 3800.00, time_msc=600),
        ]
        result = self.reconcile(deals)
        self.assertEqual(result["ledger"][0]["amount"], "3000.0")
        issues = {i["issue"] for i in result["issues"]}
        self.assertEqual(issues, {"STILL_OPEN", "OTHER_SYMBOL", "UNSUPPORTED_POSITION_SHAPE"})
        flat = balance_at(deals, 350)
        self.assertEqual(flat["balance"], "3000.93")
        self.assertEqual(flat["method"], "sum_of_supplied_deals_before_boundary")
        self.assertTrue(flat["equity_equals_balance"])
        busy = balance_at(deals, 450)
        self.assertEqual(busy["positions_open_across_boundary"], ["6"])
        self.assertFalse(busy["equity_equals_balance"])

    def test_balance_from_current_balance_needs_no_earlier_history(self):
        later = [deal(3, 5, 1, 1, 0.01, 3801.00, 1.0, time_msc=300, commission=-0.07),
                 deal(9, 0, 2, 0, 0, 0, -100.0, time_msc=900)]
        result = balance_at(later, 250, current_balance=4900.93)
        self.assertEqual(result["method"], "current_balance_minus_later_deals")
        self.assertEqual(result["balance"], "5000.00")
        self.assertEqual(balance_at(later, 250)["balance"], "0")

    def test_exit_without_entry_marks_incomplete_history(self):
        result = self.reconcile([deal(3, 5, 1, 1, 0.01, 3801.00, 1.0)])
        self.assertEqual(result["issues"], [{"position_id": 5, "issue": "MISSING_ENTRY"}])
        self.assertEqual(result["exits"], [])


Deal = namedtuple("Deal", reader.DEAL_FIELDS + ("comment", "external_id", "magic"))


class ReadOnlyReaderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        terminal = Path(directory.name) / "terminal64.exe"
        terminal.touch()
        self.terminal = terminal
        self.profile = DemoProfile.from_environment({
            "GOLDBOT_DEMO_PROFILE": PROFILE, "GOLDBOT_EXNESS_TERMINAL": str(terminal),
            "GOLDBOT_EXNESS_DEMO_SERVER": "ExnessKE-MT5Trial9",
            "GOLDBOT_EXNESS_DEMO_LOGIN": "987654321",
        })
        self.mt5 = Mock(ACCOUNT_TRADE_MODE_DEMO=0, COPY_TICKS_ALL=-1)
        self.mt5.initialize.return_value = True
        self.mt5.terminal_info.return_value = SimpleNamespace(connected=True, path=str(terminal.parent))
        self.mt5.account_info.return_value = SimpleNamespace(
            trade_mode=0, company="Exness (KE) Limited", server=self.profile.server,
            login=self.profile.login, currency="USD", balance=3000.93, credit=0.0,
            equity=3000.93, margin=0.0, margin_free=3000.93, leverage=100)
        self.mt5.symbol_info.return_value = SimpleNamespace(
            name="XAUUSD", custom=False, digits=2, point=0.01, trade_tick_size=0.01,
            trade_tick_value=0.1, trade_contract_size=100.0, volume_min=0.01, volume_step=0.01,
            swap_long=-50.0, swap_short=10.0, spread=25, trade_stops_level=0)
        base = self.base = int(datetime(2026, 11, 23, 10, tzinfo=timezone.utc).timestamp() * 1000)
        self.mt5.history_deals_get.return_value = (
            Deal(*deal(1, 0, 2, 0, 0, 0, 3000.0, time_msc=base).values(), "deposit 987654321", "x", 0),
            Deal(*deal(2, 5, 0, 0, 0.01, 3800.00, time_msc=base + 200_000).values(), "", "", 0),
            Deal(*deal(3, 5, 1, 1, 0.01, 3801.00, 1.0, time_msc=base + 300_000,
                       commission=-0.07).values(), "", "", 0),
        )
        self.mt5.history_orders_get.return_value = (
            {"ticket": 2, "time_setup_msc": base + 199_850, "price_open": 3799.90, "sl": 3797.50},
            {"ticket": 3, "time_setup_msc": base + 299_850, "price_open": 3801.00, "sl": 0.0},
        )
        self.mt5.copy_ticks_range.side_effect = lambda *a: [
            {"time_msc": base + 199_000, "bid": 3799.70, "ask": 3799.90},
            {"time_msc": base + 297_000, "bid": 3801.00, "ask": 3801.20},
            {"time_msc": base + 301_000, "bid": 1.0, "ask": 1.0},
        ]

    def collect(self, **kwargs):
        return reader.collect(
            self.mt5, self.profile, start=datetime(2026, 11, 23, tzinfo=timezone.utc),
            discover=lambda: [str(self.terminal)],
            clock=lambda: datetime(2026, 11, 24, tzinfo=timezone.utc), **kwargs)

    def test_collects_reconciliation_without_trading_calls(self):
        base = self.base
        evidence = self.collect(boundaries=[("open", base + 250_000, {}), ("flat", base + 350_000, {}),
                                            ("early", base + 100_000, {})])
        protocol = evidence["protocol_check"]
        self.assertTrue(protocol["compliant"], protocol["violations"])
        self.assertEqual((protocol["max_concurrent_positions"], protocol["cumulative_net_usd"]),
                         (1, "0.93"))
        self.assertEqual(protocol["positions"][0]["stop_at_entry"], 3797.50)
        self.assertEqual(evidence["reconciliation"]["summary"]["implied_usd_per_tick_per_lot"], ["1"])
        self.assertEqual(evidence["reconciliation"]["exits"][0]["entry_vs_prior_quote"], "0.1")
        self.assertIsNone(evidence["reconciliation"]["exits"][0]["exit_vs_prior_quote"])
        entry, exit_ = evidence["fill_timing"]["2"], evidence["fill_timing"]["3"]
        self.assertEqual(entry["request_to_execution_ms"], 150)
        self.assertEqual((entry["prior_quote"]["age_ms"], entry["prior_quote"]["used"],
                          entry["prior_quote"]["side_compared"]), (1000, True, "ask"))
        self.assertEqual((exit_["prior_quote"]["age_ms"], exit_["prior_quote"]["used"],
                          exit_["prior_quote"]["side_compared"]), (3000, False, "bid"))
        self.assertTrue(evidence["ledger_check"]["sums_to_current_balance"])
        open_, flat, early = evidence["risk_day_boundaries"]
        self.assertEqual(open_["opening_equity"],
                         {"status": "UNRESOLVED", "reasons": ["POSITION_OPEN_ACROSS_BOUNDARY"],
                          "conditions": [], "warnings": []})
        self.assertEqual(evidence["archived_deals_corrections"], [])
        self.assertEqual((flat["balance"], flat["opening_equity"]["status"]), ("3000.93", "SUPPORTED"))
        self.assertEqual(early["balance"], "3000.00")
        text = json.dumps(evidence, default=str)
        self.assertNotIn("987654321", text)
        self.assertNotIn("deposit", text)
        for name in ("order_send", "order_check", "positions_get", "orders_get", "login"):
            getattr(self.mt5, name).assert_not_called()
        self.mt5.shutdown.assert_called_once()

    def test_open_positions_credit_or_missing_history_keep_equity_unresolved(self):
        self.mt5.account_info.return_value.margin = 38.0
        self.mt5.account_info.return_value.credit = None
        bonus = Deal(*deal(9, 0, 6, 0, 0, 0, 50.0, time_msc=self.base + 400_000).values(), "", "", 0)
        self.mt5.history_deals_get.return_value = self.mt5.history_deals_get.return_value[2:] + (bonus,)
        evidence = self.collect(boundaries=[("flat", self.base + 350_000, {})])
        self.assertFalse(evidence["ledger_check"]["sums_to_current_balance"])
        self.assertEqual(evidence["risk_day_boundaries"][0]["opening_equity"]["reasons"],
                         ["INCOMPLETE_POSITION_HISTORY", "UNVERIFIED_LEDGER_ENTRY_TYPE",
                          "LEDGER_DOES_NOT_SUM_TO_BALANCE", "POSITIONS_OPEN_AT_COLLECTION",
                          "NONZERO_OR_UNKNOWN_CREDIT"])

    def test_stable_account_with_no_new_deals(self):
        self.mt5.account_info.return_value.balance = 3000.0
        self.mt5.account_info.return_value.equity = 3000.0
        self.mt5.history_deals_get.return_value = self.mt5.history_deals_get.return_value[:1]
        self.mt5.history_orders_get.return_value = ()
        evidence = self.collect(boundaries=[("after", self.base + 60_000, {})])
        self.assertEqual(evidence["reconciliation"]["exits"], [])
        self.assertEqual(evidence["reconciliation"]["issues"], [])
        self.assertTrue(evidence["ledger_check"]["sums_to_current_balance"])
        self.assertTrue(evidence["protocol_check"]["compliant"])
        self.assertEqual(evidence["protocol_check"]["positions"], [])
        boundary = evidence["risk_day_boundaries"][0]
        self.assertEqual((boundary["balance"], boundary["opening_equity"]["status"]),
                         ("3000.0", "SUPPORTED"))
        self.assertEqual(evidence["planned_stop_check"]["status"], "OK")

    def baseline_with_correction(self, comment, profit=0.0, balance=3000.0):
        """The 22 Nov baseline shape: a deposit, then a type-5 correction, no trades."""
        self.mt5.account_info.return_value.balance = balance
        self.mt5.account_info.return_value.equity = balance
        deposit = self.mt5.history_deals_get.return_value[0]
        correction = Deal(*deal(4, 0, 5, 0, 0, 0, profit, time_msc=self.base + 500_000).values(),
                          comment, "", 0)
        self.mt5.history_deals_get.return_value = (deposit, correction)
        self.mt5.history_orders_get.return_value = ()
        return self.collect(boundaries=[("b", self.base + 60_000, {})])

    def test_archived_deals_correction_is_conditional_not_supported(self):
        evidence = self.baseline_with_correction("Archived deals")
        equity = evidence["risk_day_boundaries"][0]["opening_equity"]
        self.assertEqual((equity["status"], equity["reasons"], equity["conditions"]),
                         ("CONDITIONAL", [], ["ARCHIVED_DEALS_CORRECTION_PRESENT"]))
        self.assertIn("cannot be independently established", equity["warnings"][0])
        self.assertTrue(evidence["ledger_check"]["sums_to_current_balance"])
        (entry,) = evidence["archived_deals_corrections"]
        self.assertEqual((entry["ticket"], entry["comment"], entry["accepted"], entry["amounts"]),
                         (4, "Archived deals", True,
                          {"profit": "0.0", "commission": "0.0", "swap": "0.0", "fee": "0.0"}))

    def test_archived_deals_with_any_amount_stays_unresolved(self):
        evidence = self.baseline_with_correction("Archived deals", profit=0.01, balance=3000.01)
        self.assertTrue(evidence["ledger_check"]["sums_to_current_balance"])
        equity = evidence["risk_day_boundaries"][0]["opening_equity"]
        self.assertEqual((equity["status"], equity["reasons"], equity["conditions"]),
                         ("UNRESOLVED", ["UNVERIFIED_LEDGER_ENTRY_TYPE"], []))
        (entry,) = evidence["archived_deals_corrections"]
        self.assertEqual((entry["accepted"], entry["reason"]), (False, "NONZERO_AMOUNT"))

    def test_other_corrections_are_not_recognized_and_comments_stay_private(self):
        for comment in ("Manual adjustment 987654321", "archived deals", "Archived deals ", None):
            with self.subTest(comment=comment):
                evidence = self.baseline_with_correction(comment)
                equity = evidence["risk_day_boundaries"][0]["opening_equity"]
                self.assertEqual((equity["status"], equity["reasons"]),
                                 ("UNRESOLVED", ["UNVERIFIED_LEDGER_ENTRY_TYPE"]))
                self.assertEqual(evidence["archived_deals_corrections"], [])
                self.assertNotIn("987654321", json.dumps(evidence, default=str))

    def test_archived_deals_never_overrides_a_blocking_reason(self):
        self.mt5.account_info.return_value.credit = 5.0
        evidence = self.baseline_with_correction("Archived deals")
        equity = evidence["risk_day_boundaries"][0]["opening_equity"]
        self.assertEqual((equity["status"], equity["reasons"]),
                         ("UNRESOLVED", ["NONZERO_OR_UNKNOWN_CREDIT"]))
        self.mt5.account_info.return_value.credit = 0.0
        evidence = self.baseline_with_correction("Archived deals", balance=2999.0)
        self.assertEqual(evidence["risk_day_boundaries"][0]["opening_equity"]["reasons"],
                         ["LEDGER_DOES_NOT_SUM_TO_BALANCE"])

    def test_empty_history_reported_as_none(self):
        self.mt5.history_deals_get.return_value = None
        self.mt5.history_orders_get.return_value = None
        self.mt5.last_error.return_value = (1, "Success")
        evidence = self.collect()
        self.assertEqual((evidence["deal_count"], evidence["orders"]), (0, []))
        self.assertFalse(evidence["ledger_check"]["sums_to_current_balance"])
        self.mt5.last_error.return_value = (-2, "Invalid params")
        with self.assertRaisesRegex(VerificationError, "history request failed"):
            self.collect()

    def test_planned_stop_check(self):
        economics = {"point": 0.01, "trade_contract_size": 100.0, "trade_stops_level": 0, "spread": 25}
        result = reader.planned_stop_check(economics)
        self.assertEqual(result["status"], "OK")
        first = result["trades"][0]
        self.assertEqual((first["stop_distance_from_entry"], first["exit_side_trigger_distance"],
                          first["loss_at_exact_stop_fill_usd"], first["slippage_allowance_usd"]),
                         ("2.50", "2.25", "2.50", "0.50"))
        self.assertEqual([r["loss_at_exact_stop_fill_usd"] for r in result["trades"]],
                         ["2.50", "2.40", "2.10", "1.00", "4.50"])
        wide = reader.planned_stop_check(dict(economics, spread=70))
        self.assertTrue(all("SPREAD_ABOVE_ENTRY_LIMIT" in r["reasons"] for r in wide["trades"]))
        self.assertIn("TRIGGER_NOT_BEYOND_SPREAD", wide["trades"][2]["reasons"])
        strict = reader.planned_stop_check(dict(economics, trade_stops_level=300))
        self.assertEqual([r["trades"] for r in strict["trades"] if "BELOW_BROKER_MINIMUM_STOP" in r["reasons"]],
                         ["1-6", "7", "8", "9"])
        self.assertEqual(reader.planned_stop_check(dict(economics, spread=None))["status"],
                         "UNKNOWN_SPECIFICATION")

    def test_balance_change_during_read_is_refused(self):
        first = self.mt5.account_info.return_value
        later = SimpleNamespace(**dict(vars(first), balance=2990.0))
        self.mt5.account_info.side_effect = [first, later]
        with self.assertRaisesRegex(VerificationError, "changed during collection"):
            self.collect()

    def test_boundary_before_window_and_missing_history_fail_closed(self):
        with self.assertRaisesRegex(VerificationError, "precedes the history window"):
            self.collect(boundaries=[("old", self.base - 3 * 86_400_000, {})])
        self.mt5.initialize.assert_not_called()
        self.mt5.history_deals_get.return_value = None
        self.mt5.last_error.return_value = (-1, "Terminal call failed")
        with self.assertRaises(VerificationError):
            self.collect()

    def test_proxy_blocks_trading_functions(self):
        proxy = reader.ReadOnlyMT5(self.mt5)
        for name in ("order_send", "order_check", "Buy", "positions_get", "login"):
            with self.subTest(name=name), self.assertRaises(PermissionError):
                getattr(proxy, name)
        self.assertIs(proxy.history_deals_get, self.mt5.history_deals_get)

    def test_identity_failure_and_errors_are_redacted(self):
        self.mt5.account_info.return_value.trade_mode = 2
        with self.assertRaises(VerificationError):
            self.collect()
        self.mt5.history_deals_get.assert_not_called()
        self.mt5.account_info.return_value.trade_mode = 0
        self.mt5.history_deals_get.side_effect = RuntimeError("987654321 secret")
        with self.assertRaises(VerificationError) as error:
            self.collect()
        self.assertNotIn("987654321", str(error.exception))

    def test_boundaries_use_measured_rule_and_record_overrides(self):
        midnight = int(datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp() * 1000)
        (utc, label, offset), = reader._boundaries(["2026-11-24T00:00:00Z"])
        self.assertEqual((utc, label), ("2026-11-24T00:00:00+00:00", midnight + 7_200_000))
        self.assertEqual((offset["offset_source"], offset["matches_measured_rule"]),
                         ("measured_rule", True))
        (_, label, offset), = reader._boundaries(["2026-11-24T00:00:00Z"], 3)
        self.assertEqual(label, midnight + 10_800_000)
        self.assertEqual((offset["offset_source"], offset["matches_measured_rule"]),
                         ("explicit", False))
        with self.assertRaises(VerificationError):
            reader._boundaries(["2026-11-24T00:00:00"])


class ServerClockTests(unittest.TestCase):
    def test_measured_2026_transitions(self):
        utc = timezone.utc
        cases = {
            datetime(2026, 3, 27, 12, tzinfo=utc): 2, datetime(2026, 3, 29, 0, 59, tzinfo=utc): 2,
            datetime(2026, 3, 29, 1, 0, tzinfo=utc): 3, datetime(2026, 10, 23, 12, tzinfo=utc): 3,
            datetime(2026, 10, 25, 0, 59, tzinfo=utc): 3, datetime(2026, 10, 25, 1, tzinfo=utc): 2,
            datetime(2026, 11, 24, tzinfo=utc): 2, datetime(2027, 1, 1, tzinfo=utc): 2,
        }
        for moment, hours in cases.items():
            with self.subTest(moment=moment):
                self.assertEqual(server_clock.offset_hours(moment), hours)
        with self.assertRaises(ValueError):
            server_clock.offset_hours(datetime(2026, 11, 24))


class ExposureLogTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "log.jsonl"

    def add(self, source="a", **kwargs):
        values = dict(source=source, sha256_digest="ab" * 32, coverage_utc=["2026-10-01", "2026-10-31"],
                      purpose="test", tool="unit", path=self.path,
                      clock=lambda: datetime(2026, 11, 22, tzinfo=timezone.utc))
        values.update(kwargs)
        return exposure_log.append(**values)

    def test_chain_appends_and_verifies(self):
        first = self.add("a")
        second = self.add("b", sha256_digest=None, coverage_utc=None)
        self.assertEqual(first["prev_entry_sha256"], exposure_log.GENESIS)
        self.assertEqual(first["label"], "SELF_TESTED_EXPOSED")
        self.assertEqual(second["prev_entry_sha256"],
                         sha256(self.path.read_bytes().splitlines()[0]).hexdigest())
        self.assertEqual([e["source"] for e in exposure_log.verify(self.path)], ["a", "b"])
        self.assertEqual(exposure_log.verify(self.path.with_name("missing.jsonl")), [])

    def test_edits_deletions_and_truncation_are_detected(self):
        for name in ("a", "b", "c"):
            self.add(name)
        lines = self.path.read_bytes().splitlines(keepends=True)
        for tampered in (lines[1:], [lines[0].replace(b'"a"', b'"z"')] + lines[1:],
                         lines[:1] + lines[2:], b"".join(lines)[:-1]):
            with self.subTest(tampered=str(tampered)[:40]):
                self.path.write_bytes(tampered if isinstance(tampered, bytes) else b"".join(tampered))
                with self.assertRaises(exposure_log.ExposureLogError):
                    exposure_log.verify(self.path)
                with self.assertRaises(exposure_log.ExposureLogError):
                    self.add("d")

    def test_rejects_incomplete_entries(self):
        for kwargs in ({"source": " "}, {"sha256_digest": "XYZ"}, {"coverage_utc": ["b", "a"]},
                       {"purpose": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(exposure_log.ExposureLogError):
                self.add(**kwargs)
        self.assertFalse(self.path.exists())


class ProtocolCheckTests(unittest.TestCase):
    HOUR = 3_600_000
    START = int(datetime(2026, 11, 23, 2, tzinfo=timezone.utc).timestamp() * 1000)

    def position(self, pid, open_h, close_h, volume=0.01, profit=0.0, side=0):
        start = self.START
        rows = [deal(pid * 10, pid, side, 0, volume, 3800.0, time_msc=start + int(open_h * self.HOUR))]
        if close_h is not None:
            rows.append(deal(pid * 10 + 1, pid, 1 - side, 1, volume, 3800.0, profit,
                             time_msc=start + int(close_h * self.HOUR)))
        return rows

    def check(self, deals, orders=None, now_h=200):
        orders = orders if orders is not None else {
            d["order"]: {"sl": 3799.3} for d in deals if d["entry"] == 0}
        return protocol_check(deals, orders, start_msc=self.START,
                              now_msc=self.START + now_h * self.HOUR)

    def codes(self, result):
        return {v["code"] for v in result["violations"]}

    def test_sequential_small_trades_comply(self):
        result = self.check(self.position(1, 1, 1.01, profit=-2.0) + self.position(2, 2, 2.01, 0.03, 1.0)
                            + self.position(3, 3, 15, profit=-4.5))
        self.assertTrue(result["compliant"], result["violations"])
        self.assertEqual(result["cumulative_net_usd"], "-5.5")
        self.assertTrue(result["positions"][2]["overnight"])

    def test_each_limit_is_enforced(self):
        before = deal(1, 9, 0, 0, 0.01, 3800.0, time_msc=self.START - self.HOUR)
        overlapping = self.position(1, 1, 3) + self.position(2, 2, 2.5)
        self.assertEqual(self.codes(self.check([before] + overlapping)), {"CONCURRENT_POSITIONS"})
        self.assertEqual(self.codes(self.check(self.position(1, 1, 1.1, volume=0.10), {10: {"sl": 3799.9}})),
                         {"VOLUME_LIMIT"})
        trades = self.position(1, 1, 1.1)
        self.assertEqual(self.codes(self.check(trades, {10: {"sl": 0.0}})), {"ENTRY_WITHOUT_STOP"})
        self.assertEqual(self.codes(self.check(trades, {})), {"STOP_UNVERIFIED"})
        friday = self.position(1, 4 * 24 + 18, 7 * 24 + 1)
        self.assertEqual(self.codes(self.check(friday, now_h=300)), {"WEEKEND_HOLD"})
        self.assertEqual(self.codes(self.check(self.position(1, 1, 1.1, profit=-3.5))),
                         {"PER_TRADE_CAP_EXCEEDED"})
        losing = sum((self.position(i, i, i + 0.5, profit=-2.9) for i in range(1, 7)), [])
        result = self.check(losing)
        self.assertTrue(result["experiment_cap_reached"])
        self.assertTrue(result["compliant"])
        result = self.check(losing + self.position(7, 7, 7.5, profit=1.0))
        self.assertEqual(self.codes(result), {"TRADED_AFTER_LOSS_CAP"})
        self.assertEqual(result["violations"][0]["positions"], [7])

    def test_stop_geometry_uses_the_actual_fill(self):
        buy = self.position(1, 1, 1.1)
        (row,) = self.check(buy, {10: {"sl": 3797.5}})["positions"]
        self.assertEqual(row["stop_geometry"], {
            "stop_price": "3797.5", "distance_from_fill": "2.5",
            "loss_at_exact_stop_fill_usd": "2.500", "correct_side": True})
        self.assertEqual(self.codes(self.check(buy, {10: {"sl": 3802.5}})), {"WRONG_SIDE_STOP"})
        self.assertEqual(self.codes(self.check(buy, {10: {"sl": 3796.5}})),
                         {"STOP_IMPLIES_LOSS_ABOVE_CAP"})
        sell = self.position(2, 1, 1.1, side=1)
        (row,) = self.check(sell, {20: {"sl": 3802.5}})["positions"]
        self.assertEqual((row["stop_geometry"]["distance_from_fill"], row["stop_geometry"]["correct_side"]),
                         ("2.5", True))
        self.assertEqual(self.codes(self.check(sell, {20: {"sl": 3797.5}})), {"WRONG_SIDE_STOP"})

    def test_open_position_is_reported(self):
        result = self.check(self.position(1, 1, None), now_h=2)
        self.assertEqual(result["still_open"], [1])
        self.assertIsNone(result["positions"][0]["net_usd"])


class ArchiveExposureTests(ArchiveFixture):
    def test_analyze_records_exposure(self):
        path, digest = self.archive(row("2026-10-01 00:00:00.048Z", "1", "2")
                                    + row("2026-10-01 00:01:00.000Z", "1", "2"))
        log = self.root / "exposure.jsonl"
        with patch("sys.stdout", new=io.StringIO()):
            code = archive_tool.main(["analyze", "--file", str(path), "--sha256", digest,
                                      "--month", "2026-10", "--output", str(self.root / "out"),
                                      "--exposure-log", str(log)])
        self.assertEqual(code, 0)
        (entry,) = exposure_log.verify(log)
        self.assertEqual(entry["sha256"], digest)
        self.assertEqual(entry["coverage_utc"], ["2026-10-01T00:00:00.048+00:00",
                                                 "2026-10-01T00:01:00.000+00:00"])
        log.write_bytes(log.read_bytes() + b"tampered\n")
        with patch("sys.stderr", new=io.StringIO()):
            code = archive_tool.main(["analyze", "--file", str(path), "--sha256", digest,
                                      "--month", "2026-10", "--output", str(self.root / "out2"),
                                      "--exposure-log", str(log)])
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "out2").exists())


class PreTradeCheckTests(unittest.TestCase):
    from tools import check_pretrade_611 as checker
    ROOT = Path(__file__).resolve().parents[1]
    BASELINE = ROOT / "reports" / "phase_6_11" / "demo-baseline-2.json"
    NOW = datetime(2026, 11, 23, 9, 10, tzinfo=timezone.utc)

    def baseline(self):
        return {
            "server": "ExnessKE-MT5Trial9", "company": "Exness (KE) Limited", "mode": "demo",
            "symbol": "XAUUSD", "observed_utc": "2026-11-22T06:07:50+00:00",
            "account_snapshot": {"currency": "USD", "balance": 3000.0, "margin": 0.0, "credit": 0.0},
            "ledger_check": {"sums_to_current_balance": True},
            "deals": [{"ticket": 1}, {"ticket": 4}], "orders": [],
            "reconciliation": {"issues": []},
            "archived_deals_corrections": [{"ticket": 4, "accepted": True}],
            "risk_day_boundaries": [{"boundary_utc": "2026-11-22T00:00:00+00:00", "opening_equity": {
                "status": "CONDITIONAL", "reasons": [], "conditions": ["ARCHIVED_DEALS_CORRECTION_PRESENT"]}}],
            "symbol_economics": {"digits": 3, "trade_tick_size": 0.001, "trade_contract_size": 100.0,
                                 "trade_stops_level": 0, "volume_min": 0.01, "volume_step": 0.01},
            "planned_stop_check": {"status": "OK"}, "protocol_check": {"compliant": True},
        }

    def read(self):
        read = copy.deepcopy(self.baseline())
        read["observed_utc"] = "2026-11-23T09:00:00+00:00"
        read["risk_day_boundaries"][0]["boundary_utc"] = "2026-11-23T00:00:00+00:00"
        return read

    def run_check(self, read, baseline=None, *, sha=None, now=None, logged=("r",)):
        return {name: ok for name, ok, _ in self.checker.evaluate(
            baseline or self.baseline(), read,
            baseline_sha256=sha or self.checker.ACCEPTED_BASELINE_SHA256, read_sha256="r",
            logged_digests=set(logged), now=now or self.NOW)}

    def failed(self, read, **kwargs):
        return {name for name, ok in self.run_check(read, **kwargs).items() if not ok}

    def test_unchanged_trade_day_read_passes(self):
        self.assertEqual(self.failed(self.read()), set())

    def test_each_change_fails_its_check(self):
        cases = {
            "baseline_is_the_accepted_one": lambda r: ({}, dict(sha="0" * 64)),
            "same_account_and_symbol": lambda r: (r.update(server="Exness-MT5Real9"), {}),
            "no_exposure": lambda r: (r["account_snapshot"].update(margin=38.0), {}),
            "ledger_unchanged": lambda r: (r["account_snapshot"].update(balance=2990.0), {}),
            "no_new_account_activity": lambda r: (r["deals"].append({"ticket": 9}), {}),
            "no_reconciliation_issues": lambda r: (r["reconciliation"].update(issues=[{"issue": "X"}]), {}),
            "specification_unchanged": lambda r: (r["symbol_economics"].update(trade_stops_level=50), {}),
            "stops_feasible": lambda r: (r["planned_stop_check"].update(status="ATTENTION"), {}),
            "protocol_compliant": lambda r: (r["protocol_check"].update(compliant=False), {}),
            "read_recorded_in_exposure_log": lambda r: ({}, dict(logged=())),
        }
        for check, change in cases.items():
            with self.subTest(check=check):
                read = self.read()
                _, kwargs = change(read)
                self.assertEqual(self.failed(read, **(kwargs or {})), {check})

    def test_opening_equity_must_match_the_accepted_condition_exactly(self):
        for change in (
            lambda r: r["risk_day_boundaries"][0]["opening_equity"].update(status="UNRESOLVED"),
            lambda r: r["risk_day_boundaries"][0]["opening_equity"].update(reasons=["NONZERO_OR_UNKNOWN_CREDIT"]),
            lambda r: r["archived_deals_corrections"].append({"ticket": 5, "accepted": True}),
            lambda r: r["archived_deals_corrections"].clear(),
            lambda r: r["risk_day_boundaries"][0].update(boundary_utc="2026-11-22T00:00:00+00:00"),
            lambda r: r.update(risk_day_boundaries=[]),
        ):
            read = self.read()
            change(read)
            with self.subTest(read=str(read["risk_day_boundaries"])[:60]):
                self.assertIn("opening_equity_matches_accepted_condition", self.failed(read))

    def test_stale_or_old_reads_fail(self):
        self.assertIn("fresh_read", self.failed(self.read(), now=self.NOW + timedelta(minutes=31)))
        self.assertIn("fresh_read", self.failed(self.read(), now=self.NOW - timedelta(hours=1)))
        old = self.read()
        old["observed_utc"] = self.baseline()["observed_utc"]
        self.assertIn("fresh_read", self.failed(old, now=datetime(2026, 11, 22, 6, 10, tzinfo=timezone.utc)))

    @unittest.skipUnless(BASELINE.exists(), "accepted baseline is local evidence")
    def test_real_accepted_baseline_has_the_expected_shape(self):
        raw = self.BASELINE.read_bytes()
        baseline = json.loads(raw)
        self.assertEqual(sha256(raw).hexdigest(), self.checker.ACCEPTED_BASELINE_SHA256)
        read = copy.deepcopy(baseline)
        now = datetime.fromisoformat(baseline["observed_utc"]) + timedelta(minutes=5)
        read["observed_utc"] = (now - timedelta(minutes=1)).isoformat()
        checks = self.checker.evaluate(baseline, read, baseline_sha256=sha256(raw).hexdigest(),
                                       read_sha256="r", logged_digests={"r"}, now=now)
        self.assertEqual([name for name, ok, _ in checks if not ok], [])


if __name__ == "__main__":
    unittest.main()
