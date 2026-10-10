# DEC-1.0-04 — How the generated registry maps headers to the gate's seven columns, and which modules are sources
Status: ACTIVE
WP: WP-1.0
Date: 2026-10-10
Spec basis: FR-1.0-03 ("The Lab Map, generated registry and impact selection exactly as WO-1.0-03 specifies; the registry is adopted with `--adopt-registry`, every legacy row accounted for"), `CHANGE_CONTROL.md` sections 1 and 2, and the owner's BLK-1.0-05 answer (option 1, capability records). WO-1.0-03 section 7 anticipates headers that differ from section 1 in a way that changes parsing.

Question: Measured on the branch (scratchpad script over every `.py` under `aqis_lab/`, `tools/`, `tests/aqis_lab/`):
- 25 test modules under `tests/aqis_lab/outsourcing/` repeat their tested module's capability ID in their own CAPABILITIES section, so E3 ("a capability listed in two modules is an error") would fail on the real tree.
- `tests/aqis_lab/fixtures/gate/non_utf8.py` is deliberately unparsable gate data, kept out of pytest by `collect_ignore = ["fixtures"]`; B9 would make every build exit non-zero.
- 112 legacy rows have headers; their tests agree with the registry for all 112, but 62 descriptions differ from the hand-written "What it does", and the header standard has no Functions field.
- Header descriptions contain `|` (for example `CAP-CONTRACTS-006`), and the audit gate splits cells on every `|`.
- 56 first change-log entries name a work order (`WO-1.0-10 created.`) rather than a WP.

Options:
1. Pin the mapping in WO-1.0-03 B12:
   - registry sources are modules under `aqis_lab/`, `tools/` and `kit-staging/`, the directories `CHANGE_CONTROL.md` section 1 names;
   - `tests/aqis_lab/fixtures/` is skipped as data;
   - Functions holds the module's public top-level names, generated;
   - What it does holds the header description;
   - `|` is written as `&#124;`;
   - the owning WP falls back from `WP-` to the `WO-` token.
2. Keep legacy prose for header rows: records for all 152 rows. That gives two sources of truth for 112 capabilities, and the header would no longer be what the registry says.
3. Edit the 25 test headers and the gate fixture. That touches gate data the gate's own tests rely on, and it would still leave the column questions open.

Choice: 1. The acceptance test `tests/aqis_lab/index/test_acceptance_wo_1_0_03.py` checks each pin. It also adopts a copy of the real registry and requires every legacy row back, the 40 non-code rows verbatim.

Why: `CHANGE_CONTROL.md` section 2 says the registry "is generated on `main` from module headers"; the header is therefore the source of a header capability's description, and the legacy prose for those 62 rows stays in git history at the adoption commit. No capability, test link or row is lost: the test sets agree for all 112 header rows (measured), and the gate's column, module, test and never-deleted checks keep applying.

Cannot-do check (all must be "no"):
- Weakens, skips or deletes a test: no
- Changes a requirement, threshold or exit criterion: no
- Touches a NEVER path: no
- Adds synthetic or substitute data where real data is required: no
- Widens network, credentials or security permissions: no
- Spends money or starts a paid service or trial: no

Reversal: replace B12 pins 2, 3 and 6 and regenerate; the records and headers stay unchanged.
