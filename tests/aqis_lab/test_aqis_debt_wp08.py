"""Accepted debts closed in WP-0.8 (docs/progress/DEBT.md; docs/approvals/WP-0.8.md, question 2).

- DEBT-010 (WP-0.4-F03): a registry row's licence must equal the licence datasets.yaml gives its dataset and split.
- DEBT-018 (WP-0.7-F05): `phase0 smoke --bundle-dir` on Google Drive outside MyDrive/AQIS_LAB is refused (NFR-0.5-02).
- DEBT-020 (WP-0.7-F07): the smoke re-validates each event log before storing it, and the report's summary lines
  equal values recomputed here from the bundle's result rows.
"""
import csv
import io
import json
import shutil
import statistics
import tarfile

import pytest
import yaml

from aqis_adapters_testutil import drive_view
from aqis_packs_testutil import ROOT, download_entry, write_datasets
from aqis_runner_testutil import SMOKE_PACK, tree_snapshot
from aqis_lab import smoke
from aqis_lab.registry import datasets as ds
from aqis_lab.registry import registry as reg


# --- DEBT-010: registry licence against the dataset's licence -------------------------------------------------------

def _datasets(tmp_path):
    entries = {
        "librispeech-test-clean": download_entry("http://127.0.0.1/x.tar.gz", b"x", "librispeech", "librispeech",
                                                 "speech", ["LibriSpeech/test-clean/**"], "CC-BY-4.0",
                                                 split="test-clean"),
        # The dataset licence differs from both subset licences, so a check against the dataset licence alone
        # would reject the valid music and noise rows below.
        "musan": download_entry("http://127.0.0.1/m.tar.gz", b"m", "musan", "musan", "non-speech",
                                ["musan/noise/free-sound/**", "musan/music/rfm/**"], "CC-BY-4.0",
                                subsets={"noise/free-sound": {"split": "noise", "licence": "LicenseRef-public-domain",
                                                              "licence_file_sha256": "0" * 64,
                                                              "annotations": "noise-background-list"},
                                         "music/rfm": {"split": "music", "licence": "CC-BY-3.0",
                                                       "licence_file_sha256": "1" * 64,
                                                       "annotations": "music-table", "titles": "rfm-licence",
                                                       "attribution_template": "{title} {artist}"}}),
    }
    return ds.load_datasets(write_datasets(tmp_path / "datasets.yaml", entries))


def _speech_row(**changes):
    row = {"clip_id": "ls-test-clean-100-7-0000", "source": "librispeech",
           "source_ref": "LibriSpeech/test-clean/100/7/100-7-0000.flac", "licence": "CC-BY-4.0",
           "speaker_id": "100", "consent_ref": "", "transcript": "HELLO THERE", "split": "test-clean",
           "dataset": "librispeech-test-clean", "tags": "", "sha256": "a" * 64, "sample_rate_hz": "16000",
           "channels": "1", "n_samples": "16000", "attribution": ""}
    row.update(changes)
    return row


def _musan_row(name, split, licence):
    folder = "noise/free-sound" if split == "noise" else "music/rfm"
    return {"clip_id": f"musan-{name}", "source": "musan", "source_ref": f"musan/{folder}/{name}.wav",
            "licence": licence, "speaker_id": "", "consent_ref": "", "transcript": "", "split": split,
            "dataset": "musan", "tags": "", "sha256": "b" * 64, "sample_rate_hz": "16000", "channels": "1",
            "n_samples": "16000", "attribution": ""}


def _csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(reg.COLUMNS)
    for row in rows:
        writer.writerow([row[c] for c in reg.COLUMNS])
    return buf.getvalue().encode("utf-8")


def _licence_problems(tmp_path, rows):
    return [p for p in reg.check_registry_bytes(_csv(rows), _datasets(tmp_path), tmp_path) if p.column == "licence"]


@pytest.mark.parametrize("bad, expected", [
    (_speech_row(licence="CC0-1.0"), "CC-BY-4.0"),                       # relabelled LibriSpeech row (DEBT-010)
    (_musan_row("noise-free-sound-0001", "noise", "CC-BY-3.0"), "LicenseRef-public-domain"),  # music's licence
    (_musan_row("music-rfm-0001", "music", "CC-BY-4.0"), "CC-BY-3.0"),   # the dataset licence, not the subset's
])
def test_FR_0_4_01_rejects_licence_that_differs_from_its_dataset(tmp_path, bad, expected):
    good = [_speech_row(clip_id="ls-test-clean-100-7-0001"),
            _musan_row("noise-free-sound-0002", "noise", "LicenseRef-public-domain"),
            _musan_row("music-rfm-0002", "music", "CC-BY-3.0")]
    assert _licence_problems(tmp_path, good) == []
    problems = _licence_problems(tmp_path, good + [bad])
    assert len(problems) == 1, problems
    problem = problems[0]
    assert problem.line == 5                                              # header, three good rows, then the bad one
    assert repr(bad["licence"]) in problem.message and repr(expected) in problem.message
    assert repr(bad["dataset"]) in problem.message and repr(bad["split"]) in problem.message


def test_FR_0_4_01_committed_registry_licences_equal_dataset_licences():
    # The committed registry passes the full validation, including the licence-per-dataset rule.
    datasets = ds.load_datasets(ROOT / "data" / "registry" / "datasets.yaml")
    data = (ROOT / "data" / "registry" / "sources.csv").read_bytes()
    assert reg.check_registry_bytes(data, datasets, ROOT) == []
    # Independently of the code: every row's licence is its dataset's licence, or its MUSAN subset's licence.
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    for row in rows:
        entry = datasets.datasets[row["dataset"]].fields
        subsets = [s for s in entry.get("subsets", {}).values() if s["split"] == row["split"]]
        assert row["licence"] == (subsets[0]["licence"] if subsets else entry["licence"]), row["clip_id"]


# --- DEBT-018: the smoke's bundle folder goes through the Drive write guard -----------------------------------------

def test_NFR_0_5_02_smoke_refuses_bundle_dir_on_drive_outside_aqis_lab(tmp_path):
    # A Colab runtime with a Drive mount: --bundle-dir on Drive but outside MyDrive/AQIS_LAB is refused with exit 2
    # before any task runs (the GPU preflight would otherwise stop first) and before anything is written.
    system, mount = drive_view(tmp_path)
    out = mount / "MyDrive" / "AQIS_LAB" / "results" / "phase0-smoke-colab"
    bundles = mount / "MyDrive" / "elsewhere" / "bundles"
    work = tmp_path / "work"
    before = tree_snapshot(mount)
    with pytest.raises(smoke.SmokeInputError) as info:
        smoke.run_smoke("colab", out=out, work_dir=work, bundle_dir=bundles, drive_mount=mount, system=system,
                        echo=None)
    message = str(info.value)
    assert info.value.exit_code == 2
    assert "refusing to write" in message and str(bundles) in message and "AQIS_LAB" in message, message
    assert tree_snapshot(mount) == before and not work.exists()


def test_NFR_0_5_02_smoke_accepts_bundle_dir_inside_aqis_lab(tmp_path):
    # The guard does not refuse a bundle folder inside MyDrive/AQIS_LAB: the smoke passes it and stops later, at the
    # GPU preflight's own message (this runtime has no GPU), still before anything is written.
    system, mount = drive_view(tmp_path)
    out = mount / "MyDrive" / "AQIS_LAB" / "results" / "phase0-smoke-colab"
    bundles = mount / "MyDrive" / "AQIS_LAB" / "bundles"
    before = tree_snapshot(mount)
    with pytest.raises(smoke.SmokeInputError, match="no GPU") as info:
        smoke.run_smoke("colab", out=out, work_dir=tmp_path / "work", bundle_dir=bundles, drive_mount=mount,
                        system=system, echo=None)
    assert info.value.exit_code == 2 and "refusing to write" not in str(info.value)
    assert tree_snapshot(mount) == before


# --- DEBT-020: the smoke's own event-log re-validation, and the report's summary lines --------------------------------

@pytest.fixture(scope="module")
def harness_vad_run(tmp_path_factory):
    """The folder and run card ID of one real, finished harness-vad run on the smoke pack."""
    from aqis_lab.runner.run import RunOptions, run
    root = tmp_path_factory.mktemp("harness-vad")
    outcome = run(RunOptions(task="harness-vad", pack=SMOKE_PACK, out=root / "out", seed=0, work_dir=root / "work"),
                  echo=None)
    assert outcome.status == "complete"
    return root / "out", outcome.run_card_id


@pytest.mark.parametrize("where", ["first", "middle", "last"])
def test_FR_0_7_07_smoke_revalidates_each_event_log_before_storing(tmp_path, harness_vad_run, where):
    # The bundle copy of a run's events.jsonl is checked again before the run is stored: one record made invalid
    # (its run_id removed) anywhere in the file stops the smoke (SmokeFailure, exit 1) at that line, and nothing is
    # stored.
    out, card = harness_vad_run
    folder = tmp_path / "bundle" / "runs" / "harness-vad"
    folder.mkdir(parents=True)
    for name in smoke.RUN_FILES:
        shutil.copyfile(out / name, folder / name)
    lines = (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()
    index = {"first": 0, "middle": len(lines) // 2, "last": len(lines) - 1}[where]
    record = json.loads(lines[index])
    del record["run_id"]
    lines[index] = json.dumps(record)
    (folder / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    store = tmp_path / "store"
    with pytest.raises(smoke.SmokeFailure) as info:
        smoke._check_and_store(tmp_path / "bundle", store, {"harness-vad": card}, [])
    message = str(info.value)
    assert info.value.exit_code == 1
    assert f"events.jsonl line {index + 1} is not valid event log v1" in message and "run_id" in message, message
    assert not store.exists() or not any(p.is_file() for p in store.rglob("*"))


def _median_max(values):
    values = [v for v in values if v is not None]
    return f"median {statistics.median(values):.4f}, maximum {max(values):.4f}"


def _results(bundle, task):
    path = bundle / "runs" / task / "results.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("tar", sorted((ROOT / "data" / "runs" / "phase0-smoke").glob("phase0-smoke-*.tar")),
                         ids=lambda p: p.name.split("-")[2])
def test_FR_0_7_07_report_summary_lines_recomputed_from_bundle_rows(tmp_path, tar):
    with tarfile.open(tar) as archive:
        archive.extractall(tmp_path, filter="data")
    bundle = tmp_path / tar.name[:-len(".tar")]
    meta = json.loads((bundle / "BUNDLE.json").read_text(encoding="utf-8"))
    # BUNDLE.json is written with sorted keys; the smoke builds the report with the runs in the target's task order
    # and the score tables in scored-task, then score-subset order of the config. Put them back in that order.
    config = yaml.safe_load((ROOT / "config" / "aqis_lab" / "phase0_smoke.yaml").read_text(encoding="utf-8"))
    tasks = [r["task"] for r in config["runs"] if meta["target"] in r["targets"]]
    tables = [f"{t}-{s}" for t in config["scored_tasks"] if t in meta["runs"] for s in config["score_subsets"]]
    assert sorted(tasks) == sorted(meta["runs"]) and sorted(tables) == sorted(meta["scores"])
    meta["runs"] = {t: meta["runs"][t] for t in tasks}
    meta["scores"] = {t: meta["scores"][t] for t in tables}
    manifest = json.loads((SMOKE_PACK / "manifest.json").read_text(encoding="utf-8"))
    report = smoke._report(meta, bundle, manifest, smoke.load_config(smoke.DEFAULT_CONFIG))
    assert report.encode("utf-8") == (bundle / "PHASE0_SMOKE.md").read_bytes()
    # Summary lines from values computed here from the result rows (4 decimals, docs/runs/PHASE0_SMOKE.md).
    realspeed = _results(bundle, "vosk-realspeed")
    batch = {r["clip_id"]: r["text_sha256"] for r in _results(bundle, "vosk-batch")}
    same = sum(1 for r in realspeed if r["text_sha256"] == batch[r["clip_id"]])
    expected = [
        f"- First-partial latency: {_median_max([r['first_partial_latency_ms'] for r in realspeed])} ms.",
        f"- Finalisation latency: {_median_max([r['finalisation_latency_ms'] for r in realspeed])} ms.",
        f"- Real-speed transcript equal to the batch transcript: {same} of {len(realspeed)} clips.",
    ]
    if "parakeet-compute-delay" in meta["runs"]:
        delay = _results(bundle, "parakeet-compute-delay")
        gpus = {r["gpu"] for r in delay}
        assert len(gpus) == 1
        expected.append(f"- Processing time: {_median_max([r['processing_ms'] for r in delay])} ms per clip on "
                        f"{gpus.pop()}.")
    summary = [line for line in report.splitlines() if line.startswith(("- First-partial", "- Finalisation",
                                                                         "- Real-speed transcript", "- Processing"))]
    assert summary == expected
    # In every committed bundle all real-speed transcripts equal the batch ones, so the count is also checked on
    # this extracted copy with one real-speed transcript hash changed: the line must count only the equal ones.
    path = bundle / "runs" / "vosk-realspeed" / "results.jsonl"
    rows = _results(bundle, "vosk-realspeed")
    rows[0]["text_sha256"] = "0" * 64
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    same = sum(1 for r in rows if r["text_sha256"] == batch[r["clip_id"]])
    assert same == len(rows) - 1
    changed = smoke._report(meta, bundle, manifest, smoke.load_config(smoke.DEFAULT_CONFIG))
    assert f"- Real-speed transcript equal to the batch transcript: {same} of {len(rows)} clips." in changed
