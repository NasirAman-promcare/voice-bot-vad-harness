# Owner verification in Colab: WP-0.0

- Branch: `claude/hopeful-noether-yinc4e` at `aa9e74cfa02368c899bba23adcc1cd0f4c21ab31`
- Checked: 20260925T151855Z
- Lab Python: Python 3.13.15
- GPU: none (CPU runtime)

| Check | Result | Command | Summary |
| --- | --- | --- | --- |
| Version, must not say +dirty | PASS | `.venv/bin/python -m aqis_lab version` | aqis_lab 0.0.1 commit=aa9e74c python=3.13.15 |
| Fast lab tests | FAIL | `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` | 3 failed, 135 passed, 8 deselected in 30.33s |
| Slow lab tests | FAIL | `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m slow` | 1 failed, 7 passed, 138 deselected in 80.50s (0:01:20) |
| Audit gate for this WP | PASS | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` | 0 findings: OK (0.3 s) |
| Harness tests, compare with docs/baselines/harness_tests_baseline.md | INFO | `.venv-harness/bin/python -m pytest tests -q -p no:cacheprovider --ignore=tests/aqis_lab` | 1 failed, 21 passed in 4.89s |
| Repository still clean afterwards | PASS | `git status --porcelain` | (no output) |

## Setup
- install uv: PASS
- lab environment (dev_bootstrap.sh): PASS
- harness environment (harness_provision.sh): PASS

## Output
### Fast lab tests
```text
FAILED tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_rejects_ten_vad_at_other_commit
FAILED tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_reinstalls_when_pip_check_fails
FAILED tests/aqis_lab/test_aqis_harness_provision.py::test_FR_0_0_12_venv_problem_detects_venv_without_pip
E subprocess.CalledProcessError: Command '['/content/verify/.venv/bin/python', '-m', 'venv', '/tmp/pytest-of-root/pytest-0/test_FR_0_0_12_venv_problem_de0/with-pip']' returned non-zero exit status 1.
Slow lab tests
code
Text
FAILED tests/aqis_lab/test_aqis_lock.py::test_FR_0_0_03_lock_installable_with_plain_pip
E subprocess.CalledProcessError: Command '['/content/verify/.venv/bin/python', '-m', 'venv', '/tmp/pytest-of-root/pytest-1/test_FR_0_0_03_lock_installabl0/pipvenv']' returned non-zero exit status 1.
Error: Command '['/tmp/pytest-of-root/pytest-1/test_FR_0_0_03_lock_installabl0/pipvenv/bin/python3.13', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.
