"""NFR-0.5-01: runner overhead against a direct loop on the smoke pack.

Owner decision (BLK-008, option 1; docs/approvals/WP-0.5.md): the 5 % limit is checked in WP-0.7 with Vosk, and is
DEBT-013 until then. This test runs the measurement WP-0.5 records in EVIDENCE.md: the same process, the same staged
pack and the same task, fsync on in both loops, medians of alternating repetitions. It asserts that the comparison is
like for like (both loops write byte-identical results) and prints the numbers; it does not assert the 5 % limit.
"""
import statistics
import time

import pytest

from aqis_lab import drive
from aqis_lab.contracts.canonical import canonical_json
from aqis_lab.runner.run import RunOptions, run
from aqis_lab.runner.stage import stage_pack
from aqis_lab.runner.tasks import TASKS
from aqis_runner_testutil import SMOKE_PACK

REPEATS = 9


@pytest.mark.slow
def test_NFR_0_5_01_overhead_measured_against_direct_loop(tmp_path):
    task = TASKS["clip-stats"]
    work = tmp_path / "work"
    staged = stage_pack(SMOKE_PACK, work)
    reference = run(RunOptions(task=task.name, pack=SMOKE_PACK, out=tmp_path / "reference", seed=0, work_dir=work),
                    echo=None)
    expected = (tmp_path / "reference" / "results.jsonl").read_bytes()

    def direct(i):
        rows = []
        for clip in staged.manifest["clips"]:
            stats = task.run_clip(clip, staged.read_clip(clip))
            rows.append(canonical_json({"clip_id": clip["clip_id"], "run_card_id": reference.run_card_id,
                                        "task": task.name, "task_version": task.version, **stats}) + b"\n")
        folder = tmp_path / f"direct-{i}"
        folder.mkdir()
        return drive.write_bytes(folder / "results.jsonl", b"".join(rows)).read_bytes()

    def runner(i):
        out = tmp_path / f"run-{i}"
        run(RunOptions(task=task.name, pack=SMOKE_PACK, out=out, seed=0, work_dir=work), echo=None)
        return (out / "results.jsonl").read_bytes()

    assert direct(-1) == expected and runner(-1) == expected      # warm-up, and the two loops do the same work
    times = {"direct": [], "runner": []}
    for i in range(REPEATS):
        for name, loop in (("direct", direct), ("runner", runner)):
            start = time.perf_counter_ns()
            assert loop(i) == expected
            times[name].append(time.perf_counter_ns() - start)
    direct_ms = statistics.median(times["direct"]) / 1e6
    runner_ms = statistics.median(times["runner"]) / 1e6
    print(f"NFR-0.5-01 measurement: direct median {direct_ms:.1f} ms; runner median {runner_ms:.1f} ms; "
          f"fixed overhead {runner_ms - direct_ms:.1f} ms ({(runner_ms - direct_ms) / direct_ms * 100:.1f} %); "
          f"5 % limit deferred to WP-0.7 (DEBT-013)")
    assert direct_ms > 0 and runner_ms > 0
