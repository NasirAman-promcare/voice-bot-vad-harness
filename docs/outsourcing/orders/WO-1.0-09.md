---
id: WO-1.0-09
wp: WP-1.0
title: CI workflows for generation, break suite, scope, main guard, mutation and kit parity
model: default
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
  - .github/workflows/aqis-lab-ci.yml
  - docs/process/PROTECTED_PATHS.txt
  - docs/process/templates/FRAGMENTS.md
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
steps:
  - tools/ci/__init__.py, tests/aqis_lab/ci/__init__.py, tools/ci/refs.py, tests/aqis_lab/ci/test_refs.py
  - tools/ci/main_guard.py, tests/aqis_lab/ci/test_main_guard.py
  - tools/ci/kit_parity.py, tests/aqis_lab/ci/test_kit_parity.py
  - .github/workflows/aqis-lab-generate.yml, .github/workflows/aqis-lab-breaks.yml, .github/workflows/aqis-lab-scope.yml
  - .github/workflows/aqis-lab-main-guard.yml, .github/workflows/aqis-lab-mutation.yml, .github/workflows/aqis-lab-kit-parity.yml
  - tests/aqis_lab/ci/test_workflows.py
read_only_tests:
  - tests/aqis_lab/ci/test_acceptance_wo_1_0_09.py
allowed_dependencies:
  - stdlib
  - pyyaml
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/ci -q --tb=short
---

# WO-1.0-09 — CI workflows for generation, break suite, scope, main guard, mutation and kit parity

**Before sending (Claude):** add the existing `.github/workflows/aqis-lab-*.yml` files to `context`, and state in section 1 which Python setup and bootstrap steps they use, so the new workflows install the environment the same way. If `requirements/aqis_lab` pins a YAML package, add it to `allowed_dependencies`. *(Done 2026-10-10. The only existing lab workflow is `aqis-lab-ci.yml`, now in `context`. `pyyaml==6.0.3` is pinned in `requirements/aqis_lab/phase0.txt` and listed in `allowed_dependencies`, for `test_workflows.py` only.)*

## 1. Context
The lab's tables and map are generated on `main` only, break recipes must run on every pull request and nightly, outsourced branches need a scope check, `main` needs a guard that flags commits that did not come through the merge gate, mutation reports are advisory, and installed hooks must match the audited staged copies. Workflow files matching `.github/workflows/aqis-lab-*.yml` are lab-owned. Logic lives in small Python modules under `tools/ci/` so it can be unit-tested; the workflows only call them. The existing `aqis-lab-ci.yml` installs the environment in three steps: `actions/checkout` with `fetch-depth: 0`, `astral-sh/setup-uv` with `version: "0.8.17"`, then `run: bash aqis_lab/deploy/dev_bootstrap.sh`, which builds `.venv` on the Colab Python from `docs/environment/colab_probe.txt` with the hash-checked lock. Every new job repeats these three steps, with the actions pinned as B8 says, and calls the tools as `.venv/bin/python -m …`.

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
- **B7** `test_workflows.py` reads each workflow (with the YAML loader listed in `allowed_dependencies` if there is one, otherwise as text, line by line) and asserts the triggers, permissions, runner expressions, SHA-pinned actions and the bot-skip condition.

- **B8** Pins (amended by Claude with the acceptance tests; each is checked there):
  1. **Action pins.** Use exactly these, each followed by its version comment:
     - `actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0`
     - `astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e # v6.8.0`
     - `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2`
     Claude read these with `git ls-remote --tags` on 2026-10-10; all three are lightweight tags, so they are commit SHAs. No other action is used.
  2. **Permissions.** Every workflow sets workflow-level `permissions: {contents: read}`. Write scopes appear only at job level, on jobs whose `if:` contains `github.event_name == 'push'`. The main guard job has exactly `contents: read`, `issues: write` and `pull-requests: read`.
  3. **Generate.** It runs on `pull_request` and on `push` to `branches: [main]`, with two jobs.
     - The pull-request job (`if: github.event_name == 'pull_request'`) runs:
       - `tools.index build --out <scratch>`;
       - `tools.progress build --on-main --out <scratch>`;
       - `tools.progress lint`.
       It never commits.
     - The regeneration job (`if: github.event_name == 'push' && !startsWith(github.event.head_commit.message, 'chore(bot):')`) does this:
       - It runs `tools.index build` and `tools.progress build --on-main`.
       - It sets the identity `github-actions[bot]` / `41898282+github-actions[bot]@users.noreply.github.com`.
       - It checks `git status --porcelain` on the generated paths. When they changed, it runs `git add` naming only those paths, then commits with the message `chore(bot): regenerate index and progress` and pushes.
     The generated paths are `docs/index/`, `docs/capabilities/REGISTRY.md`, `docs/progress/{STATUS,BLOCKERS,DEBT,DECISIONS,OWNER_QUEUE}.md` and `docs/outsourcing/LEDGER.md`.
  4. **Breaks.** One job, triggered by `pull_request` and `schedule: [{cron: "17 2 * * *"}]`. On a pull request it runs `.venv/bin/python -m tools.ci.refs wp "$GITHUB_HEAD_REF"`. An empty answer prints `::notice::` and ends successfully. Otherwise it runs `.venv/bin/python -m tools.audit.breaks --wp "$WP"`. On the schedule it runs `--all`. There is no `continue-on-error`.
  5. **Scope.** One job, `if: startsWith(github.head_ref, 'wo/')`. The work order comes from `tools.ci.refs wo`. The job runs `tools.outsourcing scope --wo docs/outsourcing/orders/<WO>.md --base origin/<base>`.
  6. **Mutation.** One job with the line `continue-on-error: true  # audit-allow: advisory report` at job level. It runs `tools.audit.mutation_report --base origin/<base> --out <file>`, appends the report to `$GITHUB_STEP_SUMMARY` and uploads the report.
  7. **Runners.** Breaks and mutation use exactly `${{ vars.AQIS_HEAVY_RUNNER || 'ubuntu-latest' }}`; every other job uses `ubuntu-latest`.
  8. **refs command line.** `python -m tools.ci.refs (wp|wo) <branch>` prints the derived ID, or nothing, and exits 0. `wp_from_branch` accepts `claude/wp-<n>-<m>(-<slug>)?` with numeric `<n>` and `<m>` only. `wo_from_branch` accepts `wo/WO-<n>.<m>-<k>`.
  9. **Main guard command line.** `python -m tools.ci.main_guard --repo OWNER/REPO --before SHA --after SHA`, run in a full clone.
     - **Commits.** They come from `git rev-list --first-parent --reverse <before>..<after>`; an all-zero `before` means `<after>` alone.
     - **Output.** One line per commit: `<short sha> <classification> <subject>`.
     - **Facts.** They come from git: parents, subject, author and committer names and emails, and the files changed against the first parent. The pull requests come from `gh api repos/<repo>/commits/<sha>/pulls`.
     - **`gated-merge`** needs all of these:
       - two parents;
       - a subject `Merge <WP>: … (gate PASS)` (the title the merge gate WO-1.0-05 sets);
       - a pull request whose `head.sha` is the second parent and whose `head.ref` gives the same WP through `wp_from_branch`;
       - `git show <head.sha>:docs/progress/<WP>/AUDIT.md` with a line `## Verdict: PASS`.
     - **`bot-regeneration`** needs the author `github-actions[bot]`, a subject starting `chore(bot):`, and every changed file under the generated paths of pin 3.
     - **`owner-never-edit`** needs the committer `GitHub` / `noreply@github.com` and every changed file NEVER under `docs/process/PROTECTED_PATHS.txt`, as committed in that commit, plus the hooks' built-in NEVER list.
     - **`unexpected`.** Each one gets `gh api --method POST repos/<repo>/issues -f title=main-guard: unexpected commit <short sha> -f body=<facts>`.
     - **Exit codes.** 1 when any commit is unexpected; 2 when git or `gh` fails; 0 otherwise.
  10. **Kit parity command line.** `python -m tools.ci.kit_parity` compares every file under `kit-staging/.claude/` with the same path under `.claude/`; installed files that were never staged are ignored.
      - It prints each differing or missing file's path relative to `.claude/` (for example `hooks/stop_gate.py`).
      - It exits 1 when there is any difference, unless a blocker fragment in `docs/progress/blockers.d/` has `Status: OPEN`, `Owner capability: KIT` and the words "install staged kit" (any case). In that case it prints `::notice::` and exits 0.
      - Without `kit-staging/` it prints `::notice::` and exits 0.

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
- **D2** B1 to B8 and E1 to E4 are implemented; point at each.
- **D3** Helper tests use scratch repositories and a stand-in `gh` on `PATH`.
- **D4** `tests/aqis_lab/ci/test_acceptance_wo_1_0_09.py` passes unmodified.
- **D5** No placeholder or swallowed error.
