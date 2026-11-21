# Phase 6.10.1 verification

- Both Phase 6.8.5 JSON archives reproduced byte for byte. The two isolated Phase 6.10.1 audit runs also matched byte for byte. Audit SHA-256 is 635882d9e2055c8c5c9ed7aef88d1302e34b17867055b57abebf32c53f10da70. [Audit](audit.json)
- All 197 offline tests passed with OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1, including two tests for exclusion of exit-bar extremes. [Full regression](offline-regression.txt)
- All 13 Phase 6.7 files regenerated in scratch and matched the saved relative paths and bytes by SHA-256. [Regenerated inventory](phase-6-7-regenerated.sha256)
- All 105 earlier report files and both original CSVs matched the live pre-installation and isolated-copy hashes. The live files also matched all 96 Phase 6.9.6 pre-change commitments. [Before](preserved-before.sha256) · [After](preserved-after.sha256)
- The source assessment retains NO-GO and the audit retains RESEARCH classification. [Readiness assessment](../phase_6_9_6/assessment.json)
