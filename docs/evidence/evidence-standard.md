# GoldBot research evidence standard (proposed)

**Status: PROPOSED, not adopted.** It takes effect only when the operator
completes the adoption record at the end and commits it. Until then the
Phase 6.10.7 criteria apply. GoldBot remains **NO-GO** under Phase 6.9.6.

## What this standard governs

GoldBot has three separate kinds of decision. This standard covers only the
first.

| Decision | Governed by | Changed by this standard? |
| --- | --- | --- |
| **Research evidence acceptance.** Accepting a measurement as an internal research fact, with stated scope. | This standard, once adopted | Yes |
| **Prospective protocol approval and registration** | Phase 6.10.6, including its independent-approval requirement | **No.** The registration procedure below adds evidence. Replacing independent approval would need its own explicit, dated decision record. |
| **Automated demo and live trading authorization** | Phase 6.9.6 | **No** |

Adopting this standard closes no existing blocker. Each blocker closes only
through the closure rule below, in its own dated review.

Work runs on the [personal research track](research-track.md). Its results
are labelled **self-tested, not independently validated**, and everything
examined is recorded as exposed in the hash-chained exposure log.

## Evidence tiers

| Tier | Kind | Examples | Caveats |
| --- | --- | --- | --- |
| **A** | The broker's own ledger for this account | MT5 deal and order history, account balance and equity | Describes recorded transactions in the sampled period only. |
| **B** | Data or specifications published by the broker | Exness public tick archive, terminal symbol specification and sessions, published notices | Applies only to the product, server and dates the source covers. Record its effective date or retrieval date. |
| **C** | Agreement between two sources | Archive candles (UTC) matched to MT5 candle exports (server labels) | State whether the sources share an origin. Agreement between two outputs of the same broker is weaker than agreement with an outside reference. |
| **D** | An operator policy decision | Risk-day boundary, research scope | Selects internal rules. Never evidence of broker behavior. |

A written broker answer, if one arrives, is Tier B for its stated scope.

## Closure rule

A measurement is accepted, and a dependency may be marked closed, only when
**all** of the following hold:

1. **Reproducible.** A script in this repository produces the evidence from
   recorded inputs.
2. **Pinned.** Every input has a recorded SHA-256 and source (a URL with its
   retrieval time and Last-Modified header, or a tool command with its
   output file).
3. **Sufficient tier.** The evidence meets the tier the dependency requires.
4. **Scoped.** An accepted-conclusion record, using the template below,
   states its scope, effective period, sample, limitations and
   re-verification triggers.
5. **Reviewed after a delay.** The operator commits a dated review in
   `docs/evidence/`, at least **24 hours** after the evidence was produced,
   noting what was checked and what would disconfirm it.
6. **Nothing discarded.** Contradictory, failed or inconclusive results are
   kept and reported, never overwritten.

### Accepted-conclusion record (template)

```
Conclusion:
Evidence tier and sources (paths, SHA-256):
Scope: account / server / symbol / account type
Effective period observed (UTC):
Sample: size and composition
Not established (limitations):
Re-verification triggers and expiry:
Contradicting evidence considered:
Review date (UTC), at least 24 h after the evidence:
```

Typical re-verification triggers are a change to the contract
specification, a server or account change, a broker notice, a
daylight-saving transition not yet observed, or a set expiry such as
quarterly.

## Session evidence: four separate classes

A finding in one class is not evidence for another.

| Class | Acceptable evidence | Not acceptable |
| --- | --- | --- |
| Quote availability | Archive or terminal ticks, with gap analysis | — |
| Trade permissions (open, modify, close) | Terminal trade sessions and symbol trade mode (Tier B); observed order acceptance (Tier A) | Archive quote gaps |
| Close-only or restricted periods | Broker notices (Tier B); observed rejections with their codes (Tier A) | Archive quote gaps; the absence of a notice |
| Holidays and exceptional closures | Broker notices (Tier B); observed quote gaps, labeled as quote evidence only | Calendar assumptions |

## Prospective registration evidence

This procedure documents **what was committed and when**. It does not by
itself prove that later data went unseen. It does not replace the Phase
6.10.6 independent-approval requirement unless a separate decision says so.

1. **Registration bundle.** Commit the protocol, frozen strategy and
   evaluator hashes, cost and execution rules, scoring, stopping and
   violation rules, the full cohort list, and the exposure inventory.
2. **Exposure inventory.** Start from the research-track exposure log
   (`docs/evidence/exposure-log.jsonl`) after its chain verifies. List every
   dataset and source accessed before registration. For each, give the source, UTC coverage envelope, SHA-256
   and access date. State that nothing inside the prospective window was
   accessed. Name the sources to be used during the window, and the
   manifest format each intake chunk will carry (URL, retrieval time,
   Last-Modified, SHA-256).
3. **Signed tag.** Create a signed annotated tag of the registration commit
   (GPG or SSH signing).
4. **Independent timestamps.** Obtain an
   [OpenTimestamps](https://opentimestamps.org/) proof and/or an RFC 3161
   timestamp from a public timestamp authority for the tag's commit hash.
   Both can be verified without trusting the repository host. Commit the
   proofs afterwards; they still verify the earlier hash.
5. **Protected remote.** Push to a remote whose rules prevent tag deletion
   and force-pushes. Mirroring to a second host is optional.
6. **Change control.** Registered files are never edited. Each amendment is
   a new dated document that references the registration and gives its
   reason, and it is reported with the results.
7. **Complete reporting.** Report every registered cohort, including
   failed, inconclusive and stopped ones, together with all amendments and
   deviations.
8. **Stated limitation.** For a solo operator, the claim that no later data
   was seen remains self-attested. Source-side manifests (archive SHA-256
   and Last-Modified) make it checkable, not independent.

## Risk day and opening equity

**Proposed internal policy, not adopted: the risk day starts at 00:00 UTC.**
UTC is fixed, while server midnight moves with EU daylight saving.

Opening equity at a boundary is **established** only by one of these:

- **Ledger reconstruction:** current balance minus every later deal, and
  only when the reader reports `opening_equity.status = SUPPORTED`.
  `CONDITIONAL`, for example when an Exness "Archived deals" correction is
  present, does not establish opening equity. That
  status requires that no position was open across the boundary, that
  position history in the window is complete, that no position was open at
  the read, and that credit is 0.
- **Boundary snapshot:** a terminal reading of balance, credit, equity and
  open positions, taken after the boundary and before the risk day's first
  entry. Identity must be verified at that attachment, and the reading
  stored with its time and SHA-256.

Otherwise opening equity is **UNRESOLVED**:

- **Positions open across the boundary.** Equity includes floating P/L at
  that moment. Ledger reconstruction cannot provide it, so only a boundary
  snapshot can.
- **Missing snapshot, disconnection or restart.** Nothing is inferred from a
  stale or earlier-session value. After a restart, identity and the ledger
  are read again before any value is used.
- **Credit, bonus or other non-deal adjustments** must be accounted for, or
  the status stays unresolved.

While opening equity is unresolved, the existing risk-day latches apply and
no new entries are permitted that day. These are requirements for any future
implementation. This standard implements nothing.

## Dependencies: candidate evidence after Phase 6.11

None of these is closed. "Candidate" means evidence exists that could
support closure after a scoped review.

| Dependency | Tier needed | Candidate evidence | Scope and limitations |
| --- | --- | --- | --- |
| broker_identity_and_product | B | None new. Needs an identity check at attachment plus a redacted Personal Area screenshot. | Open |
| utc_mapping_and_freshness | C | Archive vs MT5 candles give server label = UTC+3 until 25 Oct 2026 and UTC+2 after; UTC+2 until 29 Mar 2026 and UTC+3 after. Best match ≈ 0.13 vs 4–7 for the runner-up on every day. | Covers Mar and Oct 2026, H1 (and M15 for Oct). Both sources are Exness outputs. The archive's UTC labelling is corroborated by its daily break falling at 17:00 New York, not independently verified. Live-quote freshness is not covered. |
| quote_trade_sessions_and_exceptions | B | Archive quote gaps for Mar and Oct 2026 | **Quote availability only.** Trade permissions, close-only periods and holidays are unaddressed. US standard-time gaps were observed only on 2–6 Mar 2026. |
| historical_provenance_and_coverage | B | Mar and Oct 2026 archive months with manifests; every row passes the audit | Research use only. The archive feed differs from this demo's (close gaps: median 0.13–0.16, 90th percentile 0.28–0.35). Two months are not a research range. Reuse rights are not reviewed. |
| monetary_precision_and_booked_pnl | A | None yet. The [manual experiment](manual-demo-trades.md) is ready but not run. | Results will describe the tested trades only. |
| costs_margin_and_slippage | A, B | Pro-archive spread: median 0.168 (Oct 2026), 0.252 (Mar 2026) | Archive spread is not this demo's spread. Commission, swap, margin tiers and fills are unmeasured. |
| risk_day_and_opening_equity | D, A | Proposed policy and reader support | Policy not adopted. Not exercised. |
| minimum_volume_feasibility | A, B | — | Waits for cost inputs |
| prospective_registration_and_exposure | Phase 6.10.6 | — | Unchanged requirement. The procedure above adds evidence only. |
| profitability_not_demonstrated | Phase 6.10.6 | — | Unchanged. Earlier results are adverse. |
| phase7_operational_controls | Phase 6.9.6 | — | Unchanged |
| live_authorization | Phase 6.9.6 | — | Unchanged |

## Adoption record

Leave this blank to keep the standard proposed.

- Adopted by:
- Date (UTC):
- Amendments or exceptions:
- Explicitly not changed: Phase 6.10.6 prospective approval, the Phase 6.9.6
  gate, and the status of every existing blocker.
