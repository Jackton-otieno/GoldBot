# Consolidated Exness technical inquiry — unsent

We are reviewing XAUUSD data and execution specifications for an Exness
(KE) Limited USD MT5 demo on ExnessKE-MT5Trial9. We can verify the exact
account through your authenticated support channel. Please distinguish this
demo from any live or other account variant, and include authoritative
references, effective UTC dates, version and server scope for each answer.

1. **Account and symbol.** Please confirm the exact product variant,
   execution mode, symbol identity, base/profit/margin currencies, contract
   size, price tick and tick value, price digits, minimum and step volume,
   and stop and freeze levels. Identify limits that vary with equity,
   session, news or account status.
2. **Monetary precision.** Please document the calculation and booking rule
   for BUY and SELL, including sub-cent gains and losses, half-cent ties,
   minimum fees, commission posting, partial closes, FX conversion and
   balance postings. For example, a read-only calculator returned USD 0.00
   for a theoretical USD +0.006 and USD −0.01 for a theoretical USD −0.006
   at 0.01 lot. The sample fit separate cent-rounded entry and exit
   notionals. Please confirm whether that reflects the specification and
   distinguish the MT5 Python calculator estimate, display rounding,
   gross deal P/L and booked net P/L.
3. **Time and bars.** Please document live quote seconds and milliseconds,
   Python historical bounds and return labels, epoch encoding, range
   inclusivity, and dated offset transitions. Confirm the quote basis for
   M1/M15/H1 candles, when a nominal close becomes observable at position
   one, and how tickless, partial and session-spanning bars are labeled.
4. **Sessions and exceptional periods.** Please supply separate account-scoped
   UTC quote and trade intervals including opening, closing and
   modification permissions, close-only periods, weekly breaks, DST,
   holidays, maintenance and exceptional closures. Include how to obtain
   past versions, revisions and the authoritative calendar.
5. **Historical quote provenance.** Is there an account/server-matched raw
   bid/ask archive? Please specify historical depth, tick precision,
   completeness, quote heartbeat, treatment of gaps, revisions and data
   retention, permitted local research and redistribution rights, and
   differences from the indicative public MT4 real-server files. Please
   identify supported bounded retrieval methods and known MT5 API limits.
6. **Trading economics.** Please provide dated commission and spread
   coverage, long and short swap rates and units, swap-free status,
   rollover and triple-swap exceptions, financing and payment costs, FX
   conversion, overnight margin, leverage and HMR tiers, and margin-call
   and stop-out rules. Please document execution and slippage policy,
   requotes, trigger side, gaps, and differences between demo and live.
7. **Statement dates and equity.** Please distinguish broker statement and
   rollover dates from a separately agreed policy-day boundary. Can you
   provide an independently verifiable account-equity record at an exact
   UTC boundary, including floating P/L, fees, swap and cash movements?

We are requesting written specifications and sanitized examples. Please
route platform-specific issues to the appropriate technical team if
needed. No trading, account change, or payment is requested.
