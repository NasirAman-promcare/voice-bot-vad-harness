"""Environment health check: Python, lock, disk, RAM, GPU and (on Colab) Google Drive, as a PASS/FAIL report.

CAPABILITIES:
  CAP-DOCTOR-001: run_doctor() checks, in order: platform equals the target; Python major.minor equals the Colab probe's; installed distributions equal the lock (none missing, none extra, versions equal); free disk and available RAM against the target's minimums in config/aqis_lab/doctor.yaml; a GPU when expect_gpu (else SKIP); on colab, the Drive mount and a writable MyDrive/AQIS_LAB; on oracle, the core reservation of config/aqis_lab/oracle.yaml against this machine (WP-0.6 FR-0.6-04); every check runs even after a FAIL [tests: test_FR_0_6_04_doctor_oracle_cores_row, test_FR_0_5_02_fails_on_python_version_other_than_probe, test_FR_0_5_02_fails_on_package_version_other_than_lock, test_FR_0_5_02_fails_on_package_missing_from_lock, test_FR_0_5_02_fails_on_lock_package_not_installed, test_FR_0_5_02_fails_below_disk_minimum, test_FR_0_5_02_fails_below_ram_minimum, test_FR_0_5_02_gpu_skipped_without_expect_gpu, test_FR_0_5_02_expect_gpu_fails_without_gpu, test_FR_0_5_02_expect_gpu_passes_with_gpu, test_FR_0_5_02_fails_when_target_is_not_this_platform, test_FR_0_5_02_colab_fails_when_drive_not_mounted, test_FR_0_5_02_colab_fails_when_aqis_lab_missing, test_FR_0_5_02_colab_fails_when_aqis_lab_read_only, test_FR_0_5_02_colab_drive_checks_pass_when_writable]
  CAP-DOCTOR-002: DoctorReport renders a fixed-width PASS/FAIL table and writes doctor_<platform>_<YYYYMMDDTHHMMSSZ>.json (never replacing a report) [tests: test_FR_0_5_02_cloud_doctor_prints_table_and_writes_json, test_FR_0_5_02_minimums_documented_equal_config]
INPUTS AND OUTPUTS: target, --expect-gpu, the Drive mount and the inputs below the repository root
  (docs/environment/colab_probe.txt, requirements/aqis_lab/phase0.txt, config/aqis_lab/doctor.yaml) in; a
  DoctorReport and its JSON file out. Machine facts come from aqis_lab.platform only.
CONTRACTS: report format in docs/doctor/DOCTOR.md.
INVARIANTS:
  - A missing or unreadable input is a FAIL row, never a PASS or a skipped check.
  - The Drive write check reuses one file (AQIS_LAB/doctor_write_check.json); nothing is deleted or accumulates.
NOT IN SCOPE:
  - Installing or repairing anything (aqis_lab/deploy/dev_bootstrap.sh does the install).
  - The GPU lock (WP-0.7).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-02 created.
  2026-09-28 WP-0.6 FR-0.6-04: `cores` check for target oracle (run_doctor, _check_cores).
"""
import hashlib
import importlib.metadata as md
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from packaging.markers import InvalidMarker, Marker

from aqis_lab import drive
from aqis_lab import oracle_config
from aqis_lab import platform as lp
from aqis_lab.commands.version import VersionInfoError, version_line

REPORT_VERSION = "1.0"
TARGETS = {"cloud": "cloud-vm", "colab": "colab", "oracle": "oracle"}
PROBE_REL = "docs/environment/colab_probe.txt"
LOCK_REL = "requirements/aqis_lab/phase0.txt"
MINIMUMS_REL = "config/aqis_lab/doctor.yaml"
ORACLE_CONFIG_REL = "config/aqis_lab/oracle.yaml"
WRITE_CHECK = "doctor_write_check.json"
GB = 1_000_000_000
PROBE_RE = re.compile(r"\s*(?:Python Version:\s*|Python\s+)(\d+)\.(\d+)")
PIN_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;]+)\s*(?:;\s*(.*))?")


class DoctorInputError(ValueError):
    """An input file of the doctor is missing or malformed."""


@dataclass
class Check:
    name: str
    status: str          # PASS, FAIL or SKIP
    expected: str
    actual: str
    detail: str


@dataclass
class DoctorReport:
    target: str
    expect_gpu: bool
    created_utc: str
    machine: dict | None
    lock_sha256: str | None
    code: str | None
    checks: list = field(default_factory=list)

    @property
    def result(self):
        return "FAIL" if any(c.status == "FAIL" for c in self.checks) else "PASS"

    @property
    def platform_name(self):
        return self.machine["platform"] if self.machine else "unknown"

    def to_json(self):
        return {"report_version": REPORT_VERSION, "target": self.target, "expect_gpu": self.expect_gpu,
                "created_utc": self.created_utc, "machine": self.machine,
                "lock": {"file": LOCK_REL, "sha256": self.lock_sha256}, "code": self.code,
                "checks": [asdict(c) for c in self.checks], "result": self.result}

    def table(self):
        head = f"{'check':<13} {'status':<6} {'expected':<22} {'actual':<30} detail"
        lines = [head, "-" * len(head)]
        for c in self.checks:
            lines.append(f"{c.name:<13} {c.status:<6} {c.expected:<22} {c.actual:<30} {c.detail}")
        lines.append(f"result: {self.result}")
        return "\n".join(lines)

    def file_name(self):
        stamp = re.sub(r"[-:]|\.\d+", "", self.created_utc)
        return f"doctor_{self.platform_name}_{stamp}.json"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def probe_major_minor(text):
    """The one Python major.minor named by the Colab probe text."""
    found = {f"{m.group(1)}.{m.group(2)}" for m in (PROBE_RE.match(line) for line in text.splitlines()) if m}
    if len(found) != 1:
        raise DoctorInputError(f"{PROBE_REL} must name exactly one Python version, found {sorted(found) or 'none'}")
    return found.pop()


def normalise(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(text):
    """{normalised name: (version, marker or '')} from a hashed pip lock of exact pins."""
    entries, logical, current = {}, [], ""
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        current += line
        if current.strip():
            logical.append(current.strip())
        current = ""
    if current.strip():
        logical.append(current.strip())
    for item in logical:
        if item.startswith("--"):
            continue
        spec = item.split("--hash=", 1)[0].strip()
        m = PIN_RE.fullmatch(spec)
        if not m:
            raise DoctorInputError(f"{LOCK_REL}: not an exact pin: {item[:80]!r}")
        name = normalise(m.group(1))
        if name in entries:
            raise DoctorInputError(f"{LOCK_REL}: {name} is pinned twice")
        entries[name] = (m.group(2), (m.group(3) or "").strip())
    if not entries:
        raise DoctorInputError(f"{LOCK_REL} pins no package")
    return entries


def installed_distributions():
    """{normalised name: version} of the running interpreter's environment (first on the path wins)."""
    found = {}
    for dist in md.distributions():
        name = dist.metadata["Name"]
        if name:
            found.setdefault(normalise(name), dist.version)
    return found


def load_minimums(path):
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DoctorInputError(f"{MINIMUMS_REL} is unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != "1.0" or set(data) != {"schema_version", "minimums"}:
        raise DoctorInputError(f"{MINIMUMS_REL} must hold exactly schema_version: \"1.0\" and minimums")
    minimums = data["minimums"]
    if not isinstance(minimums, dict) or set(minimums) != set(TARGETS):
        raise DoctorInputError(f"{MINIMUMS_REL}: minimums must name exactly {sorted(TARGETS)}")
    for target, values in minimums.items():
        if not isinstance(values, dict) or set(values) != {"free_disk_gb", "available_ram_gb"}:
            raise DoctorInputError(f"{MINIMUMS_REL}: {target} must give exactly free_disk_gb and available_ram_gb")
        for key, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
                raise DoctorInputError(f"{MINIMUMS_REL}: {target}.{key} must be a positive number, got {value!r}")
    return minimums


def _bytes_text(n):
    return f"{n:,} bytes ({n / GB:.2f} GB)"


def _check_platform(target, machine, error):
    expected = TARGETS[target]
    if machine is None:
        return Check("platform", "FAIL", expected, "unknown", f"platform detection failed: {error}")
    status = "PASS" if machine.platform == expected else "FAIL"
    detail = "signal: " + "; ".join(machine.signals)
    if status == "FAIL":
        detail = f"--target {target} needs platform {expected}, but this machine is {machine.platform} ({detail})"
    return Check("platform", status, expected, machine.platform, detail)


def _check_python(repo_root):
    actual = lp.python_version()
    try:
        expected = probe_major_minor((repo_root / PROBE_REL).read_text(encoding="utf-8", errors="replace"))
    except (OSError, DoctorInputError) as exc:
        return Check("python", "FAIL", "?", actual, f"cannot read the Colab probe: {exc}")
    running = lp.python_major_minor()
    status = "PASS" if running == expected else "FAIL"
    return Check("python", status, expected, actual,
                 f"major.minor {running} {'equals' if status == 'PASS' else 'differs from'} the Colab probe's "
                 f"{expected} ({PROBE_REL}; owner decision: major.minor)")


def _check_lock(repo_root):
    try:
        entries = parse_lock((repo_root / LOCK_REL).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, DoctorInputError) as exc:
        return Check("lock", "FAIL", LOCK_REL, "?", f"cannot read the lock: {exc}")
    problems, applicable = [], {}
    for name, (version, marker) in entries.items():
        try:
            if marker and not Marker(marker).evaluate():
                continue
        except InvalidMarker as exc:
            problems.append(f"{name}: invalid marker {marker!r} ({exc})")
            continue
        applicable[name] = version
    installed = installed_distributions()
    for name, version in sorted(applicable.items()):
        if name not in installed:
            problems.append(f"{name} {version} is in the lock but not installed")
        elif installed[name] != version:
            problems.append(f"{name}: installed {installed[name]}, lock {version}")
    for name in sorted(set(installed) - set(applicable)):
        problems.append(f"{name} {installed[name]} is installed but not in the lock")
    if problems:
        return Check("lock", "FAIL", f"{len(applicable)} packages", f"{len(problems)} difference(s)",
                     "; ".join(problems))
    return Check("lock", "PASS", f"{len(applicable)} packages", f"{len(installed)} installed",
                 f"installed packages equal {LOCK_REL}")


def _check_minimum(name, minimums, key, actual_fn, where):
    if isinstance(minimums, Exception):
        return Check(name, "FAIL", "?", "?", str(minimums))
    need = int(minimums[key] * GB)
    try:
        have = actual_fn()
    except lp.PlatformError as exc:
        return Check(name, "FAIL", f">= {_bytes_text(need)}", "?", str(exc))
    status = "PASS" if have >= need else "FAIL"
    return Check(name, status, f">= {minimums[key]} GB", _bytes_text(have),
                 f"{where}; minimum {minimums[key]} GB ({MINIMUMS_REL})")


def _check_gpu(expect_gpu, machine, system):
    if machine is not None:
        gpu, error = machine.gpu, None
    else:
        try:
            gpu, error = lp.gpu_type(system or lp.SystemView.real()), None
        except lp.PlatformError as exc:
            gpu, error = None, str(exc)
    if not expect_gpu:
        return Check("gpu", "SKIP", "not requested", gpu or "none", "--expect-gpu not given")
    if error:
        return Check("gpu", "FAIL", "a GPU", "?", error)
    if gpu is None:
        return Check("gpu", "FAIL", "a GPU", "none", "--expect-gpu given, but no GPU was detected")
    return Check("gpu", "PASS", "a GPU", gpu, "GPU type from aqis_lab.platform")


def _check_drive_mount(drive_mount, system):
    try:
        mounts = [m.resolve() for m in lp.drive_mounts(system)]
    except lp.PlatformError as exc:
        return Check("drive-mount", "FAIL", str(drive_mount), "?", str(exc))
    want = Path(drive_mount).resolve()
    actual = ", ".join(str(m) for m in mounts) or "none"
    if want in mounts:
        return Check("drive-mount", "PASS", str(want), actual, "Google Drive (fuse.drive) is mounted")
    return Check("drive-mount", "FAIL", str(want), actual,
                 f"Google Drive is not mounted at {want} (run the launcher's first cell)")


def _check_drive_folder(drive_mount, created_utc, system):
    folder = drive.aqis_lab_folder(drive_mount)
    if not folder.is_dir():
        return Check("drive-folder", "FAIL", str(folder), "missing",
                     f"missing: {folder} (create the folder {drive.MY_DRIVE}/{drive.AQIS_FOLDER} in Google Drive; "
                     f"the lab never creates it)")
    data = json.dumps({"created_utc": created_utc, "purpose": "doctor write check"}, sort_keys=True).encode()
    target = folder / WRITE_CHECK
    try:
        drive.write_bytes(target, data, system)
        back = target.read_bytes()
    except (OSError, drive.DriveError, lp.PlatformError) as exc:
        return Check("drive-folder", "FAIL", str(folder), "not writable", f"not writable: {exc}")
    if back != data:
        return Check("drive-folder", "FAIL", str(folder), "not writable",
                     f"not writable: {target} read back different bytes")
    return Check("drive-folder", "PASS", str(folder), "writable", f"wrote and read back {target.name}")


def _check_cores(system, config):
    from aqis_lab.timing import cores
    try:
        plan = cores.build_plan(system, config)
    except (cores.CoreError, oracle_config.OracleConfigError, lp.PlatformError) as exc:
        return Check("cores", "FAIL", "a possible reservation", "not possible", str(exc))
    return Check("cores", "PASS", "a possible reservation",
                 f"timing on {cores.format_cpus(plan.reserved)}, batch on {cores.format_cpus(plan.batch)}",
                 f"cores.reserved_for_timing in {plan.config}; every reserved CPU online, whole physical cores, "
                 f"at least one CPU left for batch runs")


def run_doctor(target, expect_gpu=False, repo_root=None, work_dir=None, drive_mount=None, system=None,
               oracle_config_path=None):
    """Run every check for `target` ('cloud', 'colab' or 'oracle'); returns a DoctorReport."""
    if target not in TARGETS:
        raise DoctorInputError(f"unknown target {target!r}; use one of {sorted(TARGETS)}")
    if target == "colab" and drive_mount is None:
        raise DoctorInputError("--target colab needs --drive-mount (the folder Google Drive is mounted at)")
    code_root = Path(__file__).resolve().parents[1]
    repo_root = Path(repo_root) if repo_root is not None else code_root
    work_dir = Path(work_dir) if work_dir is not None else code_root / "data" / "raw" / "aqis_lab" / "work"
    created = utc_now()
    try:
        machine, error = lp.machine_info(system), None
    except lp.PlatformError as exc:
        machine, error = None, str(exc)
    try:
        lock_sha = hashlib.sha256((repo_root / LOCK_REL).read_bytes()).hexdigest()
    except OSError:
        lock_sha = None
    try:
        code = version_line()
    except VersionInfoError as exc:
        code = f"unknown: {exc}"
    report = DoctorReport(target=target, expect_gpu=expect_gpu, created_utc=created,
                          machine=machine.block() if machine else None, lock_sha256=lock_sha, code=code)
    try:
        minimums = load_minimums(repo_root / MINIMUMS_REL)[target]
    except DoctorInputError as exc:
        minimums = exc
    report.checks += [
        _check_platform(target, machine, error),
        _check_python(repo_root),
        _check_lock(repo_root),
        _check_minimum("disk", minimums, "free_disk_gb", lambda: lp.disk_free_bytes(work_dir),
                       f"free on the file system of {work_dir}"),
        _check_minimum("ram", minimums, "available_ram_gb", lambda: lp.memory_available_bytes(system),
                       "MemAvailable"),
        _check_gpu(expect_gpu, machine, system),
    ]
    if target == "colab":
        report.checks.append(_check_drive_mount(drive_mount, system))
        report.checks.append(_check_drive_folder(drive_mount, created, system))
    if target == "oracle":
        report.checks.append(_check_cores(system, oracle_config_path or repo_root / ORACLE_CONFIG_REL))
    return report


def write_report(report, out_dir, system=None):
    """Write the report JSON into out_dir (created when missing); an existing report is never replaced."""
    folder = drive.make_dirs(out_dir, system)
    data = (json.dumps(report.to_json(), indent=2, sort_keys=False, ensure_ascii=False) + "\n").encode("utf-8")
    return drive.write_bytes(folder / report.file_name(), data, system, exclusive=True)
