CAP: CAP-ENV-002
Module: `requirements/aqis_lab/phase0.txt`
Functions: lock generated from `phase0.in`
What it does: Hash-pinned, universal phase 0 CPU lock (pytest, jsonschema, pyyaml, whisper-normalizer 0.1.1, pyarrow, jiwer 4.0.0, soundfile, numpy, duckdb 1.5.6 (WP-0.6 FR-0.6-02), vosk 0.3.45 and webrtcvad-wheels 2.0.14 (WP-0.7), setuptools as the build tool of the approved source-only `srt`, packaging below 25 for the GPU extras (WP-0.7 question 3) and dependencies) with its regeneration command recorded
Tests: `test_FR_0_0_03_every_pin_has_hashes`, `test_FR_0_0_03_lock_generated_from_in_file`, `test_FR_0_0_03_regeneration_command_documented`, `test_FR_0_0_03_environment_matches_lock`, `test_FR_0_0_03_regeneration_is_reproducible`, `test_FR_0_0_03_lock_installable_with_plain_pip`, `test_FR_0_7_02_lock_pins_vosk_webrtcvad_and_the_srt_build_tool`
Introduced by: WP-0.0 FR-0.0-03
Status: ACTIVE
