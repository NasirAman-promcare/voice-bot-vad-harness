# WP-0.0 — Guardrails and audit tooling

- **Depends on**: none
- **Runs on**: cloud VM and GitHub Actions
- **Read first**: `CLAUDE.md`, `.claude/rules/`, `docs/process/`, `.claude/hooks/*.py`, `docs/environment/colab_probe.txt`

## Goal
Give every later WP an automated safety net: a lab package skeleton, an environment that matches Colab, an audit gate that catches compromise and scope violations, continuous integration on GitHub, and a recorded baseline of the existing harness tests.

## Deliverables
- `aqis_lab/__init__.py`, `aqis_lab/__main__.py` (command dispatcher), the `version` command
- `aqis_lab/deploy/dev_bootstrap.sh`
- `requirements/aqis_lab/phase0.in` and `phase0.txt`
- `tests/aqis_lab/conftest.py` registering markers
- `tools/__init__.py`, `tools/audit/__init__.py`, `tools/audit/gate.py`, `tools/audit/patterns.py`
- `.github/workflows/aqis-lab-ci.yml`
- `docs/baselines/harness_tests_baseline.md`, `docs/tools/AUDIT_GATE.md`

## Functional requirements
- **FR-0.0-01** `python -m aqis_lab version` prints the package version, the short git commit (with `+dirty` when uncommitted changes exist) and the Python version, and exits 0.
- **FR-0.0-02** `aqis_lab/deploy/dev_bootstrap.sh` creates `.venv` with the exact Python major.minor from `docs/environment/colab_probe.txt` using uv, installs `phase0.txt` with hash checking, and is idempotent: a second run with nothing changed makes no changes and finishes within 30 s. It fails with a clear message if the probe file is missing or unreadable.
- **FR-0.0-03** `phase0.txt` pins every package with hashes and is generated from `phase0.in`; it includes pytest, jsonschema and everything WP-0.0 needs. The regeneration command is documented.
- **FR-0.0-04** Lab tests are discovered from `tests/aqis_lab/` with all five markers registered, without changing how existing harness tests are discovered or run.
- **FR-0.0-05** `python -m tools.audit.gate --base <ref> [--wp <WP-ID>] [--json]` checks changes since `<ref>` plus uncommitted work for: (a) protected paths per `docs/process/PROTECTED_PATHS.txt`, with approvals read from `origin/main`; (b) existing tests modified or deleted without `ALLOW-EDIT`; (c) compromise patterns in added lines of `aqis_lab/` and `tools/` code, and skip, xfail or trivial asserts in `tests/aqis_lab/`; (d) CAPABILITIES headers in new `aqis_lab/` modules; (e) registry consistency; (f) requirement traceability when `--wp` is given. It exits 0 only when nothing is found.
- **FR-0.0-06** Checks (a) to (d) match the Stop hook exactly. A parity test runs the gate and `.claude/hooks/stop_gate.py` on the same fixture repositories and asserts identical findings.
- **FR-0.0-07** `# audit-allow: <reason>` exempts one line only when a reason is present; the gate lists every exempted line. `ALLOW-PATTERNS-IN` approvals exempt whole files and are listed too.
- **FR-0.0-08** Registry consistency: every row in `docs/capabilities/REGISTRY.md` names tests that exist and a module that exists, and no row present at `<ref>` is missing.
- **FR-0.0-09** Traceability with `--wp`: every requirement ID in that WP's spec appears in its `PLAN.md`, in at least one test function name (with `FR-0.2-03` matching `FR_0_2_03`), and in its `EVIDENCE.md`.
- **FR-0.0-10** CI runs on push and pull request: it sets up the Colab-matching Python, installs the lock with hashes, runs the fast lab suite, and runs the gate against the pull request base (or `origin/main` on push). It must not change or trigger any other workflow.
- **FR-0.0-11** Harness regression baseline: find how the existing harness tests run (read-only), run them without modifying anything, and record the command, environment and per-test results in `docs/baselines/harness_tests_baseline.md`. Record failures; never fix them in this WP.

## Non-functional requirements
- **NFR-0.0-01** Gate runtime under 60 s on this repository, excluding test execution.
- **NFR-0.0-02** Every gate message names `file:line` and the rule broken.
- **NFR-0.0-03** Standard library plus pinned dependencies only.

## Acceptance commands
- **AT-0.0-01** `bash aqis_lab/deploy/dev_bootstrap.sh && .venv/bin/python -m aqis_lab version`
- **AT-0.0-02** `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"`, including fixture-repository tests proving each gate check detects its violation and passes clean input
- **AT-0.0-03** `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` exits 0 on this branch
- **AT-0.0-04** The CI run on the pull request is green

## Owner-run checks
- Confirm the CI run is green in the GitHub Actions tab of the pull request.

## Owner needs
- `docs/environment/colab_probe.txt` committed before the build.
- The approval for this WP must include `ALLOW-PATTERNS-IN: tools/audit/patterns.py` and `ALLOW-PATTERNS-IN: tests/aqis_lab/fixtures/**`, because those files legitimately contain the forbidden patterns.

## Out of scope
Contracts, adapters, and Colab or Oracle code.

## Stop and ask if
- Harness tests cannot run read-only or need services such as Jitsi or network access.
- Lab test discovery would change how harness tests behave.
- uv cannot install the probe's Python version.
