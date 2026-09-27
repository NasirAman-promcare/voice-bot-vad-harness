# AUDIT — WP-0.4, round 2

Auditor: wp-auditor · Date: 2026-09-27 · Commit audited: 507a1bfb24e5e2a333d76668c3ea5878940eccad · Previous audited commit: 55f9b5137baa0beb277fb1b5eb5e3a5043b0c449 · Protocol: version 2

## Verdict: PASS
CRITICAL: 0 (F01 fixed) · MAJOR: 1 (fixed 1, accepted as debt 0, open 0) · MINOR: 6 (fixed 1: F06; accepted as debt 3: F03, F04, F05; new and open 2: F07, F08)

Both round 1 blockers are fixed, and I checked this myself.
- **F01 (CRITICAL):** `pack verify` now reports a listed archive, `LICENCES.md` or `build_record.json` that is a folder, a broken symbolic link, a link loop or a FIFO. Each gives `INVALID` and exit 1, where round 1 gave `OK` and exit 0. A symbolic link to the real file is still accepted.
- **F02 (MAJOR):** a `member_path` named by two clips is now reported. The member is also checked against both clips, so the round 1 probe now gives 3 problems and exit 1.

Other checks:
- AT-0.4-01, AT-0.4-02 and AT-0.4-03 reproduce.
- The fast suite (1365) and the slow suite (14) pass, and CI is green on `507a1bf`.
- All 26 must-catch breaks fail a named test. These are the 24 from round 1, re-run on the new code, plus two that bring back the F01 and F02 behaviour.

I found two new MINOR findings, and neither blocks:
- **F07:** two round 2 records say evidence is in `EVIDENCE.md` when it is not there. I verified the underlying results myself.
- **F08:** three branches of the round 2 fix have no test. None of them can make verify report success.

## Scope of this audit
Re-audit under `docs/process/AUDIT_PROTOCOL.md` version 2. It covers:
- the six round 1 findings;
- items A1 to A15 on the diff since the last audited commit;
- the full fast and slow suites, the gate, CI and the complete must-catch proof.

Unchanged code that passed round 1 was not searched again.
- **Diff audited:** `55f9b51` to `507a1bf`, 9 files, +297 −12, in 3 commits: `8f60076`, the round 1 audit; `072ffd7`, a merge of `origin/main` that brings only the approval line from `458b1b3`; and `507a1bf`, the fixes.
  - The only code change is `aqis_lab/packs/verify.py` (+52 −12).
  - Tests: 64 lines appended to `tests/aqis_lab/test_aqis_packs_verify.py`.
  - Documents: the CAP-PACK-006 row of `REGISTRY.md`, one sentence of `SMOKE_PACK.md`, three `DEBT.md` rows, `EVIDENCE.md` and `FIXES.md`.
- **Environment:** `bash aqis_lab/deploy/dev_bootstrap.sh` gives `OK: .venv ready: Python 3.13.12, lock sha256 84151d8f…2acc`.
- **Breaks** were made only in a throwaway copy, `/tmp/wp04-audit-r2/repo`:
  - The copy was made with `git archive HEAD` and has its own git repository, used only for restoring.
  - `aqis_lab.__file__` resolves to `/tmp/wp04-audit-r2/repo/aqis_lab/__init__.py`, and the unmodified copy gives `183 passed, 1196 deselected` on `-k "FR_0_4 or NFR_0_4"`. That is round 1's 175 plus the 8 new cases.
  - Each break is an exact-string replacement, checked to match exactly once.
  - Every run used `PYTHONDONTWRITEBYTECODE=1`, with `__pycache__` removed first.
  - The copy was restored with `git checkout` and `git clean` after each break, and `git status --short` in the copy was empty at the end.
  - The repository itself was never modified. `git status --short` was empty before I wrote this report.
- **Probes:** I ran the shipped code, unchanged, on copies of the committed pack under `/tmp/wp04-audit-r2/probe/`. These are inputs, not code breaks, and are not counted against the A15 limit.

## Previous findings
| ID | Round 1 severity | Status now | Evidence |
| --- | --- | --- | --- |
| WP-0.4-F01 | CRITICAL | **FIXED** | Probe table below: every non-regular input that gave `OK` in round 1 now gives `INVALID`, exit 1. New tests: `test_FR_0_4_05_verify_fails_on_archive_that_is_not_a_file` (folder, dangling_symlink) and `test_FR_0_4_05_verify_fails_on_pack_file_that_is_not_a_file` (`LICENCES.md` and `build_record.json`, each as a folder and as a dangling symlink); the guard test `test_FR_0_4_05_verify_accepts_link_to_a_real_archive`. Must-catch break 3d brings the silent skip back, and 6 cases fail |
| WP-0.4-F02 | MAJOR | **FIXED** | Round 1 probe re-run: `validate_manifest` still passes, and verify now reports `member 'test-clean/ls-test-clean-121-127105-0012.wav' is named by 2 clips (ls-test-clean-1188-133604-0029, ls-test-clean-121-127105-0012)…`, plus the first clip's `SHA-256 f41465b0… differs from clip ls-test-clean-1188-133604-0029 (7c26dd27…)` and `lasts 4.83 s, the manifest says 3.705`. That is `INVALID, 3 problem(s)`, CLI exit 1 (round 1: `ok: True []`). New test: `test_FR_0_4_05_verify_fails_on_duplicate_member_path`. Must-catch break 3e brings "last clip wins" back, and it fails |
| WP-0.4-F03 | MINOR | Accepted as debt | DEBT-010, target WP-0.8. Round 2 condition line in `docs/approvals/WP-0.4.md` on `main` (`458b1b3`) |
| WP-0.4-F04 | MINOR | Accepted as debt | DEBT-011, target WP-0.5. Same condition line |
| WP-0.4-F05 | MINOR | Accepted as debt | DEBT-012, target WP-0.8. Same condition line |
| WP-0.4-F06 | MINOR | **FIXED** (a wording remnant is part of F07) | `SMOKE_PACK.md:75` now gives the measured levels, and `EVIDENCE.md:116-121` gives the output. My own measurement on the committed pack, reading each member from its archive: `smoke-mix-06 RMS -23.6 dBFS peak 32767 {'peak_limited': True, 'snr_db': 10, 'achieved_snr_db': 10.0}`, `smoke-music-03 RMS -48.9 dBFS peak 1048`, `smoke-noise-04 RMS -47.7 dBFS peak 627`. These are identical to the documented values |

### F01 and F02 probes (shipped code at `507a1bf`, copies of the committed pack)
| Input | Round 1 (`55f9b51`) | Round 2 (`507a1bf`) |
| --- | --- | --- |
| tts archive replaced by an empty folder | `OK … tts 10`, exit 0 | `smoke-1.0.0-tts-000.tar: is a folder, not a file; nothing in it can be checked`, `INVALID, 1 problem(s)`, exit 1 |
| tts archive as a dangling symlink | `OK`, exit 0 | `…: is a broken symbolic link (to '/tmp/wp04-audit-r2/probe/nowhere/x.tar'); the file it points to is missing…`, exit 1 |
| `LICENCES.md` as a folder, and `build_record.json` as a dangling symlink | `OK`, exit 0 | 2 problems (`LICENCES.md: is a folder…`, `build_record.json: is a broken symbolic link…`), exit 1 |
| tts archive as a symlink to a folder | not probed | `is a folder, not a file`, exit 1 |
| tts archive as a symlink to itself (a loop) | not probed | reported as a broken symbolic link, exit 1 |
| tts archive as a FIFO | not probed | `is not a regular file`, exit 1, with no hang (`timeout 20` not reached) |
| tts archive moved elsewhere and linked back | not probed | `OK, 60 clips…`, exit 0: a link to a real file is accepted, as intended |
| tts archive as a symlink to the noisy archive | not probed | `INVALID, 22 problem(s)` (missing tts members and others), exit 1 |

## Checklist
| Item | Result | Evidence |
| --- | --- | --- |
| A1 Scope and dependencies | PASS | `git show origin/main:docs/progress/STATUS.md`: WP-0.0 and WP-0.2 are `MERGED`. The branch is `claude/optimistic-ptolemy-tdbotx` (not `main`), and `HEAD` = `origin/claude/optimistic-ptolemy-tdbotx` = `507a1bf`. GitHub API: PR #4 `open`, head `507a1bfb24e5…`, base `main`, `merged: false`. `docs/approvals/WP-0.4.md` on `main` (`458b1b3`) says `STATUS: APPROVED`, with the round 2 condition: fix F01, F02 and F06; accept F03 (WP-0.8), F04 (WP-0.5) and F05 (WP-0.8) as debt. `git diff --stat origin/main HEAD -- docs/approvals/ docs/specs/ docs/process/ CLAUDE.md .claude/ .gitignore corpus-v1.tar.gz` is empty. The approval-file change in `55f9b51..HEAD` comes only from merge `072ffd7`: `git diff --stat 8f60076 072ffd7` lists only `docs/approvals/WP-0.4.md`, 1 line, the same as `655b4e1..458b1b3` on `main` |
| A2 Requirement coverage | PASS | Round 2 adds 4 test functions (8 cases) named for FR-0.4-05, and all are collected (`test_aqis_packs_verify.py`: `27 tests collected`). All 17 test names in the CAP-PACK-006 header and registry row, and every `test_FR_0_4_05_verify_*` name in `EVIDENCE.md` and `FIXES.md`, are in `pytest --collect-only tests/aqis_lab`. `EVIDENCE.md` "Round 2" lists the new tests under F01 and F02. No other code changed, so round 1's coverage of the other IDs stands |
| A3 Acceptance commands | PASS | **AT-0.4-01**, the exact command in `PLAN.md`: both builds print `built pack smoke 1.0.0 … 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10`, then `exit=0` with no diff output. The eight SHA-256 values equal the committed files (`LICENCES.md c90dc5a0…`, `build_record.json 70fdb84c…`, `manifest.json 16c383bf…`, `…-tts-000.tar cc0ee350…`, …). **AT-0.4-02:** `pack smoke 1.0.0: OK, 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10`, exit 0. **AT-0.4-03:** `aqis-audit-gate: base origin/main (merge-base 458b1b30f484), head 507a1bfb24e5 … Findings: 0 … 0 findings: OK (0.6 s)`, exit 0. **NFR-0.4-01:** `time pack build …` gives `real 0m0.906s` |
| A4 Test suites and CI | PASS | **Fast** (`-m "not slow and not gpu and not colab and not oracle and not network"`): `1365 passed, 14 deselected in 144.85s`, exit 0. **Slow CPU** (`-m "slow and not gpu and not colab and not oracle" -rA`): `14 passed, 1365 deselected in 1119.12s`, exit 0. This includes `PASSED …test_FR_0_4_05_rebuild_equals_committed_smoke_pack`, `…test_NFR_0_4_01_smoke_build_under_2_minutes` and `…test_FR_0_4_02_dataset_pins_match_openslr`. The long run time is disk reads of the 11 GB MUSAN archive (about 11 MB/s this session); the build itself is timed separately. **CI on `507a1bf`** (GitHub API): run 36341331247 (push) and run 36341333664 (pull_request) have jobs `lab` and `harness-regression`, all `success`. In both runs, the `lab` steps "Fast lab test suite" and "Audit gate (pull request base with --wp, or origin/main on push)" are `success`. "Work package ID from pull request title" is `skipped` on push, as designed. `EVIDENCE.md` does not record this CI result (F07) |
| A5 Test integrity | PASS | `git diff --name-status origin/main HEAD -- tests/` lists only added files, so no test that exists on `main` changed. The round 2 test diff removes 0 lines; it appends the helper `_replace_with` and 4 tests at the end of `test_aqis_packs_verify.py`. There is no `skip`, `xfail`, `importorskip` or `audit-allow`; the only grep hit for "skip" is the docstring phrase "never skipped". Each new test asserts the specific problem text, and the guard test asserts `.ok`. One small looseness: `…_pack_file_that_is_not_a_file` checks the file-name prefix and the expected text on possibly different problem lines. Only `_not_a_file` produces those texts, so this cannot pass falsely today; not a finding |
| A6 Must-catch proof | PASS | 26 breaks across the spec's 6 behaviours, and every one fails at least one named test (table below). These are the 24 round 1 breaks, re-run on the new code (3b rewritten for the renamed `named` variable), plus 3d and 3e, which bring back the F01 and F02 behaviour |
| A7 Compromise scan | PASS | Gate: `Findings: 0`, `Exempted lines (# audit-allow): 0`, `Exempted files (ALLOW-PATTERNS-IN): 0`. My grep of the added lines in `aqis_lab/` and `tests/` for `TODO`, `FIXME`, `XXX`, "placeholder", "simplif", "for now", "temporar", "hack", "dummy", "fake", `NotImplementedError`, bare `pass`, bare or broad `except`, `os.environ` and `pytest` in code found nothing. I read the new code: `_not_a_file` (`verify.py:137-146`) returns a reason for a broken link, a folder or any other non-regular file, and every reason is appended as a problem (`:178-184`). The only skip, `continue  # reported above as missing or as not a file` (`:188`), applies to entries already reported. No values are hard-coded |
| A8 Scope diff | PASS | `git diff -U0 55f9b51 HEAD -- aqis_lab/packs/verify.py` has hunks only in the header (capability text, change log), `import os`, `_check_members`, the new `_not_a_file` (inserted after `_check_clip_bytes`, which is unchanged) and `verify_pack`. This matches the `FIXES.md` change budget. Tests: append-only. `REGISTRY.md`: only the "What it does" and "Tests" cells of CAP-PACK-006 changed; 4 tests were added to the cell, none removed, and every other row is byte-identical. `SMOKE_PACK.md`: the one sentence at line 75. `DEBT.md`: 3 rows appended. `STATUS.md`: the WP-0.4 row only. `git diff --stat 55f9b51 HEAD -- data/ packs/ aqis_lab/contracts/ docs/contracts/ requirements/` is empty. No GUARDED or NEVER path changed |
| A9 Capabilities | PASS | The `verify.py` header's CAPABILITIES text names the new checks and the 4 new tests, and CHANGE LOG has a round 2 entry. The CAP-PACK-006 row matches it, and no row was removed. The only callers of `verify_pack` are `aqis_lab/commands/pack.py` (unchanged) and tests, as `FIXES.md` says (`grep -rn verify_pack aqis_lab tools tests`). All 17 tests in the row are collected and pass in the fast suite |
| A10 Contracts | PASS | `contracts validate --kind manifest data/packs/smoke/v1/manifest.json` gives `record 1: OK`, `1 valid, 0 invalid`, exit 0. The committed pack is unchanged since round 1. The F02 probe shows that the WP-0.2 contract allows a repeated `member_path` (`validate_manifest` passes), so verify is the check that has to catch it, and it now does |
| A11 Environment parity | PASS | The added code and tests contain no absolute paths; the tests make their links under `tmp_path`. `os.readlink` and `Path.symlink_to` behave the same on the cloud VM, Colab and Oracle (all Linux). A link to a real file, such as a mounted Drive path, is still accepted (`…_accepts_link_to_a_real_archive`, and my probe). Locks unchanged; Python 3.13.12 against the Colab probe's 3.13. Owner-run checks: none, and that is justified, because the WP runs on the cloud VM and verify needs no sources or network |
| A12 Reproducibility and traceability | PASS | The build path is unchanged, since no builder module imports `verify.py`. AT-0.4-01 is byte-identical and equals the committed pack, and the slow rebuild test passes. The new verify output is deterministic: entries go through `sorted(expected_files & set(entries))` and `sorted(expected.items())` |
| A13 Errors and logging | PASS | The two round 1 silent-failure paths are closed (probe table). Every expected pack file that exists but is not a regular file is reported, and the CLI exits 1. A truly absent file is still `missing from the pack folder`. Nothing in the new code catches or discards an error |
| A14 Documentation, licences, data | PASS (with MINOR F07) | F06 is fixed, and the values match my measurement. Debt rows DEBT-010 to DEBT-012 are in `DEBT.md` with target WPs that match the approval. However, `SMOKE_PACK.md:75` says "the command and its output are in `EVIDENCE.md`"; `EVIDENCE.md:116` gives the output and a description of the method, but no command. `FIXES.md:52` says "Gate and CI: in `EVIDENCE.md`, 'Round 2'", and that section has the gate but no CI result (F07). No licence or data content changed |
| A15 Exploratory breaks | PASS (with MINOR F08) | 7 breaks, all in code changed in round 2 (table below). 4 are caught; 3 survive (X1, X2, X7). None of the survivors can make verify report success: under X1 the F02 probe still gives `INVALID, 1 problem(s)`, exit 1, and under X7 verify on a FIFO blocks until killed (`timeout 20` gives exit 124) and never prints `OK` |

## Must-catch proof (A6)
The runs used `pytest tests/aqis_lab -q -p no:cacheprovider -m "<fast markers>" -k "<named tests>"` in `/tmp/wp04-audit-r2/repo`, with bytecode disabled.

| Behaviour | Break made in /tmp copy | Test that failed | Result |
| --- | --- | --- | --- |
| 1 Licence and consent | 1a `registry.py`: missing-licence check off, and an empty licence skips the unknown-licence check | `test_FR_0_4_01_rejects_missing_licence`, `test_FR_0_4_01_cli_validate_exit_codes` (2 failed) | CAUGHT |
| 1 | 1b `registry.py`: `owner`/`campaign` rows with an empty `consent_ref` accepted | `test_FR_0_4_01_rejects_owner_row_without_consent`, `test_FR_0_4_01_cli_validate_exit_codes` (2 failed) | CAUGHT |
| 1 | 1c `registry.py`: a `consent_ref` naming no file, or a folder, accepted | `test_FR_0_4_01_rejects_consent_ref_that_does_not_resolve` (2 failed, 3 passed) | CAUGHT |
| 1 | 1d `importers.py`: owner import without `CONSENT.md` accepted | `test_FR_0_4_01_owner_import_rejects_bad_inputs` (1 failed, 7 passed) | CAUGHT |
| 2 Byte-identical builds | 2a `archive.py`: tar mtime from `time.time()` | `test_FR_0_4_05_tar_headers_are_normalised`, `…_build_twice_byte_identical`, `…_created_utc_comes_from_spec` (3 failed) | CAUGHT |
| 2 | 2b `select.py`: selection-key sort removed, rows in registry order | `test_FR_0_4_03_selection_ignores_registry_row_order`, `…_selection_key_is_the_documented_hash`, `test_FR_0_4_05_build_twice_byte_identical` (3 failed) | CAUGHT |
| 2 | 2c `build.py`: `created_utc` from the clock | `test_FR_0_4_05_created_utc_comes_from_spec`, `…_build_twice_byte_identical` (2 failed) | CAUGHT |
| 2 | 2d `build.py`: archive member order from set iteration (depends on `PYTHONHASHSEED`) | `test_FR_0_4_05_build_twice_byte_identical`, `…_members_in_documented_order` (2 failed) | CAUGHT |
| 3 Verify: changed, missing, extra member | 3a `verify.py`: member SHA-256 check off | `test_FR_0_4_05_verify_fails_on_changed_member`, `…_verify_fails_on_manifest_entry_mismatch` (2 failed, 4 passed) | CAUGHT |
| 3 | 3b `verify.py`: "extra member" problem (`if named is None`) and `n_members` check both off | `test_FR_0_4_05_verify_fails_on_extra_member` (1 failed) | CAUGHT |
| 3 | 3c `verify.py`: missing-member loop and `n_members` check both off | `test_FR_0_4_05_verify_fails_on_missing_member` (1 failed) | CAUGHT |
| 3 | 3d `verify.py`: F01 regression; a pack file that is not a regular file is left out of `readable` without a problem (`report.problems.append(f"{name}: {message}")` → `pass`) | `test_FR_0_4_05_verify_fails_on_archive_that_is_not_a_file`, `…_verify_fails_on_pack_file_that_is_not_a_file` (6 failed) | CAUGHT |
| 3 | 3e `verify.py`: F02 regression; clips indexed by `member_path`, last one wins (`expected[clip["member_path"]] = [clip]`) | `test_FR_0_4_05_verify_fails_on_duplicate_member_path` (1 failed) | CAUGHT |
| 4 Exact category counts | 4a `smoke_v1.yaml`: test-other 10 changed to 9 (category and part) | `test_FR_0_4_03_smoke_spec_declares_exact_composition` (1 failed) | CAUGHT |
| 4 | 4b `select.py`: returns the clips it found instead of failing when candidates run short | `test_FR_0_4_03_fails_when_too_few_candidates`, `…_tts_clips_need_3_to_8_seconds` (2 failed) | CAUGHT |
| 4 | 4c committed `manifest.json`: one test-other clip relabelled test-clean, build record re-pinned | `test_FR_0_4_03_committed_smoke_pack_has_exact_counts`, `test_FR_0_4_05_committed_smoke_pack_verifies` (2 failed) | CAUGHT |
| 4 | 4d `spec.py`: "category count equals its parts" check off | `test_FR_0_4_03_spec_is_checked_strictly` (1 failed, 6 passed) | CAUGHT |
| 5 Recipe and seeded reproduction | 5a `mix.py`: `noise_gain` dropped from the recipe | `test_FR_0_4_04_recipe_records_sources_snr_seed_gains`, `…_clip_rebuilt_from_recipe_alone` (2 failed) | CAUGHT |
| 5 | 5b `select.py`: offset from `random.randrange` without the seed | `test_FR_0_4_04_same_inputs_and_seed_byte_identical`, `test_FR_0_4_05_build_twice_byte_identical` (2 failed) | CAUGHT |
| 5 | 5c `build.py`: recipe records seed 0 instead of the pack seed | `test_FR_0_4_05_derived_clips_match_their_recipes` (1 failed) | CAUGHT |
| 6 Folder and archive limits | 6a `archive.py`: `MAX_ARCHIVE_BYTES = 300_000_000` | `test_FR_0_4_06_rejects_limits_above_hard_caps`, `…_verify_fails_on_oversized_archive` (3 failed) | CAUGHT |
| 6 | 6b `archive.py`: numbered subfolders never used | `test_FR_0_4_06_splits_member_folders_at_1000_files` (1 failed) | CAUGHT |
| 6 | 6c `verify.py`: archive size check off | `test_FR_0_4_06_verify_fails_on_oversized_archive` (1 failed) | CAUGHT |
| 6 | 6d `verify.py`: pack-folder and in-archive folder entry checks off | `test_FR_0_4_06_verify_fails_on_crowded_folder` (1 failed) | CAUGHT |
| 6 | 6e `archive.py`: shards never split at the byte limit | `test_FR_0_4_06_splits_archives_at_size_limit` (1 failed) | CAUGHT |
| 6 | 6f `spec.py`: folder-limit cap check off | `test_FR_0_4_06_rejects_limits_above_hard_caps` (1 failed, 1 passed) | CAUGHT |

## Exploratory breaks (A15, at most 10)
All 7 are in code changed since `55f9b51` (`aqis_lab/packs/verify.py`). For each, the run used the tests named for the behaviour.

| Break | Where | Survived? | Severity |
| --- | --- | --- | --- |
| X1 a repeated member checked only against the last clip that names it (`for clip in named:` → `named[-1:]`) | `verify.py:98`, `_check_members` | **Yes**: `test_FR_0_4_05_verify_fails_on_duplicate_member_path` `1 passed`. On the F02 probe, verify still gives `INVALID, 1 problem(s)`, exit 1, but the first clip's SHA-256 and duration lines are gone | MINOR (F08) |
| X2 a missing repeated member reported only for the first clip that names it (`for clip in expected[path]:` → `[:1]`) | `verify.py:104`, `_check_members` | **Yes**: `…_verify_fails_on_missing_member` and `…_duplicate_member_path` `2 passed`. The pack still fails verify through the duplicate line | MINOR (F08) |
| X3 every symbolic link rejected, including one to a real file | `verify.py:139`, `_not_a_file` | No: `test_FR_0_4_05_verify_accepts_link_to_a_real_archive` | — |
| X4 `LICENCES.md` and `build_record.json` left out of the file check, so their checks never run | `verify.py:179`, `verify_pack` | No: `test_FR_0_4_05_verify_reports_every_problem`, `test_FR_0_4_07_verify_fails_when_a_clip_is_missing` | — |
| X5 `build_record.json` check gated off (`if BUILD_RECORD in readable:` → `if False:`) | `verify.py:203`, `verify_pack` | No: `test_FR_0_4_05_verify_reports_every_problem` | — |
| X6 duplicate reported only for three or more clips (`> 1` → `> 2`) | `verify.py:72`, `_check_members` | No: `test_FR_0_4_05_verify_fails_on_duplicate_member_path` | — |
| X7 the "not a regular file" branch removed, so a FIFO, socket or device passes the file check | `verify.py:144-145`, `_not_a_file` | **Yes**: all 6 not-a-file cases `6 passed`. On the FIFO probe, verify then blocks in `read_bytes` until killed (`timeout 20`, exit 124) and never prints `OK` | MINOR (F08) |

## Findings
| ID | Severity | Item | Finding | Evidence | Recommendation: fix now, or accept as debt (target WP) |
| --- | --- | --- | --- | --- | --- |
| WP-0.4-F01 | CRITICAL | A13, A3; FR-0.4-05; must-catch 3 | **FIXED.** `pack verify` reported `OK` when a listed archive, `LICENCES.md` or `build_record.json` was a folder or a dangling symlink | "Previous findings" and the probe table; must-catch 3d | Closed |
| WP-0.4-F02 | MAJOR | A13; FR-0.4-05 | **FIXED.** Two clips naming one `member_path` collapsed into one expected entry | "Previous findings"; must-catch 3e | Closed |
| WP-0.4-F03 | MINOR | A13; FR-0.4-01 | Registry licence not checked against the dataset's licence in `datasets.yaml` | DEBT-010; approval on `main` (`458b1b3`) | Accepted as debt, target WP-0.8 |
| WP-0.4-F04 | MINOR | A5, A15 | `test_FR_0_4_03_distinct_speakers_and_utterances` does not fail when the one-per-speaker rule is removed | DEBT-011; approval on `main` (`458b1b3`) | Accepted as debt, target WP-0.5 |
| WP-0.4-F05 | MINOR | A14; FR-0.4-07 | "Changes made: none" written when a dataset has no `changes` field | DEBT-012; approval on `main` (`458b1b3`) | Accepted as debt, target WP-0.8 |
| WP-0.4-F06 | MINOR | A14 | **FIXED.** The clip levels are now measured and recorded | `SMOKE_PACK.md:75`, `EVIDENCE.md:116-121`; the values equal my measurement | Closed (the wording remnant is in F07) |
| WP-0.4-F07 | MINOR | A14, A4 | Two round 2 records say evidence is in `EVIDENCE.md` when it is not there. (1) `SMOKE_PACK.md:75` says "the command and its output are in `EVIDENCE.md`, 'Clip levels'". `EVIDENCE.md:116` gives the output but describes the method only in words ("measured by reading each clip's samples from its archive and computing the RMS and peak"), with no command, which also falls short of `.claude/rules/30-testing-and-evidence.md` ("the exact command"). (2) `FIXES.md:52` says "Gate and CI: in `EVIDENCE.md`, 'Round 2'", but that section (`EVIDENCE.md:283-291`) has the gate and no CI result for `507a1bf`. The underlying facts are true: the levels match my own measurement, and CI is green on `507a1bf` (runs 36341331247 and 36341333664). Only the pointers are wrong | `grep -n` of the three lines; my measurement output and CI job results under A4 and "Previous findings" | Accept as debt, target WP-0.5: add the measuring command to `EVIDENCE.md` (or reword `SMOKE_PACK.md:75`) and record the CI run IDs for `507a1bf` |
| WP-0.4-F08 | MINOR | A15, A5 | Three branches of the round 2 fix have no test. (a) Checking a repeated member against every clip that names it (`verify.py:98`), which the module header and `FIXES.md` state as behaviour. (b) Reporting a missing repeated member once per clip (`verify.py:104`). (c) The "not a regular file" branch of `_not_a_file` (`verify.py:144-145`) for a FIFO, socket or device, which the header also states. None of them can make verify report success: in (a) and (b) the duplicate line keeps the pack `INVALID`, and without (c) a FIFO makes verify block rather than pass | X1, X2 and X7 above: `1 passed`, `2 passed`, `6 passed` on the named tests; X1 probe `INVALID, 1 problem(s)`, exit 1; X7 probe exit 124 from `timeout 20` | Accept as debt, target WP-0.5. The fix is test-only, in `test_aqis_packs_verify.py`: a duplicate where the first clip's hash is wrong, asserting its SHA-256 line; a duplicate path with its member removed, asserting one missing line per clip; a FIFO in place of an archive, asserting "is not a regular file" |

## Convergence (round 3 onwards)
Not required at round 2. For the record: no open finding sits inside the must-catch list. F01 (must-catch 3) is fixed, and must-catch breaks 3d and 3e protect the fix.

| Round | CRITICAL | MAJOR | MINOR | Open findings inside the must-catch list |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 4 | F01 (must-catch 3) |
| 2 | 0 | 0 open (1 fixed) | 5 open (F03 to F05 accepted as debt; F07, F08 new), 1 fixed (F06) | None |

## For the owner
- audit-allow lines: None (gate: `Exempted lines (# audit-allow): 0`).
- Approvals used: `docs/approvals/WP-0.4.md` on `main` (`458b1b3`), which covers:
  - questions 1 to 9 as recommended;
  - the D6 conditions (synthetic Kokoro-82M TTS clips replace the owner recordings);
  - the round 2 condition (fix F01, F02 and F06; accept F03, F04 and F05 as debt).
- Debt accepted so far for WP-0.4: DEBT-010 (F03, WP-0.8), DEBT-011 (F04, WP-0.5) and DEBT-012 (F05, WP-0.8). I recommend accepting the two new MINOR findings as debt too: F07 and F08, both targeting WP-0.5. MINOR findings do not block, and the builder records them in `DEBT.md`.
- Owner-run checks still pending: None. WP-0.4 runs on the cloud VM only, and everything in it ran here.
