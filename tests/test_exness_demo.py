import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from goldbot.core.exness_demo import DemoProfile, PROFILE, VerificationError, verify


class ExnessDemoTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "terminal64.exe"
        self.path.touch()
        self.env = {
            "GOLDBOT_DEMO_PROFILE": PROFILE,
            "GOLDBOT_EXNESS_TERMINAL": str(self.path),
            "GOLDBOT_EXNESS_DEMO_SERVER": "Exness-MT5Trial99",
            "GOLDBOT_EXNESS_DEMO_LOGIN": "987654321",
        }
        self.profile = DemoProfile.from_environment(self.env)
        self.mt5 = Mock(ACCOUNT_TRADE_MODE_DEMO=0)
        self.mt5.initialize.return_value = True
        self.mt5.terminal_info.return_value = SimpleNamespace(
            connected=True, path=str(self.path.parent), build=5000
        )
        self.mt5.account_info.return_value = SimpleNamespace(
            trade_mode=0, company="Exness (KE) Limited", server=self.profile.server,
            login=self.profile.login, currency="USD", balance=3000, leverage=100,
        )
        self.mt5.symbol_info.return_value = SimpleNamespace(name="XAUUSD", custom=False)

    def verify(self):
        return verify(self.mt5, self.profile, lambda: [str(self.path)])

    def test_profile_and_allowlisted_evidence(self):
        evidence = self.verify()
        self.assertEqual(evidence["profile"], PROFILE)
        self.assertEqual(evidence["server"], self.profile.server)
        self.assertTrue(evidence["ke_entity_reported_by_terminal"])
        self.assertNotIn(str(self.profile.login), repr(evidence))
        self.assertNotIn(str(self.profile.login), repr(self.profile))
        self.mt5.initialize.assert_called_once_with(str(self.path), timeout=5000)
        self.mt5.symbol_info.assert_called_once_with("XAUUSD")
        self.mt5.shutdown.assert_called_once()

    def test_kenyan_server_prefix(self):
        profile = DemoProfile.from_environment(dict(
            self.env, GOLDBOT_EXNESS_DEMO_SERVER="ExnessKE-MT5Trial9",
        ))
        self.assertEqual(profile.server, "ExnessKE-MT5Trial9")

    def test_opt_in_and_configuration_required(self):
        for key in self.env:
            with self.subTest(key=key), self.assertRaises(VerificationError):
                DemoProfile.from_environment({k: v for k, v in self.env.items() if k != key})
        for server in ("MetaQuotes-Demo", "Exness-MT5Real1", "Exness-MT5Trial99\n"):
            with self.subTest(server=server), self.assertRaises(VerificationError):
                DemoProfile.from_environment(dict(self.env, GOLDBOT_EXNESS_DEMO_SERVER=server))

    def test_missing_and_ambiguous_terminal_fail_before_attachment(self):
        for paths in ([], [" "], [str(self.path), str(self.path)], [str(self.path), ""]):
            with self.subTest(paths=paths), self.assertRaises(VerificationError):
                verify(self.mt5, self.profile, lambda: paths)
        self.mt5.initialize.assert_not_called()

    def test_exact_selection_with_multiple_terminal_paths(self):
        result = verify(self.mt5, self.profile, lambda: [
            str(self.path.parent / "other" / self.path.name), str(self.path)
        ])
        self.assertEqual(result["mode"], "demo")

    def test_identity_and_mode_mismatches_block_symbol_reads(self):
        account = self.mt5.account_info.return_value
        for field, value in (
            ("trade_mode", 1), ("trade_mode", 2), ("trade_mode", None),
            ("company", "Other Exness"), ("server", "Exness-MT5Trial1"),
            ("login", 12), ("currency", "KES"),
        ):
            with self.subTest(field=field, value=value):
                self.mt5.account_info.return_value = SimpleNamespace(
                    **dict(vars(account), **{field: value})
                )
                with self.assertRaises(VerificationError):
                    self.verify()
        self.mt5.symbol_info.assert_not_called()

    def test_group_company_does_not_confirm_ke_routing(self):
        self.mt5.account_info.return_value.company = "Exness Technologies Ltd"
        self.assertFalse(self.verify()["ke_entity_reported_by_terminal"])

    def test_wrong_terminal_and_account_switch_are_rejected(self):
        terminal = self.mt5.terminal_info.return_value
        terminal.path = str(self.path.parent / "other")
        with self.assertRaisesRegex(VerificationError, "different terminal path"):
            self.verify()
        terminal.path = str(self.path.parent)
        account = self.mt5.account_info.return_value
        self.mt5.account_info.side_effect = [
            account, SimpleNamespace(**dict(vars(account), login=12))
        ]
        with self.assertRaisesRegex(VerificationError, "differs from the verified demo account"):
            self.verify()

    def test_api_error_is_redacted(self):
        self.mt5.account_info.side_effect = RuntimeError("987654321 test-secret")
        with self.assertRaises(VerificationError) as error:
            self.verify()
        self.assertNotIn("987654321", str(error.exception))
        self.assertNotIn("test-secret", str(error.exception))
        self.mt5.shutdown.assert_called_once()
