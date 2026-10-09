# Autonomy: what Claude decides, what gates decide, what the owner decides

Control rests on checks Claude cannot argue with: the spec the owner commits, an independent audit, CI, the stop gate and the merge gate. Claude owns everything that clears the bar; the owner owns everything that sets it.

## Who decides what

| Matter | Decided by | Record |
| --- | --- | --- |
| A plan that covers every spec ID with no deviation | Claude (self-approval after a clean plan check) | `PLAN-STATUS: SELF-APPROVED` in the plan |
| A choice inside the spec's intent (equivalent options, pins, helpers, file layout) | Claude | Decision record `DEC-<WP>-<nn>` |
| An allowed kind of test change | Claude, confirmed by the auditor | `TEST_CHANGES.md` |
| A MAJOR finding accepted as debt inside the phase, touching no exit criterion or must-catch behaviour | Claude | Decision record and debt fragment |
| Merging a WP | The merge gate | Gate output in the pull request's merge commit title |
| Spec deviations, requirement or threshold changes, debt beyond the phase, new spending, licences, deletions outside the repo | Owner | DECISION blocker, then the owner's answer |
| Specs, process, kit, NEVER paths | Owner | Commits on `main` |

## Decision records
Template: `templates/DECISION.md`. A decision record can never:
1. weaken, skip or delete a test;
2. change a requirement, a threshold or an exit criterion;
3. touch a NEVER path;
4. add synthetic or substitute data where the spec needs real data;
5. widen network access, credentials or security permissions;
6. spend money or start a paid service or trial.
The owner reads new decision records in the weekly digest (the owner queue lists them). A veto starts a revert WP; the vetoed record stays, marked VETOED.

## Merge gate criteria
`tools/autonomy/merge_gate.py` (WP-1.0) merges only when all hold, and then merges through GitHub's REST endpoint pinned to the head commit:
1. **Audit**: `docs/progress/<WP>/AUDIT.md` says `Verdict: PASS` for the head commit, or for an earlier commit followed only by commits that touch `docs/progress/<WP>/**` and fragments.
2. **CI**: every check run and status on the head commit has completed with success.
3. **Fresh base**: the branch contains the current `origin/main`.
4. **Findings and blockers**: no open blocker for the WP; no open CRITICAL; every MAJOR fixed or accepted under the debt rule.
5. **Paths**: no NEVER path changed; guarded paths changed only where the spec or an approval allows.
6. **Owner-run checks**: every check the spec marks `blocking` has a committed PASS report.
7. **Status**: the WP's status fragment says AUDIT-PASS.
The bash guard hook (WP-1.0) blocks `gh pr merge`, hand-made merge API calls and pushes to `main`; a main-guard workflow opens an issue for any commit on `main` that did not come through a gated merge, a CI regeneration commit or an owner edit of NEVER paths.

## Owner-run checks
The spec marks each check `blocking` (the merge waits) or `post-merge` (queued; must pass before phase exit). Post-merge checks are batched into one weekly Colab notebook run. Oracle checks become CI jobs once the Oracle runner is registered.

## Interim rules (until WP-1.0's tooling is merged and its hooks installed)
1. Merges: Claude checks the merge criteria by hand, records them in `EVIDENCE.md`, sets MERGE-READY and raises a KIT blocker; the owner clicks Merge.
2. Existing tests: any modification still needs an owner `ALLOW-EDIT:` approval (the v3 stop gate enforces this).
3. Guarded paths: approval files only; spec allowances take effect with the hook update.
4. Loop guard: an instruction in rule 10, not yet a hook.
5. Blockers and decisions: written as fragments already; the legacy `BLOCKERS.md` and `DEBT.md` stay as they are until WP-1.0 migrates them.
