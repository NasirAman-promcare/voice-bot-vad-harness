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

## Round 3 audit fixes (F23 to F27)

**Source.** `docs/progress/WP-0.0/AUDIT.md` round 3, commit `5cdf131`, verdict FAIL.

**Owner go-ahead (session chat, 2026-09-25).** Fixes approved as proposed and recorded under CONDITIONS in `docs/approvals/WP-0.0.md` on `main` (`1bade2d`, merged here at `8a5383a`). The conditions this round must meet:
- `git lfs install --local` before `git lfs pull`, and git-lfs's output always shown when pointer files remain.
- A broken `.venv-harness` is rebuilt.
- Platform (F16 decision): harness provisioning supports **Debian or Ubuntu on x86_64** only. Any other platform fails fast with one platform FAIL row naming the reason. The Oracle row reads "Debian or Ubuntu on x86_64".
- Tests never run real `apt-get`, `sudo` or other system-changing commands; stand-ins go on PATH inside the test's temporary folder only.
- The non-root test runs the script as an unprivileged user (directly when not root, through `setpriv` when root). It is never skipped, and it asserts that `sudo -n` is attempted for a missing package.
- The `harness-regression` CI job runs the harness tests on their own (difference 5 acknowledged). Both jobs must pass before merge.

### Root causes
| Finding | Root cause |
| --- | --- |
| F23 CRITICAL | **Unrealistic fixture.** The fixture's weights repository had no `.gitattributes`, unlike the real Hugging Face repository (35 LFS rules). git-lfs 3.7.0 then ignores the pointer (exit 0, "Skipping object checkout"), while 3.4.1 still tries the transfer (exit 2), so the test result depended on the git-lfs version. **Real defect behind it.** Reproduced with both 3.4.1 and 3.7.0: when Git LFS is not installed in git config, `git lfs pull` downloads the object but skips the checkout, exits 0 and leaves the pointer. Provisioning worked only because Debian's git-lfs package installs the filter in the system config. **Process.** I set READY-FOR-AUDIT without checking CI on the fix commit. |
| F24 MAJOR | The F16 decision existed only in chat (now in the approval). The platform check tested only the machine, although the system step needs `apt-get` and `dpkg-query`, which only Debian and Ubuntu have. |
| F25 MAJOR | No test ran `step_system` without root: the fast tests request no packages, and the slow tests run as root here. |
| F26 MINOR | The `git lfs pull` output was added to the FAIL detail only when its exit code was not 0. |
| F27 MINOR | `step_python` reused any `.venv-harness` whose Python version matched, even one left without pip by a failed `uv venv --seed`. |

### Change budget
| File | Functions or parts changed | Finding |
| --- | --- | --- |
| `aqis_lab/deploy/harness_provision.py` | `check_platform` (distribution check via `platform.freedesktop_os_release()`); `step_weights` (`git lfs install --local`; the pull's output in the FAIL detail for any exit code); new `venv_problem`; `step_python` (rebuild when `venv_problem` reports one); module header | F23, F24, F26, F27 |
| `aqis_lab/deploy/harness_provision.sh` | Header only (platform wording, change log) | F24 |
| `config/aqis_lab/harness_assets.json` | `platform`: new `distributions` and `distribution_reason` keys | F24 |
| `tests/aqis_lab/test_aqis_harness_provision.py` | Helpers: `make_tree` (weights source gets the LFS `.gitattributes` rule of the real repository; options for real LFS content and system packages), `run_real` (stand-in `apt-get` and `sudo` on PATH, as the conditions require), new `standin_bin`. New tests listed under Evidence. No assertion of an existing test changed | F23, F24, F25, F26, F27 |
| `docs/colab/HARNESS_SETUP.md` | Platform note | F24 |
| `docs/capabilities/REGISTRY.md` | Rows CAP-ENV-003, CAP-ENV-006 (descriptions and test lists) | all |
| `docs/progress/WP-0.0/EVIDENCE.md`, `STATUS.md`, this file | Records; Oracle row wording | all |
