"""Which lock set this environment was installed from: the CPU lock alone, or the CPU lock plus the GPU extras.

CAPABILITIES:
  CAP-LOCKS-001: lock_differences() lists every difference between the installed distributions and a set of hashed lock files (a package missing, extra or at another version; markers evaluated for this interpreter); installed_lock() names the lock the run card records: requirements/aqis_lab/phase0.txt when the environment equals it exactly, requirements/aqis_lab/phase0-gpu.txt when it equals the CPU lock plus the GPU extras exactly, else a LockError naming the differences [tests: test_FR_0_7_03_installed_lock_is_the_cpu_lock_here, test_FR_0_7_03_installed_lock_names_the_gpu_lock_when_extras_are_installed, test_FR_0_7_03_doctor_lock_row_names_the_lock_set]
  CAP-LOCKS-002: pinned_version() gives a package's exact pin in a lock file (the GPU adapter's run card records the pinned NeMo and torch versions) [tests: test_FR_0_7_03_parakeet_model_block_records_pinned_versions]
INPUTS AND OUTPUTS: the repository root (lock files) and the running interpreter's distributions in; a lock path
  or a list of differences out; LockError on failure.
CONTRACTS: hashed pip locks (requirements/aqis_lab/phase0.txt, phase0-gpu.txt); run-card v1 `lock`.
INVARIANTS:
  - Exactly one lock set must match; a partial match is an error, never a guess.
NOT IN SCOPE:
  - Installing (aqis_lab/deploy/dev_bootstrap.sh); the doctor's report layout (aqis_lab/doctor.py).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-03 created.
"""
from pathlib import Path

from packaging.markers import InvalidMarker, Marker

REPO_ROOT = Path(__file__).resolve().parents[1]
CPU_LOCK = "requirements/aqis_lab/phase0.txt"
GPU_LOCK = "requirements/aqis_lab/phase0-gpu.txt"


class LockError(RuntimeError):
    """The environment matches no known lock set, or a lock file cannot be read."""


def _entries(root, rel):
    from aqis_lab.doctor import DoctorInputError, parse_lock
    try:
        return parse_lock((Path(root) / rel).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, DoctorInputError) as exc:
        raise LockError(f"cannot read {rel}: {exc}") from exc


def lock_differences(root, rels, installed=None):
    """(number of applicable pins, [every difference]) between the installed distributions and the lock files."""
    from aqis_lab.doctor import installed_distributions
    installed = installed_distributions() if installed is None else installed
    applicable, problems = {}, []
    for rel in rels:
        for name, (version, marker) in _entries(root, rel).items():
            try:
                if marker and not Marker(marker).evaluate():
                    continue
            except InvalidMarker as exc:
                problems.append(f"{name}: invalid marker {marker!r} ({exc})")
                continue
            if name in applicable and applicable[name] != version:
                problems.append(f"{name}: pinned {applicable[name]} and {version} in different lock files")
            applicable[name] = version
    for name, version in sorted(applicable.items()):
        if name not in installed:
            problems.append(f"{name} {version} is in the lock but not installed")
        elif installed[name] != version:
            problems.append(f"{name}: installed {installed[name]}, lock {version}")
    for name in sorted(set(installed) - set(applicable)):
        problems.append(f"{name} {installed[name]} is installed but not in the lock")
    return len(applicable), problems


def lock_sets(root=REPO_ROOT):
    """The lock sets an environment may be installed from, CPU first: [(recorded lock, [lock files])]."""
    sets = [(CPU_LOCK, [CPU_LOCK])]
    if (Path(root) / GPU_LOCK).is_file():
        sets.append((GPU_LOCK, [CPU_LOCK, GPU_LOCK]))
    return sets


def installed_lock(root=REPO_ROOT, installed=None):
    """The lock file (repository-relative) this environment equals exactly; LockError otherwise."""
    report = []
    for recorded, rels in lock_sets(root):
        _, problems = lock_differences(root, rels, installed)
        if not problems:
            return recorded
        report.append(f"{' + '.join(rels)}: {'; '.join(problems)}")
    raise LockError("the installed packages equal no lock set: " + " | ".join(report))


def pinned_version(rel, name, root=REPO_ROOT):
    """The exact version `name` is pinned to in lock file `rel`."""
    entries = _entries(root, rel)
    if name not in entries:
        raise LockError(f"{name} is not pinned in {rel}")
    return entries[name][0]
