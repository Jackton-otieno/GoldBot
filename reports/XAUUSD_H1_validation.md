# XAUUSD H1 data validation

Input `XAUUSD_H1.csv`  
SHA-256 `a0ec85476a9cf5b5186c69dfed2d65bb6ccd100e5a05044bf1c041d94ad32541`  
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

- First and last valid labels in file order: `1740704400` and `1794927600`
- Repeated labels (distinct / extra occurrences): 0 / 0
- Backward / equal adjacent pairs: 0 / 0
- Adjacent pairs with an unusable label: 0
- Nominal / shorter positive / longer differences: 9,553 / 0 / 446
- Positive differences off the 3,600-second grid: 0

| Adjacent label difference (seconds) | Pairs |
| ---: | ---: |
| 3,600 | 9,553 |
| 7,200 | 218 |
| 10,800 | 126 |
| 14,400 | 7 |
| 21,600 | 2 |
| 32,400 | 1 |
| 93,600 | 1 |
| 104,400 | 1 |
| 176,400 | 2 |
| 180,000 | 50 |
| 183,600 | 32 |
| 187,200 | 1 |
| 190,800 | 2 |
| 194,400 | 1 |
| 266,400 | 1 |
| 270,000 | 1 |

Ten largest gaps by raw label difference, with ties in file order.

| Seconds | Data row after gap | Previous raw label | Next raw label |
| ---: | ---: | ---: | ---: |
| 270,000 | 6,445 | `1775167200` | `1775437200` |
| 266,400 | 806 | `1744930800` | `1745197200` |
| 194,400 | 2,050 | `1751655600` | `1751850000` |
| 190,800 | 7,652 | `1781899200` | `1782090000` |
| 190,800 | 7,870 | `1783108800` | `1783299600` |
| 187,200 | 4,460 | `1764363600` | `1764550800` |
| 183,600 | 484 | `1743199200` | `1743382800` |
| 183,600 | 4,002 | `1761948000` | `1762131600` |
| 183,600 | 6,357 | `1774648800` | `1774832400` |
| 183,600 | 6,555 | `1775858400` | `1776042000` |

## OHLC price statistics

Finite positive observations per field.

- open: n=10,000, min=2833.45, median=4101.445, mean=4025.6465, max=5562.51, sample SD=606.418
- high: n=10,000, min=2847.71, median=4111.74, mean=4034.293, max=5598.03, sample SD=609.411
- low: n=10,000, min=2832.57, median=4090.72, mean=4016.6078, max=5554.77, sample SD=602.912
- close: n=10,000, min=2833.79, median=4102.095, mean=4025.8534, max=5562.51, sample SD=606.37

## Close-to-close returns and volatility

Simple returns in percent use consecutive CSV rows with finite positive closes. Pairs with unusable labels, backward or repeated labels, or shorter positive differences are excluded. Longer differences may span unequal amounts of elapsed time and are summarized separately. Volatility is the sample standard deviation in percentage points, without annualization.

- Nominal-interval pairs: n=9,553, min=-5.7148055, median=0.0026347424, mean=0.0011481798, max=2.5752923, sample SD=0.317149
- Longer-interval pairs: n=446, min=-3.1212777, median=0.033868077, mean=0.052773212, max=2.4987715, sample SD=0.466784
- Eligible pairs with a nonfinite computed return: 0
