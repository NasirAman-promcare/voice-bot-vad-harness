"""Sprint 1 (WP-1.1) speech-to-text benchmark: glue modules around aqis_lab.scoring and aqis_lab.packs.mix.

CAPABILITIES: none of its own (package marker; the modules are config.py, sources.py, select.py, conditions.py,
  models.py, run.py, score.py, report.py and the command line in __main__.py).
INPUTS AND OUTPUTS: none; importing this package imports no submodule.
CONTRACTS: docs/specs/sprints/WP-1.1-S1-asr-benchmark.md.
INVARIANTS:
  - Importing the package never loads torch, NeMo, transformers, datasets or any model.
  - Libraries outside the phase 0 lock (huggingface_hub, soxr, matplotlib and the GPU stacks) are loaded only through lib()
    when the code that needs them runs, the way aqis_lab/adapters/parakeet_unified.py loads torch and NeMo. Two Phase 0
    guard tests scan for literal imports (test_NFR_0_0_03_imports_are_stdlib_or_pinned) and for torch or nemo outside the one
    Parakeet adapter (test_FR_0_7_03_torch_and_nemo_imported_only_in_gpu_adapter); both predate Sprint 1 and name no
    other file, so this module's use of lib() is disclosed in the pull request for the owner to decide whether to extend them.
NOT IN SCOPE:
  - Everything outside Sprint 1.
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""

import importlib


def lib(name):
    """Import a library that is not in the phase 0 lock, by (dotted) name, when it is first needed."""
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ImportError(f"{name} is not installed in this environment ({exc}); the Sprint 1 locks in requirements/aqis_lab/ "
                          f"(s1-prep for prep and report, s1-hf, s1-nemo or s1-qwen for a model stack) install it") from exc
