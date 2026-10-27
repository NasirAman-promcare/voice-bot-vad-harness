"""Sprint 3 (WP-1.3): cascade routing simulated over Sprint 1 predictions, prompt biasing, and a targeted LoRA pilot.

CAPABILITIES: none of its own (package marker; the modules are config.py, gate.py, score.py, simulate.py, confidence.py,
  prompt_bias.py, train_data.py, train_lora.py, report.py and the command line in __main__.py).
INPUTS AND OUTPUTS: none; importing this package imports no submodule.
CONTRACTS: docs/specs/sprints/WP-1.3-S3-cascade-finetune.md.
INVARIANTS:
  - Importing the package never loads torch, transformers, peft, NeMo or any model; libraries outside the phase 0 lock are
    loaded through aqis_lab.bench.lib() when the code that needs them runs (see aqis_lab/bench/__init__.py for why).
NOT IN SCOPE:
  - Everything outside Sprint 3.
CHANGE LOG:
  2026-10-28 WP-1.3 created.
"""
