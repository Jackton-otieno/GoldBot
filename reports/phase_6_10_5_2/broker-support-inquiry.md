# Draft Exness support inquiry

Please confirm the policy and effective dates for XAUUSD on Exness (KE) Limited's ExnessKE-MT5Trial9 USD MT5 demo. We can confirm the account privately through your authenticated support channel.

- What clock and units do live quote seconds, milliseconds, Python history request bounds, returned ticks and bar labels use? Were there changes, and at which exact UTC instants?
- Can you provide effective-dated UTC quote and trade sessions, including close-only, holiday, DST and maintenance exceptions?
- Which fields and price stream build M1, M15 and H1 OHLC? Is there an account/server-matched archive, and what UTC dates, completeness guarantees, timestamp precision and corrections does it cover?
- What statement-day or rollover convention applies to this account? Is there authoritative timestamped opening equity for an explicitly specified UTC boundary, including floating P/L and cash movements?

Our latest guarded observations compared the nominal close implied by position one with position zero and the raw quote coordinates on M1, M15 and H1. Could you confirm when position one first becomes available after a nominal close, how the terminal handles bars with no ticks, and how bars spanning a daily break or a partial session are labeled? Please give the effective date, server scope and timestamp precision for the Python APIs, and clarify inclusive or exclusive range endpoints.

For the 1 November 2026 DST transition and holidays including Thanksgiving and Christmas, please provide separate UTC quote and trading intervals for this exact demo. Within each interval, specify whether quotes are distributed and whether opening, closing or modifying positions is permitted. Please identify the source of dated maintenance and exceptional-closure notices and how clients should resolve conflicts or later corrections.

For a separately specified GoldBot policy boundary, can you provide or identify authoritative timestamped account equity at that exact UTC instant and describe the treatment of floating P/L, pending postings, cash movements and any opening-quote conventions? Please distinguish statement dates and rollover from the proposed policy boundary.
