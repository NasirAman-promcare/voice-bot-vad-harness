# FIXES — WP-0.0

## Round 2 audit fixes (F11 to F22)

**Source.** `docs/progress/WP-0.0/AUDIT.md` round 2, commit `8be9e8b`, verdict FAIL.

**Owner instruction (session chat, 2026-09-25).** Run `/surgical-fix` for F11 to F22, test-first, then `/wp-audit WP-0.0`. The owner also gave these decisions:
- **F16 (Oracle).** Document that harness provisioning and TEN VAD need Linux x86_64. On Arm, provisioning must fail fast with a clear error saying TEN VAD has no Arm binary.
- **F17 (approval).** `docs/approvals/WP-0.0.md` on `main` (`227dac4`) now names commit `1479626` for the corpus and `harness-vcs.txt` for TEN VAD. It was merged into this branch at `d0b387b` before any fix. No code change is needed.

### Root causes
| Finding | Root cause |
| --- | --- |
| F11 CRITICAL | The code is correct, but the parser test only tried rejected titles with no WP ID anywhere. A title with the ID later on was never tried, so dropping the `^` anchor went unnoticed. |
| F12 CRITICAL | `step_verify` is correct, but every fast test starts and ends with a clean tree. No test makes the tree dirty, so blinding the check went unnoticed. |
| F13 MAJOR | Both safeguards exist in code but have no test. (1) No regression test uses a `skipped` outcome. (2) `check_ten_vad` is only reached by slow tests that install the correct commit. |
| F14 MAJOR | Cell 2 runs the clone with `check=True`. On failure, `CalledProcessError` shows the whole argument list, and that list includes the base64 header. The same arguments stay reachable through the `CompletedProcess` object. |
| F15 MAJOR | Cell 1 defaults to `main`, where the provisioning script does not exist until merge. The OC-0.0-01 steps do not say to change it. |
| F16 MAJOR | The pinned TEN VAD ships a native library only for Linux x64. Provisioning never checked the machine, so on Arm it would fail late and unclearly, in the import check. |
| F17 MAJOR | The approval conditions predated the BLK-004 and BLK-005 answers. The owner fixed this on `main`. |
| F18 MINOR | Round 2 changes outside the approved budget were not listed as differences. The `dev_bootstrap.sh` change log line is missing. The planned `pip check` in the stamp skip was left out. |
| F19 MINOR | The F09 citation fix for F1 got no assertion. |
| F20 MINOR | The CAP-AUDIT-008 row was not updated when `patterns.py` grew. |
| F21 MINOR | `git lfs pull` runs with `check=False` and its output is discarded. `git cat-file blob` has no timeout. `cfg.get(key, [])` turns a missing config key into a silent PASS. |
| F22 MINOR | Text was not updated after the BLK-005 and OC-0.0-01 changes. The approval-read behaviour was not described. The FireRedVAD licence is recorded only in PLAN.md. |

### Change budget
| File | Functions or parts changed | Finding |
| --- | --- | --- |
| `tests/aqis_lab/test_aqis_ci.py` | `test_FR_0_0_10_pr_title_parser`: rejected titles added; nothing removed | F11 |
| `tests/aqis_lab/test_aqis_harness_provision.py` | New tests (listed under Evidence) and helpers `local_package`, `scratch_venv`, `pip_install`, `load_provision_module`. Constant `REAL_CONFIG`. `make_tree` gains the `platform` pin, copied from the real config. Module docstring corrected. No existing test function changed | F12, F13, F16, F18, F21, F22 |
| `tests/aqis_lab/test_aqis_harness_regression.py` | New test `test_FR_0_0_11_regression_check_flags_newly_skipped_baseline_pass` | F13 |
| `tests/aqis_lab/test_aqis_gate_trace.py` | `test_FR_0_0_09_reports_unknown_wp`: path and line assertions for F1 added | F19 |
| `tests/aqis_lab/test_aqis_colab_doc.py` | New tests `test_FR_0_0_13_clone_failure_never_shows_token`, `test_FR_0_0_13_oc_steps_use_pull_request_branch` | F14, F15 |
| `aqis_lab/deploy/harness_provision.py` | Constant `REQUIRED_KEYS`; `Provisioner.__init__` (required keys); new `check_platform`, `reinstall_reason`, and `report` (the existing table printing moved out of `provision`, unchanged, so the platform failure prints the same table); `step_system`, `step_python`, `check_imports` (no defaults); `step_corpus` (timeout on `git cat-file`); `step_weights` (keep the `git lfs pull` result); `provision` (platform check first); module header | F16, F18, F21 |
| `aqis_lab/deploy/harness_provision.sh` | Header only: x86_64 requirement, change log | F16 |
| `config/aqis_lab/harness_assets.json` | New keys `platform` and `firered.licence`; `_about` text | F16, F22 |
| `docs/colab/HARNESS_SETUP.md` | Cells 1 and 2, the OC-0.0-01 steps, the x86_64 note | F14, F15, F16 |
| `aqis_lab/deploy/dev_bootstrap.sh` | CHANGE LOG line only | F18 |
| `tools/harness/regression_check.py` | Header test list and change log only | F13 |
| `docs/capabilities/REGISTRY.md` | Rows CAP-AUDIT-008 (functions and description), CAP-ENV-003, CAP-ENV-006, CAP-HARN-001, CAP-DOC-001 (descriptions and test lists) | F13, F14, F16, F20 |
| `docs/tools/AUDIT_GATE.md` | Approvals paragraph: an unreadable approval file does not count | F22 |
| `docs/progress/WP-0.0/EVIDENCE.md`, `STATUS.md`, this file | Records | all |

No protected path, no test on `main` and no other function is touched.

**Capabilities at risk.**
- CAP-ENV-003 and CAP-ENV-005: provisioning behaviour.
- CAP-HARN-001: header only.
- CAP-DOC-001: the Colab cells.
- CAP-CI-001: test only.
- CAP-AUDIT-006: test only.

Their linked tests form the baseline below.

### Baseline (before any change, commit `d0b387b`)
- Fast suite: `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` → `121 passed, 7 deselected in 20.64s`.
- Slow and network suite: `-m "slow or network"` → `7 passed, 121 deselected in 8.67s`.

These suites include every test linked to the capabilities at risk.

### Verification
- **Red first.** The new tests failed for the named reasons before the fixes (`6 failed, 18 passed`). The tests that guard already-correct code (F11, F12, F13, F19) fail under the auditor's mutations. Output is in EVIDENCE.md, "Round 2 audit fixes".
- **After the fixes.**
  - Fast suite: `132 passed, 7 deselected`.
  - Slow and network suite, on the clean committed tree: `7 passed`.
  - AT-0.0-05 in a fresh clone: run 1 `exit=0 48.3s`, run 2 `exit=0 1.1s`, `Downloads this run: 0`, git status empty.
  - Harness plus lab tests combined in `.venv-harness`: harness outcomes identical (`True 22 22 21 passed`).
- **Gate.** `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` → `0 findings: OK`. The Stop hook prints nothing.
- **Diff inside the budget.** `git diff d0b387b -U0 --stat` lists only the files in the change budget. In `harness_provision.py`, only the budgeted functions and the header changed.
