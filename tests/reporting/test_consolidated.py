import hashlib
import json
import re
import shutil
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
from xml.etree import ElementTree

from goldbot.reporting.generate import generate, table

ROOT = Path(__file__).resolve().parents[2]
INPUT = "reports/sensitivity_phase_6_5/sensitivity.json"


def snapshot(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = set()
        self.urls = []
        self.tags = set()
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.urls.append(attrs[key])


class ConsolidatedReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        shutil.copytree(ROOT / "data", cls.root / "data")
        shutil.copytree(ROOT / "reports", cls.root / "reports",
                        ignore=shutil.ignore_patterns("consolidated_phase_6_7"))
        shutil.copytree(ROOT / "docs", cls.root / "docs")
        cls.output = generate(cls.root)
        cls.files = snapshot(cls.output)
        cls.summary = json.loads(cls.files["summary.json"])

    def test_exact_regeneration_including_all_charts(self):
        with patch("socket.socket", side_effect=AssertionError("Network access")):
            self.assertEqual(snapshot(generate(self.root)), self.files)
        deployed = snapshot(ROOT / "reports/consolidated_phase_6_7")
        if deployed:
            self.assertEqual(self.files, deployed)

    def test_provenance_and_cross_report_reconciliation(self):
        source_files = {f"data/{key}" for key in snapshot(self.root / "data")}
        report_root = self.root / "reports"
        later_phases = {"phase_6_8_1", "phase_6_8_2", "phase_6_8_3", "phase_6_8_4",
                        "research_phase_6_8_5", "validation_phase_6_8_6", "phase_6_9_1", "phase_6_9_2",
                        "phase_6_9_3", "phase_6_9_3_1", "phase_6_9_4", "phase_6_9_4_1",
                        "phase_6_9_5", "phase_6_9_6", "phase_6_10_1", "phase_6_10_2", "phase_6_10_3",
                        "phase_6_10_4", "phase_6_10_5_1", "phase_6_10_5_2",
                        "phase_6_10_5_3", "phase_6_10_5_4", "phase_6_10_5_5", "phase_6_10_6",
                        "phase_6_10_7", "phase_6_11"}
        source_files.update(
            path.relative_to(self.root).as_posix()
            for path in report_root.rglob("*")
            if path.is_file()
            and path.relative_to(report_root).parts[0] not in later_phases | {"consolidated_phase_6_7"}
        )
        self.assertEqual(set(self.summary["input_sha256"]), source_files)
        for path, digest in self.summary["input_sha256"].items():
            self.assertEqual(hashlib.sha256((self.root / path).read_bytes()).hexdigest(), digest)
        historical = self.summary["historical_observations"]
        original_validation = json.loads(
            (self.root / "reports/validation_phase_6_6/validation.json").read_bytes())
        self.assertEqual(historical["retrospective_partitions"], original_validation)
        for frame, record in historical["timeframes"].items():
            stem = f"reports/signals_phase_4_1/XAUUSD_{frame}_signals_phase_4_1"
            signals = json.loads((self.root / f"{stem}_counts.json").read_bytes())
            self.assertEqual(record["signal_counts"], signals)
            counts = record["replay_audit"]["counts"]
            self.assertEqual(counts["decisions"], signals["decisions"])
            self.assertEqual(counts["raw_label_gaps"], record["market_quality"]["longer_pairs"])
            self.assertEqual(counts["source_rows"], sum(signals["decisions"].values()))
        self.assertEqual(self.summary["hypothetical_synthetic_results"],
                         json.loads((self.root / INPUT).read_bytes()))

    def test_scopes_and_null_reasons_are_explicit(self):
        html = self.files["index.html"].decode()
        for label in ("Historical observations", "Hypothetical synthetic results",
                      "Historical execution and profitability are unavailable",
                      "Dynamic realized net P/L", "Dynamic marked equity", "Unresolved position",
                      "Retrospective partition validation", "including each partition named test"):
            self.assertIn(label, html)
        unavailable = self.summary["historical_performance"]
        self.assertIsNone(unavailable["value"])
        self.assertTrue(unavailable["reason"])
        self.assertFalse(self.summary["historical_observations"]["retrospective_partitions"]
                         ["prospective_holdout_collected"])
        perf = self.summary["hypothetical_synthetic_results"]["scenarios"]["ideal"][
            "dynamic_portfolio"]["performance"]
        self.assertEqual(perf["trades"]["profit_factor"],
                         {"status": "infinite", "value": None, "reason": "no_net_losses"})
        self.assertIsNone(perf["costs"]["spread_cost"]["value"])
        self.assertTrue(perf["costs"]["spread_cost"]["reason"])
        self.assertIsNotNone(perf["unresolved_position"])

    def test_local_links_and_source_series(self):
        html = self.files["index.html"].decode()
        page = Page(html)
        self.assertTrue({"script", "iframe", "link"}.isdisjoint(page.tags))
        self.assertNotRegex(html, r"(?i)(https?:|@import|url\()")
        for url in page.urls:
            parts = urlsplit(url)
            self.assertFalse(parts.scheme or parts.netloc)
            if parts.path:
                target = (self.output / parts.path).resolve()
                self.assertTrue(target.is_relative_to(self.root))
                self.assertTrue(target.is_file(), url)
            else:
                self.assertIn(parts.fragment, page.ids)
        ns = "{http://www.w3.org/2000/svg}"
        cases = self.summary["hypothetical_synthetic_results"]["scenarios"]
        for path, data in self.files.items():
            if path.endswith(".svg"):
                tree = ElementTree.fromstring(data)
                title = tree.findtext(ns + "title")
                scope = "Historical" if "historical" in path else "Hypothetical synthetic"
                self.assertTrue(title.startswith(scope))
                self.assertTrue(tree.findtext(ns + "desc"))
                if match := re.fullmatch(r"charts/synthetic-(\w+)-(equity|drawdown)\.svg", path):
                    case, _ = match.groups()
                    series = cases[case]["dynamic_portfolio"]["performance"]["event_series"]
                    self.assertEqual(len(tree.findall(ns + "circle")), len(series))
                    self.assertEqual(len(tree.find(ns + "polyline").get("points").split()), len(series))

    def test_missing_and_malformed_inputs_fail_without_overwriting_report(self):
        path = self.root / INPUT
        original = path.read_bytes()
        try:
            path.unlink()
            with self.assertRaisesRegex(ValueError, INPUT):
                generate(self.root)
            path.write_bytes(b'{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                generate(self.root)
            data = json.loads(original)
            data["scenarios"]["ideal"]["dynamic_portfolio"]["performance"]["event_series"] = []
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing event series"):
                generate(self.root)
        finally:
            path.write_bytes(original)
        self.assertEqual(snapshot(self.output), self.files)

    def test_inconsistent_counts_and_escaped_cells(self):
        path = self.root / "reports/signals_phase_4_1/XAUUSD_M15_signals_phase_4_1_counts.json"
        original = path.read_bytes()
        try:
            data = json.loads(original)
            data["decisions"]["BUY"] += 1
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "counts disagree with the signal CSV"):
                generate(self.root)
        finally:
            path.write_bytes(original)
        rendered = table('<caption>"', ("<script>", "Value"), [("a & b", "</td>")])
        self.assertNotIn("<script>", rendered)
        self.assertIn("&quot;", rendered)
        self.assertIn("&amp;", rendered)
        self.assertIn("&lt;/td&gt;", rendered)

