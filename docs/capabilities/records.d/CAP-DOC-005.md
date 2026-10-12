CAP: CAP-DOC-005
Module: `docs/contracts/NORMALISATION.md`
Functions: normalisers, steps, filler list, variants, surprising behaviours, examples table, versioning and change policy
What it does: Normalisation document: every row of its examples table (at least 30, each FR-0.3-02 category at least 3 times) is a test for both variants, and its filler list is the list the normaliser removes
Tests: `test_FR_0_3_02_documented_example`, `test_FR_0_3_02_at_least_30_examples_cover_every_category`, `test_FR_0_3_02_parser_reads_every_table_row`, `test_FR_0_3_03_documented_filler_list_matches_normaliser`
Introduced by: WP-0.3 FR-0.3-02
Status: ACTIVE
