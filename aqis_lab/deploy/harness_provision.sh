#!/usr/bin/env bash
# Provision the existing VAD harness: system packages, .venv-harness, corpus-v1 and FireRedVAD weights.
#
# CAPABILITIES:
#   CAP-ENV-003: entry point for harness provisioning; runs aqis_lab/deploy/harness_provision.py with the system
#                python3 and passes its options and exit code through
#                [tests: test_FR_0_0_12_places_data_only_in_ignored_paths, test_FR_0_0_12_rejects_unknown_step,
#                 test_FR_0_0_12_provisions_harness_end_to_end]
# INPUTS AND OUTPUTS: see aqis_lab/deploy/harness_provision.py. Usage:
#   bash aqis_lab/deploy/harness_provision.sh [--steps system,python,corpus,weights,verify]
# INVARIANTS:
#   - Repository root derived from this script's location; no absolute paths; exits non-zero on any failure.
#   - Needs only bash and python3 (3.10 or newer) before any virtual environment exists.
# NOT IN SCOPE:
#   - The provisioning logic itself (harness_provision.py).
# CHANGE LOG:
#   2026-09-25 WP-0.0 round 2 FR-0.0-12 created.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$(command -v python3)" || { echo "ERROR: python3 not found on PATH (3.10 or newer is needed)." >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || { echo "ERROR: $PY is older than Python 3.10." >&2; exit 1; }
cd "$ROOT"
exec "$PY" -B "$ROOT/aqis_lab/deploy/harness_provision.py" "$@"
