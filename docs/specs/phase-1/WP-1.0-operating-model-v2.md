# WP-1.0 — Operating model v2: tooling, migration and Phase 0 debts

- **Depends on**: WP-0.9 (MERGED) and kit patch 4 on `main`. The Phase 1 overview arrives with the Phase 1 specs; WP-1.0 needs nothing else from it.
- **Risk tier**: T1 (enforcement tooling)
- **Size**: L
- **Thread model**: Opus, high
- **Runs on**: cloud VM and CI
- **Touches**: `tools/outsourcing/**`, `tools/index/**`, `tools/progress/**`, `tools/autonomy/**`, `tools/audit/breaks.py`, `tools/audit/mutate.py`, `tools/audit/mutation_report.py`, `tools/ci/**`, `kit-staging/**`, `tests/aqis_lab/{outsourcing,index,progress,autonomy,audit_breaks,kit,ci}/**`, `tests/aqis_lab/breaks/WP-1.0/**`, `.github/workflows/aqis-lab-*.yml`, `docs/outsourcing/**`, `docs/progress/**`, `docs/capabilities/retired.d/**`, `.gitignore`, and the files named by DEBT-032, DEBT-033 and DEBT-034
- **Produces / Consumes**: produces the outsourcing relay, the Lab Map, progress fragments and generated tables, the merge gate, the break suite, staged kit v4 hooks and settings, and the CI workflows; consumes the existing audit gate and pattern tables
- **Read first**: `docs/process/AUTONOMY.md`, `ESCALATION.md`, `CHANGE_CONTROL.md`, `AUDIT_PROTOCOL.md`, `PARALLEL.md`, `docs/process/outsourcing/` (README, FOUNDATION, templates), the eleven work orders `docs/outsourcing/orders/WO-1.0-01.md` to `WO-1.0-11.md`, `config/aqis_lab/model_pool.json`, and the DEBT-032 to DEBT-034 rows of `docs/progress/DEBT.md`

## Goal
Build, audit and hand over the tooling that lets work packages run with the owner only as a capability provider: Gemini writes the code through work orders, Claude navigates by a generated map, records are parallel-safe fragments, audits rest on break recipes, merges go through a deterministic gate, and hooks stop loops and raw merges. WP-1.0 is itself the first WP built mostly through work orders.

## Deliverables
- The tools and tests specified by WO-1.0-01 to WO-1.0-11.
- Break recipes for this WP's must-catch list in `tests/aqis_lab/breaks/WP-1.0/`.
- Legacy `STATUS.md`, `BLOCKERS.md` and `DEBT.md` migrated to fragments; the hand-written registry adopted.
- Staged kit v4 in `kit-staging/.claude/` and its installation handed to the owner.
- DEBT-032, DEBT-033 and DEBT-034 closed.

## Functional requirements
- **FR-1.0-01** Work-order tools exactly as WO-1.0-01 specifies.
- **FR-1.0-02** The step-wise Gemini relay exactly as WO-1.0-02 (building blocks) and WO-1.0-11 (orchestration) specify.
- **FR-1.0-03** The Lab Map, generated registry and impact selection exactly as WO-1.0-03 specifies; the registry is adopted with `--adopt-registry`, every legacy row accounted for.
- **FR-1.0-04** Progress fragments, generated tables, owner queue, lint and migration exactly as WO-1.0-04 specifies; the migration is run in this WP and every legacy ID and its text appear in fragments.
- **FR-1.0-05** The merge gate exactly as WO-1.0-05 specifies.
- **FR-1.0-06** The break suite and mutation report exactly as WO-1.0-06 specifies.
- **FR-1.0-07** The hook updates, staged, exactly as WO-1.0-07 specifies.
- **FR-1.0-08** The new hooks and settings v4, staged, exactly as WO-1.0-08 specifies.
- **FR-1.0-09** The CI workflows and helpers exactly as WO-1.0-09 specifies.
- **FR-1.0-10** `.gitignore` ignores `.relay/`.
- **FR-1.0-11** DEBT-032, DEBT-033 and DEBT-034 are closed as their rows describe, each with a test, and their debt fragments set to CLOSED.
- **FR-1.0-12** Kit handover: a KIT blocker gives the exact steps to copy every file under `kit-staging/.claude/` into `.claude/` on `main`. After the owner installs, the kit parity check passes, the self-test in `docs/OPERATOR_GUIDE.md` passes, and Claude resolves the blocker.
- **FR-1.0-13** Outsourcing evidence: every work order has its summary and ledger fragment, and every relay order its step log; WO-1.0-01 and WO-1.0-10 (in parallel), then WO-1.0-02, then WO-1.0-11, go through Jules or the paste channel, and WO-1.0-03 to WO-1.0-09 through the relay.
- **FR-1.0-14** The model clients, rate governor and quota classification exactly as WO-1.0-10 specifies, and the model router as WO-1.0-11 specifies, using `config/aqis_lab/model_pool.json`.

## Non-functional requirements
- **NFR-1.0-01** Standard library only, for every tool and hook.
- **NFR-1.0-02** With impact selection, the stop gate finishes in under 2 minutes on the cloud VM for a change to one module (measured and recorded).
- **NFR-1.0-03** Output limits: relay at most 25 lines, stop gate at most 40, session context at most 15.

## Acceptance commands
- **AT-1.0-01** The fast suite passes, including every new test directory.
- **AT-1.0-02** `.venv/bin/python -m tools.index build --out /tmp/idx` succeeds, and `.venv/bin/python -m tools.index impact --base origin/main` prints a selection.
- **AT-1.0-03** `.venv/bin/python -m tools.progress migrate --dry-run` lists every legacy BLK and DEBT ID; `.venv/bin/python -m tools.progress lint` is clean.
- **AT-1.0-04** `.venv/bin/python -m tools.audit.breaks --wp WP-1.0` reports every recipe caught.
- **AT-1.0-05** `.venv/bin/python -m tools.autonomy.merge_gate --wp WP-1.0 --dry-run` prints all seven criteria with reasons.
- **AT-1.0-06** `.venv/bin/python -m tools.outsourcing.relay --wo docs/outsourcing/orders/WO-1.0-09.md --dry-run` measures the request and sends nothing.
- **AT-1.0-07** The audit gate passes with `--wp WP-1.0`.
- **AT-1.0-08** `.venv/bin/python -m tools.outsourcing.relay --status` prints today's request counts per model and the next resets in UTC, provider time and Asia/Karachi, and sends nothing.
- **AT-1.0-09** `.venv/bin/python -m tools.outsourcing.relay --models` confirms every enabled pool model's name with its provider (owner-run once the credentials exist).

## Allowed guarded edits
- `.gitignore`

## Owner needs
| Capability class | What | When |
| --- | --- | --- |
| EXTERNAL-AI | Start Jules (or use the paste channel) for WO-1.0-01 and WO-1.0-10 together, then WO-1.0-02, then WO-1.0-11 | After their acceptance tests are committed |
| ACCESS | Gemini API credential on the `aqis-lab` environment (header `x-goog-api-key`, host `generativelanguage.googleapis.com`); recommended: Mistral credential (`Authorization: Bearer`, host `api.mistral.ai`) with Mistral enabled in `config/aqis_lab/model_pool.json` (operator guide 1.5) | Before WO-1.0-03 |
| KIT | Interim merge of WP-1.0; then install `kit-staging/.claude/` into `.claude/` | After the audit passes |
| ACCESS (optional) | Register the Oracle VM as a self-hosted runner and set the repository variable `AQIS_HEAVY_RUNNER` | Any time |

## Owner-run checks
| Check | Blocking or post-merge | Where | Command | Expected output |
| --- | --- | --- | --- | --- |
| OC-1.0-01 Kit self-test after install | post-merge | new cloud session | the self-test prompt in `docs/OPERATOR_GUIDE.md` | every step as the guide says |
| OC-1.0-02 First generation on `main` | post-merge | GitHub Actions | the `aqis-lab-generate` run after the merge | a `chore(bot):` commit with `docs/index/` and the generated tables |

## Outsourcing candidates
- WO-1.0-01 to WO-1.0-11, all of the tooling. Claude writes the acceptance tests, the break recipes, the debt fixes and the migration run.

## Stop and ask if (DECISION triggers)
- A work order needs a dependency beyond the standard library.
- The current Claude Code hooks reference contradicts how the existing hooks read input.
- Migration finds legacy content that no fragment format can hold verbatim.
- (ACCESS, not DECISION) GitHub's REST merge or check-run endpoints, or every enabled model provider's API, are unreachable from the session.

## Must-catch behaviours
Every must-catch item in section 8 of WO-1.0-01 to WO-1.0-11, each with an acceptance test and a break recipe, and in particular:
1. A bundle path outside a work order's outputs writes nothing.
2. The relay sends only listed files and never handles a key.
3. A stale map fails `tools.index check`; a capability cannot vanish without a retirement record.
4. A blocker without a capability class fails lint; migration keeps every legacy ID and its text.
5. The merge gate refuses on: an audit that does not cover head, pending or failed CI, a stale base, an open blocker, a NEVER path, a missing blocking owner-run check; a dry run never merges; the merge is pinned to the head SHA.
6. A broken break recipe is never reported as caught; worktrees are always removed.
7. Spec allowances come only from `origin/main` and apply only on their WP's branch.
8. The stop gate blocks a weakened or newly skipped test even with a TEST_CHANGES record.
9. The loop guard warns at 3, blocks at 5, resets on success, and escalates environment failures at 2.
10. The bash guard blocks raw merges and pushes to `main` and allows the merge gate.
11. Regeneration on `main` cannot trigger itself; pull-request jobs are read-only; the main guard flags an unexpected commit; kit parity fails on drift.
12. Nothing that exists today breaks: the WP-0.0 pattern-parity tests and the WP-0.9 memo checks pass unmodified on the branch, after the merge, and after the owner installs the staged kit.
13. The relay paces every model and provider under the pool file's limits, moves a step to the next eligible model when one is used up, pauses only when the whole eligible pool is, resumes at the next unaccepted step from the pushed `wo/<WO>` branch, and never sends a T1 order to a model not listed for T1.
