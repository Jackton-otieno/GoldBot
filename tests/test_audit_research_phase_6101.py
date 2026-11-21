from decimal import Decimal
from types import SimpleNamespace
import unittest

from tools.audit_research_phase_6101 import excursions


class ExcursionTests(unittest.TestCase):
    def test_excludes_exit_row_extremes_for_each_side(self):
        opens = {1: SimpleNamespace(open=100), 2: SimpleNamespace(open=101)}
        # There is deliberately no close event available for the exit row.
        closes = {1: SimpleNamespace(low=98, high=105)}
        for side, entry, expected in (
            ("BUY", "101", ("4", "3")),
            ("SELL", "99", ("7", "0")),
        ):
            with self.subTest(side=side):
                position = SimpleNamespace(
                    entry_row=1, plan=SimpleNamespace(side=side, entry=Decimal(entry)),
                )
                self.assertEqual(excursions(position, 2, opens, closes, Decimal(2)), {
                    "mae_lower_bound_usd_per_oz": Decimal(expected[0]),
                    "mfe_lower_bound_usd_per_oz": Decimal(expected[1]),
                    "fully_held_bar_count": 1,
                })

    def test_same_bar_exit_uses_only_its_open(self):
        position = SimpleNamespace(
            entry_row=1, plan=SimpleNamespace(side="SELL", entry=Decimal("99")),
        )
        self.assertEqual(excursions(
            position, 1, {1: SimpleNamespace(open=100)}, {}, Decimal(2),
        ), {
            "mae_lower_bound_usd_per_oz": Decimal(2),
            "mfe_lower_bound_usd_per_oz": Decimal(0),
            "fully_held_bar_count": 0,
        })
