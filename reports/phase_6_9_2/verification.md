# Offline verification

All 173 offline tests passed in 38.527 seconds with OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1. The eight new tests use local fixtures and mocked MT5 responses. The Phase 6.7 regression regenerated the report in a temporary project copy and matched the deployed tree byte for byte, including all 11 charts.

The before and after SHA-256 inventories matched across all 62 existing files under reports and data, including both raw CSVs and all 60 earlier report files. All 58 entries in the Phase 6.9.1 preservation manifest also matched. The provenance test excludes the new report directory from the frozen Phase 6.7 input set.

[Before inventory](preserved-before.sha256)

No MT5 Python attachment was attempted. The check requires the dedicated terminal process to be running before calling the pinned MetaTrader initializer. The MetaTrader API can launch that executable if it closes between the process check and initialization, so keep the selected demo terminal open throughout verification. The returned terminal and account identity must match before the symbol read, and identity is checked again after it. [MetaTrader initialization reference](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py)
