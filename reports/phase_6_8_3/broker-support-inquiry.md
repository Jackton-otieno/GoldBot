# Unsent broker inquiry

Hello,

We are checking the market-hours and timestamp conventions for XAUUSD on
MetaQuotes-Demo. Could you confirm the following for this exact server
and symbol, or direct us to the authoritative specifications?

- The separate quote and trade calendars, including ordinary breaks,
  overnight spans and their assigned weekdays, holidays, early closes,
  and any restrictions such as close-only intervals. Please include
  effective dates and how dated changes supersede weekly hours.
- The clock used for each session endpoint, its offset from UTC, and the
  precise effective UTC instants for offset changes. If available, please
  include sample dated UTC intervals spanning a weekend and a DST change.
- Whether terminal Specification and the MQL5 quote and trade session
  functions include dated exceptions or only scheduled weekly hours, and
  what a failed lookup means.
- The convention for Python tick seconds and milliseconds and how to
  convert them to UTC on this server. A recent paired raw and UTC quote
  timestamp and any published delay or maintenance windows would help.
- The broker's swap posting and statement-day conventions, including
  changes over weekends and holidays, and whether an authoritative
  account-equity snapshot can be obtained at a separately specified
  UTC instant.

Thank you.
