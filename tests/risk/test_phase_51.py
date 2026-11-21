"""Phase 5.1 tests with explicit hypothetical USD inputs."""
import csv
from dataclasses import replace
from pathlib import Path
import unittest

from goldbot.risk.exness_risk import evaluate_xau_margin_risk
from goldbot.risk.position_sizing import size_position
from goldbot.risk.risk_config import AccountState, BrokerSpecs, D, Evidence, ExecutionAssumptions, RiskDayState
from goldbot.risk.risk_manager import evaluate_risk


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.evidence = Evidence("scenario", "hypothetical test fixture", True)
        self.row = {"decision": "BUY", "reasons": "BUY_SETUP", "gap_before": "False",
                    "atr_14": "0.83", "close": "123", "raw_server_clock_label": "1"}
        self.account = AccountState(self.evidence, "demo-fixture", "USD",
                                    D("3000"), D("3000"), D("3000"), 0)
        self.day = RiskDayState(self.evidence, "demo-fixture", "external-day", D("3000"), D(0))
        self.specs = BrokerSpecs(self.evidence, "XAUUSD", "USD", "USD",
                                 D(".01"), D(".05"), D(5), D(100),
                                 D(".01"), D(100), D(".01"), 0, "USD_LINEAR")
        self.execution = ExecutionAssumptions(self.evidence, "XAUUSD", "BUY",
                                              D("1999.80"), D("2000"), D(".03"),
                                              D(".10"), D(5), D(1500))

    def evaluate(self, evaluator=evaluate_risk, **changes):
        values = dict(row=self.row, scenario_id="scenario", risk_day_id="external-day",
                      signal_evidence=self.evidence, account=self.account, risk_day=self.day,
                      specs=self.specs, execution=self.execution)
        return evaluator(**(values | changes))

    def test_buy_rounds_stop_outward_and_counts_costs_once(self):
        plan = self.evaluate().plan
        self.assertEqual((plan.entry, plan.stop, plan.target, plan.stop_distance),
                         (D("2000.05"), D("1998.75"), D("2002.65"), D("1.30")))
        self.assertEqual(plan.spread, D(".20"))
        self.assertEqual(plan.loss_budget, D(15))
        self.assertEqual(plan.volume, D(".10"))
        self.assertEqual(plan.modeled_stop_loss, D("14.50"))
        self.assertEqual(plan.modeled_margin, D(150))
        self.assertEqual(plan.status, "INDICATIVE")
        self.assertIn("Gaps", plan.caveat)
        self.assertIn("above", plan.caveat)

    def test_xau_margin_requires_explicit_usd_conversion_and_costs(self):
        specs = replace(
            self.specs, margin_currency="XAU",
            point=D(".001"), tick_size=D(".001"), tick_value_loss=D(".10"), volume_max=D(200),
        )
        execution = replace(self.execution, margin_per_lot=D("3782.49"))
        result = self.evaluate(evaluate_xau_margin_risk, specs=specs, execution=execution)
        self.assertEqual(result.reason, "INDICATIVE")
        self.assertEqual(result.plan.volume, D(".10"))
        self.assertEqual(result.plan.modeled_stop_loss, D("14.25"))
        self.assertEqual(result.plan.modeled_margin, D("378.249"))
        self.assertEqual(self.evaluate(
            specs=specs, execution=execution,
        ).reason, "UNSUPPORTED_CURRENCY")
        self.assertEqual(self.evaluate(
            evaluate_xau_margin_risk, specs=specs, execution=replace(execution, margin_per_lot=D(0)),
        ).reason, "INVALID_SIZING_INPUT")
        self.assertEqual(self.evaluate(
            evaluate_xau_margin_risk, specs=specs, execution=execution,
            account=replace(self.account, free_margin=D(378)),
        ).reason, "INSUFFICIENT_MARGIN")
        self.assertEqual(self.evaluate(
            evaluate_xau_margin_risk, specs=specs, execution=execution, risk_day=None,
        ).reason, "UNVERIFIED_RISK_DAY")
        self.assertEqual(self.evaluate(
            evaluate_xau_margin_risk, specs=replace(specs, evidence=replace(self.evidence, verified=False)),
            execution=execution,
        ).reason, "UNVERIFIED_BROKER_SPECS")

    def test_sell_rounds_stop_outward(self):
        row = self.row | dict(decision="SELL", reasons="SELL_SETUP")
        plan = self.evaluate(row=row, execution=replace(self.execution, side="SELL")).plan
        self.assertEqual((plan.entry, plan.stop, plan.target, plan.stop_distance),
                         (D("1999.75"), D("2001.05"), D("1997.15"), D("1.30")))
        self.assertEqual(plan.modeled_stop_loss, D("14.50"))

    def test_reads_real_phase_41_report_schema_for_both_directions(self):
        report_dir = Path(__file__).resolve().parents[2] / "reports" / "signals_phase_4_1"
        for timeframe in ("M15", "H1"):
            report = report_dir / f"XAUUSD_{timeframe}_signals_phase_4_1.csv"
            with report.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            for side in ("BUY", "SELL", "HOLD"):
                with self.subTest(timeframe=timeframe, side=side):
                    row = next(row for row in rows if row["decision"] == side)
                    result = self.evaluate(row=row, execution=replace(self.execution, side=side))
                    if side == "HOLD":
                        self.assertEqual(result.reason, "HOLD_SIGNAL")
                    else:
                        self.assertIn(result.reason, ("INDICATIVE", "BELOW_MINIMUM_VOLUME"))

    def test_missing_unverified_or_mismatched_inputs(self):
        for argument, reason in (
            ("account", "UNVERIFIED_ACCOUNT"), ("risk_day", "UNVERIFIED_RISK_DAY"),
            ("specs", "UNVERIFIED_BROKER_SPECS"), ("execution", "UNVERIFIED_EXECUTION"),
            ("signal_evidence", "UNVERIFIED_SIGNAL"),
        ):
            with self.subTest(argument=argument):
                self.assertEqual(self.evaluate(**{argument: None}).reason, reason)
        self.assertEqual(self.evaluate(risk_day_id="other").reason, "UNVERIFIED_RISK_DAY")
        self.assertEqual(self.evaluate(risk_day=replace(self.day, account_ref="other")).reason,
                         "UNVERIFIED_RISK_DAY")
        bad = replace(self.evidence, verified=False)
        self.assertEqual(self.evaluate(account=replace(self.account, evidence=bad)).reason,
                         "UNVERIFIED_ACCOUNT")
        other = replace(self.evidence, scenario_id="old")
        self.assertEqual(self.evaluate(specs=replace(self.specs, evidence=other)).reason,
                         "UNVERIFIED_BROKER_SPECS")

    def test_position_and_daily_limit_at_equality(self):
        self.assertEqual(self.evaluate(account=replace(self.account, open_positions=1)).reason,
                         "POSITION_LIMIT")
        self.assertEqual(self.evaluate(risk_day=replace(self.day, loss_to_date=D(60))).reason,
                         "DAILY_LOSS_LIMIT")
        self.assertEqual(self.evaluate(account=replace(self.account, equity=D(2940))).reason,
                         "DAILY_LOSS_LIMIT")

    def test_drawdown_limit_and_remaining_budget(self):
        account = replace(self.account, equity=D("2700"))
        day = replace(self.day, opening_equity=D("2700"))
        self.assertEqual(self.evaluate(account=account, risk_day=day).reason, "DRAWDOWN_LIMIT")
        decision = self.evaluate(account=replace(account, equity=D("2702")), risk_day=day)
        self.assertEqual(decision.plan.loss_budget, D(2))
        self.assertEqual(decision.plan.volume, D(".01"))

    def test_daily_headroom_constrains_projected_loss(self):
        day = replace(self.day, loss_to_date=D("58.55"))
        plan = self.evaluate(risk_day=day).plan
        self.assertEqual(plan.loss_budget, D("1.45"))
        self.assertEqual(plan.modeled_stop_loss, D("1.45"))
        day = replace(day, loss_to_date=D("58.56"))
        self.assertEqual(self.evaluate(risk_day=day).reason, "BELOW_MINIMUM_VOLUME")

    def test_margin_rejection_and_exact_margin(self):
        self.assertEqual(self.evaluate(account=replace(self.account, free_margin=D("149.99"))).reason,
                         "INSUFFICIENT_MARGIN")
        self.assertEqual(self.evaluate(account=replace(self.account, free_margin=D("150"))).reason,
                         "INDICATIVE")

    def test_commission_and_stop_slippage_can_preclude_minimum(self):
        for changes in (dict(commission_round_trip_per_lot=D(2000)), dict(stop_slippage=D(20))):
            with self.subTest(changes=changes):
                self.assertEqual(self.evaluate(execution=replace(self.execution, **changes)).reason,
                                 "BELOW_MINIMUM_VOLUME")

    def test_stop_inside_spread_or_broker_minimum_is_rejected(self):
        self.assertEqual(self.evaluate(row=self.row | {"atr_14": ".01"}).reason,
                         "INVALID_STOP_OR_TARGET")
        self.assertEqual(self.evaluate(specs=replace(self.specs, stops_level_points=110)).reason,
                         "INVALID_STOP_OR_TARGET")
        self.assertEqual(self.evaluate(specs=replace(self.specs, stops_level_points=105)).reason,
                         "INDICATIVE")

    def test_sizer_rejects_absent_stop_and_caps_oversize_on_grid(self):
        arguments = dict(budget=D(1000), free_margin=D(1000),
                         specs=replace(self.specs, volume_max=D(".025")), execution=self.execution)
        for distance in (None, D(0), D("-1")):
            self.assertEqual(size_position(stop_distance=distance, **arguments),
                             (None, "INVALID_STOP"))
        size, reason = size_position(stop_distance=D(1), **arguments)
        self.assertEqual(reason, "INDICATIVE")
        self.assertEqual(size.volume, D(".02"))

    def test_inconsistent_tick_value_and_conversion(self):
        self.assertEqual(self.evaluate(specs=replace(self.specs, loss_model="unknown")).reason,
                         "UNSUPPORTED_LOSS_MODEL")
        self.assertEqual(self.evaluate(specs=replace(self.specs, tick_value_loss=D(".50"))).reason,
                         "INCONSISTENT_TICK_VALUE")
        for key, value in (("specs", replace(self.specs, profit_currency="EUR")),
                           ("specs", replace(self.specs, margin_currency="EUR")),
                           ("account", replace(self.account, currency="EUR"))):
            with self.subTest(key=key, value=value):
                self.assertEqual(self.evaluate(**{key: value}).reason, "UNSUPPORTED_CURRENCY")

    def test_rejects_bad_signal_and_nonfinite_values(self):
        self.assertEqual(self.evaluate(row=self.row | {"gap_before": "True"}).reason,
                         "UNVERIFIED_SIGNAL_INTERVAL")
        self.assertEqual(self.evaluate(row=self.row | {"reasons": "WARMUP"}).reason,
                         "INVALID_SIGNAL")
        for atr in ("0", "NaN", "Infinity", "-1"):
            self.assertEqual(self.evaluate(row=self.row | {"atr_14": atr}).reason, "INVALID_ATR")
        self.assertEqual(self.evaluate(account=replace(self.account, equity=D("NaN"))).reason,
                         "INVALID_STATE")
        self.assertEqual(self.evaluate(execution=replace(self.execution, ask=D("NaN"))).reason,
                         "INVALID_MARKET_INPUT")


if __name__ == "__main__":
    unittest.main()
