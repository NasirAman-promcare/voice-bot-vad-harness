CAP: CAP-DOC-017
Module: `docs/fillers/FILLER_LIBRARY_v0.md`
Functions: risk levels, never-play contexts, fillers tables
What it does: Filler library v0: 20 fillers `fil-001` to `fil-020` across the blueprint's four risk levels, each with text, intended use, a risk level and at least one never-play context ID; the risk-level table equals the blueprint's ladder; every blueprint example is a filler at its level; the blueprint's three never-play rules are encoded (rule 1 on positive Level 2 fillers, rule 2 on every Level 3 filler, rule 3 on every Level 2 and 3 filler and never on Level 0 or 1); contexts not in the blueprint are marked "Drafted in WP-0.8 for owner review"
Tests: `test_FR_0_8_04_library_has_about_20_fillers`, `test_FR_0_8_04_risk_levels_are_the_blueprint_four_and_all_used`, `test_FR_0_8_04_every_filler_has_id_text_use_and_risk_level`, `test_FR_0_8_04_every_filler_has_a_never_play_context`, `test_FR_0_8_04_ids_and_texts_unique`, `test_FR_0_8_04_every_context_used_is_defined`, `test_FR_0_8_04_blueprint_examples_are_in_the_library_at_their_level`, `test_FR_0_8_04_blueprint_never_play_rules_are_encoded`, `test_FR_0_8_04_checks_detect_missing_level_or_context`, `test_FR_0_8_04_level_2_tone_is_explicit_and_rule_1_keys_on_it`
Introduced by: WP-0.8 FR-0.8-04
Status: ACTIVE
