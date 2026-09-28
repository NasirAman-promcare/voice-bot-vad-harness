#!/usr/bin/env bash
# Set up the AQIS lab on the Oracle VM: check the machine, check every locked package has a build for it, build
# .venv on the Colab Python from the hashed lock, and run the doctor for target oracle.
#
# CAPABILITIES:
#   CAP-ENV-007: six steps (platform, tools, python, wheels, venv, doctor), each printed as "step N/6 <name>: ...";
#                stops with "ERROR: unsupported architecture/operating system ..." before doing anything on a machine
#                outside the setup pin of config/aqis_lab/oracle.yaml (x86_64 or aarch64, the listed ID:VERSION_ID,
#                glibc at least setup.min_glibc); needs git and uv 0.8.17; stops naming every package of the lock
#                that has no binary build for this architecture, glibc and Python; builds .venv with
#                aqis_lab/deploy/dev_bootstrap.sh; runs `doctor --target oracle` with the work and report folders from
#                oracle.yaml and exits with its status; --dry-run runs only the read-only checks, explains each step
#                and changes nothing; a second run reuses .venv and installs nothing (idempotent)
#                [tests: test_FR_0_6_01_dry_run_explains_each_step_and_changes_nothing,
#                 test_FR_0_6_01_refuses_unsupported_architecture, test_FR_0_6_01_refuses_unsupported_operating_system,
#                 test_FR_0_6_01_refuses_glibc_below_minimum, test_FR_0_6_01_setup_pin_read_by_script_equals_yaml,
#                 test_FR_0_6_01_missing_build_names_the_package, test_FR_0_6_01_fails_when_uv_missing,
#                 test_FR_0_6_01_creates_venv_installs_lock_and_runs_oracle_doctor,
#                 test_FR_0_6_01_second_run_changes_nothing]
# INPUTS AND OUTPUTS: config/aqis_lab/oracle.yaml, docs/environment/colab_probe.txt and
#   requirements/aqis_lab/phase0.txt in; <repo>/.venv and one doctor report out. Usage:
#   bash aqis_lab/deploy/oracle_setup.sh [--dry-run]
# INVARIANTS:
#   - The repository root is derived from this script's location; no absolute paths.
#   - Nothing is written before step 1 passes; under --dry-run nothing is written at all.
#   - Only binary builds are accepted: no package is compiled from source on the Oracle VM.
#   - Exits non-zero with a message starting "ERROR:" on any failure; never continues on a guess.
# NOT IN SCOPE:
#   - Installing uv or rclone, configuring rclone, the nightly sync (docs/oracle/ORACLE_RUNBOOK.md).
# CHANGE LOG:
#   2026-09-28 WP-0.6 FR-0.6-01 created.
set -euo pipefail

UV_VERSION="0.8.17"
RUNBOOK="docs/oracle/ORACLE_RUNBOOK.md"
CONFIG_REL="config/aqis_lab/oracle.yaml"
PROBE_REL="docs/environment/colab_probe.txt"
LOCK_REL="requirements/aqis_lab/phase0.txt"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

usage() {
    echo "usage: bash aqis_lab/deploy/oracle_setup.sh [--dry-run]" >&2
    exit 2
}

DRY=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        -h|--help) echo "Set up the AQIS lab on the Oracle VM ($RUNBOOK). --dry-run explains each step and changes nothing."; exit 0 ;;
        *) usage ;;
    esac
done

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="$ROOT/$CONFIG_REL"
PROBE="$ROOT/$PROBE_REL"
LOCK="$ROOT/$LOCK_REL"
VENV="$ROOT/.venv"

step() {
    echo "step $1/6 $2: $3"
}

in_list() {
    local item="$1"; shift
    local x
    for x in "$@"; do
        [ "$x" = "$item" ] && return 0
    done
    return 1
}

version_ge() {  # version_ge A B: A >= B
    [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | sed -n 1p)" = "$2" ]
}

# One setup value of oracle.yaml, written as `  <key>: "<value>"` (aqis_lab/oracle_config.py checks the same form).
read_setup() {
    local key="$1" values
    [ -f "$CONFIG" ] || fail "$CONFIG_REL is missing."
    mapfile -t values < <(sed -nE "s/^  ${key}: \"([^\"]*)\"[[:space:]]*(#.*)?\$/\\1/p" "$CONFIG")
    [ "${#values[@]}" -eq 1 ] || fail "$CONFIG_REL: setup.${key} must be written once as '  ${key}: \"<value>\"'."
    printf '%s\n' "${values[0]}"
}

[ "$DRY" -eq 1 ] && echo "oracle_setup.sh --dry-run: explaining each step; nothing will be changed"

# 1. Platform: architecture, operating system and C library against the setup pin.
ARCH_TEXT="$(read_setup architectures)"
SYSTEM_TEXT="$(read_setup operating_systems)"
MIN_GLIBC="$(read_setup min_glibc)"
read -r -a ARCHS <<< "$ARCH_TEXT"
read -r -a SYSTEMS <<< "$SYSTEM_TEXT"
ARCH="$(uname -m)"
in_list "$ARCH" "${ARCHS[@]}" \
    || fail "unsupported architecture $ARCH: oracle_setup.sh supports ${ARCHS[*]} ($CONFIG_REL, setup.architectures)."
[ -r /etc/os-release ] \
    || fail "unsupported operating system: /etc/os-release is missing, so the system cannot be identified; oracle_setup.sh supports ${SYSTEMS[*]} ($CONFIG_REL, setup.operating_systems)."
os_value() {  # the first KEY=value of /etc/os-release, without quotes
    sed -nE "/^$1=/{s/^$1=\"?([^\"]*)\"?\$/\\1/p;q}" /etc/os-release
}
OS_ID="$(os_value ID)"
OS_VERSION="$(os_value VERSION_ID)"
OS_PRETTY="$(os_value PRETTY_NAME)"
OS="${OS_ID}:${OS_VERSION}"
in_list "$OS" "${SYSTEMS[@]}" \
    || fail "unsupported operating system $OS (${OS_PRETTY:-no PRETTY_NAME}): oracle_setup.sh supports ${SYSTEMS[*]} ($CONFIG_REL, setup.operating_systems)."
if ! LIBC="$(getconf GNU_LIBC_VERSION 2>&1)"; then
    fail "unsupported operating system $OS: no GNU C library found (getconf GNU_LIBC_VERSION: $LIBC); the lock's wheels need glibc $MIN_GLIBC or newer."
fi
GLIBC="${LIBC#glibc }"
[[ "$LIBC" == "glibc "* && "$GLIBC" =~ ^[0-9]+\.[0-9]+ ]] \
    || fail "unsupported operating system $OS: unreadable C library version '$LIBC'."
version_ge "$GLIBC" "$MIN_GLIBC" \
    || fail "unsupported operating system $OS: glibc $GLIBC is older than $MIN_GLIBC, which the lock's wheels need ($CONFIG_REL, setup.min_glibc)."
step 1 platform "PASS $ARCH (supported: ${ARCHS[*]}); ${OS_PRETTY:-$OS} ($OS; supported: ${SYSTEMS[*]}); glibc $GLIBC (minimum $MIN_GLIBC)"

# 2. Tools: git and uv 0.8.17.
GIT="$(command -v git)" || fail "git not found on PATH; install it ($RUNBOOK, section \"Install uv and rclone\")."
UV="$(command -v uv)" \
    || fail "uv not found on PATH. Install uv $UV_VERSION: curl -LsSf https://astral.sh/uv/$UV_VERSION/install.sh | sh ($RUNBOOK, section \"Install uv and rclone\")."
UV_SAYS="$("$UV" --version)" || fail "$UV --version failed."
[[ "$UV_SAYS" == "uv $UV_VERSION"* ]] \
    || fail "$UV reports '$UV_SAYS', but oracle_setup.sh needs uv $UV_VERSION. Install it: curl -LsSf https://astral.sh/uv/$UV_VERSION/install.sh | sh ($RUNBOOK, section \"Install uv and rclone\")."
step 2 tools "PASS $("$GIT" --version) at $GIT; $UV_SAYS at $UV"

# 3. Python: the Colab probe's major.minor (the rule of dev_bootstrap.sh).
[ -f "$PROBE" ] || fail "$PROBE_REL is missing."
mapfile -t VERSIONS < <(sed -nE 's/^[[:space:]]*(Python Version:[[:space:]]*|Python[[:space:]]+)([0-9]+)\.([0-9]+).*/\2.\3/p' "$PROBE" | sort -u)
[ "${#VERSIONS[@]}" -eq 1 ] || fail "$PROBE_REL must name exactly one Python version, found ${#VERSIONS[@]}."
PY="${VERSIONS[0]}"
if FOUND="$("$UV" python find "$PY" 2>&1)"; then
    step 3 python "PASS Python $PY ($PROBE_REL); uv finds $FOUND"
else
    step 3 python "PASS Python $PY ($PROBE_REL); none installed, so uv $UV_VERSION $([ "$DRY" -eq 1 ] && echo "would download" || echo "downloads") its checksum-verified build in step 5"
fi

# 4. Wheels: every applicable pin of the lock has a binary build for this architecture, glibc and Python.
GLIBC_MM="$(printf '%s' "$GLIBC" | cut -d. -f1-2)"
TARGET="${ARCH}-manylinux_${GLIBC_MM%%.*}_${GLIBC_MM##*.}"
mapfile -t PINS < <(sed -nE 's/^([A-Za-z0-9][A-Za-z0-9._-]*==[^ \\]+( ; [^\\]*[^ \\])?)[[:space:]]*\\?$/\1/p' "$LOCK")
[ "${#PINS[@]}" -gt 0 ] || fail "$LOCK_REL holds no pinned packages."
if [ "$DRY" -eq 1 ]; then
    step 4 wheels "would check that each of the ${#PINS[@]} pins in $LOCK_REL has a binary build for $TARGET and Python $PY (uv pip compile --only-binary :all:); it stops naming every package without one"
else
    WORK="$(mktemp -d)"
    trap 'rm -rf "$WORK"' EXIT
    printf '%s\n' "${PINS[@]}" > "$WORK/pins.txt"
    check() {
        "$UV" pip compile "$1" --no-deps --only-binary :all: --python-platform "$TARGET" --python-version "$PY" \
            --no-header --quiet --output-file "$WORK/out.txt" 2>&1
    }
    if ! REPORT="$(check "$WORK/pins.txt")"; then
        MISSING=()
        for pin in "${PINS[@]}"; do
            printf '%s\n' "$pin" > "$WORK/one.txt"
            if ! WHY="$(check "$WORK/one.txt")"; then
                reason="$(printf '%s\n' "$WHY" | sed -nE '/Because /{s/.*(Because .*)/\1/p;q}')"
                [ -n "$reason" ] || reason="$(printf '%s\n' "$WHY" | sed -nE '/[^[:space:]]/{s/^[[:space:]]*//p;q}')"
                name_version="${pin%% ;*}"
                MISSING+=("${name_version/==/ }: $reason")
            fi
        done
        [ "${#MISSING[@]}" -gt 0 ] || fail "uv could not check $LOCK_REL for $TARGET: $REPORT"
        for m in "${MISSING[@]}"; do
            echo "ERROR: no build of ${m%%: *} for $ARCH (glibc $GLIBC, Python $PY) in $LOCK_REL: ${m#*: }" >&2
        done
        fail "${#MISSING[@]} package(s) of $LOCK_REL have no binary build for $TARGET and Python $PY; nothing was installed."
    fi
    step 4 wheels "PASS all ${#PINS[@]} pins in $LOCK_REL have a binary build for $TARGET and Python $PY"
fi

# 5. The virtual environment and the hashed lock (aqis_lab/deploy/dev_bootstrap.sh, unchanged).
LOCK_SHA="$(sha256sum "$LOCK" | cut -d' ' -f1)"
if [ "$DRY" -eq 1 ]; then
    if [ -x "$VENV/bin/python" ] && CURRENT="$("$VENV/bin/python" -I -B -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>&1)" && [ "$CURRENT" = "$PY" ]; then
        step 5 venv "would reuse .venv (Python $CURRENT) and sync $LOCK_REL (sha256 $LOCK_SHA) with hash checking (aqis_lab/deploy/dev_bootstrap.sh)"
    else
        step 5 venv "would create .venv with Python $PY and install $LOCK_REL (sha256 $LOCK_SHA) with hash checking (aqis_lab/deploy/dev_bootstrap.sh)"
    fi
else
    bash "$ROOT/aqis_lab/deploy/dev_bootstrap.sh" || fail "aqis_lab/deploy/dev_bootstrap.sh failed (see above)."
    step 5 venv "PASS .venv on Python $("$VENV/bin/python" -I -B -c 'import platform; print(platform.python_version())'), $LOCK_REL sha256 $LOCK_SHA"
fi

# 6. The doctor for target oracle, with the work and report folders from oracle.yaml.
if [ "$DRY" -eq 1 ]; then
    step 6 doctor "would run .venv/bin/python -m aqis_lab doctor --target oracle --work-dir <paths.work_dir> --out <paths.doctor_reports> ($CONFIG_REL) and exit with its status"
    echo "DRY RUN: nothing was changed"
    exit 0
fi
WORK_DIR="$("$VENV/bin/python" -m aqis_lab.oracle_config get paths.work_dir)" || fail "cannot read paths.work_dir from $CONFIG_REL."
REPORTS="$("$VENV/bin/python" -m aqis_lab.oracle_config get paths.doctor_reports)" || fail "cannot read paths.doctor_reports from $CONFIG_REL."
echo "step 6/6 doctor: .venv/bin/python -m aqis_lab doctor --target oracle --work-dir $WORK_DIR --out $REPORTS"
status=0
(cd "$ROOT" && "$VENV/bin/python" -m aqis_lab doctor --target oracle --work-dir "$WORK_DIR" --out "$REPORTS") || status=$?
if [ "$status" -eq 0 ]; then
    echo "OK: the Oracle setup is complete and the doctor passed."
else
    echo "ERROR: the doctor reported a problem (exit $status); see its table above and $RUNBOOK, section \"When something fails\"." >&2
fi
exit "$status"
