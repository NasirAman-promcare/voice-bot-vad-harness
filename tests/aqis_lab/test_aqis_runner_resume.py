"""FR-0.5-06: a real run is killed after k shards, restarted, and gives byte-identical results without recomputing.

The smoke pack takes about a second, so killing "after k shards" by the clock would be a race. Instead the test
turns the first clip of shard k into a named pipe (FIFO): the run finishes shards 0 to k-1 and then blocks opening
that clip, so it can never write shard k's marker. The test waits for exactly k markers, sends SIGKILL, puts the
real clip back (its SHA-256 is checked when it is read) and runs the same command again. The production code has no
test hooks; only the timing of one input file is controlled.
"""
import json
import os
import signal
import subprocess
import sys
import time

from aqis_lab.runner import stage
from aqis_runner_testutil import SMOKE_PACK
from aqis_testutil import ROOT

MANIFEST = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))
K = 3                                   # shards finished before the kill; shard K blocks on its first clip


def command(out, work):
    return [sys.executable, "-m", "aqis_lab", "run", "--task", "clip-stats", "--pack", str(SMOKE_PACK), "--out",
            str(out), "--seed", "0", "--work-dir", str(work), "--shard-clips", "10"]


def markers(out):
    return sorted((out / "shards").glob("*.done.json")) if (out / "shards").exists() else []


def file_state(path):
    st = path.stat()
    return path.read_bytes(), st.st_ino, st.st_mtime_ns


def test_FR_0_5_06_kill_and_resume_byte_identical_without_recomputing(tmp_path):
    work = tmp_path / "work"
    staged = stage.stage_pack(SMOKE_PACK, work)
    reference = tmp_path / "uninterrupted"
    assert subprocess.run(command(reference, work), cwd=ROOT, capture_output=True, timeout=600).returncode == 0

    clip = staged.root / "clips" / MANIFEST["clips"][K * 10]["member_path"]
    real = clip.read_bytes()
    clip.unlink()
    os.mkfifo(clip)
    out = tmp_path / "interrupted"
    proc = subprocess.Popen(command(out, work), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 60
        while len(markers(out)) < K and time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.01)
        assert len(markers(out)) == K, f"expected {K} finished shards before the kill, got {len(markers(out))}"
        time.sleep(0.2)
        assert proc.poll() is None, "the run must still be blocked inside shard K"
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
    assert proc.returncode == -signal.SIGKILL
    assert len(markers(out)) == K and not (out / "results.jsonl").exists()
    finished = {p.name: file_state(p) for p in (out / "shards").iterdir()
                if p.name.split(".")[0] in {f"shard-{i:05d}" for i in range(K)}}
    assert len(finished) == 2 * K

    clip.unlink()
    clip.write_bytes(real)
    resumed = subprocess.run(command(out, work), cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr

    assert (out / "results.jsonl").read_bytes() == (reference / "results.jsonl").read_bytes()
    for name, state in finished.items():
        assert file_state(out / "shards" / name) == state, f"{name} was rewritten"
    log = (out / "runner.log").read_text(encoding="utf-8")
    second = log[log.index(" session 2 start"):]
    for i in range(K):
        assert f"shard {i:05d} skipped" in second and f"shard {i:05d} started" not in second
    for i in range(K, 6):
        assert f"shard {i:05d} started" in second and f"shard {i:05d} finished" in second
    first = log[:log.index(" session 2 start")]
    assert f"shard {K:05d} started" in first and f"shard {K:05d} finished" not in first


def test_FR_0_5_06_kill_during_result_write_never_counts(tmp_path):
    work = tmp_path / "work"
    out = tmp_path / "run"
    assert subprocess.run(command(out, work), cwd=ROOT, capture_output=True, timeout=600).returncode == 0
    reference = (out / "results.jsonl").read_bytes()
    shards = out / "shards"
    # what a kill leaves behind: a half-written .partial (killed before the rename), or the results file renamed
    # into place but no marker yet (killed between the two writes), with a stale final results file
    full = (shards / "shard-00001.jsonl").read_bytes()
    (shards / "shard-00001.done.json").unlink()
    (shards / "shard-00001.jsonl").unlink()
    (shards / "shard-00001.jsonl.partial").write_bytes(full[: len(full) // 2])
    (shards / "shard-00004.done.json").unlink()
    (shards / "shard-00004.jsonl").write_bytes((shards / "shard-00004.jsonl").read_bytes()[:40])
    (out / "results.jsonl").unlink()
    resumed = subprocess.run(command(out, work), cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert resumed.returncode == 0, resumed.stderr
    log = (out / "runner.log").read_text(encoding="utf-8")
    second = log[log.index(" session 2 start"):]
    assert "shard 00001 started" in second and "shard 00004 started" in second
    assert second.count(" started") == 2
    assert (out / "results.jsonl").read_bytes() == reference
    assert list(out.rglob("*.partial")) == []
