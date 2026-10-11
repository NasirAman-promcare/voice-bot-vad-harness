# EVIDENCE — WP-1.0

Environment: cloud VM, Linux x86_64, Python 3.13.16 (`.venv` from `bash aqis_lab/deploy/dev_bootstrap.sh`, lock sha256 `87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef`), branch `claude/wp-1-0-operating-model-v2`.

## Environment fixes made in this session (VM only; no repository change)
- **Shallow clone.** `git rev-parse --is-shallow-repository` printed `true` and `git rev-list --count HEAD` printed `203`. Five history-reading tests failed with `fatal: Not a valid commit name …` and `git cat-file … returned non-zero exit status 128`. The fix was `git fetch -q --unshallow origin`, after which the same check printed `false`.
- **uv version.** The VM had `uv 0.11.32`, but the lab pins 0.8.17. Four `test_aqis_oracle_setup.py` tests failed with `ERROR: /root/.local/bin/uv reports 'uv 0.11.32 …', but oracle_setup.sh needs uv 0.8.17`. The fix was `uv self update 0.8.17`, which printed `success: Downgraded uv from v0.11.32 to v0.8.17!`.
- **After both fixes.** `.venv/bin/python -m pytest -q --tb=line -p no:cacheprovider tests/aqis_lab/test_aqis_harness_provision.py tests/aqis_lab/test_aqis_oracle_setup.py tests/aqis_lab/test_aqis_phase0_memo.py tests/aqis_lab/test_aqis_smoke.py tests/aqis_lab/test_aqis_trace.py -m "not slow and not gpu and not colab and not oracle and not network"` printed `171 passed, 21 deselected in 46.23s`.

## Acceptance tests written first (failing for the expected reason)
| File | Tests | Command | Result |
| --- | --- | --- | --- |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_01.py` | 63 | `.venv/bin/python -m pytest <file> -q --tb=line` | `63 failed`: each fails with `ModuleNotFoundError: No module named 'tools.outsourcing'`, or, in the CLI tests, with the subprocess's `No module named tools.outsourcing` |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_10.py` | 31 | same | `31 failed`, all `ModuleNotFoundError: No module named 'tools.outsourcing'` |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py` | 20 | same | `20 failed`, all `ModuleNotFoundError: No module named 'tools.outsourcing'` |
| `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_11.py` | 23 | same | `23 failed`: each fails with `ModuleNotFoundError: No module named 'tools.outsourcing'`, or, in the subprocess runs, with `Error while finding module specification for 'tools.outsourcing.relay'` |

Imports sit inside the tests, so the rest of the suite still runs while these wait. A diagnostic fast-suite run (not AT-1.0-01) at `d2f8f59` printed `103 failed, 1978 passed, 55 deselected in 384.26s`. The 103 failures are the 94 wave-1 acceptance tests plus the 9 environment failures above, which pass after the fixes.

## Requirements
### FR-1.0-11 — DEBT-033 and DEBT-034
- **DEBT-033.** The test passes: `.venv/bin/python -m pytest tests/aqis_lab/ci/test_wp_1_0_requirements.py -q --tb=line` reported `test_FR_1_0_11_debt033_parakeet_doc_names_the_gpu_in_file` as passing, with the 7 other tests failing for the expected reasons (no `.relay/` line yet, no GPU output yet, no migrated fragments yet, no orders done yet, no tools yet).
- **DEBT-034, test.** `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_phase0_memo.py -q --tb=short -k move_approval` printed `7 passed, 71 deselected in 2.63s`.
- **DEBT-034, proof that the new case catches the defect.** I removed the look-behind `(?<![\w.-])` from `names_id` in `tests/aqis_lab/aqis_memo_testutil.py`, then restored the file from a copy (`git diff --stat` empty afterwards). With the look-behind removed, the same command printed `FAILED …[longer-debt-id-on-the-left]` and `1 failed, 6 passed, 71 deselected`: only the new case failed.
- Status: PARTIAL. DEBT-032 waits on BLK-1.0-03, and the debt fragments come with the WO-1.0-04 migration.

## Acceptance commands
### AT-1.0-09 (first run, 2026-10-10, relay from `8d8d5b4`)
Command: `.venv/bin/python -m tools.outsourcing.relay --models`. Output:
```text
gemini-3.8-flash: present
gemini-3.7-flash: present
gemini-3.6-flash: present
gemini-3.5-flash: present
gemini-3-flash: missing
gemini-2.5-flash: present
gemini-3.5-flash-lite: present
gemini-3.1-flash-lite: present
codestral-2508: present
mistral-large-2512: missing
ministral-14b-2512: present
exit 2
```
Both providers' credentials work, since both listings succeeded. Two pool names need the owner (BLK-1.0-04). The other acceptance commands wait for the remaining work orders.

## audit-allow lines
- `tests/aqis_lab/outsourcing/test_acceptance_wo_1_0_02.py`, the `ALLOWED_LINE = …` line. It is a test-data string that must carry `# audit-allow:` because WO-1.0-02 must-catch 5 checks that the relay's compromise check honours it. The string is not an exemption for real code.

## Test fixes
- `test_FR_1_0_10_gitignore_ignores_relay` originally called `git check-ignore -q` with two paths. git rejects that (`fatal: --quiet is only valid with a single pathname`, exit 128), so the test failed for the wrong reason; the stop gate caught it. The test now checks that git lists both paths as ignored, and it fails for the right reason: `` `.relay/` is not ignored by .gitignore `` (BLK-1.0-02).

## Acceptance tests for WO-1.0-03, -06, -07 and -09 fail first (2026-10-10)
The commands, one per file: `.venv/bin/python -m pytest tests/aqis_lab/<file> -q --tb=line -p no:cacheprovider`.

| File | Result | Reason in the output (excerpt) |
| --- | --- | --- |
| `index/test_acceptance_wo_1_0_03.py` | 23 failed | `.venv/bin/python: No module named tools.index` |
| `audit_breaks/test_acceptance_wo_1_0_06.py` | 13 failed | `No module named tools.audit.breaks`; `ModuleNotFoundError: No module named 'tools.audit.mutate'` |
| `kit/test_acceptance_wo_1_0_07.py` | 28 failed | `No such file or directory: '…/tools/index'` (the scratch repository copies it); `No such file or directory: '…/kit-staging/.claude/hooks/stop_gate.py'` |
| `ci/test_acceptance_wo_1_0_09.py` | 40 failed | `aqis-lab-generate.yml missing`; `ModuleNotFoundError: No module named 'tools.ci'` |

Each failure names the missing module or file that its work order creates. The first WO-1.0-09 run had 3 kit-parity cases passing vacuously: a missing module also exits 1. Those cases now also require the differing file's name in the output, and all 40 fail.

The stop gate's fast suite (`-x`) stops at the first of these until the relay delivers the orders. The audit gate is clean: `.venv/bin/python -m tools.audit.gate --base origin/main` printed `0 findings: OK (0.6 s)`. Three scratch strings in the WO-1.0-07 test hold the skip and xfail markers that the stop gate must block. They carry `# audit-allow: scratch weakening the stop gate must block`.

## WO-1.0-04 relay run 2 (2026-10-10, `--timeout 1200`) and the fix-reason correction (DEC-1.0-05)
Command: `.venv/bin/python -m tools.outsourcing.relay --wo docs/outsourcing/orders/WO-1.0-04.md --timeout 1200`. Report, verbatim:
```
EXHAUSTED
Parts: 0/6
Requests: codestral-2508: 3, gemini-3.5-flash: 5, gemini-3.6-flash: 1, gemini-3.7-flash: 6, gemini-3.8-flash: 6 | Retries: OVERLOADED: 16, DAILY: 2 | Minutes waited: 9.3
Tokens: in 276075, out 6357
Checks:
  none run
Reason: Bundle error: Non-blank text outside block: '```text'
EXIT 8
```
- **Gemini.** Every Gemini model answered "overloaded" (16 retries) or "daily quota" (2).
- **Codestral.** codestral-2508 answered three times. Each reply began with ```` ```text ````, which `parse_bundle` refuses (WO-1.0-01 B5). The fix turns wrongly called the answer "blocked or empty".
- **Fix.** `fixorder._format_stop_reason` now gives bundle errors and refused imports their own reason, which restates RETURN_FORMAT. The test was written first: `.venv/bin/python -m pytest tests/aqis_lab/outsourcing/test_relay_run_fixes_wo_1_0_02.py -q` gave `2 failed, 4 passed` before the fix. After it, `.venv/bin/python -m pytest tests/aqis_lab/outsourcing -q -m "not slow and not gpu and not colab and not oracle and not network"` gave `347 passed in 68.22s`.

## Relay runs 3 and 4 (2026-10-10) → BLK-1.0-06 (ACCESS) and BLK-1.0-07 (DECISION)
- **WO-1.0-04, run 3** (default model, new fix wording). Report: `EXHAUSTED`, `Requests: codestral-2508: 3, gemini-3.8-flash: 1 | Retries: DAILY: 1`, `Reason: Bundle error: Non-blank text outside block: '```text'`, `EXIT 8`. The fix turn in `attempt-3/request.json` held the DEC-1.0-05 wording. Codestral's attempts 2 and 3 still began with `'```text\n=== MANIFEST ==='`.
- **`relay --status`.** gemini-3.8, 3.6 and 3.5-flash show `Exhausted until: 2026-10-10T23:59:59…`, each with `Count today: 0/20`. `.relay/governor.json` shows `exhausted_until` for all four T1 flash models, empty `daily_counts` for them, and `codestral-2508` `{'2026-10-10': 9}`.
- **WO-1.0-04, run 4** (order pinned to `mistral-large-2512`). Report: `ACCESS: add or fix the mistral credential on the aqis-lab environment`, `CREDENTIAL`, `Requests: mistral-large-2512: 1 | Retries: CREDENTIAL: 1`, `EXIT 7`.
- **`.venv/bin/python -m tools.outsourcing.relay --models`** (AT-1.0-09). Every Gemini pool model and `codestral-2508` print `present`; `ministral-14b-2512: present`; `mistral-large-2512: missing`; exit 0.
- **WO-1.0-03, run 3** (new fix wording). Report: `EXHAUSTED`, `Requests: codestral-2508: 4, gemini-3.7-flash: 4, gemini-3.8-flash: 1 | Retries: DAILY: 2, OVERLOADED: 4`, `Reason: Bundle error: Non-blank text outside block: '```text'`, `EXIT 8`. This is the same pattern as WO-1.0-04 (BLK-1.0-06, BLK-1.0-07).

## Relay runs on codestral-2508 after the fence fixes (2026-10-11)
- **WO-1.0-03, `--timeout 1200`.** Report: `EXHAUSTED`, `Parts: 0/6`, `Requests: codestral-2508: 4 | Retries: OVERLOADED: 1`, `Reason: Quick checks failed on final attempt`, `EXIT 8`.
  - The bundles parsed and imported.
  - Attempt 1 failed `headers`: `tests/aqis_lab/index/__init__.py (missing CAPABILITIES:)`.
  - Attempts 2 and 3 failed `tests`: `4 failed, 2 passed`. The model's `parse_header` returned empty capability, contract and change-log lists against its own unit tests.
  - The report hid the failing check (FIXES.md, FIX-B18-report).
- **WO-1.0-04.** Report: `PAUSED-BUSY`, `Requests: codestral-2508: 7 | Retries: OVERLOADED: 6`, `headers: FAIL (… tools/progress/__init__.py (missing CA…)`, `Reason: Service busy`, `EXIT 12`.
- **Next.** WO-1.0-04 resumed on codestral-2508. WO-1.0-03 rerun on codestral-2508 with `--attempts 5`.

## New pool from `main` (`7155ea6`, 2026-10-11) → BLK-1.0-10
- Mistral disabled. The NVIDIA provider is enabled with `z-ai/glm-5-3`, `z-ai/glm-5-3-flash`, `moonshotai/kimi-k3` and `deepseek-ai/deepseek-v4.1-flash`.
- `.venv/bin/python -m tools.outsourcing.relay --models` → `Relay error: Model 'z-ai/glm-5-3' rank invalid`, exit 2. The NVIDIA entries lack `rank`, `risk_tiers`, `max_input_tokens` and `max_output_tokens`, and use `tiers` and `tpm` (WO-1.0-10 B1).
- WO-1.0-03 and WO-1.0-04 are set back to `model: default`.

## Pool `00c8f91` (2026-10-11): relay --models → BLK-1.0-11
`.venv/bin/python -m tools.outsourcing.relay --models` prints `present` for all 8 Gemini models, `moonshotai/kimi-k3` and `deepseek-ai/deepseek-v4.1-flash`, and `missing` for `z-ai/glm-5-3` and `z-ai/glm-5-3-flash`; exit 2. Ranks 7 and 8 are each used twice. WO-1.0-03 and WO-1.0-04 were launched with `model: default` and `--timeout 1200` before the loader fix (FIX-B1-ranks).

## Pool `4976476` (owner overhaul, BLK-1.0-11 answered, 2026-10-11)
- **`.venv/bin/python -m tools.outsourcing.relay --models`.** Exit 0. All seven models print `present`: gemini-3.8-flash, gemini-3.7-flash, gemini-3.6-flash, z-ai/glm-5.3, moonshotai/kimi-k3, deepseek-ai/deepseek-v4.1-flash and z-ai/glm-5.3-flash (AT-1.0-09).
- **Old-pool runs stopped.** The WO-1.0-03 and WO-1.0-04 runs started on the old pool had finished no attempt after 30 minutes. Meanwhile gemini-3.8, 3.7 and 3.6-flash each had 12 requests counted today. Both runs were stopped and restarted on the new ranking.
- **Outsourcing suite.** First run: `4 failed, 380 passed`. Four Jules-written unit tests asserted the real pool's data: `Unknown model: 'codestral-2508'`, and `assert 3 == 1` for gemini-3.8-flash's rank. They now load a scratch pool (TEST_CHANGES); after that, `384 passed in 72.41s`.
