# Owner verification in Colab: WP-0.0

- Branch: `claude/hopeful-noether-yinc4e` at `033322b124fb4cea75a656be2f683ef8e6e4309e`
- Checked: 20260925T155908Z
- Lab Python: Python 3.13.15
- GPU: none (CPU runtime)

| Check | Result | Command | Summary |
| --- | --- | --- | --- |
| Version, must not say +dirty | PASS | `.venv/bin/python -m aqis_lab version` | aqis_lab 0.0.1 commit=033322b python=3.13.15 |
| Fast lab tests | PASS | `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m "not slow and not gpu and not colab and not oracle and not network"` | 138 passed, 8 deselected in 44.12s |
| Slow lab tests | PASS | `.venv/bin/python -m pytest tests/aqis_lab -q -p no:cacheprovider -m slow` | 8 passed, 138 deselected in 89.76s (0:01:29) |
| Audit gate for this WP | PASS | `.venv/bin/python -m tools.audit.gate --base origin/main --wp WP-0.0` | 0 findings: OK (0.3 s) |
| Harness tests, compare with docs/baselines/harness_tests_baseline.md | INFO | `.venv-harness/bin/python -m pytest tests -q -p no:cacheprovider --ignore=tests/aqis_lab` | 1 failed, 21 passed in 5.70s |
| Repository still clean afterwards | PASS | `git status --porcelain` | (no output) |

## Setup
- install uv: PASS
- lab environment (dev_bootstrap.sh): PASS
- harness environment (harness_provision.sh): PASS

## Output
### Version, must not say +dirty

```text
aqis_lab 0.0.1 commit=033322b python=3.13.15

```
### Fast lab tests

```text
........................................................................ [ 52%]
..................................................................       [100%]
138 passed, 8 deselected in 44.12s

```
### Slow lab tests

```text
........                                                                 [100%]
8 passed, 138 deselected in 89.76s (0:01:29)

```
### Audit gate for this WP

```text
aqis-audit-gate: base origin/main (merge-base d403bad2fb8c), head 033322b124fb, approvals origin/main d403bad2fb8c, wp WP-0.0
Exempted lines (# audit-allow): 0
Exempted files (ALLOW-PATTERNS-IN): 6
  tests/aqis_lab/fixtures/gate/allow_lines.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/code_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/non_utf8.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/test_patterns.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tests/aqis_lab/fixtures/gate/test_pytestmark.py: tests/aqis_lab/fixtures/** (WP-0.0.md)
  tools/audit/patterns.py: tools/audit/patterns.py (WP-0.0.md)
Findings: 0
0 findings: OK (0.3 s)

```
### Harness tests, compare with docs/baselines/harness_tests_baseline.md

```text
upted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:418 [ListenerBot] Sequence gap detected: missing 1 packet(s) before sequence 21. Inserted 320 concealment samples. (Offset: 6400 samples)
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:418 [ListenerBot] Sequence gap detected: missing 1 packet(s) before sequence 31. Inserted 320 concealment samples. (Offset: 9600 samples)
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
WARNING  bots.listener_bot:listener_bot.py:205 [ListenerBot] Opus decode failure on 1280 byte payload: b'corrupted stream'
ERROR    bots.listener_bot:listener_bot.py:507 [ListenerBot] Timeout waiting for clip 'packet_loss_sample_01.wav' completion after 3.0s
ERROR    webrtc_bridge.listener_bridge:listener_bridge.py:332 [ListenerBridge] Stream capture failed for 'packet_loss_sample_01.wav': Clip 'packet_loss_sample_01.wav' did not complete within 3.0s
=========================== short test summary info ============================
FAILED tests/regression/test_loss_category.py::test_packet_loss_category_applies_drop_impairment_in_bridge
1 failed, 21 passed in 5.70s

```
### Repository still clean afterwards

```text

```