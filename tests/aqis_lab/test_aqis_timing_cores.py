"""FR-0.6-04: timing runs are pinned to the reserved cores in oracle.yaml, and batch runs are kept off them.

The Oracle VM's cores are replaced by a generated system tree (asset tag OracleCloud.com and CPU topology files) over
this machine's real CPUs, a test double the rules allow for Oracle cores. The pinning is real: every test reads the
CPU affinity of each thread of a running process from /proc/<pid>/task/*/status, from outside the process.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aqis_lab import doctor
from aqis_lab import oracle_config as oc
from aqis_lab import platform as lp
from aqis_lab.runner import stage
from aqis_lab.timing import cores
from aqis_results_testutil import (cloud_system, cpu_list_text, oracle_system, parse_cpu_list, thread_masks,
                                   usable_cpus, write_oracle_config)
from aqis_runner_testutil import SMOKE_PACK
from aqis_testutil import ROOT

RUN_CARD_SCHEMA = ROOT / "aqis_lab" / "contracts" / "schemas" / "run_card.v1.json"
PROBE = ROOT / "docs" / "environment" / "oracle_probe.txt"

# Starts a numpy (OpenBLAS) import and one Python thread before pinning, so the process has several threads that
# already exist when it is pinned; then reports and blocks on a named pipe while the test reads its affinity.
PIN_SCRIPT = r"""
import json, sys, threading
from pathlib import Path
import numpy
from aqis_lab import platform as lp
from aqis_lab.timing import cores
idle = threading.Event()
worker = threading.Thread(target=idle.wait, daemon=True)
worker.start()
root, mode, config, fifo = sys.argv[1:5]
env = json.loads(sys.argv[5])
view = lp.SystemView(root=Path(root), environ=env, path=env["PATH"])
pinning = cores.pin_for_mode(mode, view, config)
print(json.dumps({"cpus": sorted(pinning.cpus) if pinning.cpus is not None else None,
                  "text": pinning.describe()}), flush=True)
with open(fifo) as handle:
    handle.read()
"""


def start_pinned(tmp_path, view, mode, config):
    fifo = tmp_path / f"hold-{mode}"
    os.mkfifo(fifo)
    proc = subprocess.Popen([sys.executable, "-c", PIN_SCRIPT, str(view.root), mode, str(config), str(fifo),
                             json.dumps(view.environ)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    line = proc.stdout.readline()
    assert line, proc.stderr.read()
    return proc, fifo, json.loads(line)


def release(proc, fifo):
    with open(fifo, "w") as handle:
        handle.write("go")
    proc.wait(timeout=60)


def test_FR_0_6_04_timing_process_pinned_to_reserved_cores(tmp_path):
    cpus = usable_cpus()
    reserved = {cpus[-1]}
    config = write_oracle_config(tmp_path / "oracle.yaml", sorted(reserved))
    view = oracle_system(tmp_path)
    for mode in cores.TIMING_MODES:
        proc, fifo, answer = start_pinned(tmp_path, view, mode, config)
        try:
            masks = thread_masks(proc.pid)
        finally:
            release(proc, fifo)
        assert proc.returncode == 0, proc.stderr.read()
        assert answer["cpus"] == sorted(reserved)
        assert len(masks) >= 3, f"expected the main, numpy and Python threads, found {masks}"
        assert all(mask == reserved for mask in masks.values()), (mode, masks)
        assert answer["text"].startswith(f"timing on {cpu_list_text(reserved)}")


def test_FR_0_6_04_batch_run_kept_off_reserved_cores(tmp_path):
    # A real runner on the smoke pack, on the Oracle cores test double, held inside its first shard by a named-pipe
    # clip (as in FR-0.5-06) while the test reads the affinity of every one of its threads.
    cpus = usable_cpus()
    reserved = {cpus[-1]}
    batch = set(cpus) - reserved
    config = write_oracle_config(tmp_path / "oracle.yaml", sorted(reserved))
    view = oracle_system(tmp_path)
    work = tmp_path / "work"
    staged = stage.stage_pack(SMOKE_PACK, work)
    manifest = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))
    clip = staged.root / "clips" / manifest["clips"][0]["member_path"]
    real = clip.read_bytes()
    clip.unlink()
    os.mkfifo(clip)
    out = tmp_path / "run"
    script = (
        "import json, sys\nfrom pathlib import Path\nfrom aqis_lab import platform as lp\n"
        "from aqis_lab.runner.run import RunOptions, run\n"
        "root, pack, out, work, config, env = sys.argv[1:7]\nenv = json.loads(env)\n"
        "view = lp.SystemView(root=Path(root), environ=env, path=env['PATH'])\n"
        "outcome = run(RunOptions(task='clip-stats', pack=Path(pack), out=Path(out), seed=0, work_dir=Path(work),"
        " cores_config=Path(config)), system=view)\nprint('STATUS', outcome.status)\n")
    proc = subprocess.Popen([sys.executable, "-c", script, str(view.root), str(SMOKE_PACK), str(out), str(work),
                             str(config), json.dumps(view.environ)], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 120
        log = out / "runner.log"
        while proc.poll() is None and time.monotonic() < deadline and not (
                log.exists() and "shard 00000 started" in log.read_text(encoding="utf-8")):
            time.sleep(0.01)
        time.sleep(0.2)
        assert proc.poll() is None, proc.stderr.read()
        masks = thread_masks(proc.pid)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=120)
    clip.unlink()
    clip.write_bytes(real)
    assert masks and all(mask == batch for mask in masks.values()), masks
    text = log.read_text(encoding="utf-8")
    assert (f"cores: batch on {cpu_list_text(batch)} (timing reserved {cpu_list_text(reserved)}; "
            f"config {config})") in text
    assert text.index("cores: batch on") < text.index("shard 00000 started")


def test_FR_0_6_04_every_mode_is_timing_or_batch():
    schema = json.loads(RUN_CARD_SCHEMA.read_text(encoding="utf-8"))
    modes = set(schema["properties"]["mode"]["enum"])
    assert set(cores.TIMING_MODES) | set(cores.BATCH_MODES) == modes
    assert not set(cores.TIMING_MODES) & set(cores.BATCH_MODES)
    assert cores.BATCH_MODES == ("batch",)          # owner decision, question 8 (a)
    for mode in modes:
        assert cores.mode_group(mode) == ("batch" if mode == "batch" else "timing")
    with pytest.raises(cores.CoreError) as info:
        cores.mode_group("sideways")
    assert "sideways" in str(info.value)


def test_FR_0_6_04_plan_reserves_config_cores_and_batches_the_rest(tmp_path):
    view = oracle_system(tmp_path, online=range(4))
    plan = cores.build_plan(view, write_oracle_config(tmp_path / "o.yaml", [2, 3]))
    assert plan.reserved == frozenset({2, 3}) and plan.batch == frozenset({0, 1})


def test_FR_0_6_04_reservation_must_leave_a_batch_core(tmp_path):
    view = oracle_system(tmp_path, online=range(4))
    with pytest.raises(cores.CoreError) as info:
        cores.build_plan(view, write_oracle_config(tmp_path / "o.yaml", [0, 1, 2, 3]))
    assert "no CPU left for batch runs" in str(info.value)


def test_FR_0_6_04_reserved_core_must_be_online(tmp_path):
    view = oracle_system(tmp_path, online=range(4))
    with pytest.raises(cores.CoreError) as info:
        cores.build_plan(view, write_oracle_config(tmp_path / "o.yaml", [3, 4, 9]))
    assert "4,9" in str(info.value) and "online CPUs 0-3" in str(info.value)


def test_FR_0_6_04_reservation_must_not_split_a_physical_core(tmp_path):
    # x86 Oracle shapes: one OCPU is two hardware threads of one core (owner decision, question 10 (a)).
    view = oracle_system(tmp_path, online=range(4), siblings=[[0, 1], [2, 3]])
    with pytest.raises(cores.CoreError) as info:
        cores.build_plan(view, write_oracle_config(tmp_path / "a.yaml", [3]))
    assert "CPU 3 shares a physical core with CPU 2" in str(info.value)
    plan = cores.build_plan(view, write_oracle_config(tmp_path / "b.yaml", [2, 3]))
    assert plan.reserved == frozenset({2, 3})


def test_FR_0_6_04_missing_topology_is_an_error(tmp_path):
    view = oracle_system(tmp_path, online=range(4), siblings=[[0], [1], [2]])
    with pytest.raises(lp.PlatformError) as info:
        cores.build_plan(view, write_oracle_config(tmp_path / "o.yaml", [3]))
    assert "cpu3/topology/thread_siblings_list" in str(info.value)


def test_FR_0_6_04_no_pinning_off_oracle(tmp_path):
    view = cloud_system(tmp_path)
    before = set(os.sched_getaffinity(0))
    config = write_oracle_config(tmp_path / "o.yaml", [usable_cpus()[-1]])
    for mode in ("batch", "realspeed_cpu"):
        proc, fifo, answer = start_pinned(tmp_path, view, mode, config)
        try:
            masks = thread_masks(proc.pid)
        finally:
            release(proc, fifo)
        assert answer == {"cpus": None, "text": "no reservation (platform cloud-vm)"}
        assert all(mask == before for mask in masks.values()), masks


def test_FR_0_6_04_real_runner_logs_no_reservation_on_this_vm(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "run", "--task", "clip-stats", "--pack", str(SMOKE_PACK),
                           "--out", str(tmp_path / "run"), "--seed", "0", "--work-dir", str(tmp_path / "work")],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr
    platform = lp.detect_platform(lp.SystemView.real()).platform
    assert platform != "oracle"
    assert f"cores: no reservation (platform {platform})" in proc.stdout


def test_FR_0_6_04_pin_failure_is_an_error(tmp_path):
    # CPU 63 is online in the double but not usable here: the kernel refuses it, and that must be an error.
    cpus = usable_cpus()
    assert 63 not in cpus
    view = oracle_system(tmp_path, online=list(cpus) + [63])
    config = write_oracle_config(tmp_path / "o.yaml", [63])
    proc = subprocess.run([sys.executable, "-c", PIN_SCRIPT.split("print(")[0], str(view.root), "realspeed_cpu",
                           str(config), str(tmp_path / "unused"), json.dumps(view.environ)],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0
    assert "CoreError" in proc.stderr and "cannot pin thread" in proc.stderr


def test_FR_0_6_04_run_stops_with_exit_2_on_core_error(tmp_path):
    view = oracle_system(tmp_path, online=range(4))
    config = write_oracle_config(tmp_path / "o.yaml", [0, 1, 2, 3])
    script = ("import json, sys\nfrom pathlib import Path\nfrom aqis_lab import platform as lp\n"
              "from aqis_lab.runner.run import RunInputError, RunOptions, run\n"
              "env = json.loads(sys.argv[5])\n"
              "view = lp.SystemView(root=Path(sys.argv[1]), environ=env, path=env['PATH'])\n"
              "try:\n    run(RunOptions(task='clip-stats', pack=Path(sys.argv[2]), out=Path(sys.argv[3]), seed=0, "
              "work_dir=Path(sys.argv[4]), cores_config=Path(sys.argv[6])), system=view)\n"
              "except RunInputError as exc:\n    print('INPUT ERROR', exc)\n    sys.exit(2)\n")
    proc = subprocess.run([sys.executable, "-c", script, str(view.root), str(SMOKE_PACK), str(tmp_path / "run"),
                           str(tmp_path / "work"), json.dumps(view.environ), str(config)],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 2 and "no CPU left for batch runs" in proc.stdout, proc.stdout + proc.stderr
    assert not (tmp_path / "run").exists() and not (tmp_path / "work").exists()


def rows(report):
    return {c.name: c for c in report.checks}


def test_FR_0_6_04_doctor_oracle_cores_row(tmp_path):
    view = oracle_system(tmp_path, online=range(4))
    good = rows(doctor.run_doctor("oracle", system=view, work_dir=tmp_path,
                                  oracle_config_path=write_oracle_config(tmp_path / "a.yaml", [2, 3])))["cores"]
    assert good.status == "PASS" and good.actual == "timing on 2-3, batch on 0-1"
    bad = rows(doctor.run_doctor("oracle", system=view, work_dir=tmp_path,
                                 oracle_config_path=write_oracle_config(tmp_path / "b.yaml", [7])))["cores"]
    assert bad.status == "FAIL" and "7" in bad.detail and "not online" in bad.detail
    report = doctor.run_doctor("oracle", system=view, work_dir=tmp_path,
                               oracle_config_path=write_oracle_config(tmp_path / "b.yaml", [7]))
    assert report.result == "FAIL" and [c.name for c in report.checks][-1] == "cores"
    assert "cores" not in rows(doctor.run_doctor("cloud", system=cloud_system(tmp_path), work_dir=tmp_path))


def test_FR_0_6_04_platform_cpu_facts(tmp_path):
    view = oracle_system(tmp_path, online=[0, 1, 2, 5], siblings=[[0, 1], [2], [5]])
    assert lp.online_cpus(view) == frozenset({0, 1, 2, 5})
    assert lp.core_siblings(1, view) == frozenset({0, 1})
    assert lp.parse_cpu_list("0-2,5,7-8\n") == frozenset({0, 1, 2, 5, 7, 8})
    for bad in ("", "a-b", "3-1", "1,,2"):
        with pytest.raises(lp.PlatformError):
            lp.parse_cpu_list(bad)
    real = sorted(int(p.name) for p in Path("/proc/self/task").iterdir())
    assert sorted(lp.thread_ids()) == real
    assert lp.thread_affinity(real[0]) == frozenset(os.sched_getaffinity(0))
    assert lp.online_cpus() >= frozenset(os.sched_getaffinity(0))


def test_FR_0_6_04_committed_reservation_fits_oracle_probe():
    # docs/approvals/WP-0.6.md: cores 2-3 for timing, batch on 0-1; the probe lists online CPUs 0-3 (Ampere Altra,
    # one hardware thread per core).
    probe = PROBE.read_text(encoding="utf-8")
    line = next(l for l in probe.splitlines() if l.startswith("On-line CPU(s) list:"))
    online = parse_cpu_list(line.split(":", 1)[1])
    assert online == {0, 1, 2, 3} and "Neoverse-N1" in probe
    reserved = set(oc.load().reserved_for_timing)
    assert reserved == {2, 3} and online - reserved == {0, 1}


@pytest.mark.oracle
def test_FR_0_6_04_real_oracle_pinning(tmp_path):
    # On the Oracle VM: the real platform, the real CPU files and the committed oracle.yaml.
    real = lp.SystemView.real()
    assert lp.detect_platform(real).platform == "oracle"
    plan = cores.build_plan(real, oc.DEFAULT_CONFIG)
    for mode, want in (("realspeed_cpu", plan.reserved), ("batch", plan.batch)):
        fifo = tmp_path / f"hold-{mode}"
        os.mkfifo(fifo)
        script = PIN_SCRIPT.replace("view = lp.SystemView(root=Path(root), environ=env, path=env[\"PATH\"])",
                                    "view = None")
        proc = subprocess.Popen([sys.executable, "-c", script, "/", mode, str(oc.DEFAULT_CONFIG), str(fifo), "{}"],
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        answer = json.loads(proc.stdout.readline() or "{}")
        try:
            masks = thread_masks(proc.pid)
        finally:
            release(proc, fifo)
        assert set(answer.get("cpus") or []) == set(want)
        assert all(mask == set(want) for mask in masks.values()), (mode, masks)
