# XAU/USD source comparison

Reviewed 19 November 2026, Africa/Nairobi.

| Source | Availability and instrument | Time and quote semantics | Cost, rights and limits |
| --- | --- | --- | --- |
| Exness public tick archive | Exness KE offers an indicative bid/ask ZIP selector. Exact XAUUSD is listed separately from XAUUSDm. Group documentation describes account-variant routing to MT4 Real 1, 3 or 9 and says the server cannot be chosen. | CSV contains symbol, timestamp, bid and ask. The reviewed archive documentation leaves the timestamp zone, encoding and precision unresolved. | Public selector and Personal Area routes are documented. No data purchase was made. Confirm reuse rights, selectable dates, corrections and coverage before ingest. Published archive provenance does not match the selected MT5 demo. |
| Exness MT5 demo history | Exact non-custom XAUUSD on ExnessKE-MT5Trial9 ending 9498. The Phase 6.9.4.1 archive contains a recent bounded tick response. Current probe outcomes are in the quality report. | MT5 documents bid, ask, last, volume and flags and general UTC conventions. The selected server's effective-dated raw-label mapping, request semantics and completeness remain unresolved. | Uses the connected demo and installed MT5. No data subscription was purchased. Verify retention, reuse and historical applicability with Exness. Request failures alone convey no interval coverage. |
| Dukascopy | Own XAU/USD gold feed. Free historical quote export is documented. The sampled public hourly endpoint returned HTTP 429. | Historical best bid/ask and their quoted sizes are documented. Dukascopy documents UTC millisecond offsets and scaling for its daily BI5 archive. The legacy hourly decoder was tested on synthetic input. Live verification of that variant is pending. | Free web export and separate requester-pays S3 access. No requester-pays access was used. Website terms restrict use and redistribution. Confirm specific data rights for long-term, shared or commercial storage. |
| HistData | Lists XAU/USD and an October 2026 Generic ASCII tick ZIP on the free website. Exact local audit scope is in the manifest. | Explicitly documents UTC−05:00 year-round, with no DST, and millisecond tick labels with Bid and Ask. M1 bars use Bid. Volume is unsupported for research purposes. | Free web downloads and optional paid access or delivery. The provider disclaims guarantees and supplies gap reports. Redistribution and commercial terms were not verified. Underlying execution venue and Exness equivalence are unverified. |

[Exness KE archive](https://www.exness.ke/tick-history/) ·
[Exness archive schema and routing](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history) ·
[MetaQuotes tick API](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py) ·
[Dukascopy historical quote export](https://www.dukascopy.com/swiss/english/marketwatch/historical/) ·
[Dukascopy historical storage and decoder reference](https://wiki.dukascopy.com/en/development/data-export/) ·
[Dukascopy terms](https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/) ·
[HistData FAQ](https://www.histdata.com/f-a-q/) ·
[HistData format](https://www.histdata.com/f-a-q/data-files-detailed-specification/) ·
[HistData optional paid access](https://www.histdata.com/download-by-ftp/)

For a three-to-five-year dataset, verify the first and last available XAU/USD
chunks and an inventory of all expected intermediate chunks before a bulk
download. Pilot representative dates around holidays, DST, daily breaks and
high-spread intervals. Record missing and revised payloads independently.
Cross-provider comparisons can help diagnose differences in quotes or coverage.
They cannot establish what this Exness account could have executed.
