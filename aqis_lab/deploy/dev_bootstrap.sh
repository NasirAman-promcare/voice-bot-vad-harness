#!/usr/bin/env bash
# Build the AQIS lab development environment: .venv on the Colab Python, from the hashed lock.
#
# CAPABILITIES:
#   CAP-ENV-001: creates .venv with the Python major.minor from docs/environment/colab_probe.txt using uv,
#                installs requirements/aqis_lab/phase0.txt with hash checking, idempotently
#                [tests: test_FR_0_0_02_fails_when_probe_missing, test_FR_0_0_02_fails_when_probe_unreadable,
#                 test_FR_0_0_02_fails_when_uv_missing, test_FR_0_0_02_uses_version_named_by_probe,
#                 test_FR_0_0_02_creates_venv_with_probe_python, test_FR_0_0_02_second_run_changes_nothing_within_30s,
#                 test_FR_0_0_02_rejects_lock_with_wrong_hash]
# INPUTS AND OUTPUTS: reads the Colab probe and the lock; writes only <repo>/.venv. Usage:
#   bash aqis_lab/deploy/dev_bootstrap.sh
# INVARIANTS:
#   - The repository root is derived from this script's location; no absolute paths.
#   - Exits non-zero with a message starting "ERROR:" on any failure; never continues on a guess.
#   - A second run with nothing changed changes no file (the venv is reused, uv pip sync is a no-op).
# NOT IN SCOPE:
#   - Installing uv itself, GPU packages, or setting up Colab or Oracle (WP-0.5, WP-0.6).
# CHANGE LOG:
#   2026-09-25 WP-0.0 FR-0.0-02 created.
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

# 4. Exact, hash-checked install of the lock (uninstalls anything not in it).
"$UV" pip sync --python "$VENV/bin/python" --require-hashes --strict "$LOCK" \
    || fail "hash-checked install of $LOCK_REL failed (see the uv message above)."

echo "OK: .venv ready: Python $("$VENV/bin/python" -I -B -c 'import platform; print(platform.python_version())'), lock sha256 $(sha256sum "$LOCK" | cut -d' ' -f1)"
