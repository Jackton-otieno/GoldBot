import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from goldbot.risk.broker_spec_validator import validate
from goldbot.risk.risk_config import D


class BrokerValidationTests(unittest.TestCase):
    def setUp(self):
        self.account = SimpleNamespace(login=789456123, server="Demo", trade_mode=0,
                                       currency="USD", currency_digits=2, leverage=100)
        self.symbol = SimpleNamespace(
            name="XAUUSD", point=0.01, trade_tick_size=0.02, trade_tick_value_loss=0.50,
            trade_tick_value_profit=0.50, trade_tick_value=0.50, trade_contract_size=25,
            volume_min=0.01, volume_max=100, volume_step=0.01, volume_limit=0,
            trade_freeze_level=10, trade_stops_level=15, trade_calc_mode=4, trade_mode=4,
            digits=2, bid=3800.01, ask=3800.24, time=1700000000,
            currency_profit="USD", currency_margin="USD",
        )
        self.mt5 = Mock()
        self.mt5.__version__ = "test"
        self.mt5.version.return_value = (500, 100, "test")
        self.mt5.ACCOUNT_TRADE_MODE_DEMO = 0
        self.mt5.ORDER_TYPE_BUY = 0
        self.mt5.ORDER_TYPE_SELL = 1
        self.mt5.terminal_info.return_value = SimpleNamespace(connected=True)
        self.mt5.account_info.return_value = self.account
        self.mt5.symbol_info.return_value = self.symbol
        self.mt5.last_error.return_value = (-100, "private error detail")
        self.mt5.order_calc_profit.side_effect = self.profit
        self.mt5.order_calc_margin.side_effect = lambda side, symbol, lots, entry: round(lots * 12.34, 2)

    def profit(self, side, symbol, lots, entry, exit_price):
        return (D(str(exit_price)) - D(str(entry))) * D(str(lots)) * 25 * (1 if side == 0 else -1)

    def run_validation(self, account=None):
        report = validate(self.mt5, account or self.account, expected_server="Demo")
        self.mt5.order_send.assert_not_called()
        self.mt5.order_check.assert_not_called()
        self.mt5.symbol_select.assert_not_called()
        encoded = json.dumps(report, allow_nan=False)
        self.assertNotIn(str(self.account.login), encoded)
        self.assertNotIn("private error detail", encoded)
        return report

    def assert_rejected(self, reason):
        report = self.run_validation()
        self.assertEqual(report["status"], "REJECTED")
        self.assertIn(reason, [item["reason"] for item in report["errors"]])
        return report

    def test_both_sides_outcomes_and_grids(self):
        report = self.run_validation()
        self.assertEqual(report["status"], "CURRENT_DEMO_PROBES_CONSISTENT")
        self.assertEqual(report["historical_applicability"], "UNVERIFIED")
        self.assertEqual({p["side"] for p in report["profit"]}, {"BUY", "SELL"})
        self.assertEqual({p["outcome"] for p in report["profit"]}, {"PROFIT", "LOSS"})
        self.assertEqual({p["ticks"] for p in report["profit"]}, {1, 10, 100})
        self.assertEqual(len({p["lots"] for p in report["profit"]}), 3)
        for p in report["profit"]:
            self.assertEqual(D(p["entry"]) % D("0.02"), 0)
            self.assertEqual(abs(D(p["exit"]) - D(p["entry"])), p["ticks"] * D("0.02"))

    def test_exness_forex_margin_conversion(self):
        self.symbol.__dict__.update(
            point=.001, trade_tick_size=.001, trade_tick_value=.1,
            trade_tick_value_profit=.1, trade_tick_value_loss=.1, trade_contract_size=100,
            digits=3, trade_calc_mode=0, volume_max=200, currency_base="XAU",
            currency_margin="XAU", margin_initial=0, margin_maintenance=0, custom=False,
        )
        self.mt5.order_calc_profit.side_effect = lambda *args: self.profit(*args) * 4
        self.mt5.order_calc_margin.side_effect = lambda side, symbol, lots, entry: round(lots * entry, 2)
        identity = Mock()
        result = validate(self.mt5, self.account, expected_server="Demo", exness_identity=identity)
        self.assertEqual(result["status"], "CURRENT_DEMO_PROBES_CONSISTENT")
        self.assertEqual(result["calc_mode"], "FOREX")
        self.assertEqual((len(result["profit"]), len(result["margin"])), (144, 24))
        self.assertGreaterEqual(identity.call_count, 169)
        self.assert_rejected("UNSUPPORTED_CURRENCY")

        self.mt5.order_calc_margin.side_effect = lambda side, symbol, lots, entry: lots
        result = validate(self.mt5, self.account, expected_server="Demo", exness_identity=identity)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["probe_counts"]["margin_errors"], {"MARGIN_CONVERSION_MISMATCH": 24})

    def test_half_cent_rounding(self):
        self.mt5.order_calc_profit.side_effect = lambda *args: self.profit(*args).quantize(D(".01"))
        self.assertEqual(self.run_validation()["status"], "CURRENT_DEMO_PROBES_CONSISTENT")

    def test_reported_loss_mismatch(self):
        self.symbol.trade_tick_value_loss = .05
        report = self.assert_rejected("INCONSISTENT_TICK_VALUE_METADATA")
        self.assertTrue(any("PROFIT_METADATA_MISMATCH" in p["errors"] for p in report["profit"]))
        self.assertTrue(all("PROFIT_FORMULA_MISMATCH" not in p["errors"] for p in report["profit"]))

    def test_sign_and_formula_mismatch(self):
        self.mt5.order_calc_profit.side_effect = lambda *args: -self.profit(*args)
        report = self.assert_rejected("PROFIT_PROBE_FAILED")
        self.assertTrue(all("WRONG_PROFIT_SIGN" in p["errors"] for p in report["profit"]))

    def test_demo_guard(self):
        self.account.trade_mode = 2
        self.assert_rejected("DEMO_REQUIRED")
        self.mt5.order_calc_profit.assert_not_called()
        self.mt5.symbol_info.assert_not_called()

    def test_connection_changed(self):
        changed = SimpleNamespace(**vars(self.account))
        changed.login += 1
        self.mt5.account_info.side_effect = [self.account, changed]
        self.assert_rejected("CONNECTION_MISMATCH")
        self.mt5.order_calc_margin.assert_not_called()

    def test_metadata_changed(self):
        changed = SimpleNamespace(**vars(self.symbol))
        changed.trade_freeze_level += 1
        self.mt5.symbol_info.side_effect = [self.symbol, changed]
        self.assert_rejected("SYMBOL_METADATA_CHANGED")
        self.mt5.order_calc_margin.assert_not_called()

    def test_missing_metadata(self):
        del self.symbol.trade_tick_size
        self.assert_rejected("INVALID_OR_MISSING_DATA")

    def test_missing_symbol(self):
        self.mt5.symbol_info.return_value = None
        report = self.assert_rejected("SYMBOL_UNAVAILABLE")
        self.assertEqual(report["errors"][0]["api_code"], -100)

    def test_unsupported_precision(self):
        self.account.currency_digits = 3
        self.assert_rejected("UNSUPPORTED_ACCOUNT_PRECISION_OR_LEVERAGE")

    def test_unsupported_currency(self):
        self.symbol.currency_profit = "EUR"
        report = self.assert_rejected("UNSUPPORTED_CURRENCY")
        self.assertNotIn("formula_usd_per_tick_per_lot", report)

    def test_unsupported_calc_mode(self):
        self.symbol.trade_calc_mode = 2
        self.assert_rejected("UNSUPPORTED_CALC_MODE")
        self.mt5.order_calc_profit.assert_not_called()

    def test_volume_limit(self):
        self.symbol.volume_limit = .01
        self.assert_rejected("INSUFFICIENT_VOLUME_COVERAGE")

    def test_margin_error_keeps_profit_observations(self):
        self.mt5.order_calc_margin.side_effect = None
        self.mt5.order_calc_margin.return_value = None
        report = self.assert_rejected("MARGIN_UNAVAILABLE")
        self.assertTrue(report["profit"])
        self.assertEqual(report["margin"][0]["api_code"], -100)

    def test_nonlinear_margin(self):
        self.mt5.order_calc_margin.side_effect = lambda side, symbol, lots, entry: 1 + lots * 10
        self.assert_rejected("NONLINEAR_MARGIN")
