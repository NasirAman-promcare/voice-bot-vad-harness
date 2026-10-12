CAP: CAP-ENV-004
Module: `requirements/aqis_lab/harness-extras.txt`
Functions: lock from `harness-extras.in`; `harness-vcs.txt`
What it does: Hash-pinned harness extras (pytest, pytest-asyncio, opuslib) and the TEN VAD commit pin kept in `harness-vcs.txt` (BLK-004 option 1)
Tests: `test_FR_0_0_12_harness_extras_lock_is_hash_pinned`, `test_FR_0_0_12_asset_pins_match_repository`
Introduced by: WP-0.0 FR-0.0-12
Status: ACTIVE
