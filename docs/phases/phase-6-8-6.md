# Phase 6.8.6 prospective independent strategy validation

The offline framework implements registration manifest construction,
independent intake attestation, eligibility and an evaluation gate for
M15 and H1. Registration binds the fixed UTC horizon, exposure universe,
baseline and evaluation inputs. Receipt verification is supplied by an
independent integration. The gate checks the signed intake and payload
integrity before asking for both audited candidate ledgers. It uses
exact rational comparisons for PF, equity reconciliation and drawdown.

- [Draft protocol and read-only collection design](../../reports/validation_phase_6_8_6/draft-protocol.md)
- [Readiness and approvals](../../reports/validation_phase_6_8_6/readiness.md)
- [Reference freeze](../../reports/validation_phase_6_8_6/reference-freeze.json)
- [Original CSV and earlier report hashes](../../reports/validation_phase_6_8_6/preserved-before.sha256)

Run the offline tests from GoldBot using its existing virtual environment.

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover
```

The tests use synthetic receipts, source bytes and ledgers. There is no
active study. Phase 7 automated demo and verified historical execution
remain blocked.
