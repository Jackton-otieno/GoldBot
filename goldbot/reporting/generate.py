"""Generate the Phase 6.7 report from saved evidence only."""

import argparse
import json
from decimal import Decimal
from html import escape
from pathlib import Path
from string import Template

from .evidence import collect
from .visualization import bars, event_curve

BLOCKERS = {
    "broker_server_time_and_dst": "Verify broker server time, UTC offset and DST behavior.",
    "risk_day_boundaries": "Verify effective broker risk-day reset boundaries.",
    "historical_executable_quotes_and_inputs":
        "Verify historical executable bid/ask, quote basis and other execution inputs.",
    "broker_tick_value": "Resolve the demo broker tick-value discrepancy.",
    "prospective_holdout":
        "Inventory prior intervals and precommit before collecting genuinely unseen, "
        "verified nonoverlapping candles.",
}


def esc(value):
    return escape(str(value), quote=True)


def table(caption, headings, rows):
    heads = "".join(f'<th scope="col">{esc(text)}</th>' for text in headings)
    body = []
    for name, *values in rows:
        cells = "".join(f"<td>{esc(value)}</td>" for value in values)
        body.append(f'<tr><th scope="row">{esc(name)}</th>{cells}</tr>')
    return (f'<div class="table" tabindex="0" role="region" aria-label="{esc(caption)}">'
            f"<table><caption>{esc(caption)}</caption><thead><tr>{heads}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table></div>")


def figure(path, caption):
    return (f'<figure><img src="{esc(path)}" alt="{esc(caption)}">'
            f"<figcaption>{esc(caption)}</figcaption></figure>")


def metric(value):
    return f"{Decimal(value):,.2f}"


def historical_section(frames, validation):
    parts = [
        '<section id="historical"><h2>Historical observations</h2>',
        "<p>Each timeframe uses its own original candle sequence. Raw broker-clock labels "
        "are preserved. Longer intervals may reflect sessions, clock changes or missing "
        "observations. BUY and SELL counts refer to strategy decisions at candle close.</p>",
    ]
    partition_rows = []
    for timeframe, frame in frames.items():
        market = frame["market_quality"]
        signals = frame["signal_counts"]
        replay = frame["replay_audit"]
        parts.append(f"<h3>{esc(timeframe)}</h3>")
        parts.append(table(f"{timeframe} historical quality and replay", ("Reported measure", "Value"), [
            ("Source candles", market["rows"]),
            ("First raw label", market["first_raw_label"]),
            ("Last raw label", market["last_raw_label"]),
            ("Nominal pairs", market["nominal_pairs"]),
            ("Shorter positive pairs", market["shorter_positive_pairs"]),
            ("Longer raw-label pairs", market["longer_pairs"]),
            ("Unexpected field-count rows", market["unexpected_field_count_rows"]),
            ("Nonpositive OHLC rows", market["ohlc_checks"]["nonpositive_price"]),
            ("Out-of-bounds OHLC rows", market["ohlc_checks"]["out_of_bounds"]),
            ("Rows with insufficient finite OHLC prices", market["ohlc_checks"]["insufficient_prices"]),
            ("Replay opens", replay["counts"]["open_events"]),
            ("Replay closes", replay["counts"]["closed_events"]),
            ("Final replay close has a successor open", "No"),
            *sorted(signals["decisions"].items()),
        ]))
        parts.extend([
            '<details><summary>Gap distribution and signal reasons</summary>',
            table(f"{timeframe} historical raw-label differences", ("Seconds", "Pairs"),
                  sorted(market["adjacent_label_differences"].items())),
            table(f"{timeframe} historical signal reasons", ("Reason", "Occurrences"),
                  sorted(signals["reasons"].items())),
            "</details>",
        ])
        parts.append('<details><summary>Historical indicator exports</summary><div class="grid">')
        for phase, record in frame["indicators"].items():
            parts.extend([
                '<div>',
                figure("../../" + record["chart"], f"{timeframe} historical indicators · Phase {phase}"),
                table(f"{timeframe} Phase {phase} coverage", ("Column", "Finite rows", "Warmup rows"),
                      [(name, item["finite_rows"], item["warmup_rows"])
                       for name, item in record["columns"].items()]),
                "</div>",
            ])
        parts.append("</div></details>")
        source = validation["boundaries"]["manifest"]["sources"][timeframe]
        for item in source["partitions"]:
            partition_rows.append((
                f"{timeframe} {item['name']}",
                f"{item['first_source_row']:,}–{item['last_source_row']:,}",
                f"{item['first_raw_server_clock_label']}–{item['last_raw_server_clock_label']}",
                item["count"], item["preceding_close_warmup_rows"],
            ))
    parts.extend([
        figure("charts/historical-gaps.svg", "Historical longer raw-label intervals by timeframe"),
        "<h3>Retrospective partition validation</h3>",
        "<p>All six partitions, including each partition named test, contain previously inspected "
        "data. Genuine unseen holdout collection and partition execution results are unavailable.</p>",
        table("Retrospective partitions in original row order",
              ("Partition", "Source rows", "Raw labels", "Rows", "Preceding warmup rows"), partition_rows),
        "</section>",
    ])
    return "\n".join(parts)


def synthetic_section(source):
    parts = [
        '<section id="synthetic"><h2>Hypothetical synthetic results</h2>',
        "<p>The fixed trades isolate cost changes at the same volume and reference prices. "
        "The dynamic comparison uses eight hand-authored M15 candles and injected signals. "
        "Its trade sizes, triggers and risk gates can change with the cost scenario.</p>",
    ]
    rows, account_rows, scenario_details = [], [], []
    for name in source["scenario_order"]:
        case = source["scenarios"][name]
        costs = case["inputs"]
        dynamic = case["dynamic_portfolio"]
        perf = dynamic["performance"]
        account = perf["account"]
        position = perf["unresolved_position"]
        rows.append((name.title(), costs["spread_usd_per_oz"], costs["slippage_usd_per_oz"],
                     costs["round_trip_commission_usd_per_lot"],
                     metric(case["fixed_trade_comparison"]["total_net_pnl_usd"]),
                     metric(account["realized_net_pnl"]), metric(account["final_equity"]),
                     metric(perf["max_drawdown"]["drawdown"]["value"])))
        account_rows.append((
            name.title(), metric(account["final_balance"]), metric(account["unrealized_pnl"]),
            f'{Decimal(account["realized_return"]):.3%}', f'{Decimal(account["marked_return"]):.3%}',
            dynamic["entry_count"], perf["trades"]["closed"], dynamic["rejection_count"],
            "None" if position is None else f"Open {position['side']} from row {position['entry_row']}",
            metric(perf["costs"]["commission_paid"]),
            "None" if position is None else metric(position["commission_due_on_exit"]),
        ))
        scenario_details.extend([
            f'<details><summary>{esc(name.title())} synthetic event series</summary><div class="grid">',
            figure(f"charts/synthetic-{name}-equity.svg", f"{name.title()} synthetic marked equity by event index"),
            figure(f"charts/synthetic-{name}-drawdown.svg", f"{name.title()} synthetic drawdown by event index"),
            "</div></details>",
        ])
    parts.extend([
        table("Hypothetical cost sensitivity in USD",
              ("Scenario", "Spread per oz", "Slippage per oz per modeled leg",
               "Round-trip commission per lot", "Fixed net P/L", "Dynamic realized net P/L",
               "Dynamic marked equity", "Dynamic max drawdown"), rows),
        '<div class="grid">',
        figure("charts/synthetic-fixed-pnl.svg", "Hypothetical fixed-trade net P/L in USD"),
        figure("charts/synthetic-realized-pnl.svg", "Hypothetical dynamic realized net P/L in USD"),
        "</div>",
        table("Synthetic dynamic account and terminal state",
              ("Scenario", "Final balance (USD)", "Unrealized P/L (USD)", "Realized return",
               "Marked return", "Entries", "Closed", "Rejected", "Unresolved position",
               "Paid commission (USD)", "Pending commission (USD)"), account_rows),
        "<p>Marked equity includes the unrealized liquidation-side mark. The full pending "
        "commission is due at exit. Unresolved positions remain open at the terminal event. "
        "The dynamic ledger records modeled fill prices with combined execution costs, so separate "
        "spread and slippage attribution is unavailable. Unavailable time-based metrics and "
        "their reasons are recorded in the JSON summary.</p>",
        *scenario_details, "</section>",
    ])
    return "\n".join(parts)


def readiness_section(diagnostic):
    items = "".join(f"<li>{esc(message)}</li>" for message in BLOCKERS.values())
    reported = diagnostic["reported_tick_values"]["trade_tick_value_loss"]
    formula = diagnostic["formula_usd_per_tick_per_lot"]
    return (
        '<section id="blocked"><h2>Readiness blockers</h2>'
        '<p><strong>Historical execution and profitability are unavailable.</strong> '
        'Genuine out-of-sample validation and automated demo readiness are blocked.</p>'
        f"<ul>{items}</ul>"
        f"<p>The saved demo diagnostic recorded USD {esc(reported)} loss tick value per lot "
        f"against a USD {esc(formula)} formula value. Its status was {esc(diagnostic['status'])}.</p>"
        "<p>Resolve these blockers in a dedicated phase before Phase 7.</p></section>"
    )


def provenance_section(hashes):
    links = []
    for path, digest in sorted(hashes.items()):
        links.append(f'<li><a href="../../{esc(path)}">{esc(path)}</a><br><code>{esc(digest)}</code></li>')
    return ('<section id="sources"><h2>Evidence provenance</h2><p>SHA-256 is computed from '
            'the exact input bytes. The report validates the schemas and reconciles shared '
            'counts, labels and source commitments.</p><details><summary>Input files and SHA-256'
            f'</summary><ul>{"".join(links)}</ul></details></section>')


def generate(root):
    """Validate all inputs and render before writing Phase 6.7 outputs."""
    root = Path(root)
    output = root / "reports/consolidated_phase_6_7"
    frames, validation, synthetic, diagnostic, hashes = collect(root)
    summary = {
        "schema_version": 1,
        "historical_observations": {
            "clock_semantics": "Raw broker server-clock labels in original source order.",
            "timeframes": frames,
            "retrospective_partitions": validation,
        },
        "hypothetical_synthetic_results": synthetic,
        "historical_performance": {
            "value": None, "status": "unavailable",
            "reason": "Historical execution has not been performed.",
            "blockers": list(BLOCKERS)[:4],
        },
        "readiness": {
            "genuine_out_of_sample_validation": {"status": "blocked", "blockers": list(BLOCKERS)},
            "automated_demo": {"status": "blocked", "blockers": list(BLOCKERS)},
            "blockers": BLOCKERS,
            "prior_demo_broker_diagnostic": diagnostic,
        },
        "input_sha256": hashes,
    }
    order = synthetic["scenario_order"]
    cases = synthetic["scenarios"]
    artifacts = {
        "summary.json": json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        "charts/historical-gaps.svg": bars(
            "Historical · longer raw-label intervals",
            [(name, frame["market_quality"]["longer_pairs"]) for name, frame in frames.items()]),
        "charts/synthetic-fixed-pnl.svg": bars(
            "Hypothetical synthetic · fixed net P/L (USD)",
            [(name.title(), metric(cases[name]["fixed_trade_comparison"]["total_net_pnl_usd"]))
             for name in order]),
        "charts/synthetic-realized-pnl.svg": bars(
            "Hypothetical synthetic · realized net P/L (USD)",
            [(name.title(), metric(cases[name]["dynamic_portfolio"]["performance"]["account"]["realized_net_pnl"]))
             for name in order]),
    }
    for name in order:
        series = cases[name]["dynamic_portfolio"]["performance"]["event_series"]
        for key, label in (("equity", "Marked equity"), ("drawdown", "Drawdown")):
            artifacts[f"charts/synthetic-{name}-{key}.svg"] = event_curve(name, series, key, label)
    template = Template(Path(__file__).with_name("index.template.html").read_text("utf-8"))
    artifacts["index.html"] = template.substitute(
        historical=historical_section(frames, validation),
        synthetic=synthetic_section(synthetic),
        blocked=readiness_section(diagnostic),
        sources=provenance_section(hashes),
    )
    for path, content in artifacts.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        output = generate(args.root)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Phase 6.7 report failed: {exc}\n")
    print(output / "index.html")


if __name__ == "__main__":
    main()

