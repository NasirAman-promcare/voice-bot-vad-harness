CAP: CAP-ENV-008
Module: `requirements/aqis_lab/phase0-gpu.txt`
Functions: lock generated from `phase0-gpu.in`
What it does: Hash-pinned GPU extras for Colab (x86_64, Python 3.13): nemo_toolkit[asr] 3.0.0 and torch 2.14.0 from PyPI with their dependencies, compiled with the CPU lock as constraints so every shared pin equals phase0.txt; the `.in` records the regeneration command and the SHA-256 of the phase0.txt it was compiled against; `antlr4-python3-runtime` is its only source-only package (owner decisions, questions 2 to 5)
Tests: `test_FR_0_7_03_gpu_lock_is_hashed_and_layers_on_cpu_lock`, `test_FR_0_7_03_gpu_lock_header_binds_cpu_lock_sha256`, `test_FR_0_7_03_gpu_lock_has_x86_64_wheels_except_antlr4`, `test_FR_0_7_03_gpu_lock_installs_with_cpu_lock`
Introduced by: WP-0.7 FR-0.7-03
Status: ACTIVE
