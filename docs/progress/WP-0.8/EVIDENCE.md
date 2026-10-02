# EVIDENCE — WP-0.8 Consent, recording guide, filler library v0 and targets

Environment: cloud VM (`cloud-vm`), Ubuntu 24.04, x86_64, 4 CPUs, Python 3.13.14 in `.venv` (`dev_bootstrap.sh`: "OK: .venv ready: Python 3.13.14, lock sha256 87a1cc34c6d41388cf8ce1e415f95f61c3b24a7bc45b69a828a957c1813fdcef"), uv 0.8.17. Branch `claude/beautiful-bohr-gf9yck`.

Owner inputs used:
- `docs/approvals/WP-0.8.md` on `main` (`61c50c7`):
  - BLK-013: option 1 (a), with the sources committed in `docs/specs/sources/`;
  - questions 2 to 8 as recommended: close all five debts here; `changes` required for every dataset; both locks as `--gpu` build constraints;
  - the consent scheme `ca-sNNN` / `ca-cNNN`, the consent facts (a) to (f), owner blanks for targets and retention, and deviations D1 to D3 accepted.
- `docs/specs/sources/AQIS_Test_Lab_Blueprint.md` and `docs/specs/sources/AQIS_Test_Lab_Build_Plan.md` (`61c50c7`).

## Baseline before any change
- The fast suite at `bd0fa9c` (after merging `main`) gave `1 failed, 1747 passed, 55 deselected in 338.65s`.
- The failure was `test_FR_0_0_12_asset_pins_match_repository`: `git cat-file blob 14796262…:corpus-v1.tar.gz` exited 128, because this session's clone was shallow (`git rev-parse --is-shallow-repository` → `true`).
- After `git fetch --unshallow origin`, the same test gives `1 passed, 63 deselected in 5.53s`. That is an environment fact of this checkout, not a code fault. No file was changed.

## Debts closed (question 2)

### DEBT-010 — registry licence must equal the dataset's licence (WP-0.4-F03)
- **Code:** `aqis_lab/registry/registry.py`, `check_records`, one added check:
  - when a row's dataset is known, its licence is in the licence table and its split is one of the dataset's splits, the licence must equal `dataset.licence_for_split(split)`;
  - otherwise there is a problem at column `licence`.

  Also changed: the module docstring (CAP-REG-001, CHANGE LOG), `docs/data/REGISTRY_FORMAT.md` (one validation bullet) and the `REGISTRY.md` row CAP-REG-001.
- **Tests:**
  - `test_FR_0_4_01_rejects_licence_that_differs_from_its_dataset`, parametrised:
    - a LibriSpeech row relabelled `CC0-1.0`;
    - a MUSAN noise row with the music subset's licence;
    - a MUSAN music row with the dataset licence instead of the subset's.

    The valid music and noise rows prove the check uses the subset's licence.
  - `test_FR_0_4_01_committed_registry_licences_equal_dataset_licences`.
- **Tests first:** before the fix, the three parametrised cases failed with `AssertionError: []` / `assert 0 == 1` (no problem reported). The committed-registry test passed.
- **After the fix:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp08.py tests/aqis_lab/test_aqis_registry_validate.py tests/aqis_lab/test_aqis_registry_build.py -q -p no:cacheprovider -m "not slow and not network"
63 passed in 19.03s
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent or debt_wp08 or registry" -m "not slow and not network"
99 passed, 1708 deselected in 23.47s
$ .venv/bin/python -m aqis_lab registry validate; echo "exit $?"
/home/user/voice-bot-vad-harness/data/registry/sources.csv: OK, 6559 rows (librispeech 5559, musan 990, tts 10)
exit 0
```
- Status: DONE

### DEBT-018 — smoke `--bundle-dir` goes through the Drive write guard (WP-0.7-F05)
- **Code:** `aqis_lab/smoke.py`, `run_smoke`:
  - the `bundle_dir` default is resolved right after the platform check;
  - then `drive.check_write_path(bundle_dir, system)` runs, and a `DriveError` becomes `SmokeInputError` (`ERROR:`, exit 2), before any preflight, run or write.

  Also changed: the module docstring (CAP-SMOKE-002, CHANGE LOG) and the `REGISTRY.md` row CAP-SMOKE-002.
- **Tests:**
  - `test_NFR_0_5_02_smoke_refuses_bundle_dir_on_drive_outside_aqis_lab`: a Colab view with a stand-in Drive mount; the bundle folder is `MyDrive/elsewhere/bundles`. Expected: exit 2, the message names the path and `AQIS_LAB`, the mount tree is unchanged and `--work-dir` is not created.
  - `test_NFR_0_5_02_smoke_accepts_bundle_dir_inside_aqis_lab`: the guard lets `MyDrive/AQIS_LAB/bundles` through, and the smoke stops later at the GPU preflight's own message.
- **Tests first:** before the fix, the refusal test failed because the GPU preflight stopped first:
```text
E       assert ('refusing to write' in 'task parakeet-offline cannot run on this machine: Parakeet Unified runs only on a CUDA GPU and this machine has no GP...rm found none). It is never skipped or replaced: run it on a GPU target (the Colab T4 runtime; runbook in docs/colab/)')
1 failed, 1 passed, 4 deselected in 0.46s
```
- **After the fix:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab/test_aqis_debt_wp08.py tests/aqis_lab/test_aqis_smoke.py tests/aqis_lab/test_aqis_smoke_launcher.py -q -p no:cacheprovider -m "not slow and not network"
22 passed, 12 deselected in 10.64s
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent"
1 passed, 1808 deselected in 1.48s
```
- Status: DONE

### DEBT-020 — two smoke behaviours get tests (WP-0.7-F07)
- **Code:** none. `aqis_lab/smoke.py` changed only in its module docstring (CAP-SMOKE-003 and CAP-SMOKE-004 test lists, CHANGE LOG). The `REGISTRY.md` rows CAP-SMOKE-003 and CAP-SMOKE-004 also list the new tests.
- **Tests:**
  - `test_FR_0_7_07_smoke_revalidates_each_event_log_before_storing` (parametrised `first`, `middle`, `last`):
    - a real harness-vad run is copied into a bundle folder;
    - one `events.jsonl` record loses its `run_id`;
    - `_check_and_store` must raise `SmokeFailure` (exit 1) naming `events.jsonl line <n> is not valid event log v1` and `run_id`, and nothing must be stored.
  - `test_FR_0_7_07_report_summary_lines_recomputed_from_bundle_rows` (parametrised over the three committed bundles):
    - `_report` regenerates the committed `PHASE0_SMOKE.md` byte for byte, once the runs and score tables are put back in the config's order (`BUNDLE.json` stores them sorted);
    - the summary lines equal values recomputed in the test from `results.jsonl` (median and maximum with `statistics`, 4 decimals; transcripts equal to batch; Parakeet processing time and GPU);
    - the count is also checked after one real-speed transcript hash is changed, because in every committed bundle all transcripts are equal.
- **Break proof** (scratch worktree `wt2` of `1ae1fee`, the new test file copied in, one exact replacement per break, `git checkout` after each):

  | Break | Change | Result of `pytest tests/aqis_lab/test_aqis_debt_wp08.py -k FR_0_7_07` |
  | --- | --- | --- |
  | none | — | `6 passed, 6 deselected in 2.21s` |
  | B1 | `_check_and_store`: `bad = []` (re-validation removed) | `3 failed, 3 passed, 6 deselected in 7.77s` (the three re-validation cases) |
  | B2 | `_stats`: `statistics.mean` instead of `median` | `3 failed, 3 passed, 6 deselected in 2.05s` (the three bundles) |
  | B3 | `_report`: `same = len(rows)` | `3 failed, 3 passed, 6 deselected in 1.99s` (the three bundles; before the changed-hash step was added, B3 gave `6 passed`) |
- **Run here:**
```text
$ .venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -k "test_FR_0_0_08_repository_registry_is_consistent or debt_wp08"
13 passed, 1802 deselected in 3.24s
```
- Status: DONE
