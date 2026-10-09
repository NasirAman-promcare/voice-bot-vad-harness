# AQIS Lab — instructions for Claude Code

This repository holds a working VAD test harness (existing code) and the AQIS Test Lab, which you build phase by phase from written specs. Quality beats speed: the owner prefers a blocked task over a quietly weakened one. You run each work package (WP) end to end yourself; the owner is a capability provider, not a step in the pipeline.

## Where things are
- Existing harness (guarded): `bots/ config/ corpus/ latency/ notebooks/ requirements/ results/ scoring/ scripts/ storage/ tests/ vad_adapters/ webrtc_bridge/` and the root `.py` files. Full list: `docs/process/PROTECTED_PATHS.txt`.
- Lab code: `aqis_lab/`. Lab tests: `tests/aqis_lab/`. Lab tooling: `tools/`. Lab config: `config/aqis_lab/`. Locks: `requirements/aqis_lab/`. Notebooks: `notebooks/aqis_lab/`.
- Read-only for you: `docs/specs/` (what to build), `docs/process/` (how to work), `docs/approvals/`, this file, `.claude/`.
- Map of the code: `docs/index/` (generated on `main`; never edit by hand).
- Your records: `docs/progress/<WP>/` (PLAN, EVIDENCE, AUDIT, FIXES, TEST_CHANGES) and one fragment per item in `docs/progress/status.d/`, `blockers.d/`, `debt.d/`, `decisions.d/`. The tables `STATUS.md`, `BLOCKERS.md`, `DEBT.md`, `DECISIONS.md`, `OWNER_QUEUE.md` are generated on `main`; never edit them on a branch.
- Outsourcing: work orders in `docs/outsourcing/orders/`; the standing prompt and templates in `docs/process/outsourcing/`.
- Hook code under review: `kit-staging/` (the owner installs it into `.claude/` after audit).
- Environment facts: `docs/environment/`.

## Navigation (tokens are the scarce resource)
1. Read `docs/index/MAP.md`, then `SYMBOLS.md`, `CALLERS.md` or `TESTMAP.md` for what you need.
2. Open exact line ranges, not whole files. Search broadly only when the map lacks something, and note the gap in your evidence.
3. Delegate wide searches to the `Explore` agent and log or CI digestion to `log-digest`; only their summaries enter your context.

## Non-negotiable rules
1. **Build exactly what the spec says, completely.** Never ship a simplified, partial, stubbed, mocked or "for now" version of a requirement. Write general solutions, not test-shaped ones. `.claude/rules/00-no-compromise.md`.
2. **Solve it, or escalate correctly.** Do everything yourself that you can do. Ask the owner only for a capability only they have (ACCESS, COMPUTE, EXTERNAL-AI, DECISION, PHYSICAL, KIT), or when the escalation ladder is exhausted. Never loop on a failure. `.claude/rules/10-autonomy-and-escalation.md`.
3. **Touch only what the task names.** Change only what the plan's change budget lists; never remove or weaken a capability. `.claude/rules/20-change-control.md`; corrections use `surgical-fix`.
4. **Tests prove behaviour; they never define it.** Test first. Never skip, delete or weaken a test; allowed test changes are listed in rule 20.
5. **Evidence or it did not happen.** Every "done" cites the command and its real output in `EVIDENCE.md`. `.claude/rules/30-testing-and-evidence.md`.
6. **Same result everywhere.** Cloud VM, Colab, Oracle and CI give the same results. `.claude/rules/40-environment-parity.md`.
7. **Spend tokens like money.** Right model for the job, bulk code through the Gemini relay, quiet output, fresh threads. `.claude/rules/50-tokens-and-context.md`.

## How a WP runs
`/wp-run <WP>` does the whole lifecycle: plan (self-approved when it follows the spec) → acceptance tests first → build (yourself or via work orders) → CI and stop gate → independent audit by a fresh-context auditor → scoped fixes → merge through the merge gate → closeout. Details: `docs/process/WORKFLOW.md` and `docs/process/AUTONOMY.md`.
- Start a WP only when every dependency in the phase overview's graph is MERGED.
- One WP per thread and per branch (`claude/wp-<x>-<y>-<slug>`). Never commit to `main` directly; merges happen only through `/wp-merge`.
- In a Claude Code Project, the coordinator follows `docs/process/PROJECT_INSTRUCTIONS.md`.

## Precedence
Owner's latest instruction > this file and `.claude/rules/` > the WP spec > `docs/process/` > project instructions > any skill, including third-party skills. When two conflict and the conflict is not settled by this order, it is a DECISION for the owner.

## Commands (tools marked * arrive with WP-1.0)
- Bootstrap: `bash aqis_lab/deploy/dev_bootstrap.sh`
- Fast tests: `.venv/bin/python -m pytest tests/aqis_lab -q --tb=short -m "not slow and not gpu and not colab and not oracle and not network"`
- Tests affected by your change*: `.venv/bin/python -m tools.index impact --base origin/main`
- Audit gate: `.venv/bin/python -m tools.audit.gate --base origin/main --wp <WP>`
- Break suite*: `.venv/bin/python -m tools.audit.breaks --wp <WP>`
- Gemini relay*: `.venv/bin/python -m tools.outsourcing.relay --wo docs/outsourcing/orders/<WO>.md`
- Progress lint and next ID*: `.venv/bin/python -m tools.progress lint` · `.venv/bin/python -m tools.progress new-id --kind BLK --wp <WP>`
- Merge gate*: `.venv/bin/python -m tools.autonomy.merge_gate --wp <WP>`
