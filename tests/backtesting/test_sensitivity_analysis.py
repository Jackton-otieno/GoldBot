import json
import unittest
from dataclasses import replace
from decimal import localcontext
from pathlib import Path
from unittest.mock import patch

from goldbot.backtesting import sensitivity_analysis as sensitivity
from goldbot.backtesting.sensitivity_analysis import SCENARIOS, execution_spec
from goldbot.risk.risk_config import D


class SensitivityTests(unittest.TestCase):
    def test_exact_config_units(self):
        for (name, costs), (spread, slippage, commission) in zip(
            SCENARIOS, (("0", "0", "0"), (".15", ".05", "3"),
                        (".30", ".10", "7"), ("1", ".50", "15"))
        ):
            with self.subTest(name=name):
                with localcontext() as context:
                    context.prec = 1
                    spec = execution_spec(name, costs)
                self.assertEqual(
                    (spec.spread, spec.entry_slippage, spec.stop_slippage,
                     spec.round_trip_commission_per_lot),
                    tuple(map(D, (spread, slippage, slippage, commission))),
                )
                self.assertEqual(spec.broker.tick_size * spec.broker.contract_size,
                                 spec.broker.tick_value_loss)
        costs = replace(SCENARIOS[1][1], round_trip_commission_usd_per_lot=D("3.005"))
        self.assertEqual(execution_spec("fractional", costs).round_trip_commission_per_lot,
                         D("3.005"))

    def test_invalid_costs_rejected(self):
        costs = SCENARIOS[1][1]
        for changes in (
            {"spread_usd_per_oz": D(".155")},
            {"spread_usd_per_oz": D("-0.15")},
            {"slippage_usd_per_oz": D(".053")},
            {"slippage_usd_per_oz": .05},
            {"slippage_usd_per_oz": D("sNaN")},
            {"round_trip_commission_usd_per_lot": D("Infinity")},
            {"round_trip_commission_usd_per_lot": D("-1")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                execution_spec("invalid", replace(costs, **changes))

    def test_fixed_trade_accounting_both_sides(self):
        scenarios = sensitivity.analyze_sensitivity()["scenarios"]
        for (name, costs), expected in zip(SCENARIOS, ("60", "54.4", "48.6", "17")):
            with self.subTest(name=name):
                fixed = scenarios[name]["fixed_trade_comparison"]
                self.assertEqual(fixed["total_net_pnl_usd"], D(expected))
                self.assertEqual([trade["side"] for trade in fixed["trades"]], ["BUY", "SELL"])
                for trade, direction in zip(fixed["trades"], (1, -1)):
                    self.assertEqual(trade["volume_lots"], D(".10"))
                    self.assertEqual(trade["entry_price"], D(2000) + direction * (
                        costs.spread_usd_per_oz / 2 + costs.slippage_usd_per_oz))
                    self.assertEqual(trade["exit_price"], trade["exit_midpoint"] - direction * (
                        costs.spread_usd_per_oz / 2 + costs.slippage_usd_per_oz))
                    self.assertEqual(trade["commission_usd"], costs.round_trip_commission_usd_per_lot / 10)
                    self.assertEqual(trade["net_pnl_usd"], D(30) - trade["spread_cost_usd"]
                                     - trade["slippage_cost_usd"] - trade["commission_usd"])

    def test_repeatability_and_scenario_isolation(self):
        report = sensitivity.analyze_sensitivity()
        encoded = sensitivity.sensitivity_json()
        with localcontext() as context:
            context.prec = 3
            self.assertEqual(sensitivity.sensitivity_json(), encoded)
        with patch.object(sensitivity, "SCENARIOS", tuple(reversed(SCENARIOS))):
            self.assertEqual(sensitivity.analyze_sensitivity()["scenarios"], report["scenarios"])
        for scenario in report["scenarios"].values():
            portfolio = scenario["dynamic_portfolio"]
            self.assertEqual(portfolio["performance"]["account"]["starting_equity"], D(3000))
            first = portfolio["decision_path"][0]
            self.assertEqual(first["risk_day_opening_equity"], D(3000))
            self.assertEqual(first["risk_day_loss_to_date"], D(0))
        self.assertEqual(json.loads(encoded)["scenario_order"], [name for name, _ in SCENARIOS])

    def test_dynamic_path_risk_gates_and_commission(self):
        scenarios = sensitivity.analyze_sensitivity()["scenarios"]
        for (name, inputs), (lots, realized, rejections) in zip(SCENARIOS, (
            (".10", "60", 4), (".09", "-76.96", 4), (".08", "-67.52", 4), (".05", "-65.75", 5)
        )):
            with self.subTest(name=name):
                portfolio = scenarios[name]["dynamic_portfolio"]
                performance = portfolio["performance"]
                path = portfolio["decision_path"]
                opens = {item["row"]: item for item in path if item["event"] == "open"}
                fills = [item["exit"] for item in path if item["exit"]]
                self.assertEqual(opens[2]["entry"]["volume"], D(lots))
                self.assertEqual(opens[2]["entry"]["side"], "BUY")
                self.assertEqual(opens[5 if name == "ideal" else 6]["entry"]["side"], "SELL")
                self.assertEqual(fills[0]["reason"], "TARGET" if name == "ideal" else "OPEN_STOP")
                self.assertEqual(opens[4]["entry_status"], "UNVERIFIED_SIGNAL_INTERVAL"
                                 if name == "ideal" else "DAILY_LOSS_LIMIT")
                self.assertEqual(opens[6]["risk_day"], "synthetic-day-B")
                self.assertEqual(opens[6]["risk_day_loss_to_date"], D(0))
                self.assertEqual(opens[6]["entry_status"], "POSITION_LIMIT" if name == "ideal" else "FILLED")
                self.assertEqual(portfolio["rejection_count"], rejections)
                self.assertEqual(performance["trades"]["closed"], len(fills))
                self.assertEqual(portfolio["entry_count"], len(fills) + 1)
                self.assertEqual(sum(performance["entry_rejections"].values()), rejections)
                for fill in fills:
                    self.assertEqual(fill["commission"], fill["position"]["plan"]["volume"]
                                     * inputs.round_trip_commission_usd_per_lot)
                    self.assertEqual(fill["net_pnl"], fill["gross_pnl"] - fill["commission"])
                costs = performance["costs"]
                self.assertEqual(costs["commission_paid"], sum(fill["commission"] for fill in fills))
                self.assertEqual(performance["account"]["realized_net_pnl"], D(realized))
                self.assertEqual(sum(fill["net_pnl"] for fill in fills), D(realized))
                self.assertEqual(performance["unresolved_position"]["side"],
                                 "SELL" if name == "stress" else "BUY")
                self.assertIsNone(costs["spread_cost"]["value"])
                self.assertIsNone(costs["slippage_cost"]["value"])

    def test_checked_in_report_matches_generator(self):
        report = (Path(__file__).resolve().parents[2] / "reports" / "sensitivity_phase_6_5"
                  / "sensitivity.json")
        self.assertEqual(report.read_bytes(), sensitivity.sensitivity_json().encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
