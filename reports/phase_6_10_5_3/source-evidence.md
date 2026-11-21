# Historical source evidence

Sources reviewed on 19 November 2026, Africa/Nairobi. Provider descriptions
are separated from retrieval and data observations.

## Exness public archive

The KE page offers an instrument/period ZIP selector, names XAUUSD and
XAUUSDm as distinct symbols, and describes the quotes as indicative.
Group help describes the CSV layout, current-month daily downloads,
monthly or annual historical ZIPs and MT4 real-server routing. The
selector was available as a published interface. No public ZIP was obtained,
so available date endpoints, file-level UTC semantics and completeness
remain unverified. The website's copy notice does not establish permission
to redistribute the dataset.
[KE archive](https://www.exness.ke/tick-history/) ·
[Group help](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history)

## Exact Exness MT5 demo

The local opt-in pin and prior independent journal record matched. The
verified running installation reported build 6324 and the Exness KE USD
demo ending 9498 on ExnessKE-MT5Trial9. The guarded read queried non-custom
XAUUSD at raw-second anchors 1668686400 and 1794916800, with a 256-record
limit at each. Both calls returned MT5 error −1 and no rows. The numeric
anchors were chosen roughly four years apart. They do not assert actual UTC
coverage. The preserved new artifact is the raw diagnostic response.

The Phase 6.9.4.1 artifact contains 312 ticks inside a sampled raw minute
starting at 1795011300. The existing MT5 validator found no structural
errors. The sequence had two additional rows sharing a timestamp and zero
exact repeated records. Its largest observed raw intertick spacing was
1,156 ms. The earlier bid-derived OHLC comparison matched the terminal's
M1 bar. Phase 6.10.5.2 provides a conditional recent UTC check. It leaves
archive mapping, chart basis across the target interval and completeness
unverified. The sample remains a raw-coordinate diagnostic.
[New raw diagnostic](../../historical_data/phase_6_10_5_3/exness-mt5/xauusd-raw-ticks.json) ·
[Prior capture](../phase_6_9_4_1/diagnostic.json) ·
[Timestamp phase](../phase_6_10_5_2/timestamp-verification.json)

## Dukascopy and HistData

Dukascopy's public legacy hourly XAU/USD endpoint returned HTTP 429 on
the 2022 target. The second planned hour was skipped. The provider's
documented daily BI5 layout supports the field interpretation, but its
daily time offset is distinct from the tested hourly convention.
Requester-pays access was not used. [Dukascopy archive reference](https://wiki.dukascopy.com/en/development/data-export/)

HistData's October 2026 XAU/USD Generic ASCII listing returned HTTP 200 and
named the expected ZIP. The first download did not complete and was stopped.
The bounded retry reached its 90-second body-transfer deadline. No complete
ZIP was preserved. The documented fixed UTC−05:00 conversion and tick fields
were tested with synthetic cases. A listing does not establish actual
record coverage or provider reuse rights.
[HistData listing](https://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/xauusd/2026/10) ·
[Provider format](https://www.histdata.com/f-a-q/data-files-detailed-specification/)
