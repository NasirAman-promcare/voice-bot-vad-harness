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

### Baseline (before any change, commit `8a5383a`)
- Fast suite: `132 passed, 7 deselected in 34.52s` with git-lfs 3.4.1.
- With git-lfs 3.7.0 on PATH: `1 failed, 131 passed, 7 deselected in 29.92s`, which is the CI failure reproduced.

These suites include every test linked to CAP-ENV-003, CAP-ENV-005 and CAP-ENV-006.

### Verification
- **Red first.** The new tests failed for the named reasons before the code changed: `5 failed, 20 passed` on both git-lfs versions.
- **Mutations.** Each fix was removed in turn, and a named test caught every removal: F23 and F26 on both git-lfs versions, F24, F25, and F27 both in `venv_problem` and in `step_python`, the last through the slow test.
- **After the fixes** (`d35290b`, clean tree):
  - Fast suite: `138 passed` with git-lfs 3.4.1 and with 3.7.0.
  - Slow and network suite: `8 passed`, git status empty afterwards.
  - Gate: `0 findings`.
- **CI** on `d35290b`: push run `36151733422` success; pull request run `36151741552` success, with the `lab` job (WP ID `WP-0.0`, gate `0 findings: OK`) and the `harness-regression` job both green.
- **Diff.** `git diff 8a5383a d35290b` changes only the files and functions in the change budget. No existing test assertion changed, only the helpers `make_tree`, `run_real` and the import line.
- **Records.** The module header change logs and the registry rows (CAP-ENV-003, CAP-ENV-006) are updated.

## Colab owner check fix (BLK-006)

**Source.** `docs/progress/WP-0.0/OWNER_VERIFY_COLAB_WP-0.0_20260925T151855Z.md` (owner commit `22ce3c6`, on `aa9e74c`).
- Fast suite: `3 failed, 135 passed`.
- Slow suite: `1 failed, 7 passed`.
- The failing tests are `test_FR_0_0_12_rejects_ten_vad_at_other_commit`, `test_FR_0_0_12_reinstalls_when_pip_check_fails`, `test_FR_0_0_12_venv_problem_detects_venv_without_pip` and `test_FR_0_0_03_lock_installable_with_plain_pip`.

**Owner decision.** BLK-006 option 1, recorded under CONDITIONS in `docs/approvals/WP-0.0.md` on `main` (`d403bad`, merged here at `2c1963f`):
- Use `uv venv --seed` in shared test helpers for throwaway test environments.
- Changing the venv creation line in `test_FR_0_0_03_lock_installable_with_plain_pip` is approved, with its assertions unchanged.

**Root cause.** The four tests made scratch venvs with `python -m venv`, which runs `ensurepip`. Colab's lab Python is Ubuntu's `/usr/bin/python3.13` without the `python3.13-venv` package, where `ensurepip` fails. This VM has that package (`python3.13-venv 3.13.12-1+noble1`), so the tests passed here and in CI. Production code is not affected: provisioning makes `.venv-harness` with `uv venv --seed` and passed on Colab.

### Change budget
| File | Change |
| --- | --- |
| `tests/aqis_lab/aqis_testutil.py` | New helper `pip_venv(path)`: `uv venv --seed --python <running Python> <path>`, which fails loudly if uv is missing or the command fails |
| `tests/aqis_lab/test_aqis_harness_provision.py` | Helper `scratch_venv` delegates to `pip_venv`; import line. No test function changes |
| `tests/aqis_lab/test_aqis_lock.py` | In `test_FR_0_0_03_lock_installable_with_plain_pip`, only the venv creation line (as approved), plus `pip_venv` in the import line. Assertions unchanged |
| `docs/progress/WP-0.0/EVIDENCE.md`, `FIXES.md`, `BLOCKERS.md` (BLK-006 answer), `STATUS.md` | Records |

No production code, no capability and no registry row changes. The venv made `--without-pip` in `test_FR_0_0_12_venv_problem_detects_venv_without_pip` already works without `ensurepip`, so it stays as it is.

### Baseline and verification
- **Baseline on this VM** (`0a36ac5`, before the change): fast suite `138 passed, 8 deselected in 37.11s`.
- **Reproduced, red.** The Colab failure was reproduced here without changing the system. A uv-installed CPython 3.13.7 in the scratchpad, with `lib/python3.13/ensurepip/_bundled/*.whl` removed, stands in for Ubuntu's Python without `python3.13-venv`. Then `python -m venv` → `Error: Command '[..., '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.` A lab venv on that Python (`uv pip sync --require-hashes requirements/aqis_lab/phase0.txt`) ran `-k "rejects_ten_vad_at_other_commit or reinstalls_when_pip_check_fails or venv_problem_detects or lock_installable_with_plain_pip"` → `4 failed`, the same four as on Colab.
- **After the change, green.** Same lab venv, same command → `4 passed, 142 deselected in 10.85s`. On this VM the fast suite gives `138 passed, 8 deselected in 27.53s`.
- **Diff.** Only the budgeted lines changed: the new `pip_venv` and its two imports (`shutil`, `sys`) in `aqis_testutil.py`; the body of the `scratch_venv` helper and one import line in `test_aqis_harness_provision.py`; one venv creation line and one import line in `test_aqis_lock.py`. No assertion changed. `import sys` in `test_aqis_lock.py` is now unused and left as it is, since the line is outside the approved change.

## Round 4 audit fixes (F28 to F32)

**Source.** `docs/progress/WP-0.0/AUDIT.md` round 4, commit `db11efb`, verdict FAIL.

**Owner instruction.** `/surgical-fix WP-0.0-F28 … F32` (session chat, 2026-09-25).

### Root causes
| Finding | Root cause |
| --- | --- |
| F28 CRITICAL | The gate code is correct, but no test ever exercised three rules of checks (a) and (b): the built-in NEVER list when `PROTECTED_PATHS.txt` loses its `[NEVER]` section, `--no-renames` for a renamed test, and "`docs/approvals/README.md` is ignored". |
| F29 CRITICAL | The parity scenarios had no line matching several code patterns, no new lab module longer than 80 lines, and no modified header-less lab module. So "first pattern wins", "header within the first 80 lines" and "new modules only" were never compared with the hook. The `EXPIRES` and non-`APPROVED` status rules had gate-only tests but no parity scenario. |
| F30 MINOR | Licence entries were added for FireRedVAD only. TEN VAD (Apache-2.0 with Agora's additional conditions) and the corpus-v1 sources were missed. |
| F31 MINOR | My BLK-006 reproduction used `uv python install`, which also puts a `python3.13` link in `/root/.local/bin`, first on PATH. I did not notice it, and the records wrongly said the system was not changed. |
| F32 MINOR | After BLK-006 I recorded only the fast suite. No gate run, slow suite or CI run IDs were recorded. The CI row was left on `d35290b`, and the round 3 `_about` text edit was not listed as a difference. |

### Change budget
| File | Change | Finding |
| --- | --- | --- |
| `tests/aqis_lab/test_aqis_gate_parity.py` | New scenario functions and `SCENARIOS` entries: `never_section_stripped`, `renamed_lab_test`, `renamed_harness_test`, `readme_approval`, `expired_approval`, `unapproved_status`, `multi_pattern_line`, `late_header`, `modified_headerless_module` (the last one also in `EXPECT_NONE`). Helper `strip_never_section`. No existing scenario or assertion changed | F28, F29 |
| `tests/aqis_lab/test_aqis_gate_checks.py` | New tests `test_FR_0_0_05_a_builtin_never_list_applies_when_policy_section_removed`, `test_FR_0_0_05_a_approvals_readme_approves_nothing`, `test_FR_0_0_05_a_detects_renamed_guarded_harness_test`, `test_FR_0_0_05_b_detects_renamed_existing_lab_test` | F28 |
| `tests/aqis_lab/test_aqis_harness_provision.py` | New test `test_FR_0_0_12_asset_licences_recorded` | F30 |
| `config/aqis_lab/harness_assets.json` | New `licence` keys for `ten_vad` and `corpus` | F30 |
| `tools/audit/gate.py` | Module header only: the new tests in the CAP-AUDIT-001 and CAP-AUDIT-002 lists, and a change log line. No code | F28 |
| `aqis_lab/deploy/harness_provision.py` | Module header only: the new test in the CAP-ENV-003 list (the registry row shares it) | F30 |
| `docs/capabilities/REGISTRY.md` | Test lists of CAP-AUDIT-001, CAP-AUDIT-002, CAP-ENV-003 and CAP-ENV-006 | F28, F30 |
| `docs/progress/WP-0.0/EVIDENCE.md`, `FIXES.md`, `BLOCKERS.md`, `STATUS.md` | Records, including the corrections F31 and F32 ask for | F31, F32 |

No gate or provisioning code changes.

**Capabilities at risk.** None changes behaviour: CAP-AUDIT-001 to 004 and CAP-ENV-003 and 006 gain tests only.

**F31 system fix, already done.**
- Ran `UV_PYTHON_INSTALL_DIR=<scratchpad>/colabrepro/py uv python uninstall 3.13`, which printed `Uninstalled Python 3.13.7 in 96ms` and ` - cpython-3.13.7-linux-x86_64-gnu (python3.13)`.
- Afterwards `ls -la /root/.local/bin | grep -c python3.13` gives `0`, `command -v python3.13` gives `/usr/bin/python3.13`, and `python3.13 --version` gives `Python 3.13.12`.
- This repository's `.venv` and `.venv-harness` never used the link: both `pyvenv.cfg` files have `home = /usr/bin`.
- The scratch lab venv built on the removed Python was deleted with the rest of `scratchpad/colabrepro`.
