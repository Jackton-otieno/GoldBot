# XAUUSD M15 data validation

Input `XAUUSD_M15.csv`  
SHA-256 `a8611beccee72e10e8774a299b2fd1752521d04c755543d87f187d36b9ab986e`  
CSV data rows **10,000** of 10,000 expected  
Rows with unexpected field count **0**

## Field and OHLC checks

| Field | Missing or blank | Nonfinite | Invalid type or domain |
| --- | ---: | ---: | ---: |
| mt5_time_epoch | 0 | 0 | 0 |
| open | 0 | 0 | 0 |
| high | 0 | 0 | 0 |
| low | 0 | 0 | 0 |
| close | 0 | 0 | 0 |
| tick_volume | 0 | 0 | 0 |
| spread | 0 | 0 | 0 |
| real_volume | 0 | 0 | 0 |

- Rows with a nonpositive OHLC price: 0
- Rows violating low ≤ open/close ≤ high: 0
- Rows with insufficient finite prices for the OHLC check: 0

## Raw server-clock labels

The integer `mt5_time_epoch` values are treated as raw server-clock labels. The checks use original file order and arithmetic differences between neighboring labels. The server offset and DST behavior are unverified. Differences can reflect clock shifts, session breaks, missing observations, or other causes. The two timeframes are analyzed independently.

- First and last valid labels in file order: `1781128800` and `1794930300`
- Repeated labels (distinct / extra occurrences): 0 / 0
- Backward / equal adjacent pairs: 0 / 0
- Adjacent pairs with an unusable label: 0
- Nominal / shorter positive / longer differences: 9,885 / 0 / 114
- Positive differences off the 900-second grid: 0

| Adjacent label difference (seconds) | Pairs |
| ---: | ---: |
| 900 | 9,885 |
| 4,500 | 4 |
| 8,100 | 86 |
| 13,500 | 1 |
| 177,300 | 1 |
| 180,900 | 20 |
| 190,800 | 2 |

Ten largest gaps by raw label difference, with ties in file order.

| Seconds | Data row after gap | Previous raw label | Next raw label |
| ---: | ---: | ---: | ---: |
| 190,800 | 610 | `1781899200` | `1782090000` |
| 190,800 | 1,479 | `1783108800` | `1783299600` |
| 180,900 | 181 | `1781304300` | `1781485200` |
| 180,900 | 1,050 | `1782513900` | `1782694800` |
| 180,900 | 1,919 | `1783723500` | `1783904400` |
| 180,900 | 2,359 | `1784328300` | `1784509200` |
| 180,900 | 2,799 | `1784933100` | `1785114000` |
| 180,900 | 3,239 | `1785537900` | `1785718800` |
| 180,900 | 3,679 | `1786142700` | `1786323600` |
| 180,900 | 4,119 | `1786747500` | `1786928400` |

## OHLC price statistics

Finite positive observations per field.

- open: n=10,000, min=3837.28, median=4148.925, mean=4192.2792, max=4693.62, sample SD=177.837
- high: n=10,000, min=3850.37, median=4152.965, mean=4196.6111, max=4696.73, sample SD=178.007
- low: n=10,000, min=3832.35, median=4144.565, mean=4187.9253, max=4683.93, sample SD=177.661
- close: n=10,000, min=3837.09, median=4149.15, mean=4192.3562, max=4693.55, sample SD=177.882

## Close-to-close returns and volatility

Simple returns in percent use consecutive CSV rows with finite positive closes. Pairs with unusable labels, backward or repeated labels, or shorter positive differences are excluded. Longer differences may span unequal amounts of elapsed time and are summarized separately. Volatility is the sample standard deviation in percentage points, without annualization.

- Nominal-interval pairs: n=9,885, min=-2.1781419, median=-0.0019658145, mean=-0.00069508193, max=1.6570522, sample SD=0.147847
- Longer-interval pairs: n=114, min=-0.66789178, median=-0.011127959, mean=0.017690404, max=2.1034357, sample SD=0.306034
- Eligible pairs with a nonfinite computed return: 0
