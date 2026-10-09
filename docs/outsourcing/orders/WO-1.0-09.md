---
id: WO-1.0-09
wp: WP-1.0
title: CI workflows for generation, break suite, scope, main guard, mutation and kit parity
model: gemini-3.7-flash
channel: api
attempt_budget: 3
risk_tier: T1
max_output_tokens: 60000
context:
  - docs/process/AUTONOMY.md
  - docs/process/PARALLEL.md
  - docs/process/CHANGE_CONTROL.md
  - docs/process/CONTEXT_BUDGET.md
  - tools/index/__main__.py
  - tools/progress/__main__.py
  - tools/audit/breaks.py
  - tools/audit/mutation_report.py
  - tools/outsourcing/__main__.py
outputs:
  - .github/workflows/aqis-lab-generate.yml
  - .github/workflows/aqis-lab-breaks.yml
  - .github/workflows/aqis-lab-scope.yml
  - .github/workflows/aqis-lab-main-guard.yml
  - .github/workflows/aqis-lab-mutation.yml
  - .github/workflows/aqis-lab-kit-parity.yml
  - tools/ci/__init__.py
  - tools/ci/refs.py
  - tools/ci/main_guard.py
  - tools/ci/kit_parity.py
  - tests/aqis_lab/ci/__init__.py
  - tests/aqis_lab/ci/test_refs.py
  - tests/aqis_lab/ci/test_main_guard.py
  - tests/aqis_lab/ci/test_kit_parity.py
  - tests/aqis_lab/ci/test_workflows.py
read_only_tests:
  - tests/aqis_lab/ci/test_acceptance_wo_1_0_09.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/ci -q --tb=short
---

# WO-1.0-09 — CI workflows for generation, break suite, scope, main guard, mutation and kit parity

**Before sending (Claude):** add the existing `.github/workflows/aqis-lab-*.yml` files to `context`, and state in section 1 which Python setup and bootstrap steps they use, so the new workflows install the environment the same way.

## 1. Context
The lab's tables and map are generated on `main` only, break recipes must run on every pull request and nightly, outsourced branches need a scope check, `main` needs a guard that flags commits that did not come through the merge gate, mutation reports are advisory, and installed hooks must match the audited staged copies. Workflow files matching `.github/workflows/aqis-lab-*.yml` are lab-owned. Logic lives in small Python modules under `tools/ci/` so it can be unit-tested; the workflows only call them.

## 2. Your job
Six workflows and three helper modules, with tests.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/ci/refs.py` | Derive the WP and the work order from a branch name | `wp_from_branch(name) -> str or None` (`claude/wp-1-3-x` → `WP-1.3`); `wo_from_branch(name) -> str or None` (`wo/WO-1.3-02` → `WO-1.3-02`) | 80 |
| `tools/ci/main_guard.py` | Classify each new commit on `main` | `classify(commit_facts) -> GuardResult` (`gated-merge`, `bot-regeneration`, `owner-never-edit`, `unexpected`); `main(argv) -> int` gathers facts with `gh api` and opens an issue for each unexpected commit | 250 |
| `tools/ci/kit_parity.py` | Compare `kit-staging/.claude/` with `.claude/` | `compare(repo_root) -> ParityResult`; `main(argv) -> int`: exit 1 on any difference for a staged file, unless an open blocker fragment of class KIT mentions "install staged kit" | 150 |
| `.github/workflows/aqis-lab-generate.yml` | On pull requests: build the index and progress tables into a scratch folder and run the progress lint (no commit). On pushes to `main`: run `tools.index build` and `tools.progress build --on-main`, and commit changes as `chore(bot): regenerate index and progress` with the Actions bot identity | | 120 |
| `.github/workflows/aqis-lab-breaks.yml` | On pull requests: run the break suite for the branch's WP when one is derived, otherwise skip with a message; nightly at 02:17 UTC on `main`: `--all` | | 100 |
| `.github/workflows/aqis-lab-scope.yml` | On pull requests from `wo/*` branches: run `python -m tools.outsourcing scope` for the derived work order against the base branch | | 80 |
| `.github/workflows/aqis-lab-main-guard.yml` | On pushes to `main`: run `tools.ci.main_guard` for the pushed commits | | 80 |
| `.github/workflows/aqis-lab-mutation.yml` | On pull requests: the mutation report for changed modules, uploaded as an artifact and summarised in the job summary; advisory | | 100 |
| `.github/workflows/aqis-lab-kit-parity.yml` | On pull requests and pushes to `main`: `tools.ci.kit_parity` | | 60 |
| `tests/aqis_lab/ci/test_*.py` | Unit tests for the helpers, and structural tests of the workflows | | 300 each |

## 4. Required behaviour
- **B1** Permissions are least privilege: pull-request jobs `contents: read`; the regeneration job `contents: write`; the main guard `issues: write` and `pull-requests: read`; nothing else.
- **B2** The regeneration job never triggers itself: it skips when the head commit message starts with `chore(bot):`, and commits only when files changed.
- **B3** Heavy jobs (breaks, mutation) use `runs-on: ${{ vars.AQIS_HEAVY_RUNNER || 'ubuntu-latest' }}`; others use `ubuntu-latest`.
- **B4** Every job installs Python and the lab environment the same way the existing lab workflows do, and pins third-party actions to full commit SHAs with the version in a comment.
- **B5** The main guard classifies a commit as `gated-merge` when it is a merge commit whose pull request (from `gh api repos/<repo>/commits/<sha>/pulls`) has a head commit with an `AUDIT.md` verdict PASS for that WP and a title ending `(gate PASS)`; `bot-regeneration` when authored by the Actions bot with a `chore(bot):` message touching only generated paths; `owner-never-edit` when committed through the GitHub web interface and touching only NEVER paths; otherwise `unexpected`, which opens one issue titled `main-guard: unexpected commit <short sha>` with the facts.
- **B6** The mutation job never fails the pull request: mark the job advisory with `continue-on-error: true` and a comment `# audit-allow: advisory report`.
- **B7** `test_workflows.py` parses each workflow (use the YAML loader already in the lab lock; if none exists, return QUESTIONS rather than adding one) and asserts the triggers, permissions, runner expressions, SHA-pinned actions and the bot-skip condition.

## 5. Edge cases you must handle
- **E1** A pull request from a branch with no derivable WP → the breaks job prints a notice and succeeds without running.
- **E2** A push to `main` with several commits → every commit is classified.
- **E3** The `AQIS_HEAVY_RUNNER` variable unset → the expression falls back to `ubuntu-latest`.
- **E4** `kit-staging/` absent → parity passes with a notice.

## 6. Never
- Never give pull-request jobs write permissions.
- Never use `|| true` or `2>/dev/null` to hide failures (the compromise scan rejects them).
- Never let the regeneration job commit anything outside the generated paths.

## 7. When this order is wrong or incomplete
Return QUESTIONS if the existing lab workflows install the environment in a way these jobs cannot reuse, or if no YAML loader is available for B7.

## 8. Must-catch behaviours
1. The regeneration job skips bot commits and so cannot loop.
2. Pull-request jobs have read-only permissions.
3. The main guard flags a direct push that did not come through a gated merge.
4. The breaks job fails when a recipe survives.
5. Kit parity fails when an installed hook differs from its staged copy and no KIT blocker is open.
6. Every third-party action is pinned to a commit SHA.

## 9. Definition of Done
- **D1** Every file in section 3 exists; Python modules carry the header standard.
- **D2** B1 to B7 and E1 to E4 are implemented; point at each.
- **D3** Helper tests use temporary repositories and a stand-in `gh` on `PATH`.
- **D4** `tests/aqis_lab/ci/test_acceptance_wo_1_0_09.py` passes unmodified.
- **D5** No placeholder or swallowed error.
