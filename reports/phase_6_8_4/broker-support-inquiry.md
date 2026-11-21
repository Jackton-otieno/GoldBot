# Draft broker inquiry for XAUUSD historical execution data

Could you confirm the following for XAUUSD on MetaQuotes-Demo and the
applicable demo account group? The original GoldBot files use the raw
MT5 label ranges below. We have preserved the labels as returned.

- H1, 1740704400 through 1794927600, plus the final H1 bar.
- M15, 1781128800 through 1794930300, plus the final M15 bar.

Please provide the historical chart construction basis and export
semantics, archive availability and retention, demo feed identity,
the authoritative timestamp convention for bars and historical ticks,
and exact dated UTC offset transitions if applicable. Please explain
the integer request endpoint semantics, tie ordering, flag meanings,
and how to detect a partial, unsynchronized or unavailable archive.
If full tick exports are available, can you supply ordered bid/ask
records, archive coverage and published outages, with provenance for
each date range?

Can you provide effective intervals and the relevant account-group
terms for contract size, tick size and gain/loss tick values, price
and volume grids, commission, swap and rollover, margin and leverage,
profit and margin currencies, account currency and historical
conversion sources and rules? Please confirm any explicit zero fees
and identity conversions. Could you also clarify the observed current
tick values of 0.10 versus 1.00 implied by contract arithmetic and
demo calculator results?

Please supply dated quote and trade hours in UTC, including holidays,
maintenance and exceptional closures, and the broker rollover and
statement-day conventions. GoldBot will verify its own policy-day
boundaries separately. If any requested history is unavailable,
please state the earliest retained dates and the scope of the limitation.
