"""Independent read-only Exness calculator check and offline loss analysis."""

import argparse
from decimal import Decimal as D, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import sys

from goldbot.core.exness_demo import (
    KE_COMPANY, VerificationError, check_identity, require_running_terminal, running_terminals,
)
from goldbot.risk.broker_spec_validator import DiagnosticError, api_code, check_grid, require, snapshot
from goldbot.risk.position_sizing import size_position
from goldbot.risk.risk_config import BrokerSpecs, Evidence, ExecutionAssumptions
from tools.verify_exness_phase_6941 import local_profile
from tools.verify_exness_precision import CENT, SERVER, SUFFIX, SYMBOL


ROOT = Path(__file__).resolve().parents[1]
INSTALLATION = Path("C:/Program Files/MetaTrader 5/terminal64.exe")
CONTRACT, TICK = D("100"), D(".001")
ANCHORS = tuple(map(D, ("3741.004", "3741.005", "3741.006")))
LOTS = tuple(map(D, (".01", ".02", ".07")))
DISTANCES = (1, 4, 5, 6, 9, 37)
ARCHIVES = ("phase_6_9_3/initial-probes.json", "phase_6_9_3/probes.json",
            "phase_6_9_3_1/probes.json")


def amounts(side, lots, entry, exit_price):
    direction = 1 if side == "BUY" else -1
    quantity = lots * CONTRACT
    opening, closing = entry * quantity, exit_price * quantity
    exact = direction * (exit_price - entry) * quantity
    rounded = direction * (closing.quantize(CENT, rounding=ROUND_HALF_UP)
                           - opening.quantize(CENT, rounding=ROUND_HALF_UP))
    return exact, rounded


def cases():
    return [(side, lots, entry, entry + sign * TICK * ticks)
            for entry in ANCHORS for lots in LOTS for ticks in DISTANCES
            for side in ("BUY", "SELL") for sign in (-1, 1)]


def key(row):
    return row["side"], D(row["lots"]), D(row["entry"]), D(row["exit"])


def load_evidence(root):
    seen, observations, sources = set(), [], {}
    for name in ARCHIVES:
        path = root / "reports" / name
        raw = path.read_bytes()
        record = json.loads(raw)
        sources[name] = sha256(raw).hexdigest()
        contract = record.get("contract", record)
        seen.update(key(row) for row in contract["profit"])
        for row in record.get("precision", ()):
            case = key(row)
            seen.add(case)
            if row["repeat"] == 1 and "observed_usd" in row:
                observations.append((case, D(row["observed_usd"])))
    require(not set(cases()) & seen, "INDEPENDENT_GRID_OVERLAPS_ARCHIVE")
    return sources, observations


def probe(mt5, profile, discover=running_terminals):
    if (profile.server != SERVER or str(profile.login)[-4:] != SUFFIX
            or profile.terminal.resolve() != INSTALLATION.resolve()):
        raise VerificationError("The independently pinned Exness installation and demo are required.")
    require_running_terminal(profile.terminal, discover())

    def identity():
        terminal, account = check_identity(mt5, profile)
        require(account.company == KE_COMPANY and account.leverage == 100
                and account.currency_digits == 2 and terminal.trade_allowed is False,
                "EXNESS_SAFETY_GATE")
        return terminal

    try:
        if not mt5.initialize(str(profile.terminal), timeout=5000):
            raise VerificationError("Read-only MT5 attachment failed.")
        terminal = identity()
        info, specs, metadata = snapshot(mt5)
        check_grid(info, specs)
        require(info.custom is False and info.trade_calc_mode == 0
                and specs.profit_currency == "USD" and specs.contract_size == CONTRACT
                and specs.tick_size == TICK and specs.volume_min == LOTS[0]
                and all(v <= (D(str(info.volume_limit)) or specs.volume_max)
                        and v <= specs.volume_max and v % specs.volume_step == 0 for v in LOTS),
                "UNEXPECTED_PRECISION_CONTRACT")
        sides = {"BUY": mt5.ORDER_TYPE_BUY, "SELL": mt5.ORDER_TYPE_SELL}
        rows = []
        for side, lots, entry, exit_price in cases():
            identity()
            require(snapshot(mt5)[2] == metadata, "PRECISION_CONTEXT_CHANGED")
            value = mt5.order_calc_profit(sides[side], SYMBOL, float(lots),
                                         float(entry), float(exit_price))
            actual = D(str(value)) if value is not None else None
            rows.append({"observed_usd": actual} if actual is not None and actual.is_finite()
                        else {"error": "PROFIT_UNAVAILABLE", "api_code": api_code(mt5)})
        identity()
        require(snapshot(mt5)[2] == metadata, "PRECISION_CONTEXT_CHANGED")
        return {"status": "QUERIED", "terminal_build": terminal.build,
                "python_package": mt5.__version__}, rows
    finally:
        mt5.shutdown()


def loss_stats(observations):
    differences = [exact_loss + result for exact_loss, result in observations]
    return dict(adverse_cases=len(differences),
                zero_reported_loss=sum(result == 0 for _, result in observations),
                underestimates=sum(value > 0 for value in differences),
                overestimates=sum(value < 0 for value in differences),
                max_underestimate_usd=max([D(0), *differences]),
                max_overestimate_usd=max([D(0), *(-value for value in differences)]))


def confirmed_profile(stream):
    local = local_profile(stream)
    trusted = local_profile(stream)
    if local != trusted:
        raise VerificationError("The local opt-in and independent enrollment pins differ.")
    return local


def build(sources, archived, context, observed):
    grid = cases()
    require(not observed or len(observed) == len(grid), "INCOMPLETE_OBSERVATION_LEDGER")
    records, models, actuals = [], [], []
    for index, (side, lots, entry, exit_price) in enumerate(grid):
        exact, model = amounts(side, lots, entry, exit_price)
        result = observed[index] if observed else {"status": "NOT_QUERIED"}
        actual = result.get("observed_usd")
        records.append(dict(side=side, lots=lots, entry=entry, exit=exit_price,
                            ticks=int(abs(exit_price - entry) / TICK),
                            theoretical_usd=exact, frozen_model_usd=model,
                            calculator=result, matches_model=None if actual is None else actual == model))
        if exact < 0:
            models.append((-exact, model))
            if actual is not None:
                actuals.append((-exact, actual))

    archive_losses = []
    for case, actual in archived:
        exact, _ = amounts(*case)
        if exact < 0:
            archive_losses.append((-exact, actual))

    evidence = Evidence("precision-research", "synthetic sizing illustration", False)
    specs = BrokerSpecs(evidence, SYMBOL, "USD", "USD", TICK, TICK, CONTRACT*TICK,
                        CONTRACT, LOTS[0], D("10"), LOTS[0], 0, "USD_LINEAR")
    execution = ExecutionAssumptions(evidence, SYMBOL, "BUY", D("3741.005"), D("3741.005"),
                                    D(0), D(0), D(0), D("200"))
    exact, model = amounts("BUY", LOTS[0], D("3741.005"), D("3741.004"))
    size, status = size_position(stop_distance=TICK, budget=-exact, free_margin=D("100"),
                                 specs=specs, execution=execution)
    return (
        dict(engineering="COMPLETED", broker_acceptance="BLOCKED", readiness="NO-GO",
             account_suffix=SUFFIX, server=SERVER, symbol=SYMBOL, source_sha256=sources,
             archived_first_pass_observations=len(archived),
             archived_first_pass_model_matches=sum(amounts(*case)[1] == actual
                                                   for case, actual in archived),
             context=context, distinct_independent_cases=len(records),
             calculator_observations=sum("observed_usd" in row["calculator"] for row in records),
             calculator_model_matches=sum(row["matches_model"] is True for row in records),
             rows=records),
        dict(archived_calculator=loss_stats(archive_losses),
             independent_calculator=loss_stats(actuals) if actuals else None,
             independent_frozen_model=loss_stats(models),
             model_absolute_error_strict_upper_bound_usd=CENT,
             sizing_example=dict(status=status, volume=size.volume, budget_usd=-exact,
                                 existing_linear_loss_usd=size.modeled_loss,
                                 hypothetical_model_loss_usd=-model,
                                 hypothetical_excess_usd=-model-size.modeled_loss),
             planner_policy="UNCHANGED", booked_profit_loss="UNVERIFIED"),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-stdin", action="store_true")
    args = parser.parse_args()
    sources, archived = load_evidence(ROOT)
    context, observed = {"status": "NOT_REQUESTED"}, []
    if args.profile_stdin:
        try:
            require_running_terminal(INSTALLATION, running_terminals())
            profile = confirmed_profile(sys.stdin)
            import MetaTrader5 as mt5

            context, observed = probe(mt5, profile)
        except (VerificationError, DiagnosticError) as error:
            context = {"status": "STOPPED", "reason": getattr(error, "reason", str(error))}
    for name, data in zip(("precision-validation.json", "risk-impact.json"),
                          build(sources, archived, context, observed)):
        with (args.output / name).open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, default=str, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")


if __name__ == "__main__":
    main()
