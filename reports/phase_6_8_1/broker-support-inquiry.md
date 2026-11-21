# Draft broker support inquiry

Hello,

Could you confirm the current MT5 demo contract specification for XAUUSD?
In a read-only capture on 17 November 2026 at 22:20 UTC, MT5 Python 5.0.6231
and terminal build 6320 returned calculation mode 4 (CFDINDEX), contract size
100, point and tick size 0.01, and USD account, profit and margin currencies.
The generic, profit, and loss tick values were each 0.10.

At 0.10 lots and an open price of 3847.41, `order_calc_profit` returned USD
+1.00 and -1.00 for BUY exits of 3847.51 and 3847.31 respectively. SELL
returned the same magnitudes with the exits reversed. The CFDINDEX contract
formula gives the same values. The metadata would give USD +0.10 and -0.10
if the reported values are USD per tick per lot. The discrepancy repeated
across prices, volumes, directions and distances.

1. What are the exact currency, price increment and reference lot size
   for each of `trade_tick_value`, `trade_tick_value_profit` and
   `trade_tick_value_loss` on this demo symbol?
2. What tick value per 0.01 price increment at 1.00 lot should we expect on
   a USD account, separately for profit and loss? Can you reconcile the
   reported 0.10 with the calculator examples and confirm whether any
   symbol or server correction is required?
3. Can you confirm the current contract size and calculation mode and explain
   the margin settings (raw initial 0, maintenance 0, hedged 100, and
   larger-leg hedging enabled)? Is there a dated specification we can retain?

Thank you.
