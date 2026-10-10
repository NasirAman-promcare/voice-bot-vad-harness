---
id: WO-1.0-05
wp: WP-1.0
title: Merge gate
model: default
channel: api
attempt_budget: 3
risk_tier: T1
max_output_tokens: 60000
context:
  - docs/process/AUTONOMY.md
  - docs/process/AUDIT_PROTOCOL.md
  - docs/process/templates/AUDIT_REPORT.md
  - docs/process/templates/FRAGMENTS.md
  - docs/process/templates/WP_SPEC.md
  - docs/process/PROTECTED_PATHS.txt
interfaces:
  - tools/outsourcing/paths.py
  - tools/progress/fragments.py
outputs:
  - tools/autonomy/__init__.py
  - tools/autonomy/merge_gate.py
  - tools/autonomy/facts.py
  - tools/autonomy/criteria.py
  - tools/autonomy/github.py
  - tests/aqis_lab/autonomy/__init__.py
  - tests/aqis_lab/autonomy/stand_in_gh.py
  - tests/aqis_lab/autonomy/test_criteria.py
  - tests/aqis_lab/autonomy/test_facts.py
  - tests/aqis_lab/autonomy/test_github.py
  - tests/aqis_lab/autonomy/test_merge_gate.py
steps:
  - tools/autonomy/__init__.py, tests/aqis_lab/autonomy/__init__.py, tests/aqis_lab/autonomy/stand_in_gh.py
  - tools/autonomy/github.py, tests/aqis_lab/autonomy/test_github.py
  - tools/autonomy/facts.py, tests/aqis_lab/autonomy/test_facts.py
  - tools/autonomy/criteria.py, tests/aqis_lab/autonomy/test_criteria.py
  - tools/autonomy/merge_gate.py, tests/aqis_lab/autonomy/test_merge_gate.py
read_only_tests:
  - tests/aqis_lab/autonomy/test_acceptance_wo_1_0_05.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/autonomy -q --tb=short
---

# WO-1.0-05 — Merge gate

## 1. Context
Claude now merges its own work packages, but only through this deterministic gate, whose seven criteria are in `AUTONOMY.md` ("Merge gate criteria"). Claude Code cloud sessions reach GitHub through a proxy that authenticates the preinstalled `gh` command; GraphQL is limited there, so use `gh api` with REST endpoints only. Protected-path classification and fragment parsing already exist (in your context).

## 2. Your job
`python -m tools.autonomy.merge_gate --wp WP-x.y [--dry-run] [--json]` gathers facts, evaluates every criterion, prints a table, and merges only when all pass.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/autonomy/github.py` | Call `gh api` for REST endpoints and parse JSON, with pagination | `GitHub(repo_slug)`: `open_pr_for_branch`, `check_runs(sha)`, `combined_status(sha)`, `merge_pr(number, sha, title)`; raises `GitHubError` carrying the HTTP status | 250 |
| `tools/autonomy/facts.py` | Gather every fact the criteria need from git, files and GitHub | `gather(wp, repo_root, github) -> Facts` (immutable) | 300 |
| `tools/autonomy/criteria.py` | Evaluate the seven criteria from facts alone; pure functions | `evaluate(facts) -> list[CriterionResult]` (ID, passed, reason) | 250 |
| `tools/autonomy/merge_gate.py` | Command line, table output, merge call, exit codes | `main(argv) -> int` | 200 |
| `tests/aqis_lab/autonomy/stand_in_gh.py` | Test stand-in for the `gh` executable: answers `api` calls from a JSON script and records every call | run as a program; a test fixture puts a wrapper named `gh` first on `PATH` | 150 |
| `tests/aqis_lab/autonomy/test_*.py` | Unit tests | | 300 each |

## 4. Required behaviour
- **B1** Facts: repository slug from `git remote get-url origin` (HTTPS, SSH and proxy URL forms); current branch and head SHA; `origin/main` SHA after one fetch; merge base; the open pull request for the branch; check runs and combined status for the head SHA (all pages); the WP's `AUDIT.md` verdict line and `Commit audited` SHA; the commits from the audited SHA to head with their changed paths; open blocker fragments for the WP; the findings table's open CRITICAL and MAJOR rows and the debt or decision records accepting MAJORs; the diff paths since the merge base with their protected class; the spec's `## Allowed guarded edits` lines and its owner-run checks marked `blocking`; the committed report for each blocking check; the WP's status fragment.
- **B2** Criteria C1 to C7 exactly as in `AUTONOMY.md`. C1 accepts an earlier audited commit only if every later commit touches only `docs/progress/<WP>/**` and fragment folders. C2 requires every check run `completed` with conclusion `success` (or `skipped` for jobs the workflow marks optional) and a combined status of `success` or no statuses; anything pending fails. C3 fails with exit 2, not 3, so the caller knows to update the branch. C5 fails on any NEVER path, and on a GUARDED path matched neither by the spec's allowed edits nor by an approved `ALLOW-EDIT` line on `origin/main`.
- **B3** Output: a table of criteria with PASS or FAIL and the reason, at most 20 lines; `--json` prints the same as JSON.
- **B4** With every criterion passing and no `--dry-run`, merge with `PUT repos/<slug>/pulls/<n>/merge`, `merge_method=merge`, `sha=<head SHA>`, title `Merge <WP>: <PR title> (gate PASS)`. Confirm the response says merged; otherwise exit 4.
- **B5** Exit codes: 0 merged (or would merge, in a dry run); 2 branch behind `main`; 3 a criterion failed; 4 GitHub error (print `ACCESS:` before the message when the status is 401 or 403); 5 no open pull request for the branch.
- **B6** The gate writes nothing to the repository and makes no commit.

## 5. Edge cases you must handle
- **E1** No `AUDIT.md` → C1 fails with a clear reason.
- **E2** The audited SHA is not an ancestor of head → C1 fails.
- **E3** More than 100 check runs → paginate.
- **E4** `origin/main` missing after a fetch → raise, never pass C3.
- **E5** The head moves between gathering facts and merging → GitHub refuses because of the pinned SHA; exit 4 with that reason.

## 6. Never
- Never merge with any criterion failing, and never in a dry run.
- Never call `gh pr merge` or a GraphQL mutation.
- Never edit audit reports, fragments or specs.

## 7. When this order is wrong or incomplete
Return QUESTIONS if the audit report or fragment formats in your context do not give a criterion the fact it needs.

## 8. Must-catch behaviours
1. Refuses when the audited commit is not head and a later commit touches a non-record path.
2. Refuses when any check run is pending or failed.
3. Refuses (exit 2) when the branch lacks the current `origin/main`.
4. Refuses when a blocker for the WP is open.
5. Refuses when the diff touches a NEVER path.
6. The merge request pins `sha` to the head SHA.
7. A dry run never calls the merge endpoint.
8. Refuses when a blocking owner-run check has no PASS report.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B6 and E1 to E5 are implemented; point at each.
- **D3** Tests use scratch git repositories and the stand-in `gh`; none reaches GitHub.
- **D4** `tests/aqis_lab/autonomy/test_acceptance_wo_1_0_05.py` passes unmodified.
- **D5** No placeholder or swallowed error.
