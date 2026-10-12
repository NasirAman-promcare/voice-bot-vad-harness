CAP: CAP-DOC-002
Module: `docs/contracts/EVENT_LOG.md`
Functions: `EVENT_LOG.md`, `RUN_CARD.md`, `PACK_MANIFEST.md` (field tables, rules across fields, validating, versioning and change policy); a Module cell names one file, so `RUN_CARD.md` and `PACK_MANIFEST.md` also have their own rows, CAP-DOC-003 and CAP-DOC-004
What it does: Contract documents whose field tables list exactly the fields of the three v1 schemas (payload fields per event type), plus the rules across fields and the change policy
Tests: `test_FR_0_2_07_documents_and_schemas_list_same_fields`, `test_FR_0_2_07_comparison_detects_missing_and_extra_fields`, `test_FR_0_2_06_documents_describe_change_policy`
Introduced by: WP-0.2 FR-0.2-07
Status: ACTIVE
