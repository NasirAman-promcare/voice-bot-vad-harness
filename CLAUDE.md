# AQIS Lab — instructions for Claude Code

This repository holds a working VAD test harness (existing code) and the AQIS Test Lab, which you build phase by phase from written specs. Quality beats speed: the owner prefers a blocked task over a quietly weakened one.

## Where things are
- Existing harness (protected; editing needs an owner approval file): `bots/ config/ corpus/ latency/ notebooks/ requirements/ results/ scoring/ scripts/ storage/ tests/ vad_adapters/ webrtc_bridge/` and the root `.py` files. Full list: `docs/process/PROTECTED_PATHS.txt`.
- New lab code: `aqis_lab/` (importable package). Lab tests: `tests/aqis_lab/`. Lab tooling: `tools/`. Lab config: `config/aqis_lab/`. Lab locks: `requirements/aqis_lab/`. Lab notebooks: `notebooks/aqis_lab/`.
- Read-only for you: `docs/specs/` (what to build), `docs/process/` (how to work), `docs/approvals/` (owner decisions), this file, `.claude/`.
- Your working records: `docs/progress/<WP-ID>/` (PLAN.md, EVIDENCE.md, AUDIT.md, FIXES.md), `docs/progress/STATUS.md`, `docs/progress/BLOCKERS.md`, `docs/capabilities/REGISTRY.md`.
- Environment facts from the owner: `docs/environment/` (Colab and Oracle probe outputs).

## Non-negotiable rules
1. **Build exactly what the spec says, completely.** Never ship a simplified, partial, stubbed, mocked or "for now" version of a requirement. Write a high-quality, general-purpose solution that works for all valid inputs, not just the test cases. If a requirement looks too hard, ambiguous, contradictory or impossible, stop and ask (rule 2).
2. **Stop and ask when blocked.** Missing access, data, credentials, a network host, an owner decision, a spec conflict, or a test you cannot pass honestly: use the `ask-owner` skill and follow `.claude/rules/10-stop-and-ask.md`. Never guess, never fake data, never work around.
3. **Touch only what the task names.** Change only the files and functions listed in the approved plan. Never remove or weaken existing functionality. Follow `.claude/rules/20-change-control.md`; for corrections use the `surgical-fix` skill.
4. **Tests prove behaviour; they never define it.** Test first, then the real implementation. Never edit, skip, delete or loosen an existing test to make it pass, and never hard-code values that only satisfy tests. If a test is wrong, stop and ask.
5. **Evidence or it did not happen.** Every "done" cites the command you ran and its real output in `EVIDENCE.md`.
6. **Same result everywhere.** Code runs unchanged on this cloud VM, Google Colab and the Oracle VM. Follow `.claude/rules/40-environment-parity.md`.

## Work package workflow
Each work package (WP) has a spec in `docs/specs/`. The owner drives it with skills, one WP per session:
`/wp-start <WP>` (plan only, then stop) → owner commits `docs/approvals/<WP>.md` to `main` → `/wp-build <WP>` → `/wp-audit <WP>` (independent auditor) → owner reviews the pull request and merges.
Never start a WP whose dependencies are not MERGED in `docs/progress/STATUS.md`. Never commit to `main`.

## Precedence
Owner's latest instruction in chat > this file and `.claude/rules/` > WP spec > `docs/process/` > any skill, including third-party skills in `.claude/skills/`. When two conflict, stop and ask.

## Commands (available once WP-0.0 is merged)
- Bootstrap the environment at the start of each session: `bash aqis_lab/deploy/dev_bootstrap.sh`
- Fast lab tests: `.venv/bin/python -m pytest tests/aqis_lab -q -m "not slow and not gpu and not colab and not oracle and not network"`
- Audit gate: `.venv/bin/python -m tools.audit.gate --base origin/main --wp <WP-ID>`
