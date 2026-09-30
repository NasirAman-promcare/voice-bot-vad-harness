"""FR-0.7-08: `python -m aqis_lab parity <results-A> <results-B>` compares transcript hashes and WER per clip and in
total, and lists every difference.

Bundles are built by the test (aqis_adapters_testutil.make_bundle) in the documented format, with real score tables
from the WP-0.3 `score` command; the expected differences are known from how the test built them.
"""
import hashlib
import json
import subprocess
import sys

import pytest

from aqis_lab import parity
from aqis_adapters_testutil import make_bundle, tar_bundle
from aqis_testutil import ROOT

REFS = {f"clip-{i:02d}": f"the quick brown fox number {i} jumps over the lazy dog" for i in range(12)}


def texts(changes=None, drop=(), add=None):
    out = {c: r for c, r in REFS.items() if c not in drop}
    out.update(changes or {})
    out.update(add or {})
    return out


def bundle(root, name, hyp, **kwargs):
    return make_bundle(root, name, hyp, REFS, **kwargs)


def run_parity(a, b):
    return subprocess.run([sys.executable, "-m", "aqis_lab", "parity", str(a), str(b)], cwd=ROOT,
                          capture_output=True, text=True, timeout=300)


def test_FR_0_7_08_identical_bundles_report_no_difference(tmp_path):
    a = bundle(tmp_path, "phase0-smoke-cloud-1", texts())
    b = bundle(tmp_path, "phase0-smoke-oracle-1", texts(), target="oracle", platform="oracle", card_char="b")
    proc = run_parity(a, b)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "parity: identical" in proc.stdout and "vosk-batch: 12 clips" in proc.stdout
    assert "DIFFERENT" not in proc.stdout
    assert "phase0-smoke-cloud-1" in proc.stdout and "phase0-smoke-oracle-1" in proc.stdout


def test_FR_0_7_08_reports_every_per_clip_difference(tmp_path):
    # Must-catch 6: three changed transcripts (hash and WER), one clip missing and one extra; every one is listed.
    changed = {"clip-01": "the quick brown fox number 1 jumps over a lazy dog",
               "clip-05": "the quick brown fox number 5 leaps over the lazy dog",
               "clip-09": "the quick brown fox number 9 jumps over the lazy dog."}
    a = bundle(tmp_path, "a", texts())
    b = bundle(tmp_path, "b", texts(changed, drop=("clip-11",), add={"clip-12": "an extra clip"}))
    proc = run_parity(a, b)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    lines = [l for l in proc.stdout.splitlines() if l.startswith("DIFFERENT")]
    for clip, text in changed.items():
        want = f"DIFFERENT vosk-batch {clip} text_sha256 A={hashlib.sha256(REFS[clip].encode()).hexdigest()} " \
               f"B={hashlib.sha256(text.encode()).hexdigest()}"
        assert want in lines, want
    # clip-09 differs only in punctuation: the hash differs, the normalised WER does not
    wer_lines = [l for l in lines if " wer " in l]
    assert any(l.startswith("DIFFERENT vosk-batch-natural clip-01 main wer ") for l in wer_lines)
    assert any(l.startswith("DIFFERENT vosk-batch-natural clip-05 main wer ") for l in wer_lines)
    assert not any("clip-09" in l for l in wer_lines)
    assert "DIFFERENT vosk-batch clip-11 clip A=present B=missing" in lines
    assert "DIFFERENT vosk-batch clip-12 clip A=missing B=present" in lines
    assert "DIFFERENT vosk-batch-natural clip-11 main row A=present B=missing" in lines
    report = parity.compare(parity.load_bundle(a), parity.load_bundle(b))
    assert len([d for d in report.differences if d.field == "text_sha256"]) == 3
    assert f"parity: {len(lines)} difference(s)" in proc.stdout


def test_FR_0_7_08_total_wer_difference_reported(tmp_path):
    a = bundle(tmp_path, "a", texts())
    b = bundle(tmp_path, "b", texts({"clip-03": "completely different words here"}))
    proc = run_parity(a, b)
    assert proc.returncode == 1
    summary_a = json.loads((a / "scores/vosk-batch-natural/summary.json").read_text())["variants"]["main"]
    summary_b = json.loads((b / "scores/vosk-batch-natural/summary.json").read_text())["variants"]["main"]
    assert f"DIFFERENT vosk-batch-natural total main corpus_wer A={summary_a['corpus_wer']!r} " \
           f"B={summary_b['corpus_wer']!r}" in proc.stdout
    assert f"DIFFERENT vosk-batch-natural total main errors A={summary_a['errors']} B={summary_b['errors']}" \
        in proc.stdout


def test_FR_0_7_08_damaged_bundle_is_input_error(tmp_path):
    a = bundle(tmp_path, "a", texts())
    b = bundle(tmp_path, "b", texts())
    target = b / "runs" / "vosk-batch" / "results.jsonl"
    target.write_text(target.read_text().replace("fox", "cat", 1))
    proc = run_parity(a, b)
    assert proc.returncode == 2 and proc.stderr.startswith("ERROR:") and "runs/vosk-batch/results.jsonl" in proc.stderr
    (a / "extra.txt").write_text("x")
    proc = run_parity(a, a)
    assert proc.returncode == 2 and "extra.txt" in proc.stderr
    proc = run_parity(tmp_path / "missing", b)
    assert proc.returncode == 2


def test_FR_0_7_08_bundle_without_vosk_batch_is_input_error(tmp_path):
    a = bundle(tmp_path, "a", texts())
    meta = json.loads((a / "BUNDLE.json").read_text())
    with pytest.raises(parity.ParityInputError, match="vosk-batch"):
        parity.compare(parity.load_bundle(a), parity.Bundle(name="empty", meta=meta, files={}))


def test_FR_0_7_08_reads_folder_and_tar_alike(tmp_path):
    a = bundle(tmp_path, "a", texts())
    b = bundle(tmp_path, "b", texts({"clip-02": "the quick brown fox"}))
    folder = run_parity(a, b)
    archived = run_parity(tar_bundle(a), tar_bundle(b))
    assert folder.returncode == archived.returncode == 1
    diff = lambda out: [l for l in out.splitlines() if l.startswith("DIFFERENT") or l.startswith("parity:")]
    assert diff(folder.stdout) == diff(archived.stdout) and diff(folder.stdout)


def test_FR_0_7_08_task_in_one_bundle_only_is_named_not_hidden(tmp_path):
    rows = [{"clip_id": "clip-00", "run_card_id": "e" * 64, "task": "parakeet-offline", "task_version": "1.0",
             "text": "x", "text_sha256": hashlib.sha256(b"x").hexdigest()}]
    a = bundle(tmp_path, "a", texts())
    b = bundle(tmp_path, "b", texts(), extra_tasks={"parakeet-offline": rows})
    proc = run_parity(a, b)
    assert proc.returncode == 0
    assert "not compared: parakeet-offline is only in B (b)" in proc.stdout


@pytest.mark.slow
def test_FR_0_7_08_parity_process_always_exits(tmp_path):
    # A score table read from Python-owned bytes left Arrow's pool threads a buffer to release at interpreter exit,
    # which needs the GIL: the process hung there, in 6 of 40 runs with pq.read_table and in 1 of 190 with a closed
    # ParquetFile (docs/progress/WP-0.7/EVIDENCE.md). Each run must finish, with its result.
    a = bundle(tmp_path, "a", texts())
    b = bundle(tmp_path, "b", texts({"clip-04": "the quick brown fox"}))
    for _ in range(120):
        proc = subprocess.run([sys.executable, "-m", "aqis_lab", "parity", str(a), str(b)], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 1 and "DIFFERENT vosk-batch-natural clip-04 main wer" in proc.stdout
