"""Point-in-time MT5 demo diagnostics for the Phase 5.1 USD model."""
from collections import Counter
from math import isfinite
from datetime import datetime, timezone
from decimal import DecimalException, ROUND_FLOOR

from goldbot.risk.risk_config import BrokerSpecs, D, Evidence, SYMBOL, decimal_at_least, positive

# MT5 ENUM_SYMBOL_CALC_MODE values for supported OTC linear P/L modes.
LINEAR_MODES = {0: "FOREX", 1: "FOREX_NO_LEVERAGE", 3: "CFD",
                4: "CFDINDEX", 5: "CFDLEVERAGE"}
NUMERIC_FIELDS = {
    "point": "point", "tick_size": "trade_tick_size",
    "tick_value_loss": "trade_tick_value_loss", "contract_size": "trade_contract_size",
    "volume_min": "volume_min", "volume_max": "volume_max", "volume_step": "volume_step",
}
EXTRA_FIELDS = ("trade_tick_value", "trade_tick_value_profit", "volume_limit",
                "trade_freeze_level", "trade_calc_mode", "digits", "trade_mode")

MARGIN_FIELDS = ("margin_initial", "margin_maintenance", "margin_hedged")
CONTEXT_FIELDS = (*MARGIN_FIELDS, "margin_hedged_use_leg", "currency_base", "custom")


class DiagnosticError(Exception):
    def __init__(self, reason, api_code=None):
        self.reason = reason
        self.api_code = api_code


def require(condition, reason):
    if not condition:
        raise DiagnosticError(reason)


def api_code(mt5):
    error = mt5.last_error()
    return error[0] if isinstance(error, (tuple, list)) and error and type(error[0]) is int else None


def require_demo(mt5, initial, expected_server):
    require(initial.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO, "DEMO_REQUIRED")
    terminal = mt5.terminal_info()
    account = mt5.account_info() if terminal and terminal.connected else None
    if account is None:
        raise DiagnosticError("CONNECTION_UNAVAILABLE", api_code(mt5))
    require(account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO, "DEMO_REQUIRED")
    require(bool(initial.login) and account.login == initial.login
            and account.server == initial.server == expected_server
            and account.currency == initial.currency
            and account.currency_digits == initial.currency_digits
            and account.leverage == initial.leverage, "CONNECTION_MISMATCH")
    return account


def snapshot(mt5, report=None):
    info = mt5.symbol_info(SYMBOL)
    if info is None:
        raise DiagnosticError("SYMBOL_UNAVAILABLE", api_code(mt5))
    raw_fields = (*NUMERIC_FIELDS.values(), *EXTRA_FIELDS, "name",
                  "currency_profit", "currency_margin", "trade_stops_level")
    context = {field: getattr(info, field, None) for field in CONTEXT_FIELDS}
    if report is not None:
        report["symbol_identity"] = {
            "name": info.name,
            "custom": context["custom"] if type(context["custom"]) is bool else None,
        }
        report["currencies"] = {
            key: value if isinstance(value, str) and value.isascii()
            and value.isalpha() and 1 <= len(value) <= 8 else None
            for key, value in (("base", context["currency_base"]),
                               ("profit", info.currency_profit), ("margin", info.currency_margin))
        }
        report["margin_metadata"] = {
            field: value if type(value := context[field]) in (int, float)
            and isfinite(value) else None for field in MARGIN_FIELDS
        }
        use_leg = context["margin_hedged_use_leg"]
        report["margin_metadata"]["hedged_use_leg"] = use_leg if type(use_leg) is bool else None
        numeric = (*NUMERIC_FIELDS.values(), *EXTRA_FIELDS, "trade_stops_level",
                   "bid", "ask", "time")
        report["raw_numeric_fields"] = {
            field: value if type(value := getattr(info, field, None)) in (int, float) and isfinite(value) else None
            for field in numeric
        }
    require(info.name == SYMBOL, "SYMBOL_MISMATCH")
    require(context["custom"] is None or context["custom"] is False, "CUSTOM_SYMBOL")
    require(all(context[field] is None or (
        type(context[field]) in (int, float) and isfinite(context[field]) and context[field] >= 0
    ) for field in MARGIN_FIELDS), "INVALID_MARGIN_METADATA")
    specs = BrokerSpecs(
        evidence=Evidence("current-demo-diagnostic", "MT5 symbol_info", False),
        symbol=SYMBOL, profit_currency=info.currency_profit, margin_currency=info.currency_margin,
        stops_level_points=info.trade_stops_level, loss_model="USD_LINEAR",
        **{key: D(str(getattr(info, field))) for key, field in NUMERIC_FIELDS.items()},
    )
    metadata = tuple(getattr(info, field) for field in raw_fields) + tuple(context.values())
    return info, specs, metadata


def check_grid(info, specs):
    require(all(positive(getattr(specs, field)) for field in NUMERIC_FIELDS),
            "INVALID_SPECIFICATION")
    require(all(type(value) is int and value >= 0 for value in
                (info.digits, info.trade_stops_level, info.trade_freeze_level, info.trade_mode))
            and specs.point == D(10) ** -info.digits
            and specs.tick_size % specs.point == 0, "INVALID_PRICE_GRID_OR_LEVELS")
    limit = D(str(info.volume_limit))
    require(decimal_at_least(limit) and specs.volume_min <= specs.volume_max
            and all(value % specs.volume_step == 0
                    for value in (specs.volume_min, specs.volume_max, limit)),
            "INVALID_VOLUME_GRID")
    cap = min(specs.volume_max, limit) if limit else specs.volume_max
    volumes = sorted({v for v in (specs.volume_min, specs.volume_min + specs.volume_step,
                                  specs.volume_min + 9 * specs.volume_step) if v <= cap})
    require(len(volumes) >= 2, "INSUFFICIENT_VOLUME_COVERAGE")
    return volumes


def validate(mt5, initial, *, expected_server, exness_identity=None):
    report = {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "symbol": SYMBOL, "status": "REJECTED", "errors": [],
              "historical_applicability": "UNVERIFIED", "profit": [], "margin": []}
    try:
        run_probes(mt5, initial, expected_server, report, exness_identity)
    except DiagnosticError as error:
        report["errors"].append({"reason": error.reason, "api_code": error.api_code})
    except (AttributeError, TypeError, ValueError, DecimalException, OverflowError) as error:
        report["errors"].append({"reason": "INVALID_OR_MISSING_DATA",
                                 "exception_type": type(error).__name__})
    if not report["errors"]:
        report["status"] = "CURRENT_DEMO_PROBES_CONSISTENT"
    report["probe_counts"] = {
        "profit": len(report["profit"]),
        "margin": len(report["margin"]),
        "profit_errors": dict(Counter(
            error for row in report["profit"] for error in row.get("errors", ())
        )),
        "margin_errors": dict(Counter(
            row["error"] for row in report["margin"] if "error" in row
        )),
    }
    return report


def tick_value_comparison(reported, expected_tick, specs, generic):
    per_point = specs.point * specs.contract_size
    per_minimum_volume = expected_tick * specs.volume_min
    return {
        "formula_usd_per_point_per_lot": str(per_point),
        "formula_usd_per_tick_at_minimum_volume": str(per_minimum_volume),
        "fields": {
            field: {
                "reported": str(value),
                "formula_tick_per_lot_to_reported_ratio": str(expected_tick / value),
                "implied_lots_if_value_is_usd_per_tick": str(value / expected_tick),
                "matches_point_per_lot_exactly": value == per_point,
                "matches_tick_at_minimum_volume_exactly": value == per_minimum_volume,
            }
            for field, value in (("generic", generic), ("profit", reported["PROFIT"]),
                                 ("loss", reported["LOSS"]))
        },
        "interpretation": "Arithmetic comparisons only; broker field units remain unconfirmed.",
    }


def run_probes(mt5, initial, expected_server, report, exness_identity=None):
    if exness_identity is not None:
        exness_identity()
    account = require_demo(mt5, initial, expected_server)
    report["provenance"] = {"account_mode": "DEMO", "mt5_package": mt5.__version__,
                            "terminal_version": mt5.version(), "leverage": account.leverage,
                            "expected_server_matched": True, "account_currency_digits": account.currency_digits}
    require(type(account.leverage) is int and account.leverage > 0
            and type(account.currency_digits) is int and account.currency_digits == 2,
            "UNSUPPORTED_ACCOUNT_PRECISION_OR_LEVERAGE")
    info, specs, metadata = snapshot(mt5, report)
    report["currencies"]["account"] = (
        account.currency if isinstance(account.currency, str)
        and len(account.currency) == 3 and account.currency.isascii()
        and account.currency.isalpha() else None
    )
    if exness_identity is None:
        require(account.currency == specs.profit_currency == specs.margin_currency == "USD",
                "UNSUPPORTED_CURRENCY")
    else:
        require(account.currency == specs.profit_currency == "USD"
                and specs.margin_currency == info.currency_base == "XAU", "UNSUPPORTED_CURRENCY")
        require(info.custom is False and info.trade_calc_mode == 0
                and info.digits == 3 and specs.point == specs.tick_size == D("0.001")
                and specs.contract_size == 100 and specs.volume_min == specs.volume_step == D("0.01")
                and specs.volume_max == 200, "EXNESS_CONTRACT_MISMATCH")
    require(type(info.trade_calc_mode) is int and info.trade_calc_mode in LINEAR_MODES,
            "UNSUPPORTED_CALC_MODE")
    report["calc_mode"] = LINEAR_MODES[info.trade_calc_mode]
    if exness_identity is not None:
        require(info.margin_initial == 0 and info.margin_maintenance == 0,
                "UNSUPPORTED_EXNESS_MARGIN_OVERRIDE")
        report["margin_model"] = {
            "base": "lots * contract_size / account_leverage",
            "base_currency": "XAU",
            "conversion": "probe entry in USD per XAU",
            "assumed_margin_rate": "1",
            "result_currency": "USD",
        }
    volumes = check_grid(info, specs)
    bid, ask = D(str(info.bid)), D(str(info.ask))
    require(positive(bid) and positive(ask) and ask >= bid, "INVALID_QUOTE")
    tick = specs.tick_size
    anchors = sorted({(quote / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
                      for quote in (bid, ask, bid * D("0.99"), ask * D("1.01"))})
    if exness_identity is not None:
        require(len(anchors) == 4 and len(volumes) == 3, "INCOMPLETE_EXNESS_PROBE_GRID")
    require(len(anchors) >= 2 and anchors[0] > 100 * tick, "INSUFFICIENT_PRICE_COVERAGE")
    require(type(info.time) is int and info.time > 0, "MISSING_QUOTE_TIME")
    reported = {"LOSS": specs.tick_value_loss, "PROFIT": D(str(info.trade_tick_value_profit))}
    generic = D(str(info.trade_tick_value))
    require(all(positive(value) for value in (*reported.values(), generic)),
            "INVALID_TICK_VALUES")
    expected_tick = tick * specs.contract_size
    report["formula_usd_per_tick_per_lot"] = str(expected_tick)
    report["tick_value_comparison"] = tick_value_comparison(reported, expected_tick, specs, generic)
    # Half of the smallest reported account-currency unit plus floating-point slack.
    tolerance = D("0.00500001")
    report["cash_tolerance_usd"] = str(tolerance)
    report["metadata_tick_value_tolerance"] = "0 (Phase 5.1 exact formula check)"
    if any(value != expected_tick for value in (*reported.values(), generic)):
        report["errors"].append({"reason": "INCONSISTENT_TICK_VALUE_METADATA"})

    def check_context():
        if exness_identity is not None:
            exness_identity()
        require_demo(mt5, initial, expected_server)
        _, _, current = snapshot(mt5)
        require(current == metadata, "SYMBOL_METADATA_CHANGED")

    for side, order_type, direction in (("BUY", mt5.ORDER_TYPE_BUY, 1),
                                        ("SELL", mt5.ORDER_TYPE_SELL, -1)):
        for entry in anchors:
            linear_margins = []
            for volume in volumes:
                check_context()
                margin = mt5.order_calc_margin(order_type, SYMBOL, float(volume), float(entry))
                row = {"side": side, "lots": str(volume), "entry": str(entry)}
                report["margin"].append(row)
                if margin is None:
                    row.update(error="MARGIN_UNAVAILABLE", api_code=api_code(mt5))
                else:
                    amount = D(str(margin))
                    row["observed_usd"] = str(amount)
                    if positive(amount):
                        low = (amount - tolerance) / volume
                        high = (amount + tolerance) / volume
                        linear_margins.append((low, high))
                        row["usd_per_lot"] = str(amount / volume)
                        if exness_identity is not None:
                            base_margin = volume * specs.contract_size / account.leverage
                            expected_margin = base_margin * entry
                            row.update(formula_xau=str(base_margin), formula_usd=str(expected_margin))
                            if abs(amount - expected_margin) > tolerance:
                                row["error"] = "MARGIN_CONVERSION_MISMATCH"
                    else:
                        row["error"] = "INVALID_MARGIN"
                if "error" in row:
                    report["errors"].append({"reason": row["error"],
                                             "margin_row": len(report["margin"]) - 1})
                for ticks in (1, 10, 100):
                    for outcome, sign in (("PROFIT", 1), ("LOSS", -1)):
                        check_context()
                        exit_price = entry + direction * sign * ticks * tick
                        units = abs(exit_price - entry) / tick * volume
                        expected = sign * units * expected_tick
                        metadata_cash = sign * units * reported[outcome]
                        row = {"side": side, "outcome": outcome, "lots": str(volume),
                               "entry": str(entry), "exit": str(exit_price), "ticks": ticks,
                               "formula_usd": str(expected), "metadata_usd": str(metadata_cash),
                               "normalized_tolerance": str(tolerance / units)}
                        report["profit"].append(row)
                        value = mt5.order_calc_profit(order_type, SYMBOL, float(volume),
                                                      float(entry), float(exit_price))
                        if value is None:
                            row.update(errors=["PROFIT_UNAVAILABLE"], api_code=api_code(mt5))
                        else:
                            observed = D(str(value))
                            row["observed_usd"] = str(observed)
                            row["errors"] = []
                            if not observed.is_finite():
                                row["errors"].append("INVALID_PROFIT")
                            else:
                                row["implied_usd_per_tick_per_lot"] = str(sign * observed / units)
                                if sign * observed < 0 or (observed == 0 and abs(expected) > tolerance):
                                    row["errors"].append("WRONG_PROFIT_SIGN")
                                if abs(observed - expected) > tolerance:
                                    row["errors"].append("PROFIT_FORMULA_MISMATCH")
                                if abs(observed - metadata_cash) > tolerance:
                                    row["errors"].append("PROFIT_METADATA_MISMATCH")
                        if row["errors"]:
                            report["errors"].append({"reason": "PROFIT_PROBE_FAILED",
                                                     "profit_row": len(report["profit"]) - 1})
            if linear_margins and max(low for low, _ in linear_margins) > min(
                    high for _, high in linear_margins):
                report["errors"].append({"reason": "NONLINEAR_MARGIN", "side": side,
                                         "entry": str(entry)})
    check_context()
    report["final_metadata_recheck_passed"] = True

