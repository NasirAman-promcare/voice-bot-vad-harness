CAP: CAP-DOC-016
Module: `docs/recording/SESSION_FORM.md`
Functions: field table
What it does: Session form: speaker ID (`ca-s___`), consent reference (`ca-c___`), device (make and model), room, noise source and accent group with exactly the guide's choice IDs, plus session date (UTC) and notes (D1); no field for a name or contact detail
Tests: `test_FR_0_8_03_session_form_has_every_field`, `test_FR_0_8_03_choices_equal_the_recording_guide_lists`, `test_FR_0_8_03_speaker_id_and_consent_reference_formats_match_the_guide`, `test_FR_0_8_03_asks_for_no_identifying_details`
Introduced by: WP-0.8 FR-0.8-03
Status: ACTIVE
