"""FR-0.7-07 and NFR-0.7-01: `python -m aqis_lab phase0 smoke --target cloud|colab|oracle`.

The fast tests check the configuration and the refusals. The `slow`/`network` tests share one real cloud smoke run
(fresh model cache, so the model download is included in its time) and check its bundle independently: transcripts
are rescored with the `score` command on CSVs built here, report numbers are recomputed from the bundle's files, and
every row is traced through a results store rebuilt from the bundle.
"""
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

from aqis_lab import smoke
from aqis_lab.contracts.validate import validate_event_lines, validate_run_card
from aqis_lab.results import ingest
from aqis_lab.results import store as rstore
from aqis_lab.results.store import result_row_id
from aqis_lab.trace import trace_row
from aqis_adapters_testutil import drive_view
from aqis_runner_testutil import SMOKE_PACK
from aqis_testutil import ROOT

CONFIG = ROOT / "config" / "aqis_lab" / "phase0_smoke.yaml"
MANIFEST = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))
CLIP_IDS = [c["clip_id"] for c in MANIFEST["clips"]]
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


def expected_subset():
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["subset"]
    chosen = []
    for split, n in cfg["per_split"].items():
        clips = [c["clip_id"] for c in MANIFEST["clips"] if c["split"] == split]
        clips.sort(key=lambda cid: hashlib.sha256((cfg["key_prefix"] + cid).encode()).hexdigest())
        chosen += clips[:n]
    return chosen


def test_FR_0_7_07_config_subset_equals_rule():
    cfg = smoke.load_config(CONFIG)
    assert list(cfg.subset) == expected_subset() == [
        "ls-test-clean-3570-5695-0009", "ls-test-clean-6829-68771-0030", "ls-test-other-6128-63244-0013",
        "smoke-mix-01", "tts-smoke-04"]
    assert cfg.tasks_for("cloud") == [("vosk-batch", "all"), ("harness-vad", "all"), ("vosk-realspeed", "subset")]
    assert cfg.tasks_for("oracle") == cfg.tasks_for("cloud")
    assert [t for t, _ in cfg.tasks_for("colab")] == ["vosk-batch", "harness-vad", "vosk-realspeed",
                                                     "parakeet-offline", "parakeet-compute-delay"]


@pytest.mark.parametrize("change", ["unknown_key", "subset_mismatch", "unknown_task", "unknown_target"])
def test_FR_0_7_07_config_is_checked(tmp_path, change):
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if change == "unknown_key":
        data["extra"] = 1
    elif change == "subset_mismatch":
        data["subset"]["clip_ids"][0] = "ls-test-clean-1188-133604-0029"
    elif change == "unknown_task":
        data["runs"][0]["task"] = "whisper-batch"
    else:
        data["runs"][0]["targets"].append("kaggle")
    path = tmp_path / "smoke.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(smoke.SmokeInputError):
        smoke.load_config(path)


def test_FR_0_7_07_target_must_match_platform(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(smoke.SmokeInputError, match="cloud-vm") as info:
        smoke.run_smoke("oracle", out=out, echo=None)
    assert info.value.exit_code == 2 and not out.exists()
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "phase0", "smoke", "--target", "colab", "--out",
                           str(out)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 2 and proc.stderr.startswith("ERROR:") and "colab" in proc.stderr


def test_FR_0_7_03_colab_smoke_without_gpu_fails_never_skips(tmp_path):
    # Must-catch 3: on a Colab runtime without a GPU the colab smoke stops before running anything; Parakeet is
    # never skipped or replaced.
    system, mount = drive_view(tmp_path)
    out = mount / "MyDrive" / "AQIS_LAB" / "results" / "phase0-smoke-colab"
    with pytest.raises(smoke.SmokeInputError, match="no GPU") as info:
        smoke.run_smoke("colab", out=out, drive_mount=mount, system=system, echo=None)
    assert info.value.exit_code == 2 and not out.exists()


# --- One real cloud smoke run ---

@pytest.fixture(scope="module")
def cloud(tmp_path_factory):
    base = tmp_path_factory.mktemp("smoke")
    result = smoke.run_smoke("cloud", out=base / "out", store=base / "store", model_cache=base / "models",
                             work_dir=base / "work", bundle_dir=base / "bundles", echo=None)
    return result


def bundle_rows(bundle, task):
    path = bundle / "runs" / task / "results.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.slow
@pytest.mark.network
def test_NFR_0_7_01_cloud_smoke_within_15_minutes(cloud):
    meta = json.loads((cloud.bundle / "BUNDLE.json").read_text(encoding="utf-8"))
    assert meta["elapsed_s"] == cloud.elapsed_s and cloud.elapsed_s < 900


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_smoke_creates_valid_run_card_for_every_run(cloud):
    meta = json.loads((cloud.bundle / "BUNDLE.json").read_text(encoding="utf-8"))
    assert sorted(meta["runs"]) == ["harness-vad", "vosk-batch", "vosk-realspeed"]
    modes = {"vosk-batch": "batch", "harness-vad": "batch", "vosk-realspeed": "realspeed_cpu"}
    for task, info in meta["runs"].items():
        card = json.loads((cloud.bundle / "runs" / task / "run_card.json").read_text(encoding="utf-8"))
        validate_run_card(card)
        assert card["run_card_id"] == info["run_card_id"] and card["mode"] == modes[task]
        assert card["machine"]["platform"] == "cloud-vm" and card["seed"] == 0
        events = (cloud.bundle / "runs" / task / "events.jsonl").read_bytes()
        assert all(r.valid for r in validate_event_lines(events))


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_vosk_batch_on_all_60_clips(cloud):
    rows = bundle_rows(cloud.bundle, "vosk-batch")
    assert [r["clip_id"] for r in rows] == CLIP_IDS and len(rows) == 60
    for r in rows:
        assert r["text_sha256"] == hashlib.sha256(r["text"].encode("utf-8")).hexdigest()


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_harness_vad_on_all_clips(cloud):
    rows = bundle_rows(cloud.bundle, "harness-vad")
    assert [r["clip_id"] for r in rows] == CLIP_IDS
    silence = next(r for r in rows if r["clip_id"] == "smoke-silence-01")
    assert silence["segments"] == [] and any(r["segments"] for r in rows)


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_realspeed_vosk_on_5_clips(cloud):
    rows = bundle_rows(cloud.bundle, "vosk-realspeed")
    assert [r["clip_id"] for r in rows] == [c for c in CLIP_IDS if c in expected_subset()]
    batch = {r["clip_id"]: r for r in bundle_rows(cloud.bundle, "vosk-batch")}
    for r in rows:
        assert r["wall_s"] >= r["audio_s"] and r["first_partial_latency_ms"] is not None
        assert r["finalisation_latency_ms"] is not None and r["finalisation_latency_ms"] >= 0
        assert r["text_sha256"] == batch[r["clip_id"]]["text_sha256"], "same model, kernel and 20 ms frames"


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_speech_clips_scored_with_wp03_scorer(cloud, tmp_path):
    rows = {r["clip_id"]: r for r in bundle_rows(cloud.bundle, "vosk-batch")}
    card_id = rows[CLIP_IDS[0]]["run_card_id"]
    for subset, splits in (("natural", {"test-clean", "test-other", "noisy"}), ("synthetic-tts", {"tts"})):
        clips = [c for c in MANIFEST["clips"] if c["split"] in splits]
        ref, hyp = io.StringIO(), io.StringIO()
        rw, hw = csv.writer(ref, lineterminator="\n"), csv.writer(hyp, lineterminator="\n")
        rw.writerow(["clip_id", "text"])
        hw.writerow(["run_card_id", "clip_id", "text"])
        for c in clips:
            rw.writerow([c["clip_id"], c["transcript"]])
            hw.writerow([card_id, c["clip_id"], rows[c["clip_id"]]["text"]])
        (tmp_path / f"{subset}-ref.csv").write_text(ref.getvalue(), encoding="utf-8")
        (tmp_path / f"{subset}-hyp.csv").write_text(hyp.getvalue(), encoding="utf-8")
        out = tmp_path / subset
        proc = subprocess.run([sys.executable, "-m", "aqis_lab", "score", "--ref", str(tmp_path / f"{subset}-ref.csv"),
                               "--hyp", str(tmp_path / f"{subset}-hyp.csv"), "--out", str(out)], cwd=ROOT,
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stderr
        folder = cloud.bundle / "scores" / f"vosk-batch-{subset}"
        for name in ("scores.parquet", "scores.csv", "summary.json"):
            assert (folder / name).read_bytes() == (out / name).read_bytes(), (subset, name)
    assert not (cloud.bundle / "scores" / "parakeet-offline-natural").exists()


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_parakeet_only_on_gpu_target_and_report_says_so(cloud):
    report = (cloud.bundle / "PHASE0_SMOKE.md").read_text(encoding="utf-8")
    assert "Parakeet: not run on target cloud (a CPU target; FR-0.7-07 runs Parakeet on the GPU target only)" in report
    assert not (cloud.bundle / "runs" / "parakeet-offline").exists()


def _store_from_bundle(bundle, root):
    for task_dir in sorted((bundle / "runs").iterdir()):
        rstore.add_batch(root, ingest.from_run_folder(task_dir))
    for score_dir in sorted((bundle / "scores").iterdir()):
        rstore.add_batch(root, ingest.from_score_folder(score_dir))


def _row_ids(bundle):
    """{result_row_id: (kind, source row)} computed from the bundle's files with the documented identities."""
    ids = {}
    for task_dir in (bundle / "runs").iterdir():
        for row in bundle_rows(bundle, task_dir.name):
            identity = {"kind": "run-result", **{k: row[k] for k in ("run_card_id", "clip_id", "task", "task_version")}}
            ids[result_row_id(identity)] = ("run-result", row)
    import pyarrow.parquet as pq
    for score_dir in (bundle / "scores").iterdir():
        for row in pq.read_table(score_dir / "scores.parquet").to_pylist():
            identity = {"kind": "score", **{k: row[k] for k in ("run_card_id", "clip_id", "variant", "normaliser_name",
                                                                  "normaliser_version", "ref_sha256")}}
            ids[result_row_id(identity)] = ("score", row)
    return ids


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_trace_works_on_every_row(cloud, tmp_path):
    root = tmp_path / "store"
    _store_from_bundle(cloud.bundle, root)
    ids = _row_ids(cloud.bundle)
    assert len(ids) == 60 + 60 + 5 + 2 * 50
    for row_id in ids:
        t = trace_row(root, row_id)
        assert t.row["result_row_id"] == row_id and t.card["run_card_id"] == t.row["run_card_id"]
    some = next(i for i, (kind, _) in ids.items() if kind == "score")
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "trace", some, "--store", str(root)], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0 and f"result_row_id: {some}" in proc.stdout


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_every_report_number_traces_to_a_row(cloud):
    report = (cloud.bundle / "PHASE0_SMOKE.md").read_text(encoding="utf-8")
    ids = _row_ids(cloud.bundle)
    checked = 0
    header = None
    for line in report.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set(line) <= set("|- "):
            continue
        record = dict(zip(header, cells))
        row_ids = [v for v in record.values() if HEX64.fullmatch(v.strip("`"))]
        rid = record.get("row", "").strip("`")
        if not rid:
            continue
        assert rid in ids, rid
        kind, row = ids[rid]
        for column, value in record.items():
            key = smoke.REPORT_FIELDS.get(column)
            if key is None:
                continue
            want = row[key]
            shown = value.strip("`")
            assert shown == smoke.format_value(want), (column, shown, want, rid)
            checked += 1
        assert row_ids
    assert checked >= 60 + 60 + 5 + 40
    meta = json.loads((cloud.bundle / "BUNDLE.json").read_text(encoding="utf-8"))
    for table, info in meta["scores"].items():
        summary = json.loads((cloud.bundle / "scores" / table / "summary.json").read_text(encoding="utf-8"))
        assert hashlib.sha256((cloud.bundle / "scores" / table / "summary.json").read_bytes()).hexdigest() == \
            info["summary_sha256"]
        for variant, s in summary["variants"].items():
            line = (f"| {table} | {variant} | {smoke.format_value(s['corpus_wer'])} | {s['errors']} | "
                    f"{s['ref_words']} | {smoke.format_value(s['corpus_cer'])} | `{info['summary_sha256']}` |")
            assert line in report, line


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_bundle_files_match_bundle_json(cloud):
    meta = json.loads((cloud.bundle / "BUNDLE.json").read_text(encoding="utf-8"))
    files = {p.relative_to(cloud.bundle).as_posix(): p for p in cloud.bundle.rglob("*") if p.is_file()}
    assert set(files) - {"BUNDLE.json"} == set(meta["files"])
    for rel, info in meta["files"].items():
        data = files[rel].read_bytes()
        assert info == {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    with tarfile.open(cloud.tar) as tar:
        names = sorted(m.name for m in tar.getmembers() if m.isfile())
        assert names == sorted(f"{cloud.bundle.name}/{rel}" for rel in files)
        for m in tar.getmembers():
            if m.isfile():
                assert tar.extractfile(m).read() == files[m.name.split("/", 1)[1]].read_bytes()
    assert meta["target"] == "cloud" and meta["platform"] == "cloud-vm" and cloud.tar.name == cloud.bundle.name + ".tar"


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_7_07_second_run_resumes_and_stores_nothing_new(cloud, tmp_path):
    base = cloud.bundle.parent.parent
    before = {p: p.read_bytes() for p in (base / "store").rglob("*") if p.is_file()}
    again = smoke.run_smoke("cloud", out=base / "out", store=base / "store", model_cache=base / "models",
                            work_dir=base / "work", bundle_dir=base / "bundles-2", echo=None)
    # the smoke's own store: the second run's rows are all already there, so nothing in it changes
    assert {p: p.read_bytes() for p in (base / "store").rglob("*") if p.is_file()} == before and before
    for task in ("vosk-batch", "harness-vad", "vosk-realspeed"):
        assert (again.bundle / "runs" / task / "results.jsonl").read_bytes() == \
            (cloud.bundle / "runs" / task / "results.jsonl").read_bytes()
        log = (again.bundle / "runs" / task / "runner.log").read_text(encoding="utf-8")
        second = log[log.index(" session 2 start"):]
        assert "skipped: finished" in second and " started (" not in second
    root = tmp_path / "store"
    _store_from_bundle(cloud.bundle, root)
    for task_dir in sorted((again.bundle / "runs").iterdir()):
        result = rstore.add_batch(root, ingest.from_run_folder(task_dir))
        assert result.stored == 0 and result.already > 0


def test_FR_0_7_07_committed_bundles_and_their_reports_in_docs():
    # Each committed bundle (question 11) is intact, made from a clean tree of this branch's history, and its report
    # is byte-copied into docs/runs/PHASE0_SMOKE.md.
    from aqis_lab import parity
    tars = sorted((ROOT / "data" / "runs" / "phase0-smoke").glob("phase0-smoke-*.tar"))
    assert [t for t in tars if t.name.startswith("phase0-smoke-cloud-")], "the cloud bundle is committed"
    doc = (ROOT / "docs" / "runs" / "PHASE0_SMOKE.md").read_text(encoding="utf-8")
    for tar in tars:
        bundle = parity.load_bundle(tar)             # every file against BUNDLE.json (SHA-256 and size)
        name = tar.name[:-len(".tar")]
        assert bundle.name == bundle.meta["name"] == name
        assert bundle.meta["target"] in name and bundle.meta["git"]["dirty"] is False
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", bundle.meta["git"]["commit"], "HEAD"],
                                  cwd=ROOT, capture_output=True, text=True)
        assert ancestor.returncode == 0, (name, ancestor.stderr)
        m = re.search(rf"<!-- report {re.escape(name)} begin -->\n(.*?)<!-- report {re.escape(name)} end -->\n", doc,
                      re.S)
        assert m and m.group(1).encode("utf-8") == bundle.files["PHASE0_SMOKE.md"], name


def test_FR_0_7_07_cli_parses_every_option():
    from aqis_lab.commands.phase0 import build_parser
    ns = build_parser().parse_args(["smoke", "--target", "oracle", "--out", "o", "--store", "s", "--model-cache", "m",
                                    "--work-dir", "w", "--bundle-dir", "b", "--drive-mount", "d"])
    assert (ns.target, ns.out, ns.store, ns.model_cache, ns.work_dir, ns.bundle_dir, ns.drive_mount) == \
        ("oracle", "o", "s", "m", "w", "b", "d")
    with pytest.raises(SystemExit):
        build_parser().parse_args(["smoke", "--target", "kaggle"])
