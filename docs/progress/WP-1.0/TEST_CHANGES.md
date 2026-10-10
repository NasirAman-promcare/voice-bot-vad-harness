# TEST_CHANGES — WP-1.0

| File | Test functions | Kind (add-cases, helper-refactor, rename) | Why | Assertions before, after |
| --- | --- | --- | --- | --- |
| `tests/aqis_lab/test_aqis_phase0_memo.py` | `test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line` | add-cases | DEBT-034 (FR-1.0-11): adds the case `"- X{debt} moves to {wp}."` (not approved), with id `longer-debt-id-on-the-left`, to test the left boundary (look-behind) of `names_id`. The six existing cases and the test body are byte-identical. The edit is unlocked by `ALLOW-EDIT: tests/aqis_lab/test_aqis_phase0_memo.py` in `docs/approvals/WP-0.9.md` on `main` (DEC-1.0-02) | 1 assert statement, 6 cases → 1 assert statement, 7 cases |
