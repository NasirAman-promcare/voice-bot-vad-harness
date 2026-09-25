# PLAN — WP-0.0 Guardrails and audit tooling

Spec: `docs/specs/phase-0/WP-0.0-guardrails.md`  ·  Planned by session: https://claude.ai/code/session_01N7gtpxBMnXJe8XU2D1AzuM  ·  Date: 2026-09-25
Branch: `claude/hopeful-noether-yinc4e`  ·  Base: `origin/main` at `364d9b7`  ·  Depends on: none

## Summary
When this WP is done, one idempotent script (`aqis_lab/deploy/dev_bootstrap.sh`) builds `.venv` on the Colab Python (3.13) from a hash-pinned lock, and `python -m aqis_lab version` reports the package version, commit and Python version. Lab tests live in `tests/aqis_lab/` with five registered markers and leave harness tests untouched. `python -m tools.audit.gate` checks a branch for protected-path changes, edited or deleted tests, compromise patterns, missing module headers, registry drift and requirement traceability; for checks (a) to (d) it reports the same findings as the Stop hook. GitHub Actions runs the fast suite and the gate on every push and pull request. The existing harness test results are recorded as a baseline.

## What I found in the repository (read-only inspection)
1. **Colab probe**: `docs/environment/colab_probe.txt` says `Python Version: 3.13.15`, so the lab Python is **3.13**. The file is in a different format from the commands in `docs/environment/README.md` (it has no `python --version` line). The bootstrap parser accepts both `Python Version: X.Y...` and `Python X.Y.Z` lines, and fails if it finds none or two that disagree.
2. **This VM**: uv 0.8.17 is on PATH (`~/.local/bin/uv`). A system `/usr/bin/python3.13` (3.13.12) exists, and the default `python3` is 3.11. In a scratchpad outside the repository, `uv venv --python 3.13` worked, and `uv pip compile --generate-hashes` for pytest and jsonschema worked.
3. **Network**: `pypi.org` and `files.pythonhosted.org` are reachable. `github.com` returns 403 from the proxy and `astral.sh` is unreachable. Two consequences: uv cannot download a Python build here, which is not needed because a system 3.13 exists; and the harness's `requirements/tier1.txt` (`git+https://github.com/TEN-framework/ten-vad.git`) cannot be installed here. The regression tests do not import it.
4. **Ignored files**: `uv venv` writes `.venv/.gitignore` containing `*`, and pytest writes `.pytest_cache/.gitignore`. The guarded root `.gitignore` therefore does not need to change.
5. **Harness tests**:
   - `tests/regression/` holds 16 pytest files with 22 test functions. Two of them use `@pytest.mark.asyncio`.
   - The repository has no pytest configuration: no `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini` or `conftest.py`.
   - The tests import `webrtc_bridge`, `bots` and similar packages from the repository root, so only the form `python -m pytest ...` run from the root can import them.
   - `pytest` and `pytest-asyncio` are not listed in any `requirements/*.txt`.
   - Third-party imports: numpy, scipy, soundfile, pyyaml, aiortc, av, websockets and opuslib. The system libraries libopus0 and libsndfile1 are installed on this VM.
   - The tests look offline: they use `ws://mock` URLs, `tmp_path` and no sockets.
6. **`tests/smoke_test_tier1/`** is not a pytest suite. It is an orchestrator run config plus a manifest, both with absolute `/workspaces/voice-bot-vad-harness/...` paths. The run writes its output into a tracked file, `tests/smoke_test_tier1/results/raw_evaluations.jsonl`.
7. **CI**: there is no `.github/` folder, so no other workflows exist.
8. **Hooks**: the Stop hook reads approvals at the merge-base of HEAD and `origin/main`, while the edit guard reads them at `origin/main`. At session start the local `origin/main` was stale (`b884b84`) until I ran `git fetch`; it is now `364d9b7`, the same commit as this branch.
9. **Git config**: the global git config signs commits (`commit.gpgsign=true`), and CI runners have no git identity. Fixture repositories must therefore set their own identity and turn signing off.
10. **Requirement ID prefixes** across the Phase 0 specs are `FR-`, `NFR-`, `AT-` (acceptance) and `OC-` (owner checks, in WP-0.5 to WP-0.7). The WP-0.0 spec also mentions `FR-0.2-03` as an example, and the gate must not treat that as a WP-0.0 requirement.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command |
| --- | --- | --- | --- | --- | --- |
| FR-0.0-01 | argparse dispatcher with lazily imported command modules; `version` prints `aqis_lab <version> commit=<short>[+dirty] python=<x.y.z>` and exits 0; git is queried in the package's own repo root, not the cwd | `aqis_lab/__init__.py`, `aqis_lab/__main__.py`, `aqis_lab/commands/__init__.py`, `aqis_lab/commands/version.py` | none | `test_FR_0_0_01_version_prints_package_commit_python`, `test_FR_0_0_01_version_marks_dirty_tree`, `test_FR_0_0_01_version_fails_loudly_outside_git`, `test_FR_0_0_01_dispatcher_rejects_unknown_command` | AT-0.0-01, AT-0.0-02 |
| FR-0.0-02 | bash, `set -euo pipefail`; repo root from the script location; parse the probe; `uv venv --python X.Y`, reusing an existing `.venv` only when its major.minor matches; `uv pip sync --require-hashes --strict`; clear `ERROR:` messages for a missing or unreadable probe, missing uv, or a Python uv cannot provide | `aqis_lab/deploy/dev_bootstrap.sh` | none | fast: `test_FR_0_0_02_fails_when_probe_missing`, `test_FR_0_0_02_fails_when_probe_unreadable`, `test_FR_0_0_02_fails_when_uv_missing`; slow+network: `test_FR_0_0_02_creates_venv_with_probe_python`, `test_FR_0_0_02_second_run_changes_nothing_within_30s`, `test_FR_0_0_02_rejects_lock_with_wrong_hash` | AT-0.0-01; second run timed: `time bash aqis_lab/deploy/dev_bootstrap.sh`; `.venv/bin/python -m pytest tests/aqis_lab -q -m "slow or network" -k FR_0_0_02` |
| FR-0.0-03 | `phase0.in` lists direct needs (pytest, jsonschema, pyyaml); `phase0.txt` generated with `uv pip compile --universal --python-version 3.13 --generate-hashes`; the command is recorded in the `.in` header and in the `.txt` header (`--custom-compile-command`) | `requirements/aqis_lab/phase0.in`, `requirements/aqis_lab/phase0.txt` | none | `test_FR_0_0_03_every_pin_has_hashes`, `test_FR_0_0_03_lock_generated_from_in_file`, `test_FR_0_0_03_regeneration_command_documented`, `test_FR_0_0_03_environment_matches_lock`; slow+network: `test_FR_0_0_03_regeneration_is_reproducible`, `test_FR_0_0_03_lock_installable_with_plain_pip` | AT-0.0-02; `.venv/bin/python -m pytest tests/aqis_lab -q -m "slow or network" -k FR_0_0_03` |
| FR-0.0-04 | `tests/aqis_lab/conftest.py` registers `slow gpu colab oracle network` in `pytest_configure`; `collect_ignore = ["fixtures"]`; no root config, no `sys.path` changes, no session-wide collection hooks; no `__init__.py` in `tests/aqis_lab` (it would shadow the real `aqis_lab` package) | `tests/aqis_lab/conftest.py` | none | `test_FR_0_0_04_all_five_markers_registered`, `test_FR_0_0_04_lab_tests_use_only_registered_markers`, `test_FR_0_0_04_harness_collection_unchanged`, `test_FR_0_0_04_no_pytest_config_outside_lab`, `test_FR_0_0_04_no_test_basename_collisions` | AT-0.0-02; `.venv/bin/python -m pytest tests/aqis_lab --markers`; harness baseline re-run (FR-0.0-11 command) shows identical results after the build |
| FR-0.0-05 | Gate CLI `--base <ref> [--wp] [--json]`: diff base = `git merge-base <ref> HEAD`, plus uncommitted and untracked work; approvals read from `origin/main`; checks (a) to (f); exit 0 with no findings, 1 with findings, 2 on an operational error (bad ref, no `origin/main`) | `tools/__init__.py`, `tools/audit/__init__.py`, `tools/audit/gate.py`, `tools/audit/patterns.py`, `docs/tools/AUDIT_GATE.md`, fixture helper `tests/aqis_lab/fixture_repo.py`, fixtures under `tests/aqis_lab/fixtures/gate/` | none | For each check (a) to (d), one test proving detection and one proving a clean pass, e.g. `test_FR_0_0_05_a_detects_never_path`, `test_FR_0_0_05_a_detects_guarded_path_without_approval`, `test_FR_0_0_05_a_passes_guarded_path_with_main_approval`, `test_FR_0_0_05_a_ignores_approval_committed_only_on_branch`, `test_FR_0_0_05_a_ignores_expired_or_withdrawn_approval`, `test_FR_0_0_05_b_detects_modified_existing_test`, `test_FR_0_0_05_b_detects_deleted_existing_test`, `test_FR_0_0_05_b_passes_new_test_and_approved_edit`, `test_FR_0_0_05_c_detects_each_code_pattern`, `test_FR_0_0_05_c_detects_each_test_pattern`, `test_FR_0_0_05_c_scans_only_added_lines`, `test_FR_0_0_05_c_includes_uncommitted_and_untracked_work`, `test_FR_0_0_05_d_detects_new_module_without_header`, `test_FR_0_0_05_d_passes_module_with_header_or_short_file`, `test_FR_0_0_05_clean_branch_exits_zero`, `test_FR_0_0_05_uses_merge_base_not_ref_tip`, `test_FR_0_0_05_json_output_schema`, `test_FR_0_0_05_bad_base_ref_exits_2` | AT-0.0-02, AT-0.0-03 |
| FR-0.0-06 | Independent implementation in `tools/`, proved identical to the hook: the same fixture repos are run through the gate (`--json`) and through the real `.claude/hooks/stop_gate.py` (subprocess, `CLAUDE_PROJECT_DIR` set to the fixture); findings for (a) to (d) are normalised to tuples and compared as multisets | (tests only) | none | `test_FR_0_0_06_parity_with_stop_hook_on_fixture_repos` (parametrised over every scenario, each non-clean scenario must produce findings), `test_FR_0_0_06_pattern_tables_identical_to_stop_hook`, `test_FR_0_0_06_path_classification_identical_to_hook` | AT-0.0-02 |
| FR-0.0-07 | `# audit-allow:` followed by a non-space reason exempts that line only (the same regex as the hook); the gate prints every exempted line with its reason and every file exempted by `ALLOW-PATTERNS-IN`, naming the approval file and glob; exemptions never count as findings | (in `gate.py`) | none | `test_FR_0_0_07_audit_allow_with_reason_exempts_and_is_listed`, `test_FR_0_0_07_audit_allow_without_reason_does_not_exempt`, `test_FR_0_0_07_audit_allow_exempts_only_its_line`, `test_FR_0_0_07_allow_patterns_in_exempts_file_and_is_listed` | AT-0.0-02, AT-0.0-03 |
| FR-0.0-08 | Parse the registry table; every row must name at least one test that exists (AST-defined test function under `tests/`, fixtures excluded) and a module that exists (path or dotted name); every capability ID present at the diff base must still be present; malformed rows and an unreadable registry are findings | (in `gate.py`); rows added to `docs/capabilities/REGISTRY.md` | `docs/capabilities/REGISTRY.md`: append rows only | `test_FR_0_0_08_detects_row_with_missing_test`, `test_FR_0_0_08_detects_row_with_missing_module`, `test_FR_0_0_08_detects_row_removed_since_base`, `test_FR_0_0_08_detects_malformed_row`, `test_FR_0_0_08_passes_consistent_registry`, `test_FR_0_0_08_repository_registry_is_consistent` | AT-0.0-02, AT-0.0-03 |
| FR-0.0-09 | With `--wp`: find exactly one spec `docs/specs/**/<WP>-*.md`; collect its own IDs (see question 1); check `docs/progress/<WP>/PLAN.md`, AST test function names under `tests/aqis_lab/` (fixtures excluded; `FR-0.2-03` matches `FR_0_2_03` with alphanumeric boundaries, so `NFR_0_2_03` does not satisfy `FR-0.2-03`) and `docs/progress/<WP>/EVIDENCE.md` | (in `gate.py`) | none | `test_FR_0_0_09_detects_id_missing_from_plan`, `test_FR_0_0_09_detects_id_missing_from_test_names`, `test_FR_0_0_09_detects_id_missing_from_evidence`, `test_FR_0_0_09_underscore_matching_respects_boundaries`, `test_FR_0_0_09_ignores_other_wp_ids_in_spec`, `test_FR_0_0_09_reports_unknown_wp`, `test_FR_0_0_09_passes_complete_traceability` | AT-0.0-03 |
| FR-0.0-10 | One workflow: `on: [push, pull_request]`, `permissions: contents: read`; checkout with `fetch-depth: 0`; install uv 0.8.17; `bash aqis_lab/deploy/dev_bootstrap.sh` (Colab Python and hashed lock, the same path as local); `python -m aqis_lab version`; fast suite; gate with `--base origin/$GITHUB_BASE_REF` on pull requests or `--base origin/main` on push (passed through `env`, not inline expressions); no dispatch or `workflow_run` of anything | `.github/workflows/aqis-lab-ci.yml` (LAB-OWNED) | none | `test_FR_0_0_10_ci_triggers_push_and_pull_request`, `test_FR_0_0_10_ci_bootstraps_probe_python_and_hashed_lock`, `test_FR_0_0_10_ci_runs_fast_suite_with_exact_markers`, `test_FR_0_0_10_ci_gate_base_selection`, `test_FR_0_0_10_ci_cannot_change_or_trigger_other_workflows` | AT-0.0-04 (owner confirms green) |
| FR-0.0-11 | Before any lab file exists: throwaway venv outside the repo (Python 3.13, uv); install `requirements/base.txt`, `corpus.txt`, `tier2.txt` as they are, plus `pytest` and `pytest-asyncio`; run `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/regression -rA -p no:cacheprovider --junitxml=<outside repo>` from the root; show that `git status --porcelain --ignored` is identical before and after; record the command, platform, Python, `pip freeze`, system libraries, commit and per-test outcomes; failures recorded, never fixed | `docs/baselines/harness_tests_baseline.md` | none | `test_FR_0_0_11_baseline_records_command_and_environment`, `test_FR_0_0_11_baseline_lists_every_harness_test` (expected list computed by AST from `tests/regression`) | the recorded baseline command; re-run at the end of the build for FR-0.0-04 |
| NFR-0.0-01 | stdlib `subprocess` git calls only, a few per changed file; no test execution inside the gate | — | none | `test_NFR_0_0_01_gate_runtime_under_60s` (the real repository, `--base origin/main --wp WP-0.0`) | `time .venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` |
| NFR-0.0-02 | Every finding is printed as `path:line: [RULE] SEVERITY: message` (rule IDs below); JSON carries `path`, `line` and `rule` | — | none | `test_NFR_0_0_02_every_message_names_file_line_and_rule` (every fixture scenario) | AT-0.0-02 |
| NFR-0.0-03 | `tools/` uses the standard library only; `aqis_lab/` WP-0.0 code uses the standard library only; tests may use pinned packages | — | none | `test_NFR_0_0_03_imports_are_stdlib_or_pinned` (AST scan of `aqis_lab/` and `tools/` against `sys.stdlib_module_names`, first-party names and `phase0.txt` pins) | AT-0.0-02 |
| AT-0.0-01 | Run as written; paste the output | — | — | covered by the FR-0.0-01 and FR-0.0-02 tests | `bash aqis_lab/deploy/dev_bootstrap.sh && .venv/bin/python -m aqis_lab version` |
| AT-0.0-02 | Run as written | — | — | all of the above | `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"` |
| AT-0.0-03 | Run as written on this branch after `git fetch origin main` | — | — | — | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` |
| AT-0.0-04 | The PR's CI run | — | — | — | Owner checks the Actions tab |

**Change budget for existing files** (nothing else that already exists is touched):
- `docs/progress/STATUS.md`: the WP-0.0 row only.
- `docs/capabilities/REGISTRY.md`: new rows appended; the header and existing text stay byte-identical.
- `docs/progress/BLOCKERS.md`: append-only, and only if I get blocked.
- No GUARDED or NEVER path changes, so no `ALLOW-EDIT` is needed.

**New files**: those in the table, plus these:
- `docs/progress/WP-0.0/EVIDENCE.md`.
- Test modules `tests/aqis_lab/test_aqis_version.py`, `test_aqis_bootstrap.py`, `test_aqis_lock.py`, `test_aqis_markers.py`, `test_aqis_gate_checks.py`, `test_aqis_gate_parity.py`, `test_aqis_gate_exemptions.py`, `test_aqis_gate_registry.py`, `test_aqis_gate_trace.py`, `test_aqis_gate_nfr.py`, `test_aqis_ci.py` and `test_aqis_baseline.py`. The `test_aqis_` prefix avoids basename clashes with harness tests.

## Design details

### Package and command
- `aqis_lab/__init__.py` defines `__version__`.
- `aqis_lab/__main__.py` maps command names to `module:function` and imports a command only when it runs, so later heavy commands never slow down `version`. An unknown command gets exit code 2 with a usage message.
- Every module in `aqis_lab/` and `tools/` gets the CAPABILITIES header from `docs/process/CHANGE_CONTROL.md`.

### Gate rules
Every finding prints as `path:line: [RULE] SEVERITY: message`. Line numbers work like this:
- Pattern findings use the added line.
- File-level findings use the first changed line of a modified file. For an added, deleted or binary file they use `1`.
- Registry findings use the row's line.
- Traceability findings use the line in the spec where the ID appears.

| Rule | Check | Severity | Meaning |
| --- | --- | --- | --- |
| A1 | a | CRITICAL | NEVER path changed |
| A2 | a | CRITICAL | GUARDED path changed without a matching `ALLOW-EDIT` on `origin/main` |
| B1 / B2 | b | CRITICAL | existing `tests/**.py` modified / deleted without `ALLOW-EDIT` |
| C1 | c | COMPROMISE | code pattern in an added line of `aqis_lab/` or `tools/` (label from `patterns.py`) |
| C2 | c | COMPROMISE | skip, xfail or trivial assert in an added line of `tests/aqis_lab/` |
| D1 | d | MAJOR | new `aqis_lab/` module with more than 5 non-blank lines and no `CAPABILITIES:` in its first 80 lines |
| E1 to E5 | e | MAJOR | registry missing or unreadable; malformed row; row names no test or a test that does not exist; module does not exist; row present at the base is gone |
| F1 to F4 | f | MAJOR | spec for the WP not found or ambiguous; ID missing from PLAN.md; ID not in any test function name; ID missing from EVIDENCE.md |

- **Parity with the Stop hook**: checks (a) to (d) reproduce the hook's exact rules, including these details:
  - `--no-renames`.
  - Untracked files count as added.
  - A file added on the branch and then deleted is ignored.
  - Only `.py` files are scanned.
  - The first matching pattern per line wins.
  - `ALLOW-PATTERNS-IN` also skips the header check.
  - The `STATUS: APPROVED` and `EXPIRES` rules, and `README.md` is ignored.
  - Globs are converted the same way, and the built-in NEVER list applies.
  - `PROTECTED_PATHS.txt` is read from the working tree, as the hook does. A change to it is itself an A1 finding.
- **Output order**: the exemption list comes first, then the findings, then a one-line summary. This keeps findings visible in the 25-line tail that the Stop hook shows.
- **JSON output** (`--json`): `{tool, base_ref, base_commit, head_commit, approvals_ref, approvals_commit, wp, findings[{rule, check, severity, path, line, message, text}], exempted_lines[{path, line, reason}], exempted_files[{path, approval, glob}], ok}`.
- **Python version**: the gate uses standard-library syntax that works on Python 3.10 and later. The Stop hook falls back to the system `python3` (3.11 here) when `.venv` is missing.
- **Registry format**, documented in `docs/tools/AUDIT_GATE.md`:
  - Module column: a repo-relative file path or a dotted module name.
  - Tests column: comma-separated test function names, optionally written as `path::name`.

### Fixture repositories
- Each test builds a bare `origin` and a clone in `tmp_path`, commits the policy files and pushes `main`, then makes the scenario's changes on a branch, both committed and uncommitted. Approvals are committed to `main`, and one scenario commits an approval only on the branch.
- Every repo uses `-c commit.gpgsign=false` and a local identity.
- The real `docs/process/PROTECTED_PATHS.txt` is copied in, so the tests follow the owner's real policy.
- Lines that deliberately contain forbidden patterns live only in `tests/aqis_lab/fixtures/gate/**`, together with a hand-written `expected.json` of line and label pairs. Test modules therefore never contain those patterns themselves.
- The Stop hook is run from its real location with `CLAUDE_PROJECT_DIR` set to the fixture.
- Its pattern table and path classification are read in a `python -B` subprocess, so no bytecode is written into `.claude/`.
- The gate runs with `PYTHONPATH` set to this repository and the fixture as its working directory. The command-line interface stays exactly as the spec defines it.

### Build order
The Stop hook runs the fast suite, and later the gate, at every stop, so the branch must stay green at each commit. The order is:
1. FR-0.0-11 baseline, on the pristine tree.
2. FR-0.0-03 lock, then FR-0.0-02 bootstrap. Their tests are written first and shown failing with a throwaway `uv run --with pytest==<pin>` interpreter, because the lock does not exist yet.
3. FR-0.0-04.
4. FR-0.0-01.
5. Gate: FR-0.0-05, FR-0.0-07, FR-0.0-06, FR-0.0-08, FR-0.0-09.
6. The three NFRs.
7. FR-0.0-10.
8. Registry rows, documentation and evidence.
9. Re-run the harness baseline and compare it with the first run.
10. Run the acceptance commands and open the PR.

Registry rows are added only after their tests exist.

### Capabilities to register
The Module column of each row is a file path.
- CAP-CLI-001: `python -m aqis_lab` dispatcher.
- CAP-CLI-002: `version` command.
- CAP-ENV-001: `dev_bootstrap.sh`.
- CAP-ENV-002: `phase0` lock.
- CAP-TEST-001: lab marker registration (`tests/aqis_lab/conftest.py`).
- CAP-AUDIT-001 to CAP-AUDIT-006: gate checks (a) to (f).
- CAP-AUDIT-007: exemption listing.
- CAP-AUDIT-008: pattern tables.
- CAP-CI-001: `aqis-lab-ci.yml`.

## Owner needs
| # | What | Why | Needed by |
| --- | --- | --- | --- |
| 1 | Commit `docs/approvals/WP-0.0.md` to `main` with `STATUS: APPROVED`, `ALLOW-PATTERNS-IN: tools/audit/patterns.py` and `ALLOW-PATTERNS-IN: tests/aqis_lab/fixtures/**` | These files must contain the forbidden patterns; without the lines, the Stop hook and the gate block the build | Before `/wp-build WP-0.0` |
| 2 | Answers to the questions below; put any changes under `CONDITIONS:` in the approval | Several interpretations need your decision | Before `/wp-build WP-0.0` |
| 3 | GitHub Actions enabled for this repository, with `actions/checkout` and `astral-sh/setup-uv` allowed (Settings → Actions → General) | FR-0.0-10, AT-0.0-04 | Before the PR's CI run |
| 4 | Only if my push of `.github/workflows/aqis-lab-ci.yml` is refused for lack of the GitHub "workflows" permission: grant it, or add the file yourself from the branch; I will raise a blocker with exact steps | GitHub protects workflow files separately | During the build, only if it happens |
| 5 | Confirm the PR's CI run is green | AT-0.0-04 | After the PR opens |
| — | `docs/environment/colab_probe.txt` | Already committed ✔ | — |
| — | New network hosts | None needed: PyPI is reachable and a system Python 3.13 exists | — |

## Owner-run checks planned
| Check | Where | Command | Expected output |
| --- | --- | --- | --- |
| AT-0.0-04 CI green | GitHub → the pull request → Checks (or the Actions tab) | Open the `aqis-lab-ci` run for the PR's latest commit | Every step green; the "version" step prints `python=3.13.x`; the fast-suite step ends with `passed` and no failures; the gate step ends with `0 findings` |

## Risks and questions

**Risks**
1. **Workflow push permission.** If the session's GitHub credentials lack the "workflows" permission, pushing `.github/workflows/aqis-lab-ci.yml` fails. See owner need 4.
2. **FR-0.0-06 cannot be met in one edge case as written.** FR-0.0-05 requires approvals to be read from `origin/main`, but the Stop hook reads them at the merge-base. The two agree whenever the branch contains the latest `main`, which is the normal state because `/wp-build` step 1 merges `origin/main`, and always in CI pull-request runs. They differ only when `main` gained a new approval after the branch point and the branch has not merged it. The parity tests cover the agreeing state. See question 2.
3. **The harness baseline depends on time.** The harness requirements are unpinned (`>=`), so I record the exact `pip freeze`. A future re-run must install those exact versions to compare like with like. Some harness tests may fail on Python 3.13 or on the newest aiortc (for example, its private `_handle_rtp_packet` API). Failures are recorded, never fixed.
4. **Only `github.com` is blocked.** If this cloud image ever loses `/usr/bin/python3.13`, uv would need `github.com` to download Python, and I would raise a blocker naming that host.
5. **Stale `origin/main`.** The gate reads approvals from the local `origin/main`, so a stale ref hides new approvals; this errs toward more findings, never fewer. `docs/tools/AUDIT_GATE.md` will say to run `git fetch origin main` first. The gate fetches only when `origin/main` is missing, as the hooks do.
6. **Fast-suite runtime.** About 60 fixture-repo tests may take roughly 30 to 90 s, and the Stop hook runs them at every stop, within its 600 s limit.
7. **Duplicate CI runs.** With `on: [push, pull_request]`, each push to a PR branch runs CI twice. That is free on public repositories but uses Actions minutes on private ones.

**Questions**
1. **Which IDs does `--wp` traceability cover?** I propose:
   - `FR-` and `NFR-` IDs must appear in PLAN.md, in a test function name and in EVIDENCE.md.
   - `AT-` and `OC-` IDs only need PLAN.md and EVIDENCE.md, because acceptance commands and owner checks such as "CI is green" cannot honestly be test functions.
   - Only IDs carrying the WP's own number count, so `FR-0.2-03` inside the WP-0.0 spec is ignored.

   Alternatives are FR and NFR only, or all four prefixes including test names.
2. **Approvals edge case (risk 2).** Keep the spec's `origin/main` for the gate and accept that the Stop hook differs only on a branch that has not merged the latest `main`? Or should the gate read approvals at the merge-base, as the hook does? I recommend keeping `origin/main`.
3. **Harness baseline scope.** I propose:
   - Baseline = `tests/regression`, run on Python 3.13 (the Colab version; the harness records no version) in a throwaway venv outside the repository.
   - That venv gets `requirements/base.txt`, `corpus.txt` and `tier2.txt` as they are, plus `pytest` and `pytest-asyncio`, which the harness needs but lists nowhere.
   - `tier1.txt` is not installed: it needs `github.com`, which is blocked, and the regression tests do not import it.
   - `tests/smoke_test_tier1` is recorded as **not run**, with the reason: it is not a pytest suite, it uses absolute `/workspaces` paths, and it overwrites a tracked results file, so it cannot run read-only.

   Do you agree, or do you want it handled differently?
4. **CI actions.** I plan `actions/checkout@v4` and `astral-sh/setup-uv@v6` with uv pinned to `0.8.17`, the same version as this VM, referenced by version tag. `github.com` is blocked here, so I cannot look up commit SHAs. Is tag pinning acceptable? If not, send the SHAs you want.
5. **Defaults.** I will apply these unless your approval says otherwise:
   - (a) Package version `0.0.1`.
   - (b) `+dirty` also counts untracked, non-ignored files, which is stricter than `git describe --dirty`.
   - (c) `version` exits 1 with a clear error when it is not run inside a git checkout, rather than printing an unknown commit.
   - (d) The lock is `--universal`, so the same pins install on x86_64 (VM, Colab) and on Arm, in case the Oracle VM is Arm.
   - (e) `pyyaml` is added to `phase0.in` so the CI workflow can be tested by parsing it.
   - (f) "Changes since `<ref>`", including the registry's "rows present at `<ref>`", mean since `git merge-base <ref> HEAD`, which is what the Stop hook and a GitHub PR diff use.
   - (g) Line-number conventions for file-level findings, as in "Gate rules" above.

## Owner decisions (2026-09-25, in session chat)
1. Traceability: `FR-`/`NFR-` IDs in PLAN.md, a test function name and EVIDENCE.md; `AT-`/`OC-` IDs in PLAN.md and EVIDENCE.md only; only the WP's own IDs count. **Agreed.**
2. The gate reads approvals from `origin/main`, as the spec says; the Stop-hook difference on a branch that has not merged the latest `main` is accepted. **Agreed.**
3. Harness baseline setup as proposed (Python 3.13, throwaway venv outside the repo, base/corpus/tier2 plus pytest and pytest-asyncio, no tier1, `tests/smoke_test_tier1` recorded as not run with reasons). **Agreed.**
4. CI actions pinned by version tag: `actions/checkout@v4`, `astral-sh/setup-uv@v6`, uv 0.8.17. **Agreed.**
5. Defaults (a) to (g) in question 5. **Agreed.**

## Deviations
None. The interpretations I need you to confirm are questions 1 to 5 above; nothing will be built differently from the spec without your answer.
