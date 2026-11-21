"""Phase 6.3 offline account ledger for one replay timeframe."""

from dataclasses import dataclass
from decimal import Context, localcontext

from goldbot.analysis.data_analysis import INTERVALS
from goldbot.backtesting.execution_simulator import (
    EndOfData, EntryState, ExecutionSimulator, ExitFill, Position, SimulationSpec,
)
from goldbot.backtesting.historical_replay import ClosedEvent, OpenEvent, Replay
from goldbot.risk.risk_config import (
    AccountState, D, Evidence, ILLUSTRATIVE_EQUITY, MAX_DAILY_LOSS,
    MAX_DRAWDOWN, RiskDayState,
)


@dataclass(frozen=True)
class RiskBoundary:
    open_row: int
    risk_day_id: str


@dataclass(frozen=True)
class RiskSchedule:
    """Explicit hypothetical boundaries indexed by source row, effective before open."""
    timeframe: str
    evidence: Evidence
    boundaries: tuple[RiskBoundary, ...]

    def __post_init__(self):
        if (self.timeframe not in INTERVALS
                or not isinstance(self.evidence, Evidence)
                or not self.evidence.matches(self.evidence.scenario_id)
                or not isinstance(self.boundaries, tuple) or not self.boundaries):
            raise ValueError("explicit hypothetical risk schedule required")
        previous = 0
        ids = set()
        for boundary in self.boundaries:
            if (not isinstance(boundary, RiskBoundary)
                    or type(boundary.open_row) is not int
                    or boundary.open_row <= previous
                    or not isinstance(boundary.risk_day_id, str)
                    or not boundary.risk_day_id.strip()
                    or boundary.risk_day_id in ids):
                raise ValueError("risk boundaries require increasing rows and unique day IDs")
            previous = boundary.open_row
            ids.add(boundary.risk_day_id)
        if self.boundaries[0].open_row != 1:
            raise ValueError("risk schedule must start at source row 1")


@dataclass(frozen=True)
class PendingSignal:
    row: int
    side: str


@dataclass(frozen=True)
class LedgerEvent:
    timeframe: str
    row: int
    raw_server_clock_label: int
    event: str
    midpoint: D
    risk_day: RiskDayState
    boundary: bool
    balance: D
    unrealized_pnl: D
    liquidation_quote: D | None
    equity: D
    used_margin: D
    free_margin: D
    peak_equity: D
    drawdown: D
    drawdown_fraction: D
    daily_loss_used: D
    commission_paid: D
    commission_due_on_exit: D
    position: Position | None
    pending: PendingSignal | None
    attempted: PendingSignal | None
    entry_status: str | None
    entry: Position | None
    exit: ExitFill | None
    flags: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioResult:
    timeframe: str
    specification: SimulationSpec
    schedule: RiskSchedule
    events: tuple[LedgerEvent, ...]
    terminal: EndOfData


class PortfolioCoordinator:
    """Apply account state and risk gates around Phase 6.2 fills."""

    def __init__(self, spec: SimulationSpec, schedule: RiskSchedule):
        self._simulator = ExecutionSimulator(spec)
        if (not isinstance(schedule, RiskSchedule)
                or not schedule.evidence.matches(spec.evidence.scenario_id)):
            raise ValueError("explicit risk schedule with matching scenario provenance required")
        self._spec = spec
        self._schedule = schedule
        self._boundaries = {b.open_row: b.risk_day_id for b in schedule.boundaries}
        self._account_ref = f"{spec.evidence.scenario_id}/{schedule.timeframe}"
        self._records = []
        self._balance = self._peak = ILLUSTRATIVE_EQUITY
        self._commission = D(0)
        self._day_id = None
        self._day_open = ILLUSTRATIVE_EQUITY
        self._day_losses = D(0)
        self._daily_latched = self._drawdown_latched = self._insolvent = False
        self._position = self._pending = None

    def on_open(self, event: OpenEvent) -> LedgerEvent:
        with localcontext(Context(prec=40)):
            self._check_timeframe(event, OpenEvent)
            boundary = event.source_row in self._boundaries
            previous_equity = self._records[-1].equity if self._records else self._balance
            day_id = self._boundaries[event.source_row] if boundary else self._day_id
            day_open = previous_equity if boundary else self._day_open
            losses = D(0) if boundary else self._day_losses
            day = self._risk_day(day_id, day_open, losses)
            state, blocked = self._entry_state(day, boundary)
            result = self._simulator.on_open(
                event, state=state,
                admit=lambda position: self._entry_has_margin(position, D(str(event.open))),
            )
            status = blocked if result.entry_status == "UNAVAILABLE_STATE" else result.entry_status
            self._day_id, self._day_open, self._day_losses = day_id, day_open, losses
            if boundary:
                self._daily_latched = False
            attempted, self._pending = self._pending, None
            if result.entry is not None:
                self._position = result.entry
            return self._record(event, D(str(event.open)), boundary, attempted,
                                status, result.entry, result.exit)

    def on_closed(self, event: ClosedEvent) -> LedgerEvent:
        with localcontext(Context(prec=40)):
            self._check_timeframe(event, ClosedEvent)
            fill = self._simulator.on_closed(event)
            side = event.signal.decision
            if side in ("BUY", "SELL"):
                self._pending = PendingSignal(event.source_row, side)
            return self._record(event, D(str(event.close)), False, None, None, None, fill)

    def finish(self) -> PortfolioResult:
        if not self._records:
            raise ValueError("cannot finish an empty portfolio stream")
        terminal = self._simulator.finish()
        return PortfolioResult(self._schedule.timeframe, self._spec, self._schedule,
                               tuple(self._records), terminal)

    def _check_timeframe(self, event, kind):
        if not isinstance(event, kind) or event.timeframe != self._schedule.timeframe:
            raise ValueError("event must match the portfolio timeframe and event kind")

    def _risk_day(self, day_id, opening, losses):
        return RiskDayState(self._schedule.evidence, self._account_ref, day_id, opening, losses)

    def _entry_state(self, day, boundary):
        # A held position is handled by the simulator before it considers any entry.
        # When flat, balance is current equity and no margin is reserved.
        if self._position is not None:
            return None, None
        if self._insolvent:
            return None, "INSOLVENT"
        if self._drawdown_latched:
            return None, "DRAWDOWN_LIMIT"
        if self._daily_latched and not boundary:
            return None, "DAILY_LOSS_LIMIT"
        account = AccountState(
            self._spec.evidence, self._account_ref, "USD", self._balance, self._peak,
            self._balance, 0,
        )
        return EntryState(day.risk_day_id, account, day), None

    def _mark(self, position, midpoint):
        plan = position.plan
        direction = 1 if plan.side == "BUY" else -1
        quote = midpoint - direction * self._spec.spread / 2
        pnl = direction * (quote - plan.entry) * self._spec.broker.contract_size * plan.volume
        return quote, pnl

    def _entry_has_margin(self, position, midpoint):
        _, pnl = self._mark(position, midpoint)
        return self._balance + pnl >= position.plan.modeled_margin

    def _record(self, event, midpoint, boundary, attempted, status, entry, fill):
        if fill is not None:
            self._balance += fill.net_pnl
            self._commission += fill.commission
            self._day_losses += max(D(0), -fill.net_pnl)
            self._position = None
        quote, unrealized = None, D(0)
        margin = commission_due = D(0)
        if self._position is not None:
            quote, unrealized = self._mark(self._position, midpoint)
            margin = self._position.plan.modeled_margin
            commission_due = self._spec.round_trip_commission_per_lot * self._position.plan.volume

        equity = self._balance + unrealized
        free_margin = equity - margin
        self._peak = max(self._peak, equity)
        drawdown = self._peak - equity
        daily_used = max(self._day_losses, self._day_open - equity)
        self._daily_latched |= (
            self._day_open > 0 and daily_used >= self._day_open * MAX_DAILY_LOSS
        )
        self._drawdown_latched |= equity <= self._peak * (1 - MAX_DRAWDOWN)
        self._insolvent |= equity <= 0
        flags = tuple(name for name, active in (
            ("INSOLVENT", self._insolvent),
            ("DRAWDOWN_LIMIT", self._drawdown_latched),
            ("DAILY_LOSS_LIMIT", self._daily_latched),
            ("MARGIN_DEFICIT", free_margin < 0),
        ) if active)
        record = LedgerEvent(
            event.timeframe, event.source_row, event.raw_server_clock_label,
            "open" if isinstance(event, OpenEvent) else "closed", midpoint,
            self._risk_day(self._day_id, self._day_open, self._day_losses), boundary,
            self._balance, unrealized, quote, equity, margin, free_margin, self._peak,
            drawdown, drawdown / self._peak, daily_used, self._commission, commission_due,
            self._position, self._pending, attempted, status, entry, fill, flags,
        )
        self._records.append(record)
        return record


def run_portfolio(replay: Replay, *, spec: SimulationSpec, schedule: RiskSchedule):
    """Run one scenario. Call independently for each timeframe."""
    portfolio = PortfolioCoordinator(spec, schedule)
    if replay.timeframe != schedule.timeframe:
        raise ValueError("risk schedule must match the replay timeframe")
    for event in replay.events:
        if isinstance(event, OpenEvent):
            portfolio.on_open(event)
        else:
            portfolio.on_closed(event)
    return portfolio.finish()
