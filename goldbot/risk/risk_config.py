"""Offline USD risk policy and explicit scenario inputs."""
from dataclasses import dataclass
from decimal import Decimal

D = Decimal
SYMBOL = "XAUUSD"
ILLUSTRATIVE_EQUITY = D("3000")
RISK_PER_TRADE = D("0.005")
STOP_ATR_MULTIPLE = D("1.5")
TARGET_STOP_MULTIPLE = D("2")
MAX_POSITIONS = 1
MAX_DAILY_LOSS = D("0.02")
MAX_DRAWDOWN = D("0.10")


@dataclass(frozen=True)
class Evidence:
    scenario_id: str
    source: str
    verified: bool

    def matches(self, scenario_id):
        return (
            self.verified is True
            and isinstance(scenario_id, str) and bool(scenario_id.strip())
            and self.scenario_id == scenario_id
            and isinstance(self.source, str) and bool(self.source.strip())
        )


@dataclass(frozen=True)
class AccountState:
    evidence: Evidence
    account_ref: str
    currency: str
    equity: Decimal
    peak_equity: Decimal
    free_margin: Decimal
    open_positions: int


@dataclass(frozen=True)
class RiskDayState:
    evidence: Evidence
    account_ref: str
    risk_day_id: str
    opening_equity: Decimal
    loss_to_date: Decimal


@dataclass(frozen=True)
class BrokerSpecs:
    evidence: Evidence
    symbol: str
    profit_currency: str
    margin_currency: str
    point: Decimal
    tick_size: Decimal
    tick_value_loss: Decimal
    contract_size: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    stops_level_points: int
    loss_model: str


@dataclass(frozen=True)
class ExecutionAssumptions:
    evidence: Evidence
    symbol: str
    side: str
    bid: Decimal
    ask: Decimal
    entry_slippage: Decimal
    stop_slippage: Decimal
    commission_round_trip_per_lot: Decimal
    margin_per_lot: Decimal


def decimal_at_least(value, minimum=0):
    return isinstance(value, Decimal) and value.is_finite() and value >= minimum


def positive(value):
    return decimal_at_least(value) and value > 0


def verified(state, scenario_id):
    return (
        isinstance(getattr(state, "evidence", None), Evidence)
        and state.evidence.matches(scenario_id)
    )
