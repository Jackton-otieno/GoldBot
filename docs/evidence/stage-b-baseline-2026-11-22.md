# Stage B baseline result: 22 November 2026

**Result: NOT PASSED. 6 of 7 criteria met.** Opening equity is `UNRESOLVED`
because of one zero-amount correction entry. Under the protocol, Stage C may
not start. Self-tested, not independently validated. GoldBot remains NO-GO.

This summary has no login and no deal ticket numbers, so it can be shared.
The full output stays local.

| Item | Value |
| --- | --- |
| Output file | `reports/phase_6_11/demo-baseline.json` |
| SHA-256 | `f376ce6671b9890cc2a99ef2c6e4e4b18b77aa71f348fe8c1f200a1d6ce4ed1c` |
| Read at (UTC) | 2026-11-22 05:53:44 (corrected; first written as 08:53:44, which was Nairobi time) |
| Account | Exness (KE) Limited · ExnessKE-MT5Trial9 · demo · USD · leverage 1:100 |
| Command | `--from 2026-11-18 --boundary-utc 2026-11-22T00:00:00Z` (offset +2, from the measured rule) |

## Acceptance criteria

| # | Check | Result | Value |
| --- | --- | --- | --- |
| 1 | Identity at start and end | **Pass** | The read completed. Identity and balance were stable across it. |
| 2 | No exposure | **Pass** | margin 0, credit 0, equity = balance = 3000 |
| 3 | Ledger sums to balance | **Pass** | 3000.0 = 3000.0. No aggregate discrepancy; this does not prove completeness. |
| 4 | Opening equity `SUPPORTED` | **Fail** | `UNRESOLVED`, reason `UNVERIFIED_LEDGER_ENTRY_TYPE` |
| 5 | Planned stops feasible | **Pass** | Status `OK`. Broker minimum stop distance 0. Spread 0.168. |
| 6 | No reconciliation issues | **Pass** | 0 issues, 0 positions |
| 7 | Exposure-log entry | **Pass** | Entry 4 appended with this file's SHA-256. The chain verifies. |

### Why criterion 4 failed

The history holds two non-trading entries:

| Entry | Server time | UTC | Type | Amount (profit / commission / swap / fee) |
| --- | --- | --- | --- | --- |
| Deposit | Wed 18 Nov 06:04:23 | 04:04:23 | 2, BALANCE | 3000.00 / 0 / 0 / 0 |
| Correction | **Sun 22 Nov** 05:05:13 | 03:05:13 | **5, CORRECTION** | 0.00 / 0 / 0 / 0 |

The reader accepts only balance entries (type 2) among non-trading deals,
so a correction entry blocks `SUPPORTED` whatever its amount. It was posted
on a Sunday, when the market is closed, three hours after the boundary.
Its four recorded amounts are all zero, so it cannot have changed the
balance, and the ledger still sums to the current balance. The fail-closed
rule did what it was designed to do. Its purpose is not recorded.

**Options. Each needs a decision; none is applied:**

1. **Identify the entry.** In MT5's History tab (Deals view), find the
   correction on 22 Nov and read its comment. The reader deliberately does
   not export comments.
2. **Amend the rule.** Accept a non-trading entry of any type only when all
   four amount fields are exactly zero. Report it, but don't let it block
   `SUPPORTED`. This is a change to a reviewed safeguard, so it needs your
   approval and the reviewer's before it is made. Stage B would then be run
   again.
3. **Move the boundary.** This won't help: the correction sits after any
   boundary before 22 Nov 03:05 UTC, and every type is checked whatever its
   time.

### Update: cause identified and reader changed (22 Nov)

The operator checked MT5's History tab. The correction's comment is
**"Archived deals"**, its amount is USD 0.00, and the account shows no
trading deals. That looks like a broker-generated administrative entry tied
to deal archiving. The comment alone cannot show that no history was
archived or omitted.

Option 2 was taken in a narrower form, as the reviewer recommended:

- Only a type-5 correction whose comment is exactly `Archived deals` and
  whose four amounts are all exactly zero is recognized. Any other
  correction, or this comment with a nonzero amount, still gives
  `UNRESOLVED`.
- A recognized entry gives **`CONDITIONAL`**, never `SUPPORTED`. It carries
  the condition `ARCHIVED_DEALS_CORRECTION_PRESENT` and a warning that
  historical completeness cannot be independently established from the MT5
  ledger alone. Any other blocking reason still gives `UNRESOLVED`.
- The entry and its comment are kept in the output under
  `archived_deals_corrections`. Other comments are still not exported.
- Regression tests cover the accepted case, a nonzero amount, other and
  near-miss comments, and precedence of blocking reasons.

**A re-run of Stage B is expected to report `CONDITIONAL`.** Criterion 4
requires `SUPPORTED`, so Stage B still would not pass unless the operator
records a decision to accept `CONDITIONAL` for that baseline, with the
warning stated. That decision has not been taken. The original output above
is kept unchanged.

### Re-run with the revised reader (22 Nov)

| Item | Value |
| --- | --- |
| Output file | `reports/phase_6_11/demo-baseline-2.json` |
| SHA-256 | `0dc6e9c4f67f24026893bbf5d45eb1f5ba0240572acba84e81e8d5ed5183d95f` |
| Read at (UTC) | 2026-11-22 06:07:50 |
| Exposure log | Entry 5, with this SHA-256. The chain verifies. |

| # | Check | Result |
| --- | --- | --- |
| 1 | Identity at start and end | **Pass** |
| 2 | No exposure | **Pass**: margin 0, credit 0, equity = balance = 3000.0 |
| 3 | Ledger sums to balance | **Pass**: 3000.0 = 3000.0 (no aggregate discrepancy; does not prove completeness) |
| 4 | Opening equity `SUPPORTED` | **Not met: `CONDITIONAL`.** No blocking reasons. Condition `ARCHIVED_DEALS_CORRECTION_PRESENT`, with the completeness warning. Balance at the boundary 3000.0; no position across it. |
| 5 | Planned stops feasible | **Pass**: `OK`, spread 0.168, broker minimum 0 |
| 6 | No reconciliation issues | **Pass**: 0 issues |
| 7 | Exposure-log entry | **Pass** |

The archived-deals entry was recognized and accepted: type 5, comment
exactly `Archived deals`, all four amounts `0.0`. The symbol specification
was unchanged (3 digits, tick 0.001, tick value 0.1).

**Status: 6 of 7 met. Criterion 4 is CONDITIONAL, pending a recorded
operator decision.**

## Stage B: scoped conditional acceptance (operator decision)

**Decision:** Accepted with conditions, for the limited purpose of
evaluating readiness for a single, manually executed 0.01-lot XAUUSD demo
experiment.

**Evidence:** The 22 November 2026 baseline (`demo-baseline-2.json`, SHA-256
`0dc6e9c4f67f24026893bbf5d45eb1f5ba0240572acba84e81e8d5ed5183d95f`) met six
of seven acceptance criteria. Opening equity remains `CONDITIONAL` because
the MT5 history contains an "Archived deals" correction with zero monetary
amounts.

**Rationale:** The available ledger reconciles to the reported USD 3,000
balance, no trading deals have been reported, and the correction has no
recorded monetary effect. Historical completeness nevertheless cannot be
established solely from the MT5 ledger.

**Restrictions:**

- Do not change `CONDITIONAL` to `SUPPORTED`.
- Do not modify the general opening-equity acceptance criterion.
- Do not apply this exception to other accounts, dates or experiments.
- Do not use this exception to establish verified historical equity or to
  authorize automated trading.
- Stage C requires separate operator approval and fresh pre-trade checks.

| Item | Decision |
| --- | --- |
| Stage B, 22 November baseline | Accepted with conditions |
| Opening equity status | Remains `CONDITIONAL` |
| Historical ledger completeness | Not established |
| Other accounts or baseline dates | Not covered |
| General Stage B criterion 4 | Unchanged |
| Stage C manual trade | **Not approved** |
| Automated demo and live trading | **NO-GO** |

**Authorization record:**

| Role | Record | Date (UTC) |
| --- | --- | --- |
| Technical reviewer | Recommended this scoped exception (wording above) | 2026-11-22 |
| Operator | Jackton Otieno. Acceptance recorded on the operator's instruction to record this decision. | 2026-11-22 |

Both earlier results stay as recorded: the first baseline (6/7, criterion 4
`UNRESOLVED`) and the re-run (6/7, criterion 4 `CONDITIONAL`).

**How a trade-day check relates to this exception.** The exception covers
only this baseline. A read on the trade day will again show the same
archived entry, so it does not re-open criterion 4. Instead it is compared
with this accepted baseline by `tools.check_pretrade_611`. It passes only
if nothing has changed: the same account, the same deals, the same single
accepted archived-deals entry, no new conditions or reasons, no exposure,
feasible stops, and a fresh read. See Stage C in
[manual-demo-trades.md](manual-demo-trades.md).

## New findings from the specification

The `XAUUSD` specification on this account **differs from the Phase 6.8.1
snapshot of 17 Nov**, which was taken before this Pro demo was opened on 18
Nov:

| Field | 6.8.1 snapshot (17 Nov) | This account (22 Nov) |
| --- | --- | --- |
| Digits, point, tick size | 2, 0.01, 0.01 | **3, 0.001, 0.001** |
| `trade_tick_value` | 0.1 | 0.1 |
| Calculation mode | 4 | 0 |
| Volume maximum | 100 | 200 |
| Spread | 0.23 (one quote) | **0.168** (floating) |

What this means:

- **The 10× tick-value conflict does not occur here.** With a 0.001 tick and
  100 oz, one tick is worth 0.001 × 100 = USD 0.1 per lot, exactly the
  reported `trade_tick_value`. This is consistent with the Phase 6.11
  hypothesis. Booked deals are still needed to confirm it. The earlier
  calculator probes describe the previous specification, not this account.
- **Sub-cent P/L is now possible.** One 0.001 move at 0.01 lot is USD
  0.001. Cent rounding of booked P/L is a live question on this account,
  and the stage C trade can test it.
- **The spread matches the archive.** 0.168 equals the median of the
  Exness public Pro archive for October 2026.
- **Swap affects stage F.** Swap mode 1 (points): long −431.6 points and
  short 0, with the triple charge on Wednesday. That is about −USD 0.43 per
  night for a 0.01-lot BUY, and about −USD 1.29 on Wednesday. Trade 11 (stop
  4.50) could therefore lose about USD 5.79, above its USD 5 cap. Stage F is
  deferred, and its limits must be revised before it is considered.

## Next step

1. Re-run Stage B with a new output file, for example
   `reports\phase_6_11\demo-baseline-2.json`. The result should be
   `CONDITIONAL`, with the archived-deals entry listed.
2. Decide whether a `CONDITIONAL` baseline may count for criterion 4. Record
   that decision either way.

Stage C stays closed until criterion 4 is met (or its acceptance is
recorded) and Stage C is approved separately.
