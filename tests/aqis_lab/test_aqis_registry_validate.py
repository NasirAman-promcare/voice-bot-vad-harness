"""WP-0.4 FR-0.4-01: registry format and validation (aqis_lab/registry/registry.py, datasets.py)."""
import csv
import io
import re
import subprocess
import sys

import pytest

from aqis_packs_testutil import ROOT, download_entry, write_datasets
from aqis_lab.registry import datasets as ds
from aqis_lab.registry import registry as reg

# The spec's list for FR-0.4-01, written out here independently of the code.
SPEC_FIELDS = ["clip_id", "source", "source_ref", "licence", "speaker_id", "consent_ref", "transcript", "split"]


def _datasets(tmp_path):
    entries = {
        "librispeech-test-clean": download_entry("http://127.0.0.1/x.tar.gz", b"x", "librispeech", "librispeech",
                                                 "speech", ["LibriSpeech/test-clean/**"], "CC-BY-4.0",
                                                 split="test-clean"),
        "musan": download_entry("http://127.0.0.1/m.tar.gz", b"m", "musan", "musan", "non-speech",
                                ["musan/noise/free-sound/**"], "CC-BY-4.0",
                                subsets={"noise/free-sound": {"split": "noise", "licence": "LicenseRef-public-domain",
                                                              "licence_file_sha256": "0" * 64,
                                                              "annotations": "noise-background-list"}}),
        "owner-smoke": {"type": "local", "source": "owner", "kind": "speech", "importer": "owner",
                        "folder": "data/owner_smoke", "split": "owner", "licence": "LicenseRef-AQIS-owner-consent",
                        "consent_file": "data/owner_smoke/CONSENT.md", "speaker_id": "owner",
                        "clip_prefix": "owner-", "attribution": "owner", "homepage": None, "changes": "owner"},
    }
    path = write_datasets(tmp_path / "datasets.yaml", entries)
    return ds.load_datasets(path)


def _row(**changes):
    row = {"clip_id": "ls-test-clean-100-7-0000", "source": "librispeech",
           "source_ref": "LibriSpeech/test-clean/100/7/100-7-0000.flac", "licence": "CC-BY-4.0",
           "speaker_id": "100", "consent_ref": "", "transcript": "HELLO THERE", "split": "test-clean",
           "dataset": "librispeech-test-clean", "tags": "", "sha256": "a" * 64, "sample_rate_hz": "16000",
           "channels": "1", "n_samples": "16000", "attribution": ""}
    row.update(changes)
    return row


def _owner_row(**changes):
    row = _row(clip_id="owner-01", source="owner", source_ref="data/owner_smoke/01.wav",
               licence="LicenseRef-AQIS-owner-consent", speaker_id="owner",
               consent_ref="data/owner_smoke/CONSENT.md", transcript="owner sentence", split="owner",
               dataset="owner-smoke")
    row.update(changes)
    return row


def _csv(rows, header=None):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header or reg.COLUMNS)
    for row in rows:
        writer.writerow([row[c] for c in (header or reg.COLUMNS)])
    return buf.getvalue().encode("utf-8")


def _problems(tmp_path, rows, repo=None, header=None):
    data = _csv(rows, header)
    return reg.check_registry_bytes(data, _datasets(tmp_path), repo or tmp_path)


def _consent(tmp_path, text="The speaker agreed to lab use.\n"):
    path = tmp_path / "data" / "owner_smoke" / "CONSENT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_FR_0_4_01_registry_has_spec_columns():
    assert reg.COLUMNS[:8] == SPEC_FIELDS
    assert len(set(reg.COLUMNS)) == len(reg.COLUMNS)


def test_FR_0_4_01_valid_rows_pass(tmp_path):
    _consent(tmp_path)
    assert _problems(tmp_path, [_row(), _owner_row()]) == []


def test_FR_0_4_01_rejects_missing_licence(tmp_path):
    problems = _problems(tmp_path, [_row(licence="")])
    assert [(p.line, p.column) for p in problems] == [(2, "licence")]
    assert "missing licence" in problems[0].message


def test_FR_0_4_01_rejects_unknown_licence(tmp_path):
    problems = _problems(tmp_path, [_row(licence="CC-BY-9.9")])
    assert [(p.line, p.column) for p in problems] == [(2, "licence")]
    assert "not defined" in problems[0].message


def test_FR_0_4_01_rejects_owner_row_without_consent(tmp_path):
    _consent(tmp_path)
    problems = _problems(tmp_path, [_owner_row(consent_ref="")])
    assert [(p.line, p.column) for p in problems] == [(2, "consent_ref")]
    assert "missing consent reference" in problems[0].message
    # campaign recordings follow the same rule
    campaign = _owner_row(source="campaign", consent_ref="")
    assert any(p.column == "consent_ref" for p in _problems(tmp_path, [campaign]))


@pytest.mark.parametrize("ref", ["data/owner_smoke/NOPE.md", "/etc/passwd", "../outside.md", "data/owner_smoke",
                                 "data/owner_smoke/EMPTY.md"])
def test_FR_0_4_01_rejects_consent_ref_that_does_not_resolve(tmp_path, ref):
    _consent(tmp_path)
    (tmp_path / "data" / "owner_smoke" / "EMPTY.md").write_text("", encoding="utf-8")
    (tmp_path.parent / "outside.md").write_text("x", encoding="utf-8")
    problems = _problems(tmp_path, [_owner_row(consent_ref=ref)])
    assert [(p.line, p.column) for p in problems] == [(2, "consent_ref")], problems


def test_FR_0_4_01_rejects_consent_ref_on_other_sources(tmp_path):
    _consent(tmp_path)
    problems = _problems(tmp_path, [_row(consent_ref="data/owner_smoke/CONSENT.md")])
    assert [(p.line, p.column) for p in problems] == [(2, "consent_ref")]


@pytest.mark.parametrize("column,value", [("transcript", ""), ("transcript", "   "), ("speaker_id", "")])
def test_FR_0_4_01_rejects_speech_row_without_transcript_or_speaker(tmp_path, column, value):
    problems = _problems(tmp_path, [_row(**{column: value})])
    assert [(p.line, p.column) for p in problems] == [(2, column)]


def _noise_row(**changes):
    row = _row(clip_id="musan-noise-free-sound-0001", source="musan",
               source_ref="musan/noise/free-sound/noise-free-sound-0001.wav", licence="LicenseRef-public-domain",
               speaker_id="", transcript="", split="noise", dataset="musan", tags="background")
    row.update(changes)
    return row


@pytest.mark.parametrize("column,value", [("transcript", "HELLO"), ("speaker_id", "7")])
def test_FR_0_4_01_rejects_non_speech_row_with_transcript(tmp_path, column, value):
    assert _problems(tmp_path, [_noise_row()]) == []
    problems = _problems(tmp_path, [_noise_row(**{column: value})])
    assert [(p.line, p.column) for p in problems] == [(2, column)]


@pytest.mark.parametrize("bad", ["LS-1", "ls_1", "ls 1", "", "ls-1\n"])
def test_FR_0_4_01_rejects_invalid_or_duplicate_clip_id(tmp_path, bad):
    problems = _problems(tmp_path, [_row(clip_id=bad)])
    assert [(p.line, p.column) for p in problems] == [(2, "clip_id")]
    dup = _problems(tmp_path, [_row(), _row(source_ref="other.flac")])
    assert [(p.line, p.column) for p in dup] == [(3, "clip_id")]
    assert "repeats line 2" in dup[0].message


@pytest.mark.parametrize("column,value", [
    ("sha256", "A" * 64), ("sha256", "a" * 63), ("sample_rate_hz", "016000"), ("channels", "0"),
    ("n_samples", "1.5"), ("n_samples", ""), ("split", "Test Clean"), ("split", "noise"), ("dataset", "nope"),
    ("source", "musan"), ("tags", "b a"), ("tags", "a a"), ("tags", "Bad_tag"), ("source_ref", ""),
    ("attribution", "line\nbreak"),
])
def test_FR_0_4_01_rejects_malformed_file_facts(tmp_path, column, value):
    problems = _problems(tmp_path, [_row(**{column: value})])
    assert column in {p.column for p in problems}, (column, value, problems)


def test_FR_0_4_01_reports_every_problem_by_row_and_column(tmp_path):
    rows = [_row(licence=""), _row(clip_id="ls-2", transcript="", sha256="x"), _row(clip_id="ls-3")]
    problems = _problems(tmp_path, rows)
    assert {(p.line, p.column) for p in problems} == {(2, "licence"), (3, "transcript"), (3, "sha256")}
    text = str(reg.RegistryValidationError("reg.csv", problems))
    for p in problems:
        assert f"line {p.line} column {p.column}: " in text
    assert "reg.csv" in text and "3 problems" in text


def test_FR_0_4_01_rejects_wrong_header_and_field_count(tmp_path):
    header = list(reg.COLUMNS)
    header[0], header[1] = header[1], header[0]
    problems = _problems(tmp_path, [_row()], header=header)
    assert [(p.line, p.column) for p in problems] == [(1, "(header)")]
    data = _csv([_row()]) + b"one,two\n"
    problems = reg.check_registry_bytes(data, _datasets(tmp_path), tmp_path)
    assert [(p.line, p.column) for p in problems] == [(3, "(row)")]
    problems = reg.check_registry_bytes(b"\xff\xfe" + _csv([_row()]), _datasets(tmp_path), tmp_path)
    assert [p.column for p in problems] == ["(file)"]


def test_FR_0_4_01_rows_round_trip_and_sort(tmp_path):
    _consent(tmp_path)
    data = _csv([_owner_row(), _row()])
    rows = reg.load_registry_bytes(data, _datasets(tmp_path), tmp_path, "reg.csv")
    assert [r.clip_id for r in rows] == ["owner-01", "ls-test-clean-100-7-0000"]
    assert rows[1].speaker_id == "100" and rows[1].consent_ref is None and rows[1].n_samples == 16000
    out = reg.registry_bytes(rows)
    assert out.decode("utf-8").splitlines()[1].startswith("ls-test-clean-100-7-0000,")
    assert reg.load_registry_bytes(out, _datasets(tmp_path), tmp_path, "r") == sorted(rows, key=lambda r: r.clip_id)
    with pytest.raises(reg.RegistryValidationError):
        reg.load_registry_bytes(_csv([_row(licence="")]), _datasets(tmp_path), tmp_path, "reg.csv")


def test_FR_0_4_01_datasets_file_rejects_unknown_licence_and_keys(tmp_path):
    entries = {"x": {"type": "local", "source": "tts", "kind": "speech", "importer": "tts", "folder": "d",
                     "split": "tts", "licence": "NOPE", "generation_record": "d/G.md", "clip_prefix": "t-",
                     "speaker_prefix": "k-", "tags": ["synthetic"], "attribution": "a", "homepage": None, "changes": "c"}}
    with pytest.raises(ds.DatasetsError, match="NOPE"):
        ds.load_datasets(write_datasets(tmp_path / "a.yaml", entries))
    entries["x"]["licence"] = "Apache-2.0"
    entries["x"]["surprise"] = 1
    with pytest.raises(ds.DatasetsError, match="surprise"):
        ds.load_datasets(write_datasets(tmp_path / "b.yaml", entries))
    (tmp_path / "c.yaml").write_text("format_version: 1\nformat_version: 1\n", encoding="utf-8")
    with pytest.raises(ds.DatasetsError, match="duplicate key"):
        ds.load_datasets(tmp_path / "c.yaml")


def test_FR_0_4_01_cli_validate_exit_codes(tmp_path):
    _consent(tmp_path)
    good = tmp_path / "good.csv"
    good.write_bytes(_csv([_row(), _owner_row()]))
    bad = tmp_path / "bad.csv"
    bad.write_bytes(_csv([_row(licence=""), _owner_row(consent_ref="")]))
    _datasets(tmp_path)
    base = [sys.executable, "-m", "aqis_lab", "registry", "validate", "--datasets", str(tmp_path / "datasets.yaml"),
            "--repo-root", str(tmp_path)]
    ok = subprocess.run(base + [str(good)], capture_output=True, text=True, cwd=ROOT)
    assert ok.returncode == 0, ok.stderr
    assert "OK" in ok.stdout and "librispeech 1" in ok.stdout and "owner 1" in ok.stdout
    fail = subprocess.run(base + [str(bad)], capture_output=True, text=True, cwd=ROOT)
    assert fail.returncode == 1
    assert "line 2 column licence: missing licence" in fail.stdout
    assert "line 3 column consent_ref: missing consent reference" in fail.stdout
    missing = subprocess.run(base + [str(tmp_path / "none.csv")], capture_output=True, text=True, cwd=ROOT)
    assert missing.returncode == 2 and "ERROR" in missing.stderr


def test_FR_0_4_01_format_doc_lists_every_column():
    text = (ROOT / "docs" / "data" / "REGISTRY_FORMAT.md").read_text(encoding="utf-8")
    documented = re.findall(r"^\| `([a-z_0-9]+)` \|", text, flags=re.M)
    columns_section = documented[:len(reg.COLUMNS)]
    assert columns_section == reg.COLUMNS
    assert "synthetic" in text
