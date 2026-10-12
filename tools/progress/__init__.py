"""Progress tooling package: fragments, lint, render, ids and migration.

CAPABILITIES:
  CAP-PROGRESS-000: marks tools/progress as a package
    [tests: test_B1_status_fragment_fields, test_B1_blocker_labelled_lines_and_free_text,
    test_B1_decision_cannot_do_answers, test_B1_debt_fragment_fields, test_B1_ledger_fragment_fields,
    test_B1_missing_folders_are_empty, test_B1_unknown_fragment_file_is_ignored,
    test_B1_iteration_over_directories_is_sorted, test_E2_windows_line_endings_and_trailing_space_after_key,
    test_E6_parse_error_names_path_and_line, test_E6_key_without_value_is_a_parse_error,
    test_E6_labelled_line_before_marker_is_a_parse_error, test_fragment_error_attributes,
    test_module_public_api_is_exported]
INPUTS AND OUTPUTS: none; importing has no side effects.
CONTRACTS: none.
INVARIANTS:
  - Importing this package has no side effects.
NOT IN SCOPE:
  - Command line behaviour; see tools/progress/__main__.py.
CHANGE LOG:
  2026-10-12 WP-1.0 WO-1.0-04 step 1 created.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not a file (gate E3).
"""
from __future__ import annotations

__all__: list[str] = []
