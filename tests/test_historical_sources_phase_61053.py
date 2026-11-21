from hashlib import sha256
from io import BytesIO
import lzma
from pathlib import Path
import tempfile
from time import monotonic
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from zipfile import ZipFile

from goldbot.core.exness_demo import VerificationError
from tools import dukascopy_sample as duka, histdata_sample as hist
from tools import sample_exness_history_phase_61053 as exness


class HistoricalSourceTests(TestCase):
    start = duka.hour("2026-10-15T12:00:00+00:00")

    def test_utc_bin_edges_preserve_duplicates_and_causal_prefix(self):
        rows = [(1, 101, 100, 1, 1), (1, 101, 100, 1, 1),
                (1, 103, 102, 1, 1), (120_000, 105, 104, 1, 1)]
        before = duka.audit(rows[:-1], self.start)
        after = duka.audit(rows, self.start)
        self.assertEqual(before["bars"]["M1"][0], after["bars"]["M1"][0])
        self.assertEqual(after["bars"]["M1"][0]["bid_ohlc"], [100, 102, 100, 102])
        self.assertEqual(after["tick_counts"]["repeated_payload_rows"], 1)
        self.assertEqual(after["tick_counts"]["shared_timestamp_rows"], 2)
        self.assertEqual(after["empty_intervals"], {"M1": 58, "M15": 3, "H1": 0})
        future = duka.audit(rows + [(900_000, 110, 108, 1, 1)], self.start)
        self.assertEqual(after["bars"]["M15"][0], future["bars"]["M15"][0])
        first = after["bars"]["M1"][0]
        self.assertEqual(first["available_at_utc_ms"] - first["open_utc_ms"], 60_000)

    def test_bi5_decode_and_rejection(self):
        raw = lzma.compress(duka.RECORD.pack(100, 105, 103, 1, 1))
        self.assertEqual(list(duka.decode(raw)), [(100, 105, 103, 1, 1)])
        with self.assertRaises(ValueError):
            list(duka.decode(raw + raw))
        for rows in ([(1, 1, 2, 0, 0)], [(3_600_000, 2, 1, 0, 0)],
                     [(1, 2, 1, 0, 0), (0, 2, 1, 0, 0)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                duka.audit(rows, self.start)
        response = SimpleNamespace(headers={}, read1=lambda size: b"abc"[:size])
        with self.assertRaisesRegex(ValueError, "byte cap"):
            duka.bounded_response(response, 2, monotonic() + 10)
        with self.assertRaises(TimeoutError):
            duka.bounded_response(response, 2, monotonic() - 1)

    def test_fixed_est_utc_conversion_and_exclusive_end(self):
        raw = BytesIO(b"20261015 065959999,2,3,0\n20261015 070000123,2,3,0\n"
                      b"20261015 080000000,2,3,0\n")
        self.assertEqual(list(hist.rows_for_hour(raw, self.start, "202610")),
                         [(123, 3_000_000, 2_000_000, 0, 0)])

    def test_histdata_checks_original_hash_and_symbol_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("DAT_ASCII_XAUUSD_T_202610.csv", "20261015 070000000,2,3,0\n")
            digest = sha256(path.read_bytes()).hexdigest()
            self.assertEqual(hist.validate(self.start, path, digest)["tick_counts"]["ticks"], 1)
            with self.assertRaises(ValueError):
                hist.validate(self.start, path, "0" * 64)
            with ZipFile(path) as archive, self.assertRaises(ValueError):
                hist.expected_member(archive, "202611")

    def test_exness_installation_guard_precedes_attachment(self):
        reader = Mock()
        profile = SimpleNamespace(server=exness.SERVER, login=19498,
                                  terminal=Path("other/terminal64.exe"))
        with self.assertRaises(VerificationError):
            exness.sample(reader, profile, [1790000000])
        self.assertEqual(reader.mock_calls, [])
        failed = exness.audit_capture(dict(status="UNAVAILABLE", error_code=-1,
                                           request_start_raw_s=1790000000))
        self.assertEqual(failed["error_code"], -1)
        self.assertIsNone(failed["first_raw_ms"])
        self.assertEqual(failed["coverage"], "UNVERIFIED")
