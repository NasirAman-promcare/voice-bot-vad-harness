# PLAN — WP-1.0 Operating model v2: tooling, migration and Phase 0 debts

PLAN-STATUS: SELF-APPROVED (2026-10-10, plan-checker clean)
Spec: `docs/specs/phase-1/WP-1.0-operating-model-v2.md` · Tier: T1 · Size: L · Thread model: Opus, high · Date: 2026-10-10
Branch: `claude/wp-1-0-operating-model-v2` (DEC-1.0-01) · Base: `origin/main` at `7d39036` · Depends on: WP-0.9 (MERGED), kit patch 4 (on `main`, `e3cb080` and `7d39036`)

## Summary
When this WP is done, the lab runs on operating model v2:
- **Outsourcing.** The work-order tools and the paced, step-wise model relay (WO-01, -02, -10, -11) exist.
- **Records and gates.** The Lab Map with its generated registry (WO-03), the progress fragments with their generated tables (WO-04), the merge gate (WO-05) and the break suite (WO-06) exist.
- **Kit and CI.** Kit v4 hooks and settings are staged in `kit-staging/.claude/` (WO-07, -08), and the six CI workflows run (WO-09).
- **Migration.** The legacy tables are migrated to fragments and the registry is adopted.
- **Debts.** DEBT-032, DEBT-033 and DEBT-034 are closed.

Claude writes the acceptance tests, the break recipes, the order amendments, the debt fixes and the migration run. The models write the tooling through the eleven committed work orders.

## Requirements
| Requirement | Approach | New files | Changed files and functions (change budget) | Tests | Acceptance command | Built by |
| --- | --- | --- | --- | --- | --- | --- |
| FR-1.0-01 | WO-1.0-01 as written | `tools/outsourcing/{__init__,__main__,workorder,paths,secrets,bundle,importer,scope,pack}.py`, unit tests | none | `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py` (`test_FR_1_0_01_*`), implementer unit tests | AT-1.0-01 | WO-1.0-01 (Jules) |
| FR-1.0-02 | WO-1.0-02 (building blocks), then WO-1.0-11 (orchestration) | `tools/outsourcing/{records,interface,prompt,checks,fixorder,steplog,router,worktree,ledger,stepper,relay}.py`, unit tests | none | `test_acceptance_wo_1_0_02.py`, `test_acceptance_wo_1_0_11.py` (`test_FR_1_0_02_*`) | AT-1.0-01, AT-1.0-06, AT-1.0-08 | WO-1.0-02, WO-1.0-11 (Jules) |
| FR-1.0-03 | WO-1.0-03; then Claude runs `python -m tools.index build --adopt-registry` and accounts for every legacy registry row in EVIDENCE | `tools/index/**`, `docs/capabilities/retired.d/*.md` (from adoption) | none (the generated `docs/index/*` and `REGISTRY.md` are never committed on the branch) | `tests/aqis_lab/index/test_acceptance_wo_1_0_03.py` (`test_FR_1_0_03_*`) | AT-1.0-02 | WO-1.0-03 (relay) |
| FR-1.0-04 | WO-1.0-04; then Claude runs `python -m tools.progress migrate` and commits the fragments. The legacy tables stay untouched on the branch and are regenerated on `main` | `tools/progress/**`, `docs/progress/{status,blockers,debt}.d/*.md` (migrated) | none | `tests/aqis_lab/progress/test_acceptance_wo_1_0_04.py` (`test_FR_1_0_04_*`) | AT-1.0-03 | WO-1.0-04 (relay); migration run by Claude |
| FR-1.0-05 | WO-1.0-05 | `tools/autonomy/**` | none | `tests/aqis_lab/autonomy/test_acceptance_wo_1_0_05.py` (`test_FR_1_0_05_*`) | AT-1.0-05 | WO-1.0-05 (relay) |
| FR-1.0-06 | WO-1.0-06 | `tools/audit/{breaks,mutate,mutation_report}.py` | none (`tools/audit/gate.py` and `patterns.py` unchanged) | `tests/aqis_lab/audit_breaks/test_acceptance_wo_1_0_06.py` (`test_FR_1_0_06_*`) | AT-1.0-04 | WO-1.0-06 (relay) |
| FR-1.0-07 | WO-1.0-07, staged in `kit-staging/.claude/hooks/`. Before sending: `docs/outsourcing/refs/claude-code-hooks.md`, plus context and verify additions | `kit-staging/.claude/hooks/{_protected,guard_protected,stop_gate,session_context}.py`, `kit-staging/.claude/hooks/.gitignore` (the hooks folder's own ignore file) | none in `.claude/` (NEVER) | `tests/aqis_lab/kit/test_acceptance_wo_1_0_07.py` (`test_FR_1_0_07_*`); the WP-0.0 parity tests, unmodified | AT-1.0-01 | WO-1.0-07 (relay) |
| FR-1.0-08 | WO-1.0-08, staged | `kit-staging/.claude/hooks/{_loopstate,loop_guard,bash_guard}.py`, `kit-staging/.claude/settings.json` | none | `tests/aqis_lab/kit/test_acceptance_wo_1_0_08.py` (`test_FR_1_0_08_*`) | AT-1.0-01 | WO-1.0-08 (relay) |
| FR-1.0-09 | WO-1.0-09. Before sending: the existing `aqis-lab-*.yml` go into its context, with a note on how they set up Python | `.github/workflows/aqis-lab-{generate,breaks,scope,main-guard,mutation,kit-parity}.yml`, `tools/ci/**` | none | `tests/aqis_lab/ci/test_acceptance_wo_1_0_09.py` (`test_FR_1_0_09_*`) | AT-1.0-01; CI on the PR | WO-1.0-09 (relay) |
| FR-1.0-10 | Add `.relay/` to `.gitignore` | none | `.gitignore`: one appended line (GUARDED; the spec allows it, and the v3 hooks still need an approval, BLK-1.0-02) | `tests/aqis_lab/ci/test_wp_1_0_requirements.py::test_FR_1_0_10_gitignore_ignores_relay` (`git check-ignore`) | AT-1.0-01 | Claude |
| FR-1.0-11 | **DEBT-032**: commit the owner's full Colab output of `dev_bootstrap.sh --gpu` as `docs/progress/WP-0.8/OC-0.8-03_bootstrap_gpu_full.txt`; a test checks the `OK: GPU extras installed: requirements/aqis_lab/phase0-gpu.txt sha256 <hash>` line against the lock's real hash.<br>**DEBT-033**: one sentence in `docs/adapters/PARAKEET_UNIFIED.md` naming `phase0-gpu.in`; a test checks it against the lock files.<br>**DEBT-034**: add the case `"- X{debt} moves to {wp}."` (not approved) to the existing parametrised test. Each debt fragment is set to CLOSED | `docs/progress/WP-0.8/OC-0.8-03_bootstrap_gpu_full.txt` (owner output), `tests/aqis_lab/ci/test_wp_1_0_requirements.py` | `docs/adapters/PARAKEET_UNIFIED.md` (the sentence near line 70); `tests/aqis_lab/test_aqis_phase0_memo.py`: one parametrize row and its id added to `test_FR_0_9_01_move_approval_names_row_and_wp_on_one_line`, with no other change (add-cases, `TEST_CHANGES.md`; the WP-0.9 approval's `ALLOW-EDIT` applies, DEC-1.0-02) | `test_FR_1_0_11_debt032_*`, `test_FR_1_0_11_debt033_*`, the new `longer-debt-id-on-the-left` case | AT-1.0-01 | Claude; DEBT-032's output comes from the owner (COMPUTE, BLK-1.0-03) |
| FR-1.0-12 | KIT blocker with the exact copy steps, raised after the audit passes; after installation, the kit parity check and the operator-guide self-test; Claude resolves the blocker | none | none | `tests/aqis_lab/ci/test_acceptance_wo_1_0_09.py` (kit parity); OC-1.0-01 | `python -m tools.ci.kit_parity` | Claude, with the owner (KIT) |
| FR-1.0-13 | Each order has its summary and ledger fragment, and each relay order its step log. Orders 01 and 10 go to Jules together, then 02, then 11; 03 to 09 go through the relay. For Jules orders, Claude writes `docs/outsourcing/returns/<WO>/summary.md` and `ledger.d/<WO>.md` from the PR facts | `docs/outsourcing/returns/*/`, `docs/outsourcing/ledger.d/*.md` | `docs/outsourcing/orders/WO-1.0-03,04,07,09.md` (the pre-send amendments the orders themselves require: read-only test path, context and verify lists) | `tests/aqis_lab/ci/test_wp_1_0_requirements.py::test_FR_1_0_13_every_order_has_summary_and_ledger` | `tools.progress lint` (ledger fragments) | Claude, with the owner (EXTERNAL-AI, BLK-1.0-01) |
| FR-1.0-14 | WO-1.0-10 (clients, governor, quota), and the router in WO-1.0-11 | `tools/outsourcing/{chat,limits,quota,governor,gemini_client,openai_client}.py`, `tests/aqis_lab/outsourcing/stub_model_server.py` | none | `test_acceptance_wo_1_0_10.py` (`test_FR_1_0_14_*`); `test_acceptance_wo_1_0_11.py` router tests | AT-1.0-08, AT-1.0-09 | WO-1.0-10 (Jules) |
| NFR-1.0-01 | Every order allows `stdlib` only. A test scans the imports of `tools/{outsourcing,index,progress,autonomy,ci}`, `tools/audit/{breaks,mutate,mutation_report}.py` and `kit-staging/` against `sys.stdlib_module_names` and the repository's own packages | none | none | `tests/aqis_lab/ci/test_wp_1_0_requirements.py::test_NFR_1_0_01_tools_import_stdlib_only` | AT-1.0-01 | Claude |
| NFR-1.0-02 | Measure the staged v4 stop gate as a subprocess on the VM after a one-module change, with impact selection; record the time in EVIDENCE | none | none | `tests/aqis_lab/kit/test_acceptance_wo_1_0_07.py::test_NFR_1_0_02_*` (marked `slow`), plus the recorded measurement | measured command in EVIDENCE | Claude |
| NFR-1.0-03 | Line limits: relay ≤ 25 (WO-11 B18), stop gate ≤ 40 (WO-07 B8), session context ≤ 15 (WO-07 B10) | none | none | `test_NFR_1_0_03_*` in the WO-07 and WO-11 acceptance tests | AT-1.0-01 | WO-07, WO-11 |

Acceptance commands AT-1.0-01 to AT-1.0-09 (AT-1.0-07, the audit gate with `--wp WP-1.0`, included) are run as the spec states and recorded in EVIDENCE. AT-1.0-09 is owner-run only if the session cannot reach the providers; this session's environment already injects both model hosts' credentials, so Claude runs it once the relay exists.

## Must-catch behaviours
The spec's must-catch list is every section-8 item of WO-1.0-01 to WO-1.0-11 (93 items), plus spec items 1 to 13.
- **Acceptance tests.** Each WO item has one acceptance test named `test_FR_1_0_<nn>_mc<k>_<behaviour>` in that order's `test_acceptance_wo_1_0_<nn>.py`, and one break recipe `tests/aqis_lab/breaks/WP-1.0/MC-<WO>-<k>-<slug>.patch`.
- **Spec items.** The spec items map onto WO items:

| Spec # | Behaviour | Covered by (WO must-catch) | Extra test |
| --- | --- | --- | --- |
| 1 | Bundle path outside outputs writes nothing | WO-01 #1 | |
| 2 | Relay sends only listed files, never handles a key | WO-02 #1, #2; WO-10 #8; WO-11 #1 | |
| 3 | Stale map fails `check`; capability cannot vanish | WO-03 #1, #2 | |
| 4 | Blocker without class fails lint; migration keeps IDs and text | WO-04 #1, #3 | |
| 5 | Merge gate refusals, dry run, SHA pin | WO-05 #1 to #8 | |
| 6 | Broken recipe never caught; worktrees removed | WO-06 #1, #3 | |
| 7 | Spec allowances only from `origin/main`, only on their WP's branch | WO-07 #1 to #3 | |
| 8 | Weakened or newly skipped test blocked even with a record | WO-07 #4, #5 | |
| 9 | Loop guard 3/5/reset/environment at 2 | WO-08 #1 to #4 | |
| 10 | Bash guard blocks raw merges and pushes to `main`, allows the gate | WO-08 #5 | |
| 11 | Regeneration cannot self-trigger; PR jobs read-only; main guard; kit parity | WO-09 #1, #2, #3, #5 | |
| 12 | Nothing that exists today breaks | the full fast suite, unmodified, on the branch, after merge and after kit install | `test_FR_1_0_07_mc_parity_tests_pass_against_staged_hooks` runs the WP-0.0 parity tests against the staged copies |
| 13 | Relay pacing, switching, pausing, resuming, T1 routing | WO-10 #1 to #3; WO-11 #2, #3, #13 | |

**When the recipes are written.** A break recipe is a diff against the code it breaks, so each order's recipes are written right after that order's code is merged into the WP branch. They are all in place before READY-FOR-AUDIT, and the break suite (AT-1.0-04) must report every one caught. The acceptance tests come first: each is committed and seen failing before its order is sent.

**DEBT-034 and spec item 12.** The added case is an add-cases change, recorded in `TEST_CHANGES.md`. All six existing cases stay byte-identical and must pass. Spec item 12 is read as: no existing assertion or case changes.

## Work orders
| WO | Files | Approx. lines | Model | Channel |
| --- | --- | --- | --- | --- |
| WO-1.0-01 | `tools/outsourcing` parser, importer, scope, pack + 8 test files | 1,900 | Jules | jules (wave 1) |
| WO-1.0-10 | clients, governor, quota, limits + stub + 5 tests | 2,200 | Jules | jules (wave 1, parallel) |
| WO-1.0-02 | relay building blocks + 6 tests | 2,000 | Jules | jules (wave 2) |
| WO-1.0-11 | router, worktree, ledger, stepper, relay + 5 tests | 2,000 | Jules | jules (wave 3) |
| WO-1.0-03 | `tools/index` + tests | 1,700 | pool (T1) | api |
| WO-1.0-04 | `tools/progress` + tests | 1,700 | pool (T1) | api |
| WO-1.0-05 | `tools/autonomy` + stand-in gh + tests | 1,500 | pool (T1) | api |
| WO-1.0-06 | `tools/audit/{breaks,mutate,mutation_report}` + tests | 1,100 | pool (T1) | api |
| WO-1.0-07 | staged hooks v4 + tests | 1,700 | pool (T1) | api |
| WO-1.0-08 | loop guard, bash guard, settings v4 + tests | 1,300 | pool (T1) | api |
| WO-1.0-09 | 6 workflows, `tools/ci` + tests | 1,200 | pool (T1) | api |

Claude keeps: the 11 acceptance test files, every break recipe, the pre-send amendments of WO-03, -04, -07 and -09, the hooks reference file, the debt fixes, the migration and adoption runs, the records, and fixes under about 30 lines after review.

## Owner needs
| # | Capability class | What | Why | Needed by |
| --- | --- | --- | --- | --- |
| 1 | EXTERNAL-AI | Start Jules for WO-1.0-01 and WO-1.0-10 together, then WO-1.0-02, then WO-1.0-11 (BLK-1.0-01; one wave at a time) | FR-1.0-13 makes these four bootstrap orders go through Jules or paste | Now (wave 1) |
| 2 | KIT | Commit `docs/approvals/WP-1.0.md` with `ALLOW-EDIT: .gitignore` (BLK-1.0-02) | Spec allowances act only from the hook update. Until then, the v3 hooks require an approval for GUARDED `.gitignore` (AUTONOMY interim rule 3) | Before FR-1.0-10 is committed |
| 3 | COMPUTE | Run `bash aqis_lab/deploy/dev_bootstrap.sh --gpu` on a Colab GPU runtime and upload the full output (BLK-1.0-03) | DEBT-032's fix is that output | Before READY-FOR-AUDIT |
| 4 | ACCESS | The spec's credential need (Gemini; Mistral recommended) appears already met: this session's environment lists proxy-injected credentials for `generativelanguage.googleapis.com` and `api.mistral.ai`, and `config/aqis_lab/model_pool.json` already has Mistral `enabled: true`. Claude confirms with `relay --models` once the relay exists, and raises an ACCESS blocker only if that fails | AT-1.0-09; relay orders | Before WO-1.0-03 |
| 5 | KIT | Interim merge (AUTONOMY interim rule 1: MERGE-READY, the owner clicks Merge); then install `kit-staging/.claude/` (FR-1.0-12) | The merge gate's hooks are not installed until this WP lands | After the audit passes |
| 6 | ACCESS (optional) | Register the Oracle runner and set `AQIS_HEAVY_RUNNER` | Heavy CI jobs; falls back to `ubuntu-latest` | Any time |

## Owner-run checks
| Check | Blocking or post-merge (from spec) | Where | Command | Expected output |
| --- | --- | --- | --- | --- |
| OC-1.0-01 Kit self-test after install | post-merge | new cloud session | the self-test prompt in `docs/OPERATOR_GUIDE.md` | every step as the guide says |
| OC-1.0-02 First generation on `main` | post-merge | GitHub Actions | the `aqis-lab-generate` run after the merge | a `chore(bot):` commit with `docs/index/` and the generated tables |

## Risks and questions
1. **Acceptance tests waiting for Jules must not mask other tests.** Each acceptance file imports its modules inside the tests, not at module level. Every test then fails on its own with `ModuleNotFoundError`, with no collection error and nothing aborted under `-x`. While the orders are out, the stop gate shows these expected failures; BLK-1.0-01 records them.
2. **Interfaces the orders leave open.** Where an order does not pin a name or type that an acceptance test needs, Claude amends the order in the same commit as the test. The amendment pins only what the test relies on. Two examples: the clock, sleeper and random parameters in WO-10, and record field names.
3. **The relay's own exit 11 and 12** (quota and busy) are waits, not failures. Claude keeps building other parts while it waits.
4. **Generated files.** `docs/index/*`, `REGISTRY.md` and the progress tables are never committed on this branch; CI regenerates them on `main` (OC-1.0-02). Every legacy row stays accounted for through fragments and retirement records.
5. **The hooks reference** (WO-07 pre-send). If it cannot be fetched from the session, that is an ACCESS item. If it contradicts how the current hooks read input, that is a DECISION trigger from the spec.

## Deviations from the spec
None. Notes, none of which changes a requirement, a path outside Touches or a test:
- **Requirement tests.** The tests for FR-1.0-10, FR-1.0-11, FR-1.0-13 and NFR-1.0-01 live in `tests/aqis_lab/ci/test_wp_1_0_requirements.py`, which is inside Touches (`tests/aqis_lab/ci/**`). The two DEBT-named files are touched as their rows describe.
- **`.gitignore` approval (BLK-1.0-02).** This is the spec's own allowed guarded edit, made effective under AUTONOMY interim rule 3. It is not a new scope. `docs/approvals/` is a NEVER path, hence the KIT class.
- **ACCESS (owner need 4).** This need is expected to be met already. It is verified, not assumed.
