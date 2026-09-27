# FIXES — WP-0.4

## Round 2 (audit round 1 findings)
Owner instruction and approval: `docs/approvals/WP-0.4.md` on `main` (`458b1b3`), round 2 condition. Fix WP-0.4-F01, F02 and F06; accept F03 (target WP-0.8), F04 (target WP-0.5) and F05 (target WP-0.8) as debt (DEBT-010, DEBT-011, DEBT-012 in `docs/progress/DEBT.md`). `origin/main` was merged first (`072ffd7`).

### Change budget
| File | Functions | Finding |
| --- | --- | --- |
| `aqis_lab/packs/verify.py` | `verify_pack`; new helper `_not_a_file`; module header (capability text, tests list, change log); `import os` | F01 |
| `aqis_lab/packs/verify.py` | `_check_members` | F02 |
| `tests/aqis_lab/test_aqis_packs_verify.py` | new tests only (appended; created in this WP, so no existing test on `main` changes) | F01, F02 |
| `docs/data/SMOKE_PACK.md` | the one sentence about clip levels | F06 |
| `docs/progress/WP-0.4/EVIDENCE.md` | new "Clip levels" and "Round 2" sections | F06 |
| `docs/capabilities/REGISTRY.md` | CAP-PACK-006 row: "What it does" and "Tests" cells | F01, F02 |
| `docs/progress/DEBT.md` | rows DEBT-010 to DEBT-012 | F03, F04, F05 |

Capabilities at risk: CAP-PACK-006 (`pack verify`). Its callers are `aqis_lab/commands/pack.py` (unchanged) and the tests. Nothing else imports `verify.py`.

### Root causes
- **F01.** `verify_pack` decided that a pack file was present from the directory listing alone (`pack.iterdir()` names include folders and broken symbolic links), then skipped every check on it with `if not path.is_file(): continue` for archives and `is_file()` guards for `LICENCES.md` and `build_record.json`, and reported nothing. The fix classifies every expected entry that exists by name with `_not_a_file`: a broken symbolic link, a folder, or anything else that is not a regular file is reported. The archive, `LICENCES.md` and build-record checks run only on the entries that passed. A symbolic link to a real file (for example on a mounted Drive) is still accepted.
- **F02.** `_check_members` built `{member_path: clip}`, so a second clip with the same `member_path` replaced the first, which was then never compared with any member. The fix groups clips by `member_path`, reports every path named by more than one clip (naming those clips), checks the member against every clip that names it, and reports a missing member once per clip.
- **F06.** `SMOKE_PACK.md` said two clip levels were "checked in `EVIDENCE.md`", which had no such entry. The sentence now gives the measured values, and `EVIDENCE.md` has the measuring command and its output.

### Evidence
- **Baseline** before the change (verify, layout, licences, smoke and build tests, which cover CAP-PACK-006 and its callers): `64 passed, 2 deselected in 12.49s`.
- **Reproduced** (new tests, before the fix): `7 failed, 1 passed, 19 deselected in 1.34s`. The failing tests are `test_FR_0_4_05_verify_fails_on_archive_that_is_not_a_file` [folder, dangling_symlink], `test_FR_0_4_05_verify_fails_on_pack_file_that_is_not_a_file` [LICENCES.md and build_record.json × folder and dangling_symlink] and `test_FR_0_4_05_verify_fails_on_duplicate_member_path`. The passing one is the guard `test_FR_0_4_05_verify_accepts_link_to_a_real_archive`. Reason for the F01 failures: `assert (not True)` where `VerifyReport(... problems=[] ...).ok` is `True`.
- **After the fix**: `test_aqis_packs_verify.py` gives `27 passed in 1.53s`; the baseline set gives `72 passed, 2 deselected in 12.65s` (64 plus the 8 new cases); the fast suite gives `1365 passed, 14 deselected in 125.71s (0:02:05)`.
- **The audit's probes**, rerun on copies of the committed pack:
```text
/tmp/wp04-f01/folder: smoke-1.0.0-tts-000.tar: is a folder, not a file; nothing in it can be checked
pack smoke 1.0.0: INVALID, 1 problem(s), 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10
exit=1
/tmp/wp04-f01/link: smoke-1.0.0-tts-000.tar: is a broken symbolic link (to '/tmp/wp04-f01/nowhere/x.tar'); the file it points to is missing, so nothing in it can be checked
pack smoke 1.0.0: INVALID, 1 problem(s), 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10
exit=1
/tmp/wp04-f01/lic: LICENCES.md: is a folder, not a file; nothing in it can be checked
/tmp/wp04-f01/lic: build_record.json: is a broken symbolic link (to '/tmp/wp04-f01/nowhere/b.json'); the file it points to is missing, so nothing in it can be checked
pack smoke 1.0.0: INVALID, 2 problem(s), 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10
exit=1
pack smoke 1.0.0: OK, 60 clips in 5 archives; test-clean 20, test-other 10, noisy 10, non-speech 10, tts 10
exit=0
```
  The last run is the committed pack itself, unchanged.
- **Must-catch proof, rerun with two new breaks** (the script in `/tmp/wp04-mc/run.py`): all 18 breaks fail a named test. The two new ones:
```text
F01 skip pack files that are not regular files | aqis_lab/packs/verify.py | 6 failed, 1373 deselected in 2.70s | failed: test_FR_0_4_05_verify_fails_on_archive_that_is_not_a_file, test_FR_0_4_05_verify_fails_on_pack_file_that_is_not_a_file
F02 accept a member path named by two clips | aqis_lab/packs/verify.py | 1 failed, 1378 deselected in 2.61s | failed: test_FR_0_4_05_verify_fails_on_duplicate_member_path
```
  Breaks 3a to 3c (member hash, extra member, missing member) and 6c (archive size) still fail their named tests after the change.
- **Scope**: `git diff -U0 aqis_lab/packs/verify.py` has hunks only in the header, the imports, `_check_members`, the new `_not_a_file` (inserted before `verify_pack`) and `verify_pack`.
- **Category, not only the instance** (surgical-fix step 6): the same "exists by name but is not a file" gap covered all three kinds of pack file, and each has a test. A `manifest.json` that is a folder or a broken link was already reported (`manifest.json: cannot read`, covered by `test_FR_0_4_05_verify_input_errors`). A symbolic link to a real file stays accepted, with its own test.
- Gate and CI: in `EVIDENCE.md`, "Round 2".
