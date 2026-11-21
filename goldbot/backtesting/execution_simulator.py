"""Single-stream execution mechanics for explicitly hypothetical XAUUSD scenarios."""

from dataclasses import dataclass
from decimal import Context, ROUND_CEILING, ROUND_FLOOR, localcontext

from goldbot.analysis.data_analysis import INTERVALS
from goldbot.backtesting.historical_replay import ClosedEvent, OpenEvent
from goldbot.risk.risk_config import (
    AccountState, BrokerSpecs, D, Evidence, ExecutionAssumptions, RiskDayState,
    SYMBOL, decimal_at_least, positive,
)
from goldbot.risk.risk_manager import evaluate_risk
from goldbot.risk.trade_plan import TradePlan, round_to_tick


@dataclass(frozen=True)
class SimulationSpec:
    evidence: Evidence
    broker: BrokerSpecs
    spread: D
    entry_slippage: D
    stop_slippage: D
    round_trip_commission_per_lot: D
    margin_per_lot: D

    def __post_init__(self):
        # This object attests a hypothetical scenario only.
        evidence = self.evidence
        broker = self.broker
        if (not isinstance(evidence, Evidence) or not evidence.matches(evidence.scenario_id)
                or not isinstance(broker, BrokerSpecs) or broker.evidence != evidence
                or (broker.symbol, broker.profit_currency, broker.margin_currency,
                    broker.loss_model) != (SYMBOL, "USD", "USD", "USD_LINEAR")):
            raise ValueError("invalid hypothetical simulation specification")
        if not all(positive(value) for value in (
            broker.point, broker.tick_size, broker.tick_value_loss, broker.contract_size,
            broker.volume_min, broker.volume_max, broker.volume_step, self.margin_per_lot,
        )) or not all(decimal_at_least(value) for value in (
            self.spread, self.entry_slippage, self.stop_slippage,
            self.round_trip_commission_per_lot,
        )):
            raise ValueError("invalid simulation prices, costs or volume")
        with localcontext(Context(prec=40)):
            if (broker.tick_value_loss != broker.tick_size * broker.contract_size
                    or broker.tick_size % broker.point
                    or broker.volume_max < broker.volume_min
                    or broker.volume_min % broker.volume_step
                    or broker.volume_max % broker.volume_step
                    or type(broker.stops_level_points) is not int
                    or broker.stops_level_points < 0):
                raise ValueError("inconsistent hypothetical tick value or broker grid")


@dataclass(frozen=True)
class EntryState:
    risk_day_id: str
    account: AccountState
    risk_day: RiskDayState


@dataclass(frozen=True)
class Position:
    signal_row: int
    entry_row: int
    plan: TradePlan


@dataclass(frozen=True)
class ExitFill:
    position: Position
    row: int
    reason: str
    price: D
    gross_pnl: D
    commission: D
    net_pnl: D
    both_touched: bool = False


@dataclass(frozen=True)
class OpenResult:
    entry_status: str
    entry: Position | None = None
    exit: ExitFill | None = None


@dataclass(frozen=True)
class EndOfData:
    terminal_signal_row: int | None
    unresolved_position: Position | None


def _identity(event):
    return (event.timeframe, event.source_row, event.raw_server_clock_label,
            event.raw_label_delta, event.gap_before, event.open)


class ExecutionSimulator:
    """Consume one alternating Phase 6.1 event stream in original row order."""

    def __init__(self, spec: SimulationSpec):
        if not isinstance(spec, SimulationSpec):
            raise TypeError("explicit SimulationSpec required")
        self._spec = spec
        self._opening = None
        self._previous = None
        self._position = None
        self._end = None

    def on_open(self, event: OpenEvent, *, state: EntryState | None = None,
                admit=None) -> OpenResult:
        """Optionally reject a planned position before committing its fill."""
        with localcontext(Context(prec=40)):
            self._check_open(event)
            midpoint = self._midpoint(event.open)
            if self._position is None:
                result = self._entry(event, midpoint, state)
                if result.entry is not None and admit is not None and not admit(result.entry):
                    result = OpenResult("INSUFFICIENT_MARKED_MARGIN")
            else:
                quote = self._exit_quote(midpoint)
                fill = self._exit(event.source_row, quote, quote, at_open=True)
                result = OpenResult("POSITION_LIMIT", exit=fill)

            if result.exit is not None:
                self._position = None
            if result.entry is not None:
                self._position = result.entry
            self._opening = event
            return result

    def on_closed(self, event: ClosedEvent) -> ExitFill | None:
        with localcontext(Context(prec=40)):
            if (self._end is not None or self._opening is None
                    or not isinstance(event, ClosedEvent)
                    or _identity(event) != _identity(self._opening)):
                raise ValueError("closed event must match the outstanding open")
            low, high, close, opening = map(
                self._midpoint, (event.low, event.high, event.close, event.open)
            )
            if not low <= min(opening, close) <= max(opening, close) <= high:
                raise ValueError("inconsistent simulation OHLC")
            fill = None
            if self._position is not None:
                fill = self._exit(event.source_row, self._exit_quote(low),
                                  self._exit_quote(high), at_open=False)
            if fill is not None:
                self._position = None
            self._previous = event
            self._opening = None
            return fill

    def finish(self) -> EndOfData:
        """Seal a complete candle stream and expose any unfilled signal or position."""
        if self._opening is not None:
            raise ValueError("cannot finish with an unmatched open")
        if self._end is None:
            terminal = None
            if self._previous is not None and self._previous.signal.decision in ("BUY", "SELL"):
                terminal = self._previous.source_row
            self._end = EndOfData(terminal, self._position)
        return self._end

    def _check_open(self, event):
        if (self._end is not None or self._opening is not None
                or not isinstance(event, OpenEvent) or event.timeframe not in INTERVALS
                or type(event.raw_server_clock_label) is not int
                or event.raw_server_clock_label <= 0):
            raise ValueError("expected next replay open")
        previous = self._previous
        row = 1 if previous is None else previous.source_row + 1
        if type(event.source_row) is not int or event.source_row != row:
            raise ValueError("duplicate, stale or missing replay row")
        delta = None if previous is None else (
            event.raw_server_clock_label - previous.raw_server_clock_label
        )
        interval = INTERVALS[event.timeframe]
        if (previous is not None and (
                event.timeframe != previous.timeframe or delta <= 0 or delta % interval
            ) or event.raw_label_delta != delta
                or event.gap_before is not (delta is not None and delta > interval)):
            raise ValueError("inconsistent replay sequence metadata")

    def _midpoint(self, price):
        midpoint = D(str(price))
        if not positive(midpoint) or midpoint <= self._spec.spread / 2:
            raise ValueError("simulation midpoint must imply positive bid and ask")
        return midpoint

    def _entry(self, event, midpoint, state):
        signal = self._previous
        if signal is None:
            return OpenResult("NO_PRIOR_SIGNAL")
        side = signal.signal.decision
        if side == "HOLD":
            return OpenResult("HOLD_SIGNAL")
        if event.gap_before:
            return OpenResult("GAP_ENTRY")
        if not isinstance(state, EntryState):
            return OpenResult("UNAVAILABLE_STATE")

        spec = self._spec
        half_spread = spec.spread / 2
        # A grid-rounded stop level plus this buffered slippage stays on-grid.
        stop_buffer = round_to_tick(spec.stop_slippage, spec.broker.tick_size, ROUND_CEILING)
        execution = ExecutionAssumptions(
            spec.evidence, SYMBOL, side, midpoint - half_spread, midpoint + half_spread,
            spec.entry_slippage, stop_buffer, spec.round_trip_commission_per_lot,
            spec.margin_per_lot,
        )
        row = {
            "decision": side,
            "reasons": "|".join(signal.signal.reasons),
            "gap_before": str(signal.gap_before),
            "atr_14": dict(signal.indicators).get("atr_14"),
        }
        decision = evaluate_risk(
            row, scenario_id=spec.evidence.scenario_id, risk_day_id=state.risk_day_id,
            signal_evidence=spec.evidence, account=state.account, risk_day=state.risk_day,
            specs=spec.broker, execution=execution,
        )
        if decision.plan is None:
            return OpenResult(decision.reason)
        return OpenResult("FILLED", Position(signal.source_row, event.source_row, decision.plan))

    def _exit_quote(self, midpoint):
        half_spread = self._spec.spread / 2
        return midpoint - half_spread if self._position.plan.side == "BUY" else midpoint + half_spread

    def _exit(self, row, low, high, *, at_open):
        position = self._position
        plan = position.plan
        buy = plan.side == "BUY"
        adverse, favorable, direction = (low, high, 1) if buy else (high, low, -1)
        stop_hit = direction * (adverse - plan.stop) <= 0
        target_hit = direction * (favorable - plan.target) >= 0
        if stop_hit:
            reference = adverse if at_open else plan.stop
            price = round_to_tick(
                reference - direction * self._spec.stop_slippage,
                self._spec.broker.tick_size, ROUND_FLOOR if buy else ROUND_CEILING,
            )
            if not positive(price):
                raise ValueError("modeled stop fill must be positive")
            reason = "OPEN_STOP" if at_open else "STOP"
        elif target_hit:
            price = plan.target
            reason = "OPEN_TARGET" if at_open else "TARGET"
        else:
            return None
        gross = direction * (price - plan.entry) * self._spec.broker.contract_size * plan.volume
        commission = self._spec.round_trip_commission_per_lot * plan.volume
        return ExitFill(position, row, reason, price, gross, commission, gross - commission,
                        stop_hit and target_hit)
