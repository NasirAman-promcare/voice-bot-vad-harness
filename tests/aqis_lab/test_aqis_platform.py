"""FR-0.5-01: aqis_lab.platform is the only place that detects the platform and reads machine facts."""
import ast
import copy
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from aqis_lab import platform as lp
from aqis_lab.contracts.canonical import compute_run_card_id
from aqis_lab.contracts.validate import validate_run_card
from aqis_runner_testutil import (ARM_CPUINFO, UBUNTU_OS_RELEASE, X86_CPUINFO, drive_mountinfo_line, make_system_tree,
                                  nvidia_smi_script, write_command)
from aqis_testutil import ROOT

VALID_CARD = ROOT / "tests" / "aqis_lab" / "fixtures" / "contracts" / "valid_run_card.json"


def system(tmp_path, env, **tree):
    root = make_system_tree(tmp_path / "sys", **tree)
    environ = dict(env)
    environ.setdefault("PATH", str(root / "bin"))
    return lp.SystemView(root=root, environ=environ, path=str(root / "bin"))


SIGNALS = [
    ("colab", {"COLAB_RELEASE_TAG": "release-colab_20260920"}, None),
    ("kaggle", {"KAGGLE_KERNEL_RUN_TYPE": "Interactive"}, None),
    ("oracle", {}, "OracleCloud.com"),
    ("cloud-vm", {"CLAUDE_CODE_REMOTE": "true"}, None),
    ("cloud-vm", {"GITHUB_ACTIONS": "true"}, None),
]


@pytest.mark.parametrize("expected, env, tag", SIGNALS, ids=[f"{s[0]}-{i}" for i, s in enumerate(SIGNALS)])
def test_FR_0_5_01_detects_each_platform_from_its_signal(tmp_path, expected, env, tag):
    view = system(tmp_path, env, chassis_asset_tag=tag)
    detection = lp.detect_platform(view)
    assert detection.platform == expected
    assert detection.signals, "the matching signal must be recorded"
    info = lp.machine_info(view)
    assert info.platform == expected


@pytest.mark.parametrize("env, tag", [
    ({}, None),
    ({"COLAB_RELEASE_TAG": ""}, None),                          # set but empty is not a signal
    ({"CLAUDE_CODE_REMOTE": "false", "GITHUB_ACTIONS": "0"}, None),
    ({}, "Not Specified"),                                       # another cloud's asset tag
])
def test_FR_0_5_01_unknown_platform_is_an_error(tmp_path, env, tag):
    view = system(tmp_path, env, chassis_asset_tag=tag)
    with pytest.raises(lp.PlatformError) as err:
        lp.detect_platform(view)
    message = str(err.value)
    for signal in ("COLAB_RELEASE_TAG", "KAGGLE_KERNEL_RUN_TYPE", "chassis_asset_tag", "CLAUDE_CODE_REMOTE",
                   "GITHUB_ACTIONS"):
        assert signal in message, f"the error must list the signal {signal} it looked for: {message}"


def test_FR_0_5_01_conflicting_signals_are_an_error(tmp_path):
    view = system(tmp_path, {"COLAB_RELEASE_TAG": "x", "CLAUDE_CODE_REMOTE": "true"})
    with pytest.raises(lp.PlatformError) as err:
        lp.detect_platform(view)
    assert "colab" in str(err.value) and "cloud-vm" in str(err.value)
    view = system(tmp_path / "b", {"KAGGLE_KERNEL_RUN_TYPE": "Batch"}, chassis_asset_tag="OracleCloud.com")
    with pytest.raises(lp.PlatformError):
        lp.detect_platform(view)
    # two signals for the same platform are not a conflict
    view = system(tmp_path / "c", {"CLAUDE_CODE_REMOTE": "true", "GITHUB_ACTIONS": "true"})
    assert lp.detect_platform(view).platform == "cloud-vm"


@pytest.mark.parametrize("names, expected", [
    (["Tesla T4"], "Tesla T4"),
    (["NVIDIA A100-SXM4-40GB", "NVIDIA A100-SXM4-40GB"], "2 x NVIDIA A100-SXM4-40GB"),
    (["NVIDIA L4", "Tesla T4"], "NVIDIA L4 + Tesla T4"),
    ([], None),
])
def test_FR_0_5_01_gpu_type_from_nvidia_smi_else_null(tmp_path, names, expected):
    view = system(tmp_path, {"CLAUDE_CODE_REMOTE": "true"})
    write_command(view.root / "bin", "nvidia-smi", nvidia_smi_script(names))
    assert lp.gpu_type(view) == expected
    assert lp.machine_info(view).gpu == expected
    no_gpu = system(tmp_path / "none", {"CLAUDE_CODE_REMOTE": "true"})
    assert lp.gpu_type(no_gpu) is None, "without nvidia-smi on PATH the GPU type is null"


def test_FR_0_5_01_failing_nvidia_smi_is_an_error(tmp_path):
    view = system(tmp_path, {"CLAUDE_CODE_REMOTE": "true"})
    write_command(view.root / "bin", "nvidia-smi", nvidia_smi_script(
        [], exit_code=9, stderr="NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver"))
    with pytest.raises(lp.PlatformError) as err:
        lp.gpu_type(view)
    assert "couldn't communicate with the NVIDIA driver" in str(err.value)
    assert "exit 9" in str(err.value) or "exit code 9" in str(err.value)


def test_FR_0_5_01_cpu_model_from_cpuinfo_or_lscpu(tmp_path):
    x86 = system(tmp_path / "x86", {"CLAUDE_CODE_REMOTE": "true"}, cpuinfo=X86_CPUINFO)
    assert lp.cpu_model(x86) == "Intel(R) Xeon(R) CPU @ 2.20GHz"
    arm = system(tmp_path / "arm", {"CLAUDE_CODE_REMOTE": "true"}, cpuinfo=ARM_CPUINFO)
    write_command(arm.root / "bin", "lscpu", "echo 'Architecture:   aarch64'\necho 'Model name:     Neoverse-N1'\n")
    assert lp.cpu_model(arm) == "Neoverse-N1"
    neither = system(tmp_path / "none", {"CLAUDE_CODE_REMOTE": "true"}, cpuinfo=ARM_CPUINFO)
    with pytest.raises(lp.PlatformError):
        lp.cpu_model(neither)


def test_FR_0_5_01_os_from_os_release(tmp_path):
    view = system(tmp_path, {"CLAUDE_CODE_REMOTE": "true"},
                  os_release='NAME="Oracle Linux Server"\nPRETTY_NAME="Oracle Linux Server 9.4"\nID="ol"\n')
    assert lp.os_name(view) == "Oracle Linux Server 9.4"
    missing = system(tmp_path / "b", {"CLAUDE_CODE_REMOTE": "true"}, os_release="NAME=x\n")
    with pytest.raises(lp.PlatformError):
        lp.os_name(missing)


def test_FR_0_5_01_memory_disk_and_mount_facts(tmp_path):
    mountinfo = ("23 28 0:22 / /proc rw,relatime - proc proc rw\n"
                 + drive_mountinfo_line(tmp_path / "my drive")
                 + "30 28 0:50 / /content rw - overlay overlay rw\n")
    view = system(tmp_path, {"COLAB_RELEASE_TAG": "x"}, mountinfo=mountinfo)
    assert lp.memory_available_bytes(view) == 8000000 * 1024
    assert lp.drive_mounts(view) == [tmp_path / "my drive"]
    free = lp.disk_free_bytes(tmp_path / "does" / "not" / "exist")
    st = os.statvfs(tmp_path)
    assert abs(free - st.f_bavail * st.f_frsize) < 64 * 1024 * 1024


def _uname_m():
    return subprocess.run(["uname", "-m"], capture_output=True, text=True, check=True).stdout.strip()


def _pretty_name():
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        if line.startswith("PRETTY_NAME="):
            return shlex.split(line.split("=", 1)[1])[0]
    raise AssertionError("no PRETTY_NAME in /etc/os-release")


def test_FR_0_5_01_real_machine_facts():
    # This VM (Claude Code cloud session) and the CI runner (GitHub Actions) are the two cloud-vm machines.
    assert os.environ.get("CLAUDE_CODE_REMOTE") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
    info = lp.machine_info()
    assert info.platform == "cloud-vm"
    assert info.architecture == _uname_m()
    assert info.os == _pretty_name()
    assert info.python_version == "%d.%d.%d" % sys.version_info[:3]
    first = next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines()
                  if l.startswith("model name")), None)
    if first is not None:
        assert info.cpu_model == first
    assert lp.machine_info() is info, "detection runs once per process on the real system"
    assert lp.machine_block() == {"platform": info.platform, "gpu": info.gpu, "cpu_model": info.cpu_model,
                                  "architecture": info.architecture, "os": info.os,
                                  "python_version": info.python_version}


def _card_with(machine):
    card = json.loads(VALID_CARD.read_text(encoding="utf-8"))
    card = copy.deepcopy(card)
    card["machine"] = machine
    card["run_card_id"] = compute_run_card_id(card)
    return card


def test_FR_0_5_01_machine_block_valid_in_run_card(tmp_path):
    validate_run_card(_card_with(lp.machine_block()))
    for expected, env, tag in SIGNALS:
        view = system(tmp_path / expected / str(len(env)), env, chassis_asset_tag=tag)
        write_command(view.root / "bin", "nvidia-smi", nvidia_smi_script(["Tesla T4"]))
        block = lp.machine_block(view)
        assert block["platform"] == expected and block["gpu"] == "Tesla T4"
        validate_run_card(_card_with(block))


# --- must-catch 5: platform details come from aqis_lab.platform only --------------------------------------------
FORBIDDEN = [
    re.compile(r"\bplatform\.(system|machine|processor|uname|platform|freedesktop_os_release|python_version"
               r"|python_version_tuple|node|release|version|architecture|libc_ver)\s*\("),
    re.compile(r"\bos\.uname\s*\("),
    re.compile(r"\bsys\.(version|version_info|platform)\b"),
    re.compile(r"\bshutil\.disk_usage\b"),
    re.compile(r"\bos\.statvfs\b"),
    re.compile(r"nvidia-smi|/proc/|/sys/class/dmi|os-release|\blscpu\b|COLAB_|KAGGLE_|GITHUB_ACTIONS|CLAUDE_CODE_REMOTE"),
]
# Owner decision (docs/approvals/WP-0.5.md, question 7 (a)): these existing lines stay as they are.
#  - harness_provision.py guards provisioning before any lab environment exists (WP-0.0 FR-0.0-12);
#  - version.py prints the interpreter's version as tool output, not a run's machine facts (WP-0.0 FR-0.0-01).
ALLOWED = {
    "aqis_lab/deploy/harness_provision.py": {
        '- Runs only where platform.system(), platform.machine() and the /etc/os-release ID match the "platform" pin',
        "system, machine = platform.system(), platform.machine()",
        "release = platform.freedesktop_os_release()",
        'f"/etc/os-release is unreadable ({exc}). {pin[\'distribution_reason\']}") from exc',
        "proc = self.run([python, \"-I\", \"-B\", \"-c\", \"import sys; print('%d.%d' % sys.version_info[:2])\"], "
        "check=False)",
    },
    "aqis_lab/commands/version.py": {
        "return f\"aqis_lab {aqis_lab.__version__} commit={short}{'+dirty' if dirty else ''} "
        "python={platform.python_version()}\"",
    },
}


# Machine facts by module (WP-0.5-F03): every name of the standard library's platform module, and these others.
FACT_ATTRIBUTES = {"os": {"uname", "statvfs"}, "sys": {"version", "version_info", "platform"},
                   "shutil": {"disk_usage"}}
IMPORTERS = {"__import__", "importlib.import_module", "import_module"}


def _is_fact(module, attr):
    return module == "platform" or attr in FACT_ATTRIBUTES.get(module, set())


def _ast_fact_lines(tree):
    """Line numbers where a module reads a machine fact through any import form (import, alias, from-import,
    __import__, importlib.import_module, getattr)."""
    aliases, lines = {}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in FACT_ATTRIBUTES or a.name == "platform" or a.name == "importlib":
                    aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for a in node.names:
                if _is_fact(node.module, a.name):
                    lines.add(node.lineno)
                if node.module == "importlib" and a.name == "import_module":
                    aliases[a.asname or a.name] = "importlib.import_module"

    def module_of(expr):
        if isinstance(expr, ast.Name):
            return aliases.get(expr.id)
        if isinstance(expr, ast.Call) and expr.args and isinstance(expr.args[0], ast.Constant) \
                and isinstance(expr.args[0].value, str):
            func = expr.func
            name = func.id if isinstance(func, ast.Name) else (
                f"{module_of(func.value)}.{func.attr}" if isinstance(func, ast.Attribute) else None)
            if isinstance(func, ast.Name) and aliases.get(func.id) == "importlib.import_module":
                name = "importlib.import_module"
            if name in IMPORTERS:
                return expr.args[0].value
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            module = module_of(node.value)
            if module and _is_fact(module, node.attr):
                lines.add(node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" \
                and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            module = module_of(node.args[0])
            if module and _is_fact(module, node.args[1].value):
                lines.add(node.lineno)
        elif isinstance(node, ast.Call) and module_of(node) == "platform":
            lines.add(node.lineno)
    return lines


def platform_detail_lines(root):
    found = []
    for top in ("aqis_lab", "tools"):
        for path in sorted((root / top).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if rel == "aqis_lab/platform.py":
                continue
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            flagged = {no for no, line in enumerate(lines, start=1) if any(rx.search(line) for rx in FORBIDDEN)}
            flagged |= _ast_fact_lines(ast.parse(text, filename=rel))
            for no in sorted(flagged):
                line = lines[no - 1].strip()
                if line not in ALLOWED.get(rel, set()):
                    found.append(f"{rel}:{no}: {line}")
    return found


def test_FR_0_5_01_platform_details_only_from_platform_module(tmp_path):
    assert platform_detail_lines(ROOT) == []
    # every allow-listed line still exists (a stale entry would silently widen the allow-list)
    for rel, lines in ALLOWED.items():
        text = {l.strip() for l in (ROOT / rel).read_text(encoding="utf-8").splitlines()}
        assert lines <= text, f"stale allow-list entries for {rel}: {sorted(lines - text)}"
    # the scan itself catches a module that reads a machine fact on its own
    other_root = tmp_path / "repo"
    (other_root / "aqis_lab").mkdir(parents=True)
    (other_root / "tools").mkdir()
    (other_root / "aqis_lab" / "runner.py").write_text("import platform\narch = platform.machine()\n")
    (other_root / "tools" / "x.py").write_text("import os\ncolab = 'COLAB_RELEASE_TAG' in os.environ\n")
    assert len(platform_detail_lines(other_root)) == 2


# WP-0.5-F03: import forms that a text scan cannot see. Each module reads one machine fact; each must be found.
EVASIONS = {
    "from_import_alias": "from platform import machine as host_arch\narch = host_arch()\n",
    "from_import": "from platform import python_version\n",
    "module_alias": "import platform as p\nname = p.system()\n",
    "dunder_import": "kernel = __import__('os').uname()\n",
    "importlib": "import importlib\narch = importlib.import_module('platform').machine()\n",
    "import_module_name": "from importlib import import_module\nx = import_module('platform').node()\n",
    "os_from_import": "from os import uname\n",
    "os_alias": "import os as o\nfree = o.statvfs('.')\n",
    "sys_from_import": "from sys import version_info as v\n",
    "sys_alias": "import sys as s\nwhere = s.platform\n",
    "shutil_from_import": "from shutil import disk_usage\n",
    "getattr": "import platform as q\nf = getattr(q, 'machine')\n",
}


@pytest.mark.parametrize("name", sorted(EVASIONS))
def test_FR_0_5_01_platform_scan_resolves_imports(tmp_path, name):
    root = tmp_path / "repo"
    (root / "aqis_lab").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "aqis_lab" / "module.py").write_text(EVASIONS[name], encoding="utf-8")
    assert platform_detail_lines(root), f"the scan missed: {EVASIONS[name]!r}"
    # the lab's own module and ordinary standard-library use stay allowed
    (root / "aqis_lab" / "module.py").write_text(
        "from aqis_lab import platform as lp\nfrom aqis_lab import platform\nimport os\nimport sys\n"
        "info = lp.machine_info()\nhome = os.environ.get('HOME')\nargs = sys.argv\npath = os.path.join('a', 'b')\n",
        encoding="utf-8")
    assert platform_detail_lines(root) == []
