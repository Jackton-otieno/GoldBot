# Draft prospective protocol

**DRAFT. Approval, external precommit, collection and evaluation are pending.**
The proposed horizon is 12 calendar months. Start and end are deliberately
unset. Before any collection or viewing, approve explicit UTC instants for
one half-open window [start, end). Both candidates use that same window.
No performance peeks, trade-count triggers, replacements, extensions,
or early success stops. An integrity or safety stop can invalidate collection
and leave the study inconclusive. Publish both decisions together once.
A pass does not promote a candidate, pick a winner, or authorize Phase 7.

## Candidates and freeze

Evaluate the unchanged Phase 6.6 baseline independently on XAUUSD M15 and
H1. Start each with USD 3,000 and isolated state. No cross-timeframe inputs,
portfolio pooling, or changes after approval. Use the registered source
events inside the window for warmup. Begin taking signals only after the
frozen indicator initialization and a valid prior candle. Use closed-bar
inputs and make the next executable quote eligible only after signal
availability. Never use subsequent data to choose a fill. Predeclare
aggregation, quote basis for indicators, event ordering, latency,
tick/volume rounding, stop/target and gap behavior, missing-interval rules,
and a conservative slippage model supported by independent evidence. Preserve
the frozen risk configuration, including 0.5% per trade, one position,
1.5 ATR stop, 2R target, 2% loss limit and the 10% drawdown latch. Verify
account-scoped risk-day boundaries, prior loss handling, margin and conversion
before registration. Quote-observed fills remain simulated.

The Phase 6.8.5 midpoint OHLC scenarios, stop-first ambiguity, constant
margin and run-long synthetic risk bucket are frozen references only. The
prospective evaluator, its exact execution rules and environment, and the
chosen feed/broker scope are unresolved. Approve and hash their exact bytes
before collection, together with the strategy, reference inventory, UTC
window, prior-exposure declaration and criteria. Recompute the current freeze
from actual bytes in the evaluation harness. Use a separately trusted
registrar or timestamp service and retain the receipt, approval, signer
identity, verification chain and archived manifest. A local SHA-256 identifies
bytes and supplies no trusted timestamp or approval. A trusted registrar
must verify approval before sealing the registration. A reviewer independent
of strategy development must attest the canonical intake and evaluation audit
with separately authorized signer roles. The code delegates receipt validation
to this trust integration, which is still pending.

## Prior exposure

Both original 10,000-row CSVs, their complete 60/20/20 partitions, derived
indicator and signal data, replay outputs and all eight Phase 6.8.5 runs
are exposed. The original endpoint labels below have unverified time semantics.

| Source | First raw label | Last raw label |
| --- | ---: | ---: |
| XAUUSD M15 | 1781128800 | 1794930300 |
| XAUUSD H1 | 1740704400 | 1794927600 |

Also inventory quotes or market observations in Phase 5.2 and Phase 6.8.1
through 6.8.4 diagnostics, including clock/DST observations where they
contain price data. Phase 6.8.4 returned zero archived ticks. Derived files
and synthetic cases do not create new market coverage. Disclose any other
datasets or market windows inspected outside the repository and include them
before registration. The reviewer should use source-lineage evidence and
conservative verified UTC coverage bounds for each exposed source, including
bar spans, across both timeframes. Require the entire collection window
(including warmup) to avoid every prior interval across both candidates,
even for an alternative feed. Missing mapping or undisclosed prior exposure
blocks eligibility.

## Read-only collection design

Use a separate collector with data-only credentials or a vendor archive,
and no trading interface. Preserve the original bid and ask, flags, sequence
and raw source timestamps with native precision. Log UTC receipt timestamps,
clock source and offset evidence, drift, reconnects and request errors.
Retain effective-dated quote/trade sessions, holidays and exceptions, symbol
and account scope, contract and tick economics, point, volume and stop
constraints, margin and currency conversion rules, commissions and rounding,
swap units/rates and rollover calendar, risk-day boundaries and execution
eligibility. Record heartbeat/sequence and independently reconcile open
session silence against the approved gap threshold and closures. No forward
fill. Repair only from a preapproved independent source with raw evidence
and the same verified lineage. Otherwise incomplete relevant coverage makes
the study inconclusive.

Seal append-only chunks with sequence ranges, counts, hashes and UTC bounds.
Keep raw and transformed data separate, record the parser/environment and
hash chain, store revocation-resistant copies and retain access logs.
Restrict payload access to the independent custodian until the end and
review of eligibility. Operational monitoring may show integrity, heartbeat
and completeness only. Suppress prices, trades, signals and performance.
After the window, independently attest the exact payload, evidence hashes,
UTC coverage and prior-exposure mapping. Retain the evidence objects and
receipts alongside the sealed manifest. The verifier must authenticate each
role and recompute or verify evidence hashes and conclusions. The framework
does not verify the underlying vendor statements or audit a trading ledger
from raw ticks.

## Decision rules

These thresholds are provisional research choices and provide no statistical
proof. Each candidate needs at least 100 closed trades, positive net USD
P/L after all costs, after-cost profit factor at least 1.3, observed maximum
drawdown strictly below 10%, and zero risk violations, lookahead, input
overlap, or strategy/protocol changes. Net trade P/L includes executable
bid/ask, slippage, commissions and verified funding or documented
inapplicability. Missing funding evidence makes evaluation inconclusive.
Profit factor divides positive net trade P/L by absolute negative net trade
P/L. Ignore zero-P/L trades for the ratio. Positive wins with no losses
yield positive infinity. No wins and no losses makes PF undefined and fails
the positive-net criterion for a complete, sufficiently sampled ledger.
Mark equity at each observable executable quote and ledger event using the
liquidation side, including applicable accrued costs. Drawdown is the
largest observed peak-to-trough equity decline divided by its running peak.

Expire an end-window pending signal unfilled. A still-open position makes
the candidate inconclusive. No synthetic close or post-window evidence may
settle it. Record every trade and mark, preserve the full audit trail, and
reconcile flat terminal equity to starting equity and net trade P/L. Audit
event chronology, all risk checks, fill eligibility and the absence of
lookahead using the registered evaluator. A verified protocol breach fails.
Insufficient trades, missing required evidence or incomplete outcomes are
inconclusive. Before trustworthy registration or the fixed end, evaluation
is blocked. Complete assessed candidates that miss a performance threshold
fail. Record all outcomes without ranking the candidates.
