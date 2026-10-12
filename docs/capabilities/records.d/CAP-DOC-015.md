CAP: CAP-DOC-015
Module: `docs/recording/RECORDING_GUIDE.md`
Functions: about campaign A, speaker IDs and consent references, the 80 prompts, phone, rooms and background noise, accent groups, file naming, format, transfer, quality checks
What it does: Campaign A recording guide: the Build Plan's 7 prompt families and counts (80 in total) and its 22 speakers, about 30 minutes and own phones; the owner's BLK-014 answers (11 quiet-room and 11 everyday-noise speakers; one `ca-sNNN.tar.gz` per session to `MyDrive/AQIS_LAB/campaign_a/raw/`; original kept and converted to 16 kHz mono 16-bit PCM WAV; handheld 10-15 cm, no headset; the noise-source and accent-group lists; the quality-check thresholds); file names `<speaker-id>-<family-id>-<NN>.wav` valid and unique for all 1,760 recordings and clashing with no registry clip ID
Tests: `test_FR_0_8_02_guide_has_every_required_section`, `test_FR_0_8_02_prompt_families_total_80`, `test_FR_0_8_02_prompt_families_match_the_build_plan`, `test_FR_0_8_02_file_names_are_valid_and_unique`, `test_FR_0_8_02_delivered_format_is_the_working_format`, `test_FR_0_8_02_every_quality_check_has_a_pass_rule`, `test_FR_0_8_02_owner_values_appear_as_given`, `test_FR_0_8_02_choice_lists_equal_the_owner_lists`, `test_FR_0_8_02_guide_has_no_owner_blank_left`
Introduced by: WP-0.8 FR-0.8-02
Status: ACTIVE
