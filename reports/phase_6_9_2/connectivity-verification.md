# Phase 6.9.2 strict read-only connectivity

**Passed on 18 November 2026 at 16:42 EAT.** The running executable at `C:\Program Files\MetaTrader 5\terminal64.exe` matched the MT5 data-directory installation marker. The latest local authorization in that installation's journal identified ExnessKE-MT5Trial9 and the account ending 9498. The full local account reference was matched against MT5 in memory.

The pinned MT5 attachment confirmed the same installation path, connected demo mode, exact server and account, Exness (KE) Limited, USD 3,000 balance, 1:100 leverage and the exact non-custom XAUUSD symbol. Terminal build was 6324. Algo Trading was disabled when checked. The verifier supplied no credentials, performed no account switch or order submission, and shut down its Python connection afterward.

The Exness Personal Area and the Pro account classification were unavailable for independent verification. There was one running terminal on the selected path. Its journal also contains earlier MetaQuotes activity, so the exact active account check is required on every verification.

[Sanitized connectivity evidence](connectivity.json) · [Earlier offline verification](verification.md) · [Phase 6.9.3 results](../phase_6_9_3/verification.md)
