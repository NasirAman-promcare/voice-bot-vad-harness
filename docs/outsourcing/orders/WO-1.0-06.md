---
id: WO-1.0-06
wp: WP-1.0
title: Break suite runner and mutation report
model: gemini-3.7-flash
channel: api
attempt_budget: 3
risk_tier: T1
max_output_tokens: 60000
context:
  - docs/process/AUDIT_PROTOCOL.md
  - docs/process/templates/BREAK_RECIPE.md
  - tools/index/impact.py
outputs:
  - tools/audit/breaks.py
  - tools/audit/mutate.py
  - tools/audit/mutation_report.py
  - tests/aqis_lab/audit_breaks/__init__.py
  - tests/aqis_lab/audit_breaks/test_breaks.py
  - tests/aqis_lab/audit_breaks/test_mutate.py
  - tests/aqis_lab/audit_breaks/test_mutation_report.py
read_only_tests:
  - tests/aqis_lab/audit_breaks/test_acceptance_wo_1_0_06.py
allowed_dependencies:
  - stdlib
verify:
  - .venv/bin/python -m pytest tests/aqis_lab/audit_breaks -q --tb=short
---

# WO-1.0-06 — Break suite runner and mutation report

## 1. Context
Must-catch proofs used to be manual breaks repeated every audit round. Now each must-catch behaviour has a break recipe (format in `BREAK_RECIPE.md`), and a runner applies recipes in throwaway worktrees and checks that the named tests fail. A small, deterministic mutation engine produces an advisory report that tells the auditor where exploratory breaks are worth spending. `tools/index/impact.py` (in context) maps changes to tests.

## 2. Your job
`python -m tools.audit.breaks (--wp WP-x.y | --all)` and `python -m tools.audit.mutation_report --base REF [--max-mutants N] [--seed S] --out PATH`.

## 3. Files you create
| Path | One responsibility | Public API (in words) | Max lines |
| --- | --- | --- | --- |
| `tools/audit/breaks.py` | Find, validate and run break recipes; report | `load_recipes(repo_root, wp or None) -> list[Recipe]`; `run_recipe(recipe, repo_root) -> RecipeResult` (`caught`, `survived` or `broken`, with details); `main(argv) -> int` | 300 |
| `tools/audit/mutate.py` | Generate deterministic single-point mutants of a Python module with `ast` | `mutants(source_text, seed, limit) -> list[Mutant]` (operator, line, description, mutated source) | 300 |
| `tools/audit/mutation_report.py` | Run mutants of changed modules against their affected tests and write the report | `run(repo_root, base_ref, max_mutants, seed) -> Report`; `main(argv) -> int` | 250 |
| `tests/aqis_lab/audit_breaks/test_*.py` | Unit tests per module | | 300 each |

## 4. Required behaviour
- **B1** Recipes live at `tests/aqis_lab/breaks/<WP>/MC-<nn>-<slug>.patch`; header lines `# MC:`, `# behaviour:` and at least one `# expect-fail:` with a pytest node ID; a missing header or node ID makes the recipe `broken`.
- **B2** For each recipe: create a detached worktree of `HEAD` in a temporary directory; `git apply --check`, then apply; run only the `expect-fail` node IDs with the project's Python from the worktree, with the worktree as working directory; parse the results (use pytest's `-rA` summary or `--junitxml` to a temporary file).
- **B3** `caught` only when every `expect-fail` node failed or errored. `survived` when any of them passed. `broken` when the patch does not apply, a node ID does not exist, or pytest could not run.
- **B4** The worktree is removed in every case, including crashes and timeouts (default 600 seconds per recipe).
- **B5** Breaks report: a table (recipe, behaviour, result, details), at most 30 lines. Exit 0 when all are caught; 1 when any survived; 2 when any is broken and none survived.
- **B6** Mutation operators: comparison swap (`<` with `>=`, `>` with `<=`, `==` with `!=`), boolean operator swap (`and` with `or`), condition negation in `if` and `while`, integer constant plus or minus one, a `return <expr>` replaced by `return None`, and a `raise` replaced by `pass`. One mutation per mutant; mutants that do not compile are discarded. Selection is deterministic for a given seed and limit.
- **B7** The mutation report mutates only the modules changed since the merge base with `--base`, runs each mutant in a temporary worktree against the module's affected tests (from `tools.index.impact`), and writes a markdown report: per module, mutants run, killed and survived, then each survivor with `path:line`, operator and description. It never modifies the real working tree. Exit 0 unless the tool itself failed (exit 2).

## 5. Edge cases you must handle
- **E1** No recipes for the WP → exit 2 with "no recipes", never 0.
- **E2** A recipe that changes a test file instead of code → `broken` (recipes break code, not tests).
- **E3** A module with no affected tests → reported as "no tests selected", not as all mutants surviving.
- **E4** `--all` runs every WP's recipes and groups the table by WP.

## 6. Never
- Never apply a recipe or a mutant to the real working tree.
- Never report `caught` because some other test failed.
- Never leave worktrees behind.

## 7. When this order is wrong or incomplete
Return QUESTIONS if `tools.index.impact` does not expose what B7 needs.

## 8. Must-catch behaviours
1. A recipe whose patch no longer applies is `broken` (exit 2), never `caught`.
2. A surviving recipe makes the run exit 1.
3. Worktrees are removed even when the test run crashes.
4. Only the named `expect-fail` tests count.
5. The mutant set is identical for the same seed and limit.
6. The mutation report leaves the working tree unchanged.

## 9. Definition of Done
- **D1** Every file in section 3 exists with its public API and the module header standard.
- **D2** B1 to B7 and E1 to E4 are implemented; point at each.
- **D3** Unit tests build small temporary repositories with their own recipes and tests.
- **D4** `tests/aqis_lab/audit_breaks/test_acceptance_wo_1_0_06.py` passes unmodified.
- **D5** No placeholder or swallowed error.
