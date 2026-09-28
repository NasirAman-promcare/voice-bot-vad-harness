"""The one place that detects the lab platform and reads machine facts (cloud VM, Colab, Kaggle, Oracle).

CAPABILITIES:
  CAP-PLAT-001: detect_platform() names the platform (cloud-vm, colab, kaggle, oracle) from exactly one kind of positive signal; no signal, or signals for two platforms, is a PlatformError listing what it looked for [tests: test_FR_0_5_01_detects_each_platform_from_its_signal, test_FR_0_5_01_unknown_platform_is_an_error, test_FR_0_5_01_conflicting_signals_are_an_error]
  CAP-PLAT-002: machine_info()/machine_block() give the run card machine block: platform, GPU type (from nvidia-smi when present, else null; a failing nvidia-smi is an error), CPU model (/proc/cpuinfo, else lscpu), architecture, OS (PRETTY_NAME) and Python version; detected once per process on the real system [tests: test_FR_0_5_01_gpu_type_from_nvidia_smi_else_null, test_FR_0_5_01_failing_nvidia_smi_is_an_error, test_FR_0_5_01_cpu_model_from_cpuinfo_or_lscpu, test_FR_0_5_01_os_from_os_release, test_FR_0_5_01_real_machine_facts, test_FR_0_5_01_machine_block_valid_in_run_card, test_FR_0_5_01_colab_runtime_detected]
  CAP-PLAT-003: memory_available_bytes(), disk_free_bytes() and drive_mounts() give the RAM, disk and Google Drive mount facts the doctor and the Drive guard use [tests: test_FR_0_5_01_memory_disk_and_mount_facts, test_FR_0_5_01_platform_details_only_from_platform_module, test_FR_0_5_01_platform_scan_resolves_imports]
  CAP-PLAT-004: online_cpus(), core_siblings(), thread_ids() and thread_affinity() give the CPU facts core reservation uses: the online CPU list, the hardware threads sharing a physical core, every thread of this process and a thread's allowed CPUs; parse_cpu_list() reads kernel CPU lists strictly [tests: test_FR_0_6_04_platform_cpu_facts, test_FR_0_6_04_missing_topology_is_an_error, test_FR_0_6_04_reservation_must_not_split_a_physical_core]
INPUTS AND OUTPUTS: a SystemView (environment variables, a root folder for the operating-system files, a PATH for
  commands; the real system by default) in; MachineInfo, dicts and numbers out; PlatformError on failure.
CONTRACTS: run-card v1 `machine` block (docs/contracts/RUN_CARD.md).
INVARIANTS:
  - No other lab module reads machine facts (must-catch 5; allow-list in tests/aqis_lab/test_aqis_platform.py).
  - A failed detection is an error, never a default platform or "no GPU".
  - The only absolute path is the operating-system root; every system file is resolved against SystemView.root.
NOT IN SCOPE:
  - Deciding whether a machine is good enough to run the lab (aqis_lab/doctor.py).
CHANGE LOG:
  2026-09-28 WP-0.5 FR-0.5-01 created.
  2026-09-28 WP-0.5 NFR-0.5-01: SystemView.real() is built once per process.
  2026-09-28 WP-0.5 round 2 F03: header lists the import-resolving scan test (header only).
  2026-09-28 WP-0.6 FR-0.6-04: CPU facts for core reservation (online_cpus, core_siblings, thread_ids,
    thread_affinity, parse_cpu_list); existing functions unchanged.
"""
import functools
import os
import platform
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PLATFORMS = ("cloud-vm", "colab", "kaggle", "oracle")
ORACLE_ASSET_TAG = "OracleCloud.com"
DRIVE_FSTYPE = "fuse.drive"   # docs/environment/colab_platform_probe.txt
COMMAND_TIMEOUT_S = 60

CPUINFO = "proc/cpuinfo"
MEMINFO = "proc/meminfo"
MOUNTINFO = "proc/self/mountinfo"
OS_RELEASE = "etc/os-release"
CHASSIS_ASSET_TAG = "sys/class/dmi/id/chassis_asset_tag"
CPU_ONLINE = "sys/devices/system/cpu/online"
CPU_SIBLINGS = "sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list"
PROC_TASKS = "proc/self/task"


class PlatformError(RuntimeError):
    """The platform or a machine fact could not be determined."""


@dataclass(frozen=True)
class SystemView:
    """What this module reads: environment variables, operating-system files below `root`, commands on `path`."""
    root: Path = Path("/")
    environ: dict = field(default_factory=lambda: dict(os.environ))
    path: str | None = None

    @classmethod
    def real(cls):
        """The real system, built once per process (like the platform detection itself)."""
        return _real_view()

    def file(self, rel):
        return Path(self.root) / rel

    def read_text(self, rel):
        """Text of a system file, or None when it does not exist; any other read failure is a PlatformError."""
        path = self.file(rel)
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise PlatformError(f"cannot read {path}: {exc.strerror or exc}") from exc

    def which(self, command):
        return shutil.which(command, path=self.path if self.path is not None else self.environ.get("PATH", ""))

    def run(self, command, *args):
        """(exit code, stdout, stderr) of a command found on this view's PATH, or None when it is not there."""
        exe = self.which(command)
        if exe is None:
            return None
        try:
            proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S,
                                  env={**self.environ, "LC_ALL": "C"})
        except subprocess.TimeoutExpired as exc:
            raise PlatformError(f"{command} did not answer within {COMMAND_TIMEOUT_S} s") from exc
        except OSError as exc:
            raise PlatformError(f"cannot run {exe}: {exc.strerror or exc}") from exc
        return proc.returncode, proc.stdout, proc.stderr


@functools.lru_cache(maxsize=1)
def _real_view():
    return SystemView(root=Path(os.sep), environ=dict(os.environ), path=os.environ.get("PATH"))


@dataclass(frozen=True)
class Detection:
    platform: str
    signals: tuple


@dataclass(frozen=True)
class MachineInfo:
    platform: str
    gpu: str | None
    cpu_model: str
    architecture: str
    os: str
    python_version: str
    signals: tuple

    def block(self):
        """The run card `machine` object."""
        return {"platform": self.platform, "gpu": self.gpu, "cpu_model": self.cpu_model,
                "architecture": self.architecture, "os": self.os, "python_version": self.python_version}


def _env_set(name):
    return (f"environment variable {name} is set", lambda s: bool(s.environ.get(name)))


def _env_true(name):
    return (f"environment variable {name}=true", lambda s: s.environ.get(name) == "true")


def _oracle_tag(system):
    text = system.read_text(CHASSIS_ASSET_TAG)
    return text is not None and text.strip() == ORACLE_ASSET_TAG


# (platform, description, test). Owner decision: docs/approvals/WP-0.5.md, question 6 (a).
SIGNALS = (
    ("colab", *_env_set("COLAB_RELEASE_TAG")),
    ("kaggle", *_env_set("KAGGLE_KERNEL_RUN_TYPE")),
    ("oracle", f"/{CHASSIS_ASSET_TAG} reads {ORACLE_ASSET_TAG}", _oracle_tag),
    ("cloud-vm", *_env_true("CLAUDE_CODE_REMOTE")),
    ("cloud-vm", *_env_true("GITHUB_ACTIONS")),
)


def detect_platform(system):
    """The platform named by the one kind of signal present; PlatformError when none or several platforms match."""
    matched = [(name, text) for name, text, test in SIGNALS if test(system)]
    names = sorted({name for name, _ in matched})
    if len(names) == 1:
        return Detection(names[0], tuple(text for _, text in matched))
    looked_for = "; ".join(f"{name}: {text}" for name, text, _ in SIGNALS)
    if not names:
        raise PlatformError(f"unknown platform: none of the platform signals is present (looked for {looked_for})")
    found = "; ".join(f"{name}: {text}" for name, text in matched)
    raise PlatformError(f"conflicting platform signals for {', '.join(names)} ({found}); exactly one platform "
                        f"must match")


def gpu_type(system):
    """GPU type from `nvidia-smi --query-gpu=name --format=csv,noheader`; None when nvidia-smi is absent or lists none."""
    result = system.run("nvidia-smi", "--query-gpu=name", "--format=csv,noheader")
    if result is None:
        return None
    code, out, err = result
    if code != 0:
        raise PlatformError(f"nvidia-smi is present but failed (exit {code}): {(err or out).strip() or 'no message'}")
    names = [line.strip() for line in out.splitlines() if line.strip()]
    if not names:
        return None
    if len(set(names)) == 1:
        return names[0] if len(names) == 1 else f"{len(names)} x {names[0]}"
    return " + ".join(names)


def cpu_model(system):
    """The first `model name` of /proc/cpuinfo, else lscpu's `Model name` (aarch64 kernels have no model name line)."""
    text = system.read_text(CPUINFO)
    for line in (text or "").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "model name" and value.strip():
            return value.strip()
    result = system.run("lscpu")
    if result is not None and result[0] == 0:
        for line in result[1].splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() == "Model name" and value.strip():
                return value.strip()
    raise PlatformError(f"cannot tell the CPU model: no 'model name' line in /{CPUINFO} and no 'Model name' from lscpu")


def os_name(system):
    """PRETTY_NAME from /etc/os-release."""
    text = system.read_text(OS_RELEASE)
    if text is None:
        raise PlatformError(f"/{OS_RELEASE} is missing; cannot tell the operating system")
    for line in text.splitlines():
        if line.startswith("PRETTY_NAME="):
            try:
                parts = shlex.split(line.split("=", 1)[1])
            except ValueError as exc:
                raise PlatformError(f"/{OS_RELEASE}: unreadable PRETTY_NAME line {line!r}: {exc}") from exc
            if parts and parts[0].strip():
                return parts[0].strip()
    raise PlatformError(f"/{OS_RELEASE} has no PRETTY_NAME; cannot tell the operating system")


def architecture():
    arch = platform.machine()
    if not arch:
        raise PlatformError("cannot tell the machine architecture")
    return arch


def python_version():
    return platform.python_version()


def python_major_minor():
    return ".".join(platform.python_version_tuple()[:2])


def _machine_info(system):
    detection = detect_platform(system)
    return MachineInfo(platform=detection.platform, gpu=gpu_type(system), cpu_model=cpu_model(system),
                       architecture=architecture(), os=os_name(system), python_version=python_version(),
                       signals=detection.signals)


@functools.lru_cache(maxsize=1)
def _real_machine_info():
    return _machine_info(SystemView.real())


def machine_info(system=None):
    """MachineInfo for `system`; for the real system it is detected once per process."""
    return _real_machine_info() if system is None else _machine_info(system)


def machine_block(system=None):
    """The run card `machine` object (docs/contracts/RUN_CARD.md)."""
    return machine_info(system).block()


def memory_available_bytes(system=None):
    system = system or SystemView.real()
    text = system.read_text(MEMINFO)
    for line in (text or "").splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) == 3 and parts[1].isdigit() and parts[2] == "kB":
                return int(parts[1]) * 1024
            raise PlatformError(f"/{MEMINFO}: unreadable MemAvailable line {line!r}")
    raise PlatformError(f"/{MEMINFO} has no MemAvailable line; cannot tell the available RAM")


def disk_free_bytes(path):
    """Free bytes for an unprivileged user on the file system of `path` (or of its nearest existing parent)."""
    probe = Path(path).absolute()
    while not probe.exists():
        if probe.parent == probe:
            raise PlatformError(f"no existing folder above {path}")
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError as exc:
        raise PlatformError(f"cannot read free disk space of {probe}: {exc.strerror or exc}") from exc


def _unescape_mount(text):
    out, i = [], 0
    while i < len(text):
        octal = text[i + 1:i + 4]
        if text[i] == "\\" and len(octal) == 3 and all(c in "01234567" for c in octal):
            out.append(chr(int(octal, 8)))
            i += 4
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def drive_mounts(system=None):
    """Mount points of Google Drive (file-system type fuse.drive) from /proc/self/mountinfo, in file order."""
    system = system or SystemView.real()
    text = system.read_text(MOUNTINFO)
    mounts = []
    for line in (text or "").splitlines():
        head, sep, tail = line.partition(" - ")
        fields, rest = head.split(), tail.split()
        if not line.strip():
            continue
        if not sep or len(fields) < 5 or not rest:
            raise PlatformError(f"/{MOUNTINFO}: unreadable line {line!r}")
        if rest[0] == DRIVE_FSTYPE:
            mounts.append(Path(_unescape_mount(fields[4])))
    return mounts


def parse_cpu_list(text):
    """The CPU numbers in kernel CPU-list text such as "0-3,6"; PlatformError when it is not that form."""
    cpus = set()
    body = text.strip()
    for part in body.split(",") if body else [""]:
        lo, dash, hi = part.partition("-")
        if not lo.isdigit() or (dash and not hi.isdigit()) or (dash and int(hi) < int(lo)):
            raise PlatformError(f"unreadable CPU list {text!r}")
        cpus.update(range(int(lo), int(hi if dash else lo) + 1))
    return frozenset(cpus)


def online_cpus(system=None):
    """The online CPUs from /sys/devices/system/cpu/online."""
    system = system or SystemView.real()
    text = system.read_text(CPU_ONLINE)
    if text is None:
        raise PlatformError(f"/{CPU_ONLINE} is missing; cannot tell the online CPUs")
    return parse_cpu_list(text)


def core_siblings(cpu, system=None):
    """The CPUs sharing CPU `cpu`'s physical core (its hardware threads), from its topology files."""
    system = system or SystemView.real()
    rel = CPU_SIBLINGS.format(cpu=int(cpu))
    text = system.read_text(rel)
    if text is None:
        raise PlatformError(f"/{rel} is missing; cannot tell which CPUs share CPU {cpu}'s physical core")
    siblings = parse_cpu_list(text)
    if cpu not in siblings:
        raise PlatformError(f"/{rel} lists {sorted(siblings)}, which does not hold CPU {cpu} itself")
    return siblings


def thread_ids():
    """The IDs of every thread of this process, from /proc/self/task (always the real system)."""
    folder = SystemView.real().file(PROC_TASKS)
    try:
        return sorted(int(entry.name) for entry in folder.iterdir())
    except OSError as exc:
        raise PlatformError(f"cannot list the threads in {folder}: {exc.strerror or exc}") from exc


def thread_affinity(tid=0):
    """The CPUs thread `tid` (0: the calling thread) may run on; ProcessLookupError when it has ended."""
    return frozenset(os.sched_getaffinity(tid))
