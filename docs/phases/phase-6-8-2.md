# GoldBot Phase 6.8.2 server time and DST verification

**Rejected for freshness and server-time conversion.** The XAUUSD demo quote
was static across the capture windows. The broker timestamp convention,
current quote-session state, and exact historical DST boundaries remain
unverified. Both diagnostics return exit code 1 while verification is
unresolved. Phase 6.8.3 is pending review.

## Current quote and host time

On 18 November 2026 at approximately 01:27–01:31 Africa/Nairobi, the
expected demo server passed the existing connection guard. Each capture
took 16 samples about two seconds apart, with host UTC and monotonic values
before and after each call and terminal connection status on both sides.
The quote retained raw seconds 1794956399, raw milliseconds 1794956399935,
bid 3847.41, and ask 3847.64. These raw seconds and prices also appear
in Phases 5.2 and 6.8.1.

The repeated quote is consistent with a cached or non-updating feed. The
terminal reported connected, but connection status alone cannot establish
the quote session was open or distinguish a normal session break from a
feed interruption or delay. Actual UTC quote age cannot be bounded without
a verified timestamp convention. Timestamp-only movement is recorded
separately from timestamp and bid/ask movement. Even advancing samples
require an independent mapping before they can establish freshness.

The [detailed quote capture](../../reports/phase_6_8_2/current-demo.json)
returned seven history ticks in that raw second. One matched both raw
timestamp fields and both prices. Its flags were 1030 versus 6 on the live
quote, so the full record did not match. One of the 16 most recent
M1 bars opened at raw seconds 1794956340, the same raw minute. These
comparisons corroborate the terminal's raw coordinates. They do not verify
an event time in UTC.

The clock check uses NIST TCP Daytime immediately before and after each
collection. It subtracts the published advance from each UTC time tag and
bounds the host correction using the entire transport bracket, a one-second
source allowance, and 0.1 seconds for wall versus monotonic sampling. The
two probes must agree, and the union of their bounds expanded by 0.1 seconds
must fit within ±2 seconds. The test assumes replies came from the named
NIST service, its healthy time codes followed its published protocol, and
there was no unobserved clock step between samples. TCP Daytime is
unauthenticated. No clock settings were changed.
[NIST Internet Time Service](https://www.nist.gov/pml/time-and-frequency-division/time-distribution/internet-time-service-its)

The [first capture](../../reports/phase_6_8_2/initial-demo.json) returned
two healthy time codes. The host UTC correction interval was
−2.240 to +1.672 seconds, which includes zero and exceeds the diagnostic
tolerance. The detailed quote capture had one healthy code and one empty
response, so it could not establish a two-sided check.
The [repeat capture](../../reports/phase_6_8_2/repeat-demo.json) passed
the host clock check with a correction interval of −1.254 to +1.693
seconds. The terminal quote stayed static through that capture as well.

## Historical DST checks

The [2025](../../reports/phase_6_8_2/dst-2025.json) and
[2026](../../reports/phase_6_8_2/dst-2026.json) reports query M1 history on
the same demo server in bounded, three-day raw-coordinate windows around
weeks where Chicago and Berlin DST differ, plus adjacent weeks. All eight
2025 windows and all five spring 2026 windows returned one bar each.
Three autumn 2026 windows contained a single qualifying gap.

| Weekend | First raw M1 after gap | Raw minus CME proxy (s) | Chicago DST | Berlin DST |
| --- | ---: | ---: | ---: | ---: |
| 2026-10-18 | 1792371600 | 10800 | 1 h | 1 h |
| 2026-10-25 | 1792972800 | 7200 | 1 h | 0 h |
| 2026-11-01 | 1793581200 | 7200 | 0 h | 0 h |

Subtracting the hypothesized DST shift from the proxy difference gives a
constant 7200 seconds for Berlin and a mix of 3600 and 7200 seconds for
Chicago. This fits the EU hypothesis for those three weekends **if** the
broker's first quoted minute coincided with the CME regular Sunday open.
That assumption is unverified. The broker-specific evidence consists of
terminal-returned ticks and M1 history. The CME futures session is a proxy
for comparison only. Broker quote hours, historical coverage and the first
quote within a bar can affect the result.
[CME metals product guide](https://www.cmegroup.com/trading/metals/files/metals-prod-guide-2022.pdf)

MetaQuotes' general Python reference describes UTC storage for tick and bar
open times. We did not obtain a server-specific statement explaining the raw
values, history request convention, or quote-session schedule. The data do
not locate exact UTC transition instants or establish a general offset.
The existing TimeManager continues to require independent server-specific
windows. No window or production offset was added.
[MetaQuotes Python tick history reference](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksfrom_py)

The [broker inquiry](../../reports/phase_6_8_2/broker-support-inquiry.md)
is unsent. It asks for the raw timestamp and request conventions, UTC
transition instants, historical sessions and coverage, and a UTC-stamped
quote example.

## Reproduce and verify

Run from PowerShell with the intended demo terminal already running and
signed in. Use distinct output paths to preserve the published captures.

```powershell
Set-Location D:\GoldBot
& .\.venv\Scripts\python.exe -B -m tools.diagnose_time --samples 16 --interval 2 --output .\quote-rerun.json
& .\.venv\Scripts\python.exe -B -m tools.verify_dst --year 2025 --output .\dst-2025-rerun.json
& .\.venv\Scripts\python.exe -B -m tools.verify_dst --year 2026 --output .\dst-2026-rerun.json
& .\.venv\Scripts\python.exe -B -m unittest discover
```

The diagnostics use the existing demo-only connection and expected-server
checks. The live diagnostic caps the sampling schedule at 120 seconds and
the supplemental requests at 128 ticks and 16 M1 bars. The historical
diagnostic caps each request to a three-day window. The reports omit account
identifiers, credentials and actual server strings. No order calls, trading
entry point, terminal setting changes, or historical execution were used.
The Phase 6.8.1 broker specification rejection and historical-execution
guard remain in force.

The offline suite ran 130 tests, including eight new regressions. Phase
6.7 regenerated byte for byte with its original provenance scope. Both
original CSVs and all 35 earlier report files, including the three Phase
6.8.1 files, matched the
[pre-change SHA-256 manifest](../../reports/phase_6_8_2/preserved-before.sha256).
