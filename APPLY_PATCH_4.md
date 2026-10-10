# Kit patch 4 — operating model v2

Prompts, rules, templates, one spec, eleven work orders and the model pool file. No code: the code is specified in the work orders and built in WP-1.0.

## Apply
1. Merge PR #10 (WP-0.9) after recording F12 as DEBT-034, and resolve the stale BLK-010 entry (guide section 1.1).
2. Upload everything in this folder except this file to `main` (see `docs/OPERATOR_GUIDE.md` section 1.2).
3. Delete `.claude/rules/10-stop-and-ask.md` on `main`.
4. Run the self-test in `docs/OPERATOR_GUIDE.md` section 1.3.
5. Do the one-time setup in sections 1.4 to 1.8, then tell the Project `Run WP-1.0`.

## Replaced files
`CLAUDE.md`; `.claude/settings.json` (adds `advisorModel` only); `.claude/rules/00`, `20`, `30`, `40`; `.claude/skills/wp-start`, `wp-build`, `wp-audit`, `surgical-fix`, `ask-owner`, `phase-audit`; `.claude/agents/wp-auditor.md`; `docs/process/WORKFLOW.md`, `AUDIT_PROTOCOL.md`, `CHANGE_CONTROL.md`, `PROTECTED_PATHS.txt`; `docs/process/templates/AUDIT_REPORT.md`, `BLOCKER.md`, `WP_PLAN.md`; `docs/OPERATOR_GUIDE.md`.

## New files
`.claude/rules/10-autonomy-and-escalation.md`, `50`, `60`, `70`; skills `wp-run`, `wp-merge`, `wo-write`; agents `wp-auditor-deep`, `doc-checker`, `plan-checker`, `second-opinion`, `Explore`, `test-runner`, `log-digest`; `docs/process/AUTONOMY.md`, `ESCALATION.md`, `PARALLEL.md`, `MODEL_ROUTING.md`, `CONTEXT_BUDGET.md`, `PROJECT_INSTRUCTIONS.md`; templates `DECISION.md`, `FRAGMENTS.md`, `BREAK_RECIPE.md`, `WP_SPEC.md`; `docs/process/outsourcing/` (Foundation, README, four templates); `docs/outsourcing/orders/WO-1.0-01.md` to `WO-1.0-11.md`; `docs/specs/phase-1/WP-1.0-operating-model-v2.md`; `config/aqis_lab/model_pool.json` (Gemini and Mistral limits already filled in from your own pages).

## Deleted file
`.claude/rules/10-stop-and-ask.md` (replaced by `10-autonomy-and-escalation.md`).

## Kept as they are
The hooks (`.claude/hooks/*`, stop gate v3) until WP-1.0 stages and you install v4; `docs/process/templates/APPROVAL.md` and `EVIDENCE.md`; all Phase 0 specs and records.
