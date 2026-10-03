#!/usr/bin/env bash
# Build the AQIS lab development environment: .venv on the Colab Python, from the hashed lock.
#
# CAPABILITIES:
#   CAP-ENV-001: creates .venv with the Python major.minor from docs/environment/colab_probe.txt using uv,
#                installs requirements/aqis_lab/phase0.txt with hash checking, idempotently; source-only
#                packages are built only with the lock's own hash-checked setuptools (--build-constraints);
#                --gpu also installs the GPU extras requirements/aqis_lab/phase0-gpu.txt (Colab), with both
#                locks as build constraints
#                [tests: test_FR_0_0_02_fails_when_probe_missing, test_FR_0_0_02_fails_when_probe_unreadable,
#                 test_FR_0_0_02_fails_when_uv_missing, test_FR_0_0_02_uses_version_named_by_probe,
#                 test_FR_0_0_02_creates_venv_with_probe_python, test_FR_0_0_02_second_run_changes_nothing_within_30s,
#                 test_FR_0_0_02_rejects_lock_with_wrong_hash,
#                 test_FR_0_7_02_bootstrap_passes_the_lock_as_build_constraints,
#                 test_FR_0_7_02_source_build_uses_only_the_locked_setuptools,
#                 test_FR_0_7_02_bootstrap_rejects_unknown_option, test_FR_0_7_03_bootstrap_gpu_needs_the_gpu_lock,
#                 test_FR_0_7_03_bootstrap_gpu_build_constraints_include_the_gpu_lock,
#                 test_FR_0_0_02_probe_repeating_one_version_is_accepted,
#                 test_FR_0_0_02_recreates_venv_built_on_another_python]
# INPUTS AND OUTPUTS: reads the Colab probe and the lock(s); writes only <repo>/.venv. Usage:
#   bash aqis_lab/deploy/dev_bootstrap.sh [--gpu]
# INVARIANTS:
#   - The repository root is derived from this script's location; no absolute paths.
#   - Exits non-zero with a message starting "ERROR:" on any failure; never continues on a guess.
#   - A second run with nothing changed changes no file (the venv is reused, uv pip sync is a no-op).
# NOT IN SCOPE:
#   - Installing uv itself, or setting up Colab or Oracle (WP-0.5, WP-0.6).
# CHANGE LOG:
#   2026-09-25 WP-0.0 FR-0.0-02 created.
#   2026-09-25 WP-0.0 round 2 F06: header test list names test_FR_0_0_02_uses_version_named_by_probe (header only).
#   2026-09-30 WP-0.7 FR-0.7-02: the sync passes the lock as --build-constraints (hash-checked source build of
#     srt, owner decision question 2 (a)); FR-0.7-03: --gpu also syncs requirements/aqis_lab/phase0-gpu.txt.
#   2026-10-02 WP-0.8 DEBT-021: --gpu passes the GPU lock as a build constraint too (both locks; a differing
#     setuptools pin between them then fails the source build loudly).
#   2026-10-04 WP-0.9 DEBT-003, DEBT-005: header lists the repeated-probe-version and wrong-Python .venv tests
#     (header only).
set -euo pipefail

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PROBE_REL="docs/environment/colab_probe.txt"
LOCK_REL="requirements/aqis_lab/phase0.txt"
PROBE="$ROOT/$PROBE_REL"
LOCK="$ROOT/$LOCK_REL"
VENV="$ROOT/.venv"
GPU_LOCK_REL="requirements/aqis_lab/phase0-gpu.txt"
GPU_LOCK="$ROOT/$GPU_LOCK_REL"
GPU=0
for arg in "$@"; do
    case "$arg" in
        --gpu) GPU=1 ;;
        *) fail "unknown option '$arg'. Usage: bash aqis_lab/deploy/dev_bootstrap.sh [--gpu]" ;;
    esac
done

# 1. Required Python major.minor from the Colab probe.
[ -e "$PROBE" ] || fail "$PROBE_REL is missing. The owner must commit the Colab probe output (see docs/environment/README.md)."
{ [ -f "$PROBE" ] && [ -r "$PROBE" ]; } || fail "$PROBE_REL is unreadable: it is not a readable regular file."
mapfile -t VERSIONS < <(sed -nE 's/^[[:space:]]*(Python Version:[[:space:]]*|Python[[:space:]]+)([0-9]+)\.([0-9]+).*/\2.\3/p' "$PROBE" | sort -u)
if [ "${#VERSIONS[@]}" -eq 0 ]; then
    fail "$PROBE_REL is unreadable: no 'Python Version: X.Y' or 'Python X.Y.Z' line found."
fi
if [ "${#VERSIONS[@]}" -gt 1 ]; then
    fail "$PROBE_REL is unreadable: it names conflicting Python versions (${VERSIONS[*]})."
fi
PY="${VERSIONS[0]}"
echo "Colab probe requires Python $PY ($PROBE_REL)"

# 2. Tools and inputs.
UV="$(command -v uv)" || fail "uv not found on PATH. Install uv 0.8.17 (https://docs.astral.sh/uv/getting-started/installation/) and re-run."
echo "Using $("$UV" --version) at $UV"
[ -f "$LOCK" ] || fail "$LOCK_REL is missing."
if [ "$GPU" -eq 1 ]; then
    [ -f "$GPU_LOCK" ] || fail "$GPU_LOCK_REL is missing (needed by --gpu)."
fi

# 3. The virtual environment, reused only when its Python major.minor matches.
current=""
if [ -x "$VENV/bin/python" ]; then
    if ! current="$("$VENV/bin/python" -I -B -c 'import sys; print("%d.%d" % sys.version_info[:2])')"; then
        echo "Existing .venv has an unusable interpreter; it will be recreated."
        current=""
    fi
fi
if [ "$current" = "$PY" ]; then
    echo "Reusing .venv (Python $current)"
else
    if [ -e "$VENV" ]; then
        echo "Recreating .venv (found Python ${current:-none}, need $PY)"
    fi
    "$UV" venv --clear --python "$PY" "$VENV" || fail "uv could not create .venv with Python $PY (is Python $PY installed or downloadable?)."
fi
actual="$("$VENV/bin/python" -I -B -c 'import sys; print("%d.%d" % sys.version_info[:2])')" \
    || fail ".venv/bin/python does not run."
[ "$actual" = "$PY" ] || fail ".venv has Python $actual but the Colab probe requires $PY."

# 4. Exact, hash-checked install of the lock (uninstalls anything not in it). The lock is also the build
#    constraint: a source-only package (srt) is built with the lock's own hash-checked setuptools.
if [ "$GPU" -eq 1 ]; then
    "$UV" pip sync --python "$VENV/bin/python" --require-hashes --strict --build-constraints "$LOCK" \
        --build-constraints "$GPU_LOCK" "$LOCK" "$GPU_LOCK" \
        || fail "hash-checked install of $LOCK_REL and $GPU_LOCK_REL failed (see the uv message above)."
else
    "$UV" pip sync --python "$VENV/bin/python" --require-hashes --strict --build-constraints "$LOCK" "$LOCK" \
        || fail "hash-checked install of $LOCK_REL failed (see the uv message above)."
fi

echo "OK: .venv ready: Python $("$VENV/bin/python" -I -B -c 'import platform; print(platform.python_version())'), lock sha256 $(sha256sum "$LOCK" | cut -d' ' -f1)"
if [ "$GPU" -eq 1 ]; then
    echo "OK: GPU extras installed: $GPU_LOCK_REL sha256 $(sha256sum "$GPU_LOCK" | cut -d' ' -f1)"
fi
