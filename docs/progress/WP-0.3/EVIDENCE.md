# EVIDENCE — WP-0.3

Environment: cloud VM (Ubuntu 24.04, x86_64, 4 vCPUs), Python 3.13.12 in `.venv` (Colab probe: 3.13), lock `requirements/aqis_lab/phase0.txt` sha256 `1524a39ec1c2777a6ea7aefd69bc963a693fcc3e88413eb3fa26c0949ab6b801` after this WP's additions, branch `claude/charming-knuth-atc1dq`. Approval: `docs/approvals/WP-0.3.md` on `main` (`2879cf4`), "Questions 1-7: as recommended in PLAN.md".

Baseline before any change (change-control step 3, for `aqis_lab/__main__.py` and the lock): fast suite `998 passed, 9 deselected in 69.84s`.

## Lock additions (supports FR-0.3-01, FR-0.3-06, FR-0.3-07; plan question 5)
- Change: `requirements/aqis_lab/phase0.in` gained one commented block (`whisper-normalizer==0.1.1`, `pyarrow`, `jiwer==4.0.0`); `phase0.txt` was regenerated with the command recorded in its header (`uv pip compile requirements/aqis_lab/phase0.in --universal --python-version 3.13 --generate-hashes --output-file requirements/aqis_lab/phase0.txt`, passed again as `--custom-compile-command`).
- Existing pins unchanged: `git diff --stat requirements/` showed only insertions.
```text
 requirements/aqis_lab/phase0.in  |   7 +
 requirements/aqis_lab/phase0.txt | 302 +++++++++++++++++++++++++++++++++++++++
 2 files changed, 309 insertions(+)
+click==8.5.0 \
+indic-num2words==1.3.2 \
+jiwer==4.0.0 \
+more-itertools==11.1.0 \
+pyarrow==25.0.1 \
+rapidfuzz==3.14.6 \
+regex==2026.9.10 \
+whisper-normalizer==0.1.1 \
```
- CAP-ENV-002 tests, including the slow network ones (regeneration is reproducible; installable with plain `pip --require-hashes`): `.venv/bin/python -m pytest tests/aqis_lab/test_aqis_lock.py -v -p no:cacheprovider`
```text
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_every_pin_has_hashes PASSED [ 16%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_generated_from_in_file PASSED [ 33%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_regeneration_command_documented PASSED [ 50%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_environment_matches_lock PASSED [ 66%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_regeneration_is_reproducible PASSED [ 83%]
tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_installable_with_plain_pip PASSED [100%]
============================== 6 passed in 7.43s ===============================
```
- Registry: CAP-ENV-002 "What it does" now names the added packages (only that cell changed).

## Requirements
