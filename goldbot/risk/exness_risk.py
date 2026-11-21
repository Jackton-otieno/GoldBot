"""Adapt an explicitly verified XAU-margin scenario to the offline USD risk model."""
from dataclasses import replace

from goldbot.risk.risk_config import BrokerSpecs
from goldbot.risk.risk_manager import evaluate_risk


def evaluate_xau_margin_risk(row, *, specs=None, execution=None, **scenario):
    """Use the scenario's explicit USD margin per lot after XAU-to-USD conversion.

    Broker evidence and all signal, account, risk-day and execution checks
    remain the responsibility of the USD risk manager.
    """
    if isinstance(specs, BrokerSpecs) and specs.margin_currency == "XAU":
        specs = replace(specs, margin_currency="USD")
    return evaluate_risk(row, specs=specs, execution=execution, **scenario)
