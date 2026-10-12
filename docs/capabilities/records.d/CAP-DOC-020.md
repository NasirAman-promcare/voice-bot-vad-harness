CAP: CAP-DOC-020
Module: `docs/progress/DEBT.md`
Functions: rows with a phase 0 target
What it does: Every debt row whose target is a phase 0 WP is CLOSED; a row moved to a later WP names that WP first in its Target cell and cites an approval on `main` that names the row (or its finding) and that WP; every approval a status cites exists (WP-0.9 must-catch 2)
Tests: `test_FR_0_9_01_no_open_debt_row_targets_phase_0`, `test_FR_0_9_01_debt_check_reports_open_or_unapproved_rows`, `test_FR_0_9_01_pinned_phase0_debt_ids_are_the_phase0_rows_before_wp09`, `test_FR_0_9_01_debt_check_covers_every_pinned_row`, `test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line`
Introduced by: WP-0.9 FR-0.9-01
Status: ACTIVE
