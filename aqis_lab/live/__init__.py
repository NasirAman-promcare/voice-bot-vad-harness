"""Sprint 2 (WP-1.2) live-stack benchmark: VAD, turn-end detection, streaming STT on CPU and emotion.

CAPABILITIES: none of its own (package marker; the modules are config.py, streaming.py, vad.py, turn.py, emotion.py,
  score.py, results.py, prep.py, report.py and the command line in __main__.py).
INPUTS AND OUTPUTS: none; importing this package imports no submodule.
CONTRACTS: docs/specs/sprints/WP-1.2-S2-live-stack.md.
INVARIANTS:
  - Importing the package never loads onnxruntime, torch, funasr, NeMo or any model; libraries outside the phase 0 lock
    are loaded through aqis_lab.bench.lib() when the code that needs them runs (the guard tests that scan for literal
    imports are explained in aqis_lab/bench/__init__.py).
NOT IN SCOPE:
  - Everything outside Sprint 2.
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
