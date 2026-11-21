# Unsent support inquiry for Exness technical support or MetaQuotes

Could you provide the documented monetary normalization rule for MT5 Python order_calc_profit on Exness (KE) Limited USD demo, server ExnessKE-MT5Trial9, exact XAUUSD, terminal build 6324 and Python package 5.0.6231? The account reported two currency digits, Forex calculation mode, 100 troy ounces per lot and tick size 0.001. All examples are hypothetical calculator calls.

For BUY 0.01 lots from 3788.548 to 3788.554, the exact price-difference formula yields USD +0.006 and the calculator returned USD 0.00. For the same entry and volume with exit 3788.542 it returned USD −0.01 against USD −0.006. BUY 0.02 lots from 3788.548 to 3788.547 returned USD −0.01 against USD −0.002. Rounding each price × contract size × lots notional to cents with half-up ties before taking the signed difference matched the sampled calculator rows.

Can you confirm whether that operation order and tie rule are specified, and identify any separate minimum-cent, volume, calculation-mode, currency-conversion, server or build conditions? Please state whether this refers to the calculator, displayed P/L or booked deal P/L, and provide the relevant documentation or escalation channel. We are seeking a technical answer without order submission or disclosure of account credentials or identifiers.
