Hello,

I am validating XAUUSD timestamps on the MetaQuotes-Demo server using the
MetaTrader 5 Python integration. Could you confirm the timestamp convention
for this specific server and symbol?

- Are the raw integers from `symbol_info_tick().time` and `time_msc`,
  `copy_ticks_from` / `copy_ticks_range`, and `copy_rates_from_pos` /
  `copy_rates_range` Unix timestamps in UTC, or do they encode server wall
  time? What input convention applies to integer and aware datetime request
  bounds, and are the bounds inclusive?
- If the convention uses server wall time, please provide the exact UTC
  transition instants and offsets before and after every transition in
  2025 and 2026, together with any historical exceptions or server migrations.
  How are skipped and repeated local times handled in the returned history?
- Please share the XAUUSD quote-session schedule, daily breaks, holidays,
  and weekend reopening changes for those periods, with time zone and
  effective dates. Does the first M1 bar represent the first quote minute,
  and what history coverage should this demo terminal expose?
- In three connected sample runs the current quote retained raw seconds
  1794956399 and milliseconds 1794956399935, with bid 3847.41 and ask
  3847.64. Can you confirm the actual UTC event time and expected behavior
  of the terminal cache and historical tick API during closed sessions or
 feed interruptions? A stamped UTC example covering both APIs would help.

Thank you.
