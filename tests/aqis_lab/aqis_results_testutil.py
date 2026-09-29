"""Shared helpers for the WP-0.6 tests (Oracle setup, core reservation, results store, trace, sync). Not a test module.

Test doubles, each for an external service the rules name: a generated system tree with the Oracle asset tag and
CPU topology files stands in for the Oracle VM's cores (the pinning itself is real and runs on this machine's
CPUs), and an rclone `alias` remote on a local folder stands in for Google Drive (rclone itself is real). Expected
values are computed here independently of the code under test.
"""
import csv
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from aqis_lab import platform as lp
from aqis_runner_testutil import SMOKE_PACK, make_system_tree

ORACLE_TAG = "OracleCloud.com"


def cpu_list_text(cpus):
    """Kernel CPU-list text ("0-2,5") for a set of CPU numbers, written independently of aqis_lab."""
    cpus = sorted(cpus)
    parts, i = [], 0
    while i < len(cpus):
        j = i
        while j + 1 < len(cpus) and cpus[j + 1] == cpus[j] + 1:
            j += 1
        parts.append(str(cpus[i]) if i == j else f"{cpus[i]}-{cpus[j]}")
        i = j + 1
    return ",".join(parts)


def parse_cpu_list(text):
    """The set of CPU numbers in kernel CPU-list text, parsed independently of aqis_lab."""
    out = set()
    for part in text.strip().split(","):
        lo, _, hi = part.partition("-")
        out.update(range(int(lo), int(hi or lo) + 1))
    return out


def usable_cpus():
    """This process's allowed CPUs; the core tests reserve the highest one and need at least one more for batch."""
    cpus = sorted(os.sched_getaffinity(0))
    assert len(cpus) >= 2, f"the core reservation tests need at least 2 CPUs, this machine allows {cpus}"
    return cpus


def oracle_system(tmp_path, online=None, siblings=None, name="oracle-sys"):
    """A SystemView that is the Oracle platform (asset tag) with the given online CPUs and SMT sibling groups.

    `online` defaults to this machine's usable CPUs; `siblings` is a list of CPU groups sharing a physical core
    (default: every CPU its own core, as on the Ampere A1 in docs/environment/oracle_probe.txt).
    """
    online = usable_cpus() if online is None else sorted(online)
    root = make_system_tree(Path(tmp_path) / name, chassis_asset_tag=ORACLE_TAG)
    base = root / "sys" / "devices" / "system" / "cpu"
    base.mkdir(parents=True, exist_ok=True)
    (base / "online").write_text(cpu_list_text(online) + "\n", encoding="utf-8")
    groups = siblings if siblings is not None else [[c] for c in online]
    for group in groups:
        for cpu in group:
            topo = base / f"cpu{cpu}" / "topology"
            topo.mkdir(parents=True, exist_ok=True)
            (topo / "thread_siblings_list").write_text(cpu_list_text(group) + "\n", encoding="utf-8")
    return lp.SystemView(root=root, environ={"PATH": str(root / "bin")}, path=str(root / "bin"))


def cloud_system(tmp_path, name="cloud-sys"):
    """A SystemView that is the cloud VM (CLAUDE_CODE_REMOTE=true), without any core files."""
    root = make_system_tree(Path(tmp_path) / name)
    return lp.SystemView(root=root, environ={"PATH": str(root / "bin"), "CLAUDE_CODE_REMOTE": "true"},
                         path=str(root / "bin"))


def oracle_config_text(reserved, remote="aqis-drive", results_store="data/raw/aqis_lab/results",
                       operating_systems="ubuntu:24.04", architectures="x86_64 aarch64", min_glibc="2.28",
                       work_dir="data/raw/aqis_lab/work", doctor_reports="data/raw/aqis_lab/doctor",
                       logs="data/raw/aqis_lab/logs"):
    return (f'schema_version: "1.0"\nsetup:\n  architectures: "{architectures}"\n'
            f'  operating_systems: "{operating_systems}"\n  min_glibc: "{min_glibc}"\npaths:\n'
            f"  work_dir: {work_dir}\n  doctor_reports: {doctor_reports}\n  results_store: {results_store}\n"
            f"  logs: {logs}\ncores:\n  reserved_for_timing: [{', '.join(str(c) for c in reserved)}]\n"
            f"rclone:\n  remote: {remote}\n")


def write_oracle_config(path, reserved, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(oracle_config_text(reserved, **kwargs), encoding="utf-8")
    return path


def thread_masks(pid):
    """{thread id: allowed CPUs} for every thread of a running process, read from /proc/<pid>/task/*/status."""
    masks = {}
    for task in sorted(Path(f"/proc/{pid}/task").iterdir()):
        text = (task / "status").read_text(encoding="utf-8")
        m = re.search(r"^Cpus_allowed_list:\s*(\S+)$", text, re.M)
        assert m, f"no Cpus_allowed_list in {task}/status"
        masks[int(task.name)] = parse_cpu_list(m.group(1))
    return masks


# --- results store inputs: real runner and scorer output ------------------------------------------------------------
SMOKE_MANIFEST = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))


def canonical(value):
    """Canonical JSON bytes (sorted keys, no spaces, UTF-8), written independently of aqis_lab.contracts."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def expected_row_id(identity):
    """result_row_id as docs/results/RESULTS_STORE.md defines it: SHA-256 of the identity's canonical JSON."""
    return hashlib.sha256(canonical(identity)).hexdigest()


def smoke_run(out, work, seed=0, shard_clips=None):
    """A real finished runner run of clip-stats over the smoke pack; returns the run folder."""
    from aqis_lab.runner.run import RunOptions, run
    run(RunOptions(task="clip-stats", pack=SMOKE_PACK, out=Path(out), seed=seed, work_dir=Path(work),
                   shard_clips=shard_clips), echo=None)
    return Path(out)


def score_folder(out, run_card_id, clip_count=3, hyp=lambda text: text.lower()):
    """A real `score` output folder: references are the smoke clips' transcripts, hypotheses `hyp(transcript)`."""
    from aqis_lab.commands.score import main as score_main
    out = Path(out)
    inputs = out.parent / (out.name + "-inputs")
    inputs.mkdir(parents=True)
    clips = SMOKE_MANIFEST["clips"][:clip_count]
    with open(inputs / "ref.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip_id", "text"])
        for c in clips:
            w.writerow([c["clip_id"], c["transcript"]])
    with open(inputs / "hyp.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run_card_id", "clip_id", "text"])
        for c in clips:
            w.writerow([run_card_id, c["clip_id"], hyp(c["transcript"])])
    assert score_main(["--ref", str(inputs / "ref.csv"), "--hyp", str(inputs / "hyp.csv"), "--out", str(out)]) == 0
    return out


def copy_tree(src, dst):
    shutil.copytree(src, dst)
    return Path(dst)


def run_rows(run_dir):
    """The result rows of a run folder, parsed from its results.jsonl."""
    return [json.loads(line) for line in (Path(run_dir) / "results.jsonl").read_text(encoding="utf-8").splitlines()]


# --- tampering with a stored results store (audit findings WP-0.6-F02, F03) ------------------------------------------
def part_file(store_dir):
    parts = sorted(Path(store_dir).glob("run_card_id=*/part-*.parquet"))
    assert len(parts) == 1, parts
    return parts[0]


def rewrite_part(part, change, keep_name):
    """Rewrite a stored part file with `change(rows)` applied. keep_name=True keeps the old (now wrong) name;
    otherwise the file is renamed after its new content, as a careful hand edit would do."""
    import io
    import pyarrow as pa
    import pyarrow.parquet as pq
    from aqis_lab.results import store
    rows = pq.read_table(part, use_threads=False).to_pylist()
    change(rows)
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=store.arrow_schema()), buffer)
    data = buffer.getvalue()
    part.chmod(0o644)
    part.unlink()
    target = part if keep_name else part.with_name(f"part-{hashlib.sha256(data).hexdigest()}.parquet")
    target.write_bytes(data)
    return target, rows
