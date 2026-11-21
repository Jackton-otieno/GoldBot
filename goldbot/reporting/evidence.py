"""Load and reconcile the Phase 6 evidence, without running a strategy."""

import csv
import hashlib
import io
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

TIMEFRAMES = {"M15": 900, "H1": 3600}
BASE_COLUMNS = "close sma_20 sma_50 sma_200 ema_9 ema_21 ema_50 ema_200".split()
EXTRA_COLUMNS = "rsi_14 macd_12_26 macd_signal_9 macd_histogram atr_14".split()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(isinstance(value, (str, int, float)) and type(value) is not bool,
            "expected a numeric value")
    result = Decimal(str(value))
    require(result.is_finite() and abs(result) <= Decimal("1e100"),
            "invalid or out-of-range numeric value")
    return result


def count(value):
    require(type(value) is int and value >= 0, "expected a nonnegative integer count")
    return value


def strict_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "duplicate JSON field")
    return result


def invalid_constant(value):
    raise ValueError(f"invalid JSON constant {value}")


class Evidence:
    def __init__(self, root):
        self.root = Path(root)
        self.hashes = {}

    def read(self, path):
        try:
            data = (self.root / path).read_bytes()
        except OSError as exc:
            raise ValueError(f"{path}: {exc.strerror}") from exc
        self.hashes[path] = hashlib.sha256(data).hexdigest()
        return data

    def parse(self, path, parser, *args):
        data = self.read(path)
        try:
            return parser(data, *args)
        except (ValueError, InvalidOperation, KeyError, IndexError, TypeError,
                AttributeError, csv.Error) as exc:
            raise ValueError(f"{path}: malformed or inconsistent evidence ({exc})") from exc


def json_data(data):
    return json.loads(data, parse_constant=invalid_constant, object_pairs_hook=strict_object)


def csv_rows(data, fields):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    require(reader.fieldnames == fields, "unexpected CSV columns")
    for row in reader:
        require(None not in row and None not in row.values(), "wrong CSV field count")
        yield row


def original_labels(data):
    fields = "mt5_time_epoch open high low close tick_volume spread real_volume".split()
    return [int(row["mt5_time_epoch"]) for row in csv_rows(data, fields)]


def quality(data, digest, labels, interval):
    source = data.decode("utf-8-sig").replace("\r\n", "\n")
    require(f"SHA-256 `{digest}`" in source, "original CSV hash mismatch")

    def captures(pattern):
        match = re.search(pattern, source, re.MULTILINE)
        require(match is not None, f"missing validation field: {pattern}")
        return [int(value.replace(",", "")) for value in match.groups()]

    rows, expected = captures(r"^CSV data rows \*\*([\d,]+)\*\* of ([\d,]+) expected")
    bad_fields, = captures(r"^Rows with unexpected field count \*\*([\d,]+)\*\*")
    first, last = captures(r"^-.+labels in file order: `(\d+)` and `(\d+)`")
    nominal, shorter, longer = captures(
        r"^- Nominal / shorter positive / longer differences: ([\d,]+) / ([\d,]+) / ([\d,]+)")
    histogram = {int(delta.replace(",", "")): int(pairs.replace(",", ""))
                 for delta, pairs in re.findall(r"^\| ([\d,]+) \| ([\d,]+) \|$",
                                                source, re.MULTILINE)}
    gaps = Counter(b - a for a, b in zip(labels, labels[1:]))
    require(rows == expected == len(labels) and (first, last) == (labels[0], labels[-1])
            and gaps == histogram and gaps[interval] == nominal
            and sum(n for delta, n in gaps.items() if delta > interval) == longer
            and sum(n for delta, n in gaps.items() if 0 < delta < interval) == shorter,
            "validation row counts, labels or gaps disagree with the original CSV")
    field_checks = {field: list(map(int, (missing, nonfinite, invalid)))
                    for field, missing, nonfinite, invalid in re.findall(
        r"^\| ([a-z_0-9]+) \| (\d+) \| (\d+) \| (\d+) \|$", source, re.MULTILINE)}
    require(set(field_checks) == set("mt5_time_epoch open high low close tick_volume spread real_volume".split()),
            "missing market quality field checks")
    return {
        "rows": rows, "unexpected_field_count_rows": bad_fields,
        "first_raw_label": first, "last_raw_label": last, "nominal_seconds": interval,
        "nominal_pairs": nominal, "shorter_positive_pairs": shorter, "longer_pairs": longer,
        "adjacent_label_differences": histogram,
        "field_checks": {key: dict(zip(("missing", "nonfinite", "invalid"), values))
                         for key, values in field_checks.items()},
        "ohlc_checks": {
            "nonpositive_price": captures(r"^- Rows with a nonpositive OHLC price: ([\d,]+)")[0],
            "out_of_bounds": captures(r"^- Rows violating low .+ high: ([\d,]+)")[0],
            "insufficient_prices": captures(r"^- Rows with insufficient finite prices for the OHLC check: ([\d,]+)")[0],
        },
    }


def derivatives(data, labels, interval, columns, signals=False):
    metadata = ["raw_server_clock_label", "raw_label_delta", "gap_before"]
    fields = metadata + columns
    if signals:
        fields = ["source_row"] + fields + ["decision", "reasons"]
    available = Counter({column: 0 for column in columns})
    decisions, reasons = Counter(), Counter()
    gap_count = rows = 0
    for rows, row in enumerate(csv_rows(data, fields), 1):
        label = labels[rows - 1]
        delta = label - labels[rows - 2] if rows > 1 else None
        gap = delta is not None and delta > interval
        require(row["raw_server_clock_label"] == str(label)
                and row["raw_label_delta"] == ("" if delta is None else str(delta))
                and row["gap_before"] == str(gap), f"row {rows}: label or gap mismatch")
        gap_count += gap
        for column in columns:
            if column != "close" and row[column] == "nan":
                continue
            number(row[column])
            available[column] += 1
        if signals:
            require(row["source_row"] == str(rows) and row["decision"] in ("BUY", "HOLD", "SELL")
                    and all(re.fullmatch(r"[A-Z_]+", token) for token in row["reasons"].split("|")),
                    f"row {rows}: invalid signal record")
            decisions[row["decision"]] += 1
            reasons.update(row["reasons"].split("|"))
    require(rows == len(labels), "CSV row count mismatch")
    if signals:
        return dict(rows=rows, decisions=dict(decisions), reasons=dict(reasons),
                    raw_label_gaps=gap_count)
    return {"rows": rows, "columns": {name: {"finite_rows": value, "warmup_rows": rows - value}
                                     for name, value in available.items()}}


def png(data):
    require(data.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
            and data.endswith(b"IEND\xaeB`\x82"), "invalid PNG framing")


def signal_counts(data, derived, timeframe, path, digest):
    result = json_data(data)
    require(result["source"] == Path(path).name and result["source_sha256"] == digest
            and result["timeframe"] == timeframe, "signal provenance mismatch")
    for key in ("decisions", "reasons"):
        for value in result[key].values():
            count(value)
    for key in ("rows", "raw_label_gaps"):
        count(result[key])
    require(all(result[key] == value for key, value in derived.items()),
            "counts disagree with the signal CSV")
    return result


def replay(data, signals, timeframe, digest, labels, interval):
    result = json_data(data)
    counts = result["counts"]
    rows = len(labels)
    require(result["timeframe"] == timeframe and result["source_sha256"] == digest
            and result["source"] == f"XAUUSD_{timeframe}.csv"
            and result["source_hash_verified"] is True, "replay provenance mismatch")
    require(all(count(counts[key]) == rows for key in ("source_rows", "closed_events", "open_events"))
            and result["final_closed_row"] == rows
            and result["final_closed_row_has_successor_open"] is False,
            "replay event counts or terminal state mismatch")
    require(all(counts[key] == signals[key] for key in ("decisions", "reasons", "raw_label_gaps")),
            "replay counts disagree with the signal audit")
    expected = [(i + 2, b, b - a) for i, (a, b) in enumerate(zip(labels, labels[1:]))
                if b - a > interval]
    events = result["gap_open_events"]
    require([(event["source_row"], event["raw_server_clock_label"], event["raw_label_delta"])
             for event in events] == expected and all(
                 event["event"] == "open" and event["gap_before"] is True
                 and event["timeframe"] == timeframe and number(event["open"]) > 0
                 for event in events), "replay gap events disagree with original labels")
    require(isinstance(result["sample_events"], list) and result["sample_events"],
            "missing replay sample events")
    return {key: result[key] for key in ("counts", "final_closed_row",
                                         "final_closed_row_has_successor_open", "source_sha256")}


def partitions(data, sources):
    result = json_data(data)
    for key in ("strategy", "boundaries"):
        record = result[key]
        manifest = record["manifest"]
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        require(hashlib.sha256(encoded).hexdigest() == record["sha256"], f"{key} digest mismatch")
    boundary = result["boundaries"]["manifest"]
    require(boundary["schema"] == "goldbot.strategy-validation.boundaries.v1"
            and boundary["classification"] == "retrospective partitions of previously inspected data"
            and boundary["genuine_unseen_holdout"] is False
            and result["historical_execution_performed"] is False
            and result["prospective_holdout_collected"] is False
            and boundary["strategy_manifest_sha256"] == result["strategy"]["sha256"]
            and set(boundary["sources"]) == set(sources), "unexpected validation scope")
    for timeframe, (digest, labels) in sources.items():
        source = boundary["sources"][timeframe]
        require(source["sha256"] == digest and source["row_count"] == len(labels)
                and source["path"] == f"data/XAUUSD_{timeframe}.csv",
                f"{timeframe}: partition source mismatch")
        records = source["partitions"]
        require([item["name"] for item in records] == ["development", "validation", "test"],
                f"{timeframe}: partition order mismatch")
        start = 0
        for record in records:
            end = count(record["last_source_row"])
            require(start < end <= len(labels) and record["first_source_row"] == start + 1
                    and record["count"] == end - start and record["preceding_close_warmup_rows"] == start
                    and record["first_raw_server_clock_label"] == labels[start]
                    and record["last_raw_server_clock_label"] == labels[end - 1],
                    f"{timeframe}: partition bounds mismatch")
            start = end
        require(start == len(labels), f"{timeframe}: incomplete partition coverage")
    return result


def sensitivity(data):
    source = json_data(data)
    order = source["scenario_order"]
    require(type(source["schema_version"]) is int and source["schema_version"] == 1
            and order == ["ideal", "low", "baseline", "stress"]
            and set(source["scenarios"]) == set(order)
            and "hand-authored" in source["dynamic_replay"]["source"]
            and "hypothetical" in source["cost_input_source"],
            "unexpected synthetic sensitivity schema or provenance")
    for name in order:
        case = source["scenarios"][name]
        require(all(number(case["inputs"][key]) >= 0 for key in (
            "spread_usd_per_oz", "slippage_usd_per_oz", "round_trip_commission_usd_per_lot")),
            "negative cost")
        fixed = case["fixed_trade_comparison"]
        dynamic = case["dynamic_portfolio"]
        perf = dynamic["performance"]
        require(perf["schema_version"] == 1 and perf["currency"] == "USD"
                and perf["timeframe"] == "M15" and perf["scenario_id"] == f"phase-6.5/{name}"
                and "hypothetical" in case["simulation_spec"]["evidence"]["source"],
                f"{name}: unexpected performance schema or provenance")
        with localcontext() as context:
            context.prec = 100
            require(sum(number(trade["net_pnl_usd"]) for trade in fixed["trades"])
                    == number(fixed["total_net_pnl_usd"]), f"{name}: fixed total mismatch")
            account = perf["account"]
            equity = number(account["final_equity"])
            balance = number(account["final_balance"])
            unrealized = number(account["unrealized_pnl"])
            realized = number(account["realized_net_pnl"])
            require(balance == number(account["starting_balance"]) + realized
                    and equity == balance + unrealized, f"{name}: account does not reconcile")
            for key in ("realized_return", "marked_return"):
                number(account[key])
            position = perf["unresolved_position"]
            require(count(dynamic["entry_count"]) == count(perf["trades"]["closed"]) + (position is not None)
                    and count(dynamic["rejection_count"]) == sum(map(count, perf["entry_rejections"].values()))
                    and (unrealized == 0 if position is None else number(position["unrealized_pnl"]) == unrealized),
                    f"{name}: trade counts or unresolved position do not reconcile")
        series = perf["event_series"]
        require(isinstance(series, list) and series, f"{name}: missing event series")
        for i, point in enumerate(series):
            require(count(point["event_index"]) == i and number(point["drawdown"]) >= 0
                    and type(point["position_open"]) is bool, f"{name}: invalid event series")
            number(point["equity"])
        require(number(series[0]["equity"]) == number(account["starting_equity"])
                and number(series[-1]["equity"]) == equity
                and series[-1]["position_open"] == (position is not None)
                and max(number(point["drawdown"]) for point in series)
                == number(perf["max_drawdown"]["drawdown"]["value"]),
                f"{name}: event series does not reconcile")
        for key in ("annualized_sharpe", "calendar_returns", "day_metrics", "elapsed_exposure"):
            item = perf["unavailable"][key]
            require(item["value"] is None and isinstance(item["reason"], str) and item["reason"],
                    f"{name}: invalid unavailable metric")
        for key in ("spread_cost", "slippage_cost"):
            item = perf["costs"][key]
            require(item["value"] is None and isinstance(item["reason"], str) and item["reason"],
                    f"{name}: invalid unavailable dynamic cost attribution")
        number(perf["costs"]["commission_paid"])
    return source


def broker(data):
    source = json_data(data)
    fields = source["raw_numeric_fields"]
    names = ("trade_tick_value", "trade_tick_value_profit", "trade_tick_value_loss")
    require(source["symbol"] == "XAUUSD" and source["provenance"]["account_mode"] == "DEMO"
            and all(number(fields[key]) > 0 for key in names)
            and number(fields["trade_tick_value_loss"]) != number(source["formula_usd_per_tick_per_lot"])
            and source["historical_applicability"] and source["errors"],
            "missing demo tick-value discrepancy evidence")
    return dict(status=source["status"], historical_applicability=source["historical_applicability"],
                reported_tick_values={key: fields[key] for key in names},
                formula_usd_per_tick_per_lot=source["formula_usd_per_tick_per_lot"],
                profit_probe_count=len(source["profit"]), margin_probe_count=len(source["margin"]))


def collect(root):
    evidence = Evidence(root)
    frames, sources = {}, {}
    for timeframe, interval in TIMEFRAMES.items():
        stem = f"XAUUSD_{timeframe}"
        raw = f"data/{stem}.csv"
        labels = evidence.parse(raw, original_labels)
        digest = evidence.hashes[raw]
        sources[timeframe] = digest, labels
        market = evidence.parse(f"reports/{stem}_validation.md", quality, digest, labels, interval)
        indicators = {}
        for phase, path, columns in (
            ("3.2", f"reports/indicators/{stem}_indicators", BASE_COLUMNS),
            ("3.3", f"reports/indicators_phase_3_3/{stem}_indicators_phase_3_3",
             BASE_COLUMNS + EXTRA_COLUMNS),
        ):
            record = evidence.parse(path + ".csv", derivatives, labels, interval, columns)
            evidence.parse(path + ".png", png)
            indicators[phase] = dict(record, chart=path + ".png", csv=path + ".csv")
        path = f"reports/signals_phase_4_1/{stem}_signals_phase_4_1"
        derived = evidence.parse(path + ".csv", derivatives, labels, interval,
                                 BASE_COLUMNS + EXTRA_COLUMNS, True)
        indicator_csv = indicators["3.3"]["csv"]
        signals = evidence.parse(path + "_counts.json", signal_counts, derived, timeframe,
                                 indicator_csv, evidence.hashes[indicator_csv])
        audit = evidence.parse(f"reports/replay_phase_6_1/{stem}_replay_audit.json", replay,
                               signals, timeframe, digest, labels, interval)
        frames[timeframe] = dict(market_quality=market, indicators=indicators,
                                 signal_counts=signals, replay_audit=audit)
    validation = evidence.parse("reports/validation_phase_6_6/validation.json", partitions, sources)
    synthetic = evidence.parse("reports/sensitivity_phase_6_5/sensitivity.json", sensitivity)
    diagnostic = evidence.parse("reports/phase_5_2_broker_diagnostic.json", broker)
    return frames, validation, synthetic, diagnostic, evidence.hashes

