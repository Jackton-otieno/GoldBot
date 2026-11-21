from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from goldbot.core.exness_demo import VerificationError
from tools import verify_exness_precision_phase_61051 as phase


class MonetaryPrecisionTests(TestCase):
    def test_half_cent_boundary_and_direction(self):
        entry, exit_price = D("3741.005"), D("3741.004")
        self.assertEqual(phase.amounts("BUY", D(".01"), entry, exit_price),
                         (D("-.001"), D("-.01")))
        self.assertEqual(phase.amounts("SELL", D(".01"), entry, exit_price),
                         (D(".001"), D(".01")))
        self.assertEqual(phase.amounts("BUY", D(".01"), entry, D("3741.006")),
                         (D(".001"), D("0")))

    def test_frozen_grid_disjoint_and_exact_sizing_limit(self):
        sources, archive = phase.load_evidence(phase.ROOT)
        report, impact = phase.build(sources, archive, {"status": "NOT_QUERIED"}, [])
        self.assertEqual(len(set(phase.cases())), 216)
        self.assertEqual(report["calculator_observations"], 0)
        self.assertIsNone(impact["independent_calculator"])
        self.assertEqual(impact["sizing_example"]["hypothetical_excess_usd"], D(".009"))
        self.assertLess(impact["independent_frozen_model"]["max_underestimate_usd"], D(".01"))

    def test_wrong_installation_rejected_before_attach(self):
        api = Mock()
        profile = SimpleNamespace(server=phase.SERVER, login=19498,
                                  terminal=Path("other/terminal64.exe"))
        with self.assertRaises(VerificationError):
            phase.probe(api, profile)
        self.assertEqual(api.mock_calls, [])

    def test_distinct_full_account_pins_fail_even_with_same_suffix(self):
        with patch.object(phase, "local_profile", side_effect=[19498, 29498]):
            with self.assertRaises(VerificationError):
                phase.confirmed_profile(None)

    def test_active_identity_failure_prevents_any_calculator_query(self):
        api = Mock()
        api.initialize.return_value = True
        profile = SimpleNamespace(server=phase.SERVER, login=19498, terminal=phase.INSTALLATION)
        with patch.object(phase, "require_running_terminal"), patch.object(
                phase, "check_identity", side_effect=VerificationError("Wrong account")):
            with self.assertRaises(VerificationError):
                phase.probe(api, profile, discover=lambda: [])
        api.order_calc_profit.assert_not_called()
        api.shutdown.assert_called_once()
