CAP: CAP-ENV-006
Module: `config/aqis_lab/harness_assets.json`
Functions: pins
What it does: Asset pins: corpus commit `1479626` and sha256, FireRedVAD commit and per-file sha256, TEN VAD commit, system packages, torch not installed (R2-3), platform Debian or Ubuntu on Linux x86_64 with its reasons (owner decision F16), licences of TEN VAD (with its additional conditions), the corpus sources and FireRedVAD
Tests: `test_FR_0_0_12_asset_pins_match_repository`, `test_FR_0_0_12_platform_pin_is_linux_x86_64`, `test_FR_0_0_12_platform_pin_is_debian_or_ubuntu`, `test_FR_0_0_12_asset_licences_recorded`, `test_FR_0_0_12_ten_vad_licence_states_all_conditions`
Introduced by: WP-0.0 FR-0.0-12
Status: ACTIVE
