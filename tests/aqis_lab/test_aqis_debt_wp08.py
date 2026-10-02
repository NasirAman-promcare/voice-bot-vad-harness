"""Accepted debts closed in WP-0.8 (docs/progress/DEBT.md; docs/approvals/WP-0.8.md, question 2).

- DEBT-010 (WP-0.4-F03): a registry row's licence must equal the licence datasets.yaml gives its dataset and split.
"""
import csv
import io

import pytest

from aqis_packs_testutil import ROOT, download_entry, write_datasets
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
