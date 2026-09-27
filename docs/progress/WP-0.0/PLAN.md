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

---

# Round 2 — after audit round 1 (planned 2026-09-25)

Inputs: `docs/progress/WP-0.0/AUDIT.md` (verdict FAIL, findings WP-0.0-F01 to F10); `docs/specs/phase-0/WP-0.0-guardrails.md` "Amendment 1"; Stop hook version 2 (`.claude/hooks/stop_gate.py`, kit patch 1, `origin/main` `ae73c4f`). `origin/main` was merged into this branch before planning (commit below). No code, tests, locks or configuration were changed while planning.

## State of the branch right now
- After merging patch 1, the fast suite is `1 failed, 82 passed`. The failing test is `test_FR_0_0_06_pattern_tables_identical_to_stop_hook`: the hook's `LAB_CODE_DIRS` and `CODE_PATTERNS` changed (new "errors silenced in shell" pattern). This is the parity test doing its job. The Stop hook now reports this failure, and **CI on PR #1 will be red from this push until the Round 2 build lands.** Nothing else in hook v2 flags this branch (I ran it read-only).
- The 16 fixture parity scenarios still agree, because none of them uses the file types or patterns that hook v2 added.

## Hook version 2: what the gate must now match (FR-0.0-06 amended)
Read from `.claude/hooks/stop_gate.py` v2 and `_protected.py`:
1. **Scan scope (check c).**
   - Code patterns apply to added lines of files under `aqis_lab/`, `tools/`, `config/aqis_lab/`, `requirements/aqis_lab/` and `.github/workflows/aqis-lab-*.yml`.
   - The file suffix must be one of `.py .sh .bash .yml .yaml .toml .cfg .ini .in`.
   - Test patterns apply only to `.py` files under `tests/aqis_lab/`.
2. **New code pattern** `errors silenced in shell`: `\|\|\s*true\b|2>\s*/dev/null`.
3. **Test skip pattern** loses the leading `@`: `pytest\.mark\.skip(?:if)?\b`. This is what catches module-level `pytestmark = pytest.mark.skip...` and `pytest.param(..., marks=pytest.mark.skip)`.
4. **Status mapping**: `?` or `A` in the status code now means added, checked before `D`. A file staged as added and then deleted in the worktree (`AD`) counts as added, not deleted.
5. **Decoding**: all git output and file content is decoded as UTF-8 with replacement, and `git diff` runs with `--text`.
6. **Header check (d)** only for `.py` files under `aqis_lab/`.
7. **Fail closed**: git and read errors become `GATE ERROR` problems, never a pass. The gate expresses the same thing as exit code 2.
8. **Approvals**: without a verified main reference, no approval counts (`_protected.approval_texts`).

## Findings: root cause, fix, proving test
| Finding | Root cause | Fix | Proving test (fails on the auditor's mutation or the defect, passes after) |
| --- | --- | --- | --- |
| **F01** CRITICAL, FR-0.0-02 not guarded against a hard-coded Python | Every FR-0.0-02 test either used the real 3.13 probe or failed before the parsed version was used, so `PY="3.13"` passed everything | No code change; the script is correct | New fast test `test_FR_0_0_02_uses_version_named_by_probe`. A probe says `Python Version: 3.99.1`. Assert a non-zero exit, `ERROR:`, `Python 3.99` in stderr and no `.venv` (offline, under 1 s). Show it fails under the mutation `PY="3.13"`. |
| **F02** CRITICAL, "approvals from `origin/main`" not guarded | `FixtureRepo.approve_on_main` always merged `origin/main` into the branch, so the merge-base always equalled `origin/main` | No gate change. Add a fixture helper option that commits to `main` **without** merging into the branch | Two new tests. `test_FR_0_0_05_a_uses_approval_added_on_main_after_branch_point`: no A2. `test_FR_0_0_05_a_honours_withdrawal_on_main_after_branch_point`: A2. Both must fail under the mutation `load_approvals(git, base)`. |
| **F03** CRITICAL, `+dirty` not guarded for staged changes | The test covered only unstaged edits and untracked files | No code change (`git status --porcelain` already covers staged changes) | Extend `test_FR_0_0_01_version_marks_dirty_tree`: a staged edit gives `+dirty`, and a staged deletion gives `+dirty`. Must fail under the auditor's mutation (`git diff --name-only` plus untracked). This branch-only test is strengthened, not loosened; it does not exist on `main`, so no `ALLOW-EDIT` is involved. |
| **F04** MAJOR, the gate fails open on I/O and git errors | I copied the hook v1 behaviour (silent `[]`) in `load_protected`, `added_lines`, `first_changed_line` and the D1 read | Raise `GateError` (exit 2, `ERROR:` naming the path) when:<br>- `PROTECTED_PATHS.txt` exists but cannot be read;<br>- a changed lab file cannot be read or is not a regular file (a dangling symlink, for example);<br>- any `git diff` or `git show` returns non-zero.<br>A missing `PROTECTED_PATHS.txt` is also an error (see difference G2 below). Document this in `AUDIT_GATE.md`. | `test_FR_0_0_06_fails_closed_on_unreadable_changed_file` (dangling symlink `aqis_lab/x.py`: exit 2, `ERROR:`, path named); `test_FR_0_0_06_fails_closed_when_protected_paths_unreadable`; `test_FR_0_0_06_fails_closed_on_git_error` (a corrupt object for a changed path, or a `--base` that becomes unreachable mid-run, whichever I can trigger deterministically without test doubles) |
| **F05** MINOR, the FR-0.0-04 proof is weak in the lab venv | Harness modules cannot import in the lab `.venv` | Amendment 1 adds a provisioned harness env (FR-0.0-12). Record in EVIDENCE the combined run `python -m pytest tests/regression tests/aqis_lab -m "not slow and not network"` in `.venv-harness`, showing harness outcomes identical to the baseline. The docstring of `test_FR_0_0_04_harness_collection_unchanged` states what the test can and cannot detect. Its pytest subprocesses get `PYTHONDONTWRITEBYTECODE=1`. | The CI `harness-regression` job (FR-0.0-11 amended) runs the harness and lab tests together, with the harness outcome compared against the baseline |
| **F06** MINOR, headers and registry disagree | Headers and registry rows were written separately, and nothing compares them | Sync them:<br>- The CAP-AUDIT-005 to 009 test lists.<br>- Full headers for `aqis_lab/commands/__init__.py`, `tools/__init__.py` and `tools/audit/__init__.py`; a field may say "none".<br>- `ALLOW_REASON_RE` added to CAP-AUDIT-008. | New lab test `test_FR_0_0_08_module_headers_match_registry`: for every module named in a registry row, the header's `CAP-…: … [tests: …]` entry equals the registry row's test list |
| **F07** MINOR, EVIDENCE gaps | NFR sections quoted no commands or output; commit `3f7d52a` held the whole gate, including checks (e) and (f), before their tests | Add the exact commands and real output for NFR-0.0-01/02/03. Correct the history account: the (e), (f) and FR-0.0-07 code landed in `3f7d52a` before their tests were committed, and commit titles `b8bbe52` to `b2067a0` describe their test files only. I will not rewrite pushed history. In Round 2, each fix is committed test-first as a separate commit (test commit showing the failure, then fix commit), so the order can be checked from `git log`. | Evidence entries; `git log --stat` |
| **F08** MINOR, additions outside the approved plan | Added during the build without asking | Nothing to build. **Owner acknowledgement requested:**<br>- `tests/aqis_lab/aqis_testutil.py`<br>- Registry rows CAP-CLI-003, CAP-BASE-001, CAP-AUDIT-009<br>- `test_FR_0_0_08_detects_missing_registry` | Your Round 2 approval |
| **F09** MINOR, error-reporting gaps | Strict UTF-8 decoding; `repository_root` does not catch `TimeoutExpired`; F1 cites a folder | Decode all git output and file content with `errors="replace"`, as amended FR-0.0-06 requires. Catch `TimeoutExpired`. F1 cites the searched glob `docs/specs/**/<WP>-*.md:1`. | `test_FR_0_0_06_decodes_non_utf8_with_replacement` (a Latin-1 `\xe9` byte added to a lab `.py` together with a compromise word: the finding is reported, exit 1, no traceback; the parity test compares with the hook on the same fixture). F1 assertion added to `test_FR_0_0_09_reports_unknown_wp`. |
| **F10** MINOR, the test pins the literal `0.0.1` | The owner default was asserted inside the behavioural test | Drop the literal. The test keeps the independent AST read of `__version__`. The default stays recorded in this plan (decision 5a). | Existing FR-0.0-01 test, now free of the literal |

## Amendment 1: amended and new requirements

### FR-0.0-06 (amended): gate matches hook v2, fails closed, wider scan
- **Approach.** Update `tools/audit/patterns.py` to the v2 tables. In `tools/audit/gate.py`:
  - Scan scope, suffixes and CI files as listed under "Hook version 2" above.
  - The new status mapping.
  - Replacement decoding and `--text`.
  - `.py`-only header check.
  - Fail-closed errors (exit 2).
  - Approvals only from `origin/main`: fetch once if missing; if still unverifiable, use **no** approvals and print `approvals: none (origin/main not verifiable)`, with `approvals_commit: null` in JSON.
- **Parity tests.** They extend to new scenarios:
  - A `.sh` file with `|| true` and one with `2>/dev/null` under `aqis_lab/deploy/`.
  - A `requirements/aqis_lab/*.in` file with a TODO.
  - An `aqis-lab-*.yml` workflow with `|| true`.
  - A `config/aqis_lab/*.toml`.
  - A lab test using `pytestmark = pytest.mark.skip`.
  - An `AD` status file.
  - A non-UTF-8 file.

  Fixture content with these patterns lives only under `tests/aqis_lab/fixtures/` (covered by `ALLOW-PATTERNS-IN`).
- **Differences from hook v2 that the amendment itself requires.** I need you to accept these (see "What I need"):
  - **G1.** Approvals come from `origin/main`; the hook reads them at the merge-base. The known and accepted difference, restated in Amendment 1.
  - **G2.** Unreadable or missing `PROTECTED_PATHS.txt`, or a changed lab file that is not a regular file (such as a dangling symlink): the gate exits 2. The hook uses the built-in NEVER list, or silently skips the file (`added_lines` returns `[]` when `is_file()` is false). The parity tests compare findings only on readable repositories, and for error cases assert that the gate exits 2.
- **Tests.**
  - `test_FR_0_0_06_parity_with_stop_hook_on_fixture_repos`, with the new scenarios added.
  - `test_FR_0_0_06_pattern_tables_identical_to_stop_hook`, extended to scan dirs, suffixes and the CI-file glob.
  - The fail-closed and decoding tests listed under F04 and F09.
  - `test_FR_0_0_06_approvals_none_when_origin_main_unverifiable`.

### FR-0.0-10 (amended): WP ID from the PR title
- **Approach.** The CI job gets the PR title through `env` (never inline). It requires the regex `^WP-[0-9]+\.[0-9]+(?=[ :]|$)` and exits 1 with a clear message when the ID is missing. Push events still run the gate without `--wp`.
- **Tests.** `test_FR_0_0_10_ci_takes_wp_from_pr_title` checks the workflow structure. `test_FR_0_0_10_pr_title_parser` runs the exact shell snippet from the workflow against sample titles:
  - `WP-0.0 Guardrails` passes, giving `WP-0.0`.
  - `Guardrails` fails.
  - `WP-0.0x` fails.
- **Note.** PR #1's title, `WP-0.0 Guardrails and audit tooling`, already complies.

### FR-0.0-11 (amended): baseline again in a provisioned env, plus a CI regression job
- **Approach.** Keep the first baseline as a "History (round 1)" section. Add a new "Provisioned baseline (round 2)" recorded in `.venv-harness` on the cloud VM after FR-0.0-12. New stdlib tool `tools/harness/regression_check.py` compares a JUnit XML file with the baseline's results table. It exits 1 when any test that **passed** in the baseline now fails or errors or is missing; it lists newly passing tests as information. New CI job `harness-regression`:
  - checkout;
  - uv;
  - `bash aqis_lab/deploy/harness_provision.sh`;
  - run the harness tests with JUnit output;
  - `python -m tools.harness.regression_check`.
- **Tests.**
  - `test_FR_0_0_11_regression_check_flags_newly_failing_baseline_pass`
  - `test_FR_0_0_11_regression_check_passes_same_or_better`
  - `test_FR_0_0_11_regression_check_rejects_unreadable_inputs`
  - `test_FR_0_0_11_ci_has_harness_regression_job`
  - The existing baseline tests, extended to require both sections.

### FR-0.0-12 (new): `aqis_lab/deploy/harness_provision.sh`
**(a) System packages.**
- Check each package with `dpkg -s`: `git-lfs`, `libc++1`, `libopus0`.
- Install the missing ones with `apt-get install -y`, running `apt-get update` first only when something is missing. Prefix with `sudo` when not root; if sudo is not available, stop with an error.
- On this VM, `git-lfs` and `libc++1` are **missing** and `libopus0` is present, so this session was started before your updated setup script took effect. The script installs them as root either way.

**(b) Python.**
- `uv venv --seed --python <probe major.minor> .venv-harness`, with `--seed` because `run_phase.py` calls `sys.executable -m pip`.
- `.venv-harness/bin/python scripts/run_phase.py install all`: the harness's own command, installing `base`, `corpus`, `tier1`, `tier2` and `report` unchanged.
- `pip install --require-hashes -r requirements/aqis_lab/harness-extras.txt`, generated from `harness-extras.in` by `uv pip compile --universal --python-version 3.13 --generate-hashes`:
  - `pytest`, `pytest-asyncio` and `opuslib` plus their dependencies;
  - versions checked against the Colab probe's Python 3.13.
- Findings:
  - `.venv-harness/` is not covered by `.gitignore`, but `uv venv` writes its own `.gitignore` containing `*` inside it (verified in round 1), so no guarded edit is needed.
  - `tier1.txt` installs `ten-vad` from `git+https://github.com/TEN-framework/ten-vad.git` **without a commit pin**; `github.com` git is reachable from here (HTTP 200). This makes the harness environment non-reproducible over time. I cannot pin it without editing guarded `requirements/tier1.txt`, so I record the resolved commit (`pip freeze`) in the baseline.
  - `vad_adapters/firered_vad_adapter.py` imports `torch`, which no harness requirement installs; `fireredvad` lists torch only as an extra. The regression tests do not import it (see question R2-3).

**(c) Data into a cache outside the tree** (`${AQIS_CACHE:-$HOME/.cache/aqis}`), with pins recorded in a new lab config file `config/aqis_lab/harness_assets.json`:
- **Corpus.** There is **no GitHub release** on this repository (`list_releases` is empty). `corpus-v1` exists only as a **git tag** (commit `a3ebbf8`, 2026-09-14). The archive is **committed** at the repository root as `corpus-v1.tar.gz`: blob `4234c5f`, identical at the tag and at HEAD, 46,353,268 bytes, sha256 `ef4d5da1e30f6a296f84fb59d38bdb5644a9d3b41ac930b9a3e4e5dae64efbbb`. See question R2-1 for where the script should take it from.
- **FireRedVAD weights.** Hugging Face `FireRedTeam/FireRedVAD` (Apache-2.0), pinned to commit `7990aaccc6b7aec1e527743bd30201f2c4a03b8c`.
  - Fetch with `git clone` plus `git lfs pull --include "Stream-VAD/*"` at that commit. Verify each file's sha256 against its LFS object ID; for example, `Stream-VAD/model.pth.tar` is `ec88a8ae8ac5f004cdbd20c1eac4a9e9d12067c3d51ac5b141afa1f921fb59c9`, 2,283,513 bytes. Reject any file that still starts with `version https://git-lfs` (a pointer file).
  - Reachable from here: `git ls-remote` works, and LFS content redirects to `us.aws.cdn.hf.co` (HTTP 206 on a range request).
  - Only `Stream-VAD/` is fetched, because that is what the adapter loads by default; `AED/` and `VAD/` are not.

**(d) Where the harness expects the data** (inspected read-only):
| Data | Where the harness reads it | Git status of that path | How provisioning makes it available |
| --- | --- | --- | --- |
| Corpus clips | `corpus/manifest.json` (tracked, 229 entries); every `clip_path` is `corpus/audio/<name>.wav`, relative to the repository root (`corpus/dataset_builder.py`, `config/run_config.yaml` `corpus_manifest_path`) | `/corpus/audio/` is ignored (`.gitignore:4`) | Create the real directory `corpus/audio/` and put in it one symlink per clip, pointing into the cache (files inside an ignored directory stay ignored). A symlink *named* `corpus/audio` would **not** be ignored, because the pattern has a trailing slash, so I do not use one. |
| Corpus manifest | `corpus/manifest.json` (tracked) | tracked | Not written. The archive's copy is byte-identical to the tracked file (verified with `cmp`); the script re-verifies this and fails if they ever differ. |
| Corpus build log | `corpus/build/recipe_log.json` (not read by the tests or the tier 1 path) | `/corpus/build/` is ignored | Not placed |
| FireRedVAD weights | `FIREREDVAD_MODEL_DIR`, else `pretrained_models/FireRedVAD/Stream-VAD` relative to the working directory (`vad_adapters/firered_vad_adapter.py:138-139`) | `pretrained_models/` is ignored (`.gitignore:68`) | Create the real directory `pretrained_models/FireRedVAD/` and a symlink `Stream-VAD` inside it, pointing to the cache |
| TEN VAD model | Bundled in the `ten-vad` package (`libten_vad.so` via ctypes; needs `libc++1`) | — | Installed by (a) and (b) |
| Harness test outputs | `tmp_path` only; `results/run_output/` is ignored | — | No tracked writes at runtime (`tests/smoke_test_tier1` is still not run, owner decision 3) |

No `ALLOW-EDIT: .gitignore` is needed.

**(e) Idempotent.**
- apt is skipped when all packages are present, and the venv is kept when its Python matches.
- Assets are skipped when the cached files match their sha256.
- `run_phase.py install all` would re-clone `ten-vad` from git on every run, which counts as a download. So the script skips the install when a stamp file inside `.venv-harness` records the same sha256 of every harness requirement file plus `harness-extras.txt`, **and** `pip check` passes.
- Test: the second run downloads nothing and finishes in under 60 s.

**(f) Report and safety.**
- It prints a PASS/FAIL table of the steps and exits 1 if any step fails.
- It checks `git status --porcelain` is empty at the end, and never reads, writes or logs a GitHub token.
- It uses no `|| true` and no `2>/dev/null`; the hook v2 pattern enforces this on `.sh` files.

**New files.**
- `aqis_lab/deploy/harness_provision.sh`
- `requirements/aqis_lab/harness-extras.in` and `harness-extras.txt`
- `config/aqis_lab/harness_assets.json`
- `tools/harness/__init__.py` and `tools/harness/regression_check.py`
- `tests/aqis_lab/test_aqis_harness_provision.py` and `test_aqis_harness_regression.py`

**Tests.**
- Fast tests, each running the real script in a throwaway tree:
  - `test_FR_0_0_12_fails_on_asset_checksum_mismatch`
  - `test_FR_0_0_12_rejects_lfs_pointer_file`
  - `test_FR_0_0_12_places_data_only_in_ignored_paths` (uses a small local corpus archive built in the test and a local git repository standing in for the Hugging Face remote, both through the script's real code paths with overridable asset sources in `harness_assets.json`)
  - `test_FR_0_0_12_manifest_mismatch_is_an_error`
- Slow and network tests on the real assets:
  - `test_FR_0_0_12_provisions_harness_end_to_end`
  - `test_FR_0_0_12_second_run_downloads_nothing_within_60s`
  - `test_FR_0_0_12_leaves_git_status_clean`
- `test_FR_0_0_12_never_writes_token` greps the script and runs it with a sentinel `GITHUB_TOKEN`, asserting the value appears nowhere under the tree, `.git/config` or the cache.

**Acceptance.** AT-0.0-05 and AT-0.0-06, below.

### FR-0.0-13 (new): `docs/colab/HARNESS_SETUP.md`
**Colab cells.**
1. Read `GITHUB_TOKEN` with `google.colab.userdata.get`.
2. Clone with a one-off `-c http.extraHeader=Authorization: Basic <base64(x-access-token:TOKEN)>`, so the token is used for that command only and never stored in `.git/config` or the remote URL. Then show `git config --list --show-origin` contains no token.
3. Install uv 0.8.17 if it is missing.
4. Run `bash aqis_lab/deploy/harness_provision.sh`.
5. Save the output to `docs/environment/colab_harness_provision.txt`.

**Test.** `test_FR_0_0_13_colab_doc_cells` parses the document's code cells. It checks:
- the token comes from Colab secrets;
- the token is never interpolated into a URL or `git config`;
- the provisioning command is present;
- the script writes the output to the path that OC-0.0-01 expects.

**Owner check.** OC-0.0-01.

### Acceptance commands added
- **AT-0.0-05.** Run `bash aqis_lab/deploy/harness_provision.sh` twice, then `git status --porcelain`. The second run's table shows 0 downloads, and git status is empty after both runs.
- **AT-0.0-06.** `PYTHONDONTWRITEBYTECODE=1 .venv-harness/bin/python -m pytest tests/regression -rA -p no:cacheprovider --junitxml=<outside repo>`. No import or collection errors; results recorded in the baseline.
- **AT-0.0-07.** The CI `harness-regression` job is green on PR #1.
- **AT-0.0-08.** An EVIDENCE table maps F01 to F10 to their proving test or evidence. The auditor's F01 to F03 mutations are re-run in a scratch clone and must now make tests fail.

## Change budget for Round 2 (existing files and functions)
| File | Functions or parts that change |
| --- | --- |
| `tools/audit/gate.py` | `Git.run` (decode with replacement), `repository_root` (`TimeoutExpired`), `load_protected` (fail closed), `resolve_approvals_ref` and `run_gate` (no approvals when unverifiable, notice in report), `changed_files` (v2 status mapping), `added_lines` (`--text`, replacement, fail closed), `first_changed_line` (return-code check), `check_patterns_and_headers` (v2 scope and suffixes, `.py`-only header, fail closed), `check_traceability` (F1 citation), `test_functions` (decoding), `render_text`/`to_json` (approvals notice), module header |
| `tools/audit/patterns.py` | `CODE_PATTERNS` (new shell pattern), `TEST_PATTERNS` (skip regex), new constants for scan dirs, suffixes and the CI glob; header |
| `aqis_lab/commands/__init__.py`, `tools/__init__.py`, `tools/audit/__init__.py` | Docstring header only (F06) |
| `.github/workflows/aqis-lab-ci.yml` | Gate step (PR-title WP ID); new job `harness-regression` |
| `tests/aqis_lab/fixture_repo.py` | `approve_on_main` gains a no-merge option (F02); new scenario helpers |
| `tests/aqis_lab/test_aqis_*.py` (branch-only files, none on `main`) | Add tests; F03 strengthening; F10 literal removal; F05 docstring and environment; parity scenarios. No test is loosened or skipped. |
| `docs/baselines/harness_tests_baseline.md` | Round 1 content moved under "History (round 1)" unchanged; new "Provisioned baseline (round 2)" |
| `docs/tools/AUDIT_GATE.md` | v2 scope, fail-closed behaviour, differences G1 and G2, `--wp` in CI |
| `docs/capabilities/REGISTRY.md` | New rows (CAP-ENV-003 provisioning, CAP-ENV-004 harness-extras lock, CAP-HARN-001 regression check, CAP-CI-002 harness-regression job, CAP-DOC-001 Colab setup); CAP-AUDIT test lists synced (F06). No row removed. |
| `docs/progress/WP-0.0/EVIDENCE.md`, `STATUS.md` | Round 2 evidence; status |

Unchanged: `aqis_lab/deploy/dev_bootstrap.sh` and `aqis_lab/commands/version.py` (F01 and F03 need tests only), and every protected harness path.

## Risks
1. **CI is red on PR #1** from this push (hook v2 parity test) until the Round 2 build lands. This is expected and explained above.
2. **Harness dependency drift.** The harness requirement files are unpinned and `ten-vad` is unpinned git. A future `install all` may resolve different versions, and the `harness-regression` job may fail for reasons unrelated to a PR. The recorded freeze makes that visible, but only you can pin those guarded files.
3. **Hugging Face storage.** LFS downloads now go through Xet (`us.aws.cdn.hf.co`). If `git lfs pull` ever stops working through the proxy, I will raise a blocker naming the exact host rather than switching sources.
4. **The `test_loss_category` failure** carries over into the provisioned baseline if it still fails there. It is a "failed" baseline test, so it does not fail the regression job.
5. **CI cost.** The `harness-regression` job installs the full harness (`jupyter`, `aiortc` and more) on every push and PR: a few minutes of Actions time per run.

## What I need from you (before `/wp-build` Round 2)
1. **R2-1, corpus source.** No GitHub release named `corpus-v1` exists; the tag exists and the archive is committed in the repository. Choose one:
   - **(A, recommended)** Provisioning takes `corpus-v1.tar.gz` from git at tag `corpus-v1` (`git show corpus-v1:corpus-v1.tar.gz`, or the identical tracked file) and verifies its sha256. No network is needed and there is no token handling anywhere. This deviates from the amendment's wording "release asset".
   - **(B)** You publish a GitHub release on tag `corpus-v1` with that file as its asset, and provisioning downloads it. On a private repository this needs a token on the VM and in CI. Tell me the asset name.
2. **R2-2, accept the gate/hook differences G1 and G2** (approvals ref; fail-closed on unreadable or non-regular files where hook v2 silently skips).
3. **R2-3, torch.** `vad_adapters/firered_vad_adapter.py` imports `torch`, and nothing installs it. The regression tests do not need it. Choose one:
   - **(A, recommended)** Provisioning does not install torch. It is outside Amendment 1's list; Colab already has torch 2.11.
   - **(B)** Add a pinned CPU torch to `harness-extras` (a large download; host `download.pytorch.org` would have to be allowed).
4. **R2-4, acknowledge the F08 additions**: `tests/aqis_lab/aqis_testutil.py`, registry rows CAP-CLI-003, CAP-BASE-001 and CAP-AUDIT-009, and the test `test_FR_0_0_08_detects_missing_registry`.
5. **R2-5, a new approval on `main`** for this Round 2 plan (Amendment 1: "An updated approval once the Round 2 plan is ready"), keeping both `ALLOW-PATTERNS-IN` lines. For example, update `docs/approvals/WP-0.0.md` with a `PLAN: docs/progress/WP-0.0/PLAN.md (Round 2)` line and your R2-1 to R2-4 answers under `CONDITIONS:`. No `ALLOW-EDIT` is needed.
6. **Cloud environment.** Add the patch-1 setup script and hosts (`huggingface.co`, `*.huggingface.co`, `*.hf.co`) to `aqis-lab`. This session still lacks `git-lfs` and `libc++1`; provisioning will install them itself, but the next session should start with them.
7. **After the build.**
   - Run OC-0.0-01 in Colab (the cells from `docs/colab/HARNESS_SETUP.md`) and commit `docs/environment/colab_harness_provision.txt`.
   - Confirm AT-0.0-04 and AT-0.0-07: both CI jobs green on PR #1.

## Round 2 correction (2026-09-25, during the build)
In FR-0.0-12(c) and question R2-1 I stated that the committed archive `corpus-v1.tar.gz` is "blob `4234c5f`, identical at the tag and at HEAD". **That is wrong.** Tag `corpus-v1` (`a3ebbf8`) does not contain the archive. Blob `4234c5f` (sha256 `ef4d5da1…`) was committed in `1479626` on 2026-09-17. An older, different archive (`832c8d3f…`, manifest differs from the tracked one) was committed in `52ab506`. Your decision R2-1 was based on my wrong statement, so it is re-opened as BLK-005 in `docs/progress/BLOCKERS.md`.
