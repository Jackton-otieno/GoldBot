"""Read-only monetary precision diagnostics for the selected Exness KE demo."""
import argparse
from collections import Counter, defaultdict
from decimal import (
    Decimal as D, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN,
    ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP,
)
import json
import os
import sys

from goldbot.core.exness_demo import (
    DemoProfile, KE_COMPANY, VerificationError, check_identity,
    require_running_terminal, running_terminals,
)
from goldbot.risk.broker_spec_validator import (
    DiagnosticError, api_code, check_grid, require, snapshot, validate,
)

SERVER = "ExnessKE-MT5Trial9"
SUFFIX = "9498"
SYMBOL = "XAUUSD"
CENT = D("0.01")
TARGETS = tuple(map(D, (
    "0", ".001", ".002", ".004", ".005", ".006", ".009", ".010",
    ".011", ".015", ".019", ".020", ".025", ".035", ".049",
    ".050", ".055", ".099", ".100", ".105", ".101", "1.000",
)))
ROUNDINGS = {
    "nearest_half_even": ROUND_HALF_EVEN,
    "nearest_half_away": ROUND_HALF_UP,
    "nearest_half_toward_zero": ROUND_HALF_DOWN,
    "away_from_zero": ROUND_UP,
    "truncate": ROUND_DOWN,
    "ceiling": ROUND_CEILING,
    "floor": ROUND_FLOOR,
}


def predictions(amount):
    values = {name: amount.quantize(CENT, rounding=mode)
              for name, mode in ROUNDINGS.items()}
    remainder = abs(amount) % CENT
    for name, fallback in (
        ("nearest_half_positive", "ceiling"),
        ("nearest_half_negative", "floor"),
    ):
        values[name] = (values[fallback] if remainder == CENT / 2
                        else values["nearest_half_even"])
    for name in tuple(values):
        if name.startswith("nearest"):
            values["minimum_cent_" + name] = (
                values[name] or (CENT.copy_sign(amount) if amount else D("0.00"))
            )
    return values


def grid(specs, info, anchors):
    cap = D(str(info.volume_limit)) or specs.volume_max
    volumes = tuple(volume for volume in map(D, (".01", ".02", ".03", ".05", ".10"))
                    if specs.volume_min <= volume <= min(cap, specs.volume_max)
                    and volume % specs.volume_step == 0)
    unsupported, cases = [], []
    for volume in volumes:
        cash_per_tick = volume * specs.contract_size * specs.tick_size
        for target in TARGETS:
            ticks, remainder = divmod(target, cash_per_tick)
            if remainder:
                unsupported.append({"lots": str(volume), "target_usd": str(target),
                                    "reason": "not attainable on the price tick grid"})
                continue
            for entry in anchors:
                for side, direction in (("BUY", 1), ("SELL", -1)):
                    for amount in (target, -target) if target else (target,):
                        move = ticks * specs.tick_size * direction
                        exit_price = entry - move if amount < 0 else entry + move
                        require(exit_price > 0, "INVALID_PRECISION_PROBE_PRICE")
                        cases.append((side, volume, entry, exit_price, amount))
    return cases, unsupported


def summarize(rows, contract_size=D("100")):
    notional_matches = Counter()
    groups = defaultdict(list)
    matches = defaultdict(Counter)
    unmatched = 0
    for row in rows:
        amount = D(row["formula_usd"])
        key = row["side"], row["lots"], row["entry"], abs(amount)
        groups[key].append(row)
        if "observed_usd" not in row:
            continue
        actual = D(row["observed_usd"])
        names = [name for name, expected in predictions(amount).items() if actual == expected]
        row["matching_policies"] = names
        quantity = D(row["lots"]) * contract_size
        opening = D(row["entry"]) * quantity
        closing = D(row["exit"]) * quantity
        direction = 1 if row["side"] == "BUY" else -1
        for mode in (ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_DOWN):
            predicted = direction * (closing.quantize(CENT, rounding=mode)
                                     - opening.quantize(CENT, rounding=mode))
            notional_matches[mode] += predicted == actual
        unmatched += not names
        for label in ("all", row["side"], "zero" if not amount else
                      ("positive" if amount > 0 else "negative")):
            matches[label]["observations"] += 1
            matches[label].update(names)
    asymmetry, changed, comparable = [], [], 0
    for key, group in groups.items():
        by_sign = defaultdict(set)
        for row in group:
            by_sign[D(row["formula_usd"])].add(row.get("observed_usd"))
        case = dict(zip(("side", "lots", "entry", "magnitude_usd"), map(str, key)))
        magnitude = key[-1]
        if any(len(values) > 1 for values in by_sign.values()):
            changed.append(case)
        if magnitude:
            for repeat in sorted({row["repeat"] for row in group}):
                pair = {D(row["formula_usd"]): D(row["observed_usd"]) for row in group
                        if row["repeat"] == repeat and "observed_usd" in row}
                if len(pair) == 2:
                    comparable += 1
                    if pair[magnitude] != -pair[-magnitude]:
                        asymmetry.append({**case, "repeat": repeat})
    return {"policy_counts": dict(matches), "notional_policy_matches": dict(notional_matches), "unsupported_observations": sum(
        "observed_usd" not in row for row in rows), "matches_no_candidate": unmatched,
        "sign_pairs_compared": comparable, "sign_asymmetries": asymmetry,
        "changed_between_repeats": changed}


def investigate(mt5, profile, discover=running_terminals):
    if profile.server != SERVER or str(profile.login)[-4:] != SUFFIX:
        raise VerificationError("Select the exact Exness KE demo ending 9498.")

    def identity():
        try:
            terminal, account = check_identity(mt5, profile)
        except VerificationError:
            raise DiagnosticError("PINNED_EXNESS_IDENTITY_CHANGED") from None
        require(account.company == KE_COMPANY and account.leverage == 100
                and terminal.trade_allowed is False, "EXNESS_SAFETY_GATE")
        return terminal, account

    require_running_terminal(profile.terminal, discover())
    try:
        if not mt5.initialize(str(profile.terminal), timeout=5000):
            raise VerificationError("Read-only MT5 attachment failed.")
        terminal, account = identity()
        info, specs, metadata = snapshot(mt5)
        require(info.custom is False, "CUSTOM_OR_UNVERIFIED_SYMBOL")
        contract = validate(mt5, account, expected_server=SERVER, exness_identity=identity)
        report = {"server": SERVER, "account_suffix": SUFFIX, "company": KE_COMPANY,
                  "mode": "demo", "terminal_build": terminal.build,
                  "account_currency_digits": account.currency_digits, "contract": contract,
                  "acceptance": "BLOCKED_PENDING_AUTHORITATIVE_EVIDENCE"}
        if (account.currency_digits != 2 or len(contract["profit"]) != 144
                or len(contract["margin"]) != 24):
            report["precision_status"] = "UNSUPPORTED_CONTRACT_OR_INCOMPLETE_BASELINE"
            return report

        def check_context():
            _, current = identity()
            require(current.currency_digits == account.currency_digits
                    and snapshot(mt5)[2] == metadata, "PRECISION_CONTEXT_CHANGED")

        check_grid(info, specs)
        anchors = sorted({D(row["entry"]) for row in contract["margin"]})
        cases, unsupported = grid(specs, info, anchors)
        sides = {"BUY": mt5.ORDER_TYPE_BUY, "SELL": mt5.ORDER_TYPE_SELL}
        rows = []
        for repeat in (1, 2):
            for side, volume, entry, exit_price, amount in cases:
                check_context()
                raw = mt5.order_calc_profit(sides[side], SYMBOL, float(volume),
                                            float(entry), float(exit_price))
                row = {"repeat": repeat, "side": side, "lots": str(volume),
                       "entry": str(entry), "exit": str(exit_price), "formula_usd": str(amount)}
                if raw is None:
                    row.update(error="PROFIT_UNAVAILABLE", api_code=api_code(mt5))
                elif not D(str(raw)).is_finite():
                    row.update(error="NONFINITE_PROFIT")
                else:
                    row["observed_usd"] = str(D(str(raw)))
                rows.append(row)
            check_context()
        report.update(precision_status="OBSERVED", precision=rows, unsupported_grid=unsupported,
                      summary=summarize(rows, specs.contract_size))
        return report
    finally:
        mt5.shutdown()


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        profile = DemoProfile.from_environment(os.environ)
        import MetaTrader5 as mt5

        result = investigate(mt5, profile)
        print(json.dumps(result, indent=2, allow_nan=False))
        return int(result["precision_status"] != "OBSERVED")
    except VerificationError as error:
        print(str(error), file=sys.stderr)
    except DiagnosticError as error:
        print(error.reason, file=sys.stderr)
    except Exception:
        print("Exness monetary precision diagnostics could not complete.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
