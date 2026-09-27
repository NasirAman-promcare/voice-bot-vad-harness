"""FR-0.3-06: score rows in Parquet and CSV, traceable, with the schema documented in SCORE_TABLE.md."""
import csv
import hashlib
import json
import re
import subprocess
import sys

import pyarrow.parquet as pq
import pytest

from aqis_scoring_testutil import (HYP_FIXTURE, KEEP_NAME, MAIN_NAME, NORMALISER_VERSION, REF_FIXTURE,
                                   RUN_CARD_FIXTURE, SCORE_TABLE_DOC, code_span, markdown_tables, run_score,
                                   write_csv)
from aqis_testutil import ROOT

from aqis_lab.scoring import table as T
from aqis_lab.scoring import wer as W

VARIANT_NAMES = {"main": MAIN_NAME, "disfluency_aware": KEEP_NAME}
DOC_TYPES = {"string": "string", "int64": "int64", "float64": "double"}


def read_fixture(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def scored(tmp_path_factory):
    out = tmp_path_factory.mktemp("score") / "out"
    proc = run_score("--ref", REF_FIXTURE, "--hyp", HYP_FIXTURE, "--out", out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return out, proc


def parquet_rows(out):
    return pq.read_table(out / "scores.parquet").to_pylist()


def documented_columns():
    tables = [t for t in markdown_tables(SCORE_TABLE_DOC.read_text(encoding="utf-8")) if t[0] == "Columns"]
    assert len(tables) == 1, "SCORE_TABLE.md needs exactly one table under the heading 'Columns'"
    _, header, rows, _ = tables[0]
    assert header == ["Column", "Parquet type", "Null", "CSV form", "Meaning"], header
    return [(code_span(r[0]), code_span(r[1]), r[2]) for r in rows]


def test_FR_0_3_06_every_row_carries_trace_fields(scored):
    out, _ = scored
    rows = parquet_rows(out)
    clips = {r["clip_id"] for r in read_fixture(REF_FIXTURE)}
    run_card_id = json.loads(RUN_CARD_FIXTURE.read_text(encoding="utf-8"))["run_card_id"]
    assert len(rows) == 2 * len(clips) == 24
    assert {(r["clip_id"], r["variant"]) for r in rows} == {(c, v) for c in clips for v in VARIANT_NAMES}
    for row in rows:
        assert row["schema_version"] == "1.0"
        assert row["run_card_id"] == run_card_id
        assert row["normaliser_name"] == VARIANT_NAMES[row["variant"]]
        assert row["normaliser_version"] == NORMALISER_VERSION
        for field in ("ref_sha256", "hyp_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", row[field]), (field, row)
        for field in ("ref_words", "hyp_words", "hits", "substitutions", "deletions", "insertions", "errors",
                      "ref_chars", "hyp_chars", "char_hits", "char_substitutions", "char_deletions",
                      "char_insertions", "char_errors"):
            assert isinstance(row[field], int) and row[field] >= 0, (field, row)
        assert row["errors"] == row["substitutions"] + row["deletions"] + row["insertions"]
        assert row["ref_words"] == row["hits"] + row["substitutions"] + row["deletions"]
        assert row["wer"] == (None if row["ref_words"] == 0 else row["errors"] / row["ref_words"])
        assert row["cer"] == (None if row["ref_chars"] == 0 else row["char_errors"] / row["ref_chars"])


def test_FR_0_3_06_hashes_are_sha256_of_raw_text(scored):
    out, _ = scored
    refs = {r["clip_id"]: r["text"] for r in read_fixture(REF_FIXTURE)}
    hyps = {r["clip_id"]: r["text"] for r in read_fixture(HYP_FIXTURE)}
    for row in parquet_rows(out):
        assert row["ref_sha256"] == hashlib.sha256(refs[row["clip_id"]].encode("utf-8")).hexdigest()
        assert row["hyp_sha256"] == hashlib.sha256(hyps[row["clip_id"]].encode("utf-8")).hexdigest()
    # The raw text, not the normalised one: "I don’t know." and "I don't know" normalise alike but hash apart.
    by_clip = {r["clip_id"]: r for r in parquet_rows(out) if r["variant"] == "main"}
    assert by_clip["c10-apostrophe"]["errors"] == 0
    assert by_clip["c10-apostrophe"]["ref_sha256"] != by_clip["c10-apostrophe"]["hyp_sha256"]


def test_FR_0_3_06_parquet_schema_matches_score_table_doc(scored):
    out, _ = scored
    schema = pq.read_schema(out / "scores.parquet")
    documented = documented_columns()
    assert [f.name for f in schema] == [name for name, _, _ in documented]
    for field, (name, doc_type, null) in zip(schema, documented):
        assert str(field.type) == DOC_TYPES[doc_type], (name, field.type, doc_type)
        assert field.nullable == (null == "yes"), (name, field.nullable, null)
        assert null in ("yes", "no")
    assert schema.metadata[b"aqis_score_table_schema_version"] == b"1.0"
    assert [f.name for f in T.arrow_schema()] == [name for name, _, _ in documented]


def test_FR_0_3_06_csv_header_matches_score_table_doc(scored):
    out, _ = scored
    with open(out / "scores.csv", encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == [name for name, _, _ in documented_columns()]


def test_FR_0_3_06_csv_and_parquet_hold_the_same_rows(scored):
    out, _ = scored
    types = {name: doc_type for name, doc_type, _ in documented_columns()}
    raw = (out / "scores.csv").read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    with open(out / "scores.csv", encoding="utf-8", newline="") as fh:
        csv_rows = list(csv.DictReader(fh))
    converted = []
    for row in csv_rows:
        item = {}
        for name, value in row.items():
            if types[name] == "int64":
                item[name] = int(value)
            elif types[name] == "float64":
                item[name] = None if value == "" else float(value)
                if value:
                    assert value == repr(item[name])  # shortest round-trip form
            else:
                item[name] = value
        converted.append(item)
    assert converted == parquet_rows(out)


def test_FR_0_3_06_rows_sorted_by_clip_and_variant(scored):
    out, _ = scored
    keys = [(r["clip_id"], r["variant"]) for r in parquet_rows(out)]
    assert keys == sorted(keys)


def test_FR_0_3_06_rejects_invalid_run_card_id_and_clip_id(tmp_path):
    good_run = "a" * 64
    for bad_run in ("A" * 64, "a" * 63, "a" * 64 + "\n", "g" * 64, ""):
        scores = W.score_corpus([("c-1", "a", "a")], bad_run)
        with pytest.raises(ValueError, match="run_card_id"):
            T.rows_from_scores(scores)
    for bad_clip in ("C-1", "c_1", "c 1", "", "c-1\n", "clip١"):
        scores = W.score_corpus([(bad_clip, "a", "a")], good_run)
        with pytest.raises(ValueError, match="clip_id"):
            T.rows_from_scores(scores)
    ref = write_csv(tmp_path / "ref.csv", ["clip_id", "text"], [["Bad_Clip", "a"]])
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [[good_run, "Bad_Clip", "a"]])
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", tmp_path / "out")
    assert proc.returncode == 2 and "ERROR:" in proc.stderr and "clip_id" in proc.stderr and "line 2" in proc.stderr
    hyp = write_csv(tmp_path / "hyp2.csv", ["run_card_id", "clip_id", "text"], [["XYZ", "c-1", "a"]])
    ref = write_csv(tmp_path / "ref2.csv", ["clip_id", "text"], [["c-1", "a"]])
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", tmp_path / "out")
    assert proc.returncode == 2 and "run_card_id" in proc.stderr and "line 2" in proc.stderr
    assert not (tmp_path / "out").exists()


RUN = "e" * 64
INPUT_ERRORS = {
    "missing-ref-file": (None, [[RUN, "c-1", "a"]], "cannot read"),
    "wrong-ref-header": ([["id", "text"], ["c-1", "a"]], [[RUN, "c-1", "a"]], "header"),
    "wrong-hyp-header": ([["clip_id", "text"], ["c-1", "a"]], [["clip_id", "run_card_id", "text"], ["c-1", RUN, "a"]],
                         "header"),
    "wrong-field-count": ([["clip_id", "text"], ["c-1", "a", "extra"]], [[RUN, "c-1", "a"]], "fields"),
    "blank-line": ([["clip_id", "text"], ["c-1", "a"], []], [[RUN, "c-1", "a"]], "fields"),
    "duplicate-ref-clip": ([["clip_id", "text"], ["c-1", "a"], ["c-1", "b"]], [[RUN, "c-1", "a"]], "more than once"),
    "duplicate-hyp-clip": ([["clip_id", "text"], ["c-1", "a"]], [[RUN, "c-1", "a"], [RUN, "c-1", "b"]],
                           "more than once"),
    "clip-sets-differ": ([["clip_id", "text"], ["c-1", "a"], ["c-2", "b"]], [[RUN, "c-1", "a"], [RUN, "c-3", "c"]],
                         "c-2"),
    "several-run-cards": ([["clip_id", "text"], ["c-1", "a"], ["c-2", "b"]], [[RUN, "c-1", "a"], ["f" * 64, "c-2", "b"]],
                          "more than one run_card_id"),
    "no-clips": ([["clip_id", "text"]], [], "no clips"),
}


@pytest.mark.parametrize("case", sorted(INPUT_ERRORS))
def test_FR_0_3_06_input_errors_exit_2(tmp_path, case):
    ref_rows, hyp_rows, message = INPUT_ERRORS[case]
    ref = tmp_path / "ref.csv"
    if ref_rows is not None:
        write_csv(ref, ref_rows[0], ref_rows[1:])
    if hyp_rows and hyp_rows[0][0] == "clip_id":
        hyp = write_csv(tmp_path / "hyp.csv", hyp_rows[0], hyp_rows[1:])
    else:
        hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], hyp_rows)
    out = tmp_path / "out"
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", out)
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert proc.stderr.startswith("ERROR:") and message in proc.stderr, proc.stderr
    assert not out.exists()
    if case == "clip-sets-differ":
        assert "c-2" in proc.stderr and "c-3" in proc.stderr


def test_FR_0_3_06_non_utf8_input_exit_2(tmp_path):
    ref = tmp_path / "ref.csv"
    ref.write_bytes(b"clip_id,text\nc-1,caf\xe9\n")
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [[RUN, "c-1", "cafe"]])
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", tmp_path / "out")
    assert proc.returncode == 2 and "UTF-8" in proc.stderr and str(ref) in proc.stderr


def test_FR_0_3_06_accepts_bom_and_multiline_text(tmp_path):
    ref = tmp_path / "ref.csv"
    ref.write_bytes("﻿clip_id,text\nc-1,\"Hello,\nworld\"\n".encode("utf-8"))
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [[RUN, "c-1", "hello world"]])
    out = tmp_path / "out"
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", out)
    assert proc.returncode == 0, proc.stderr
    rows = parquet_rows(out)
    assert {r["errors"] for r in rows} == {0}
    assert rows[0]["ref_sha256"] == hashlib.sha256("Hello,\nworld".encode("utf-8")).hexdigest()


def test_FR_0_3_06_refuses_to_overwrite_output(tmp_path):
    out = tmp_path / "out"
    first = run_score("--ref", REF_FIXTURE, "--hyp", HYP_FIXTURE, "--out", out)
    assert first.returncode == 0, first.stderr
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.iterdir()}
    assert set(before) == {"scores.parquet", "scores.csv", "summary.json"}
    second = run_score("--ref", REF_FIXTURE, "--hyp", HYP_FIXTURE, "--out", out)
    assert second.returncode == 2 and "already exists" in second.stderr
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.iterdir()} == before
    # Any one existing output file is enough to refuse, and nothing else is written.
    lone = tmp_path / "lone"
    lone.mkdir()
    (lone / "scores.csv").write_text("keep me\n", encoding="utf-8")
    third = run_score("--ref", REF_FIXTURE, "--hyp", HYP_FIXTURE, "--out", lone)
    assert third.returncode == 2 and sorted(p.name for p in lone.iterdir()) == ["scores.csv"]
    assert (lone / "scores.csv").read_text(encoding="utf-8") == "keep me\n"


def test_FR_0_3_06_summary_matches_rows(scored):
    out, _ = scored
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    rows = parquet_rows(out)
    assert summary["schema_version"] == "1.0"
    assert summary["run_card_id"] == rows[0]["run_card_id"]
    assert summary["files"] == {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                                for name in ("scores.parquet", "scores.csv")}
    assert list(summary["variants"]) == ["disfluency_aware", "main"]  # canonical JSON sorts keys
    for variant, block in summary["variants"].items():
        mine = [r for r in rows if r["variant"] == variant]
        assert block["normaliser_name"] == VARIANT_NAMES[variant]
        assert block["utterances"] == len(mine)
        for field in ("hits", "substitutions", "deletions", "insertions", "errors", "ref_words", "hyp_words",
                      "char_hits", "char_substitutions", "char_deletions", "char_insertions", "char_errors",
                      "ref_chars", "hyp_chars"):
            assert block[field] == sum(r[field] for r in mine), (variant, field)
        assert block["corpus_wer"] == block["errors"] / block["ref_words"]
        assert block["corpus_cer"] == block["char_errors"] / block["ref_chars"]
        defined = [r["wer"] for r in mine if r["wer"] is not None]
        assert block["utterances_with_wer"] == len(defined)
        assert block["mean_utterance_wer"] == pytest.approx(sum(defined) / len(defined), rel=1e-15)
    # summary.json is canonical JSON (sorted keys, no spaces).
    raw = (out / "summary.json").read_bytes()
    assert raw == json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def test_FR_0_3_06_score_listed_by_dispatcher():
    from aqis_lab.__main__ import COMMANDS
    assert COMMANDS["score"][0] == "aqis_lab.commands.score"
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "--help"], cwd=ROOT, capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0 and re.search(r"^\s+score\s+\S", proc.stdout, re.M), proc.stdout
    usage = run_score("--help")
    assert usage.returncode == 0 and "--ref" in usage.stdout and "--hyp" in usage.stdout and "--out" in usage.stdout


# WP-0.3-F01: each direction of a clip-set mismatch on its own. A clip with no hypothesis must never be scored
# as an empty text, and a hypothesis for a clip that is not in the reference file must never be dropped.
ONE_SIDED = {
    "clip-only-in-ref": ([["c-1", "a b c"], ["c-2", "d e f"]], [[RUN, "c-1", "a b c"]], "ref", "c-2"),
    "clip-only-in-hyp": ([["c-1", "a b c"]], [[RUN, "c-1", "a b c"], [RUN, "c-3", "x"]], "hyp", "c-3"),
    "ref-empty-hyp-has-clip": ([], [[RUN, "c-1", "a b c"]], "hyp", "c-1"),
}


@pytest.mark.parametrize("case", sorted(ONE_SIDED))
def test_FR_0_3_06_one_sided_clip_is_an_input_error(tmp_path, case):
    ref_rows, hyp_rows, side, clip = ONE_SIDED[case]
    ref = write_csv(tmp_path / "ref.csv", ["clip_id", "text"], ref_rows)
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], hyp_rows)
    out = tmp_path / "out"
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", out)
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert proc.stderr.startswith("ERROR:") and proc.stdout == ""
    # The one-sided clip is named after the file it appears in, and the other file lists none.
    only_in = {"ref": ref, "hyp": hyp}
    assert f"only in {only_in[side]}: {clip}" in proc.stderr, proc.stderr
    assert f"only in {only_in['hyp' if side == 'ref' else 'ref']}: none" in proc.stderr, proc.stderr
    assert not out.exists()


# Same gap in the same functions (surgical-fix step 6): input and output errors that had no test of their own.
def _hyp_bad_clip(tmp_path):
    ref = write_csv(tmp_path / "ref.csv", ["clip_id", "text"], [["c-1", "a"]])
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [[RUN, "C_1", "a"]])
    return ref, hyp, hyp, "line 2: invalid clip_id 'C_1'"


def _hyp_missing(tmp_path):
    ref = write_csv(tmp_path / "ref.csv", ["clip_id", "text"], [["c-1", "a"]])
    return ref, tmp_path / "missing.csv", tmp_path / "missing.csv", "cannot read"


def _ref_unterminated_quote(tmp_path):
    ref = tmp_path / "ref.csv"
    ref.write_text('clip_id,text\nc-1,"unterminated\n', encoding="utf-8")
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [[RUN, "c-1", "a"]])
    return ref, hyp, ref, "line 2: unexpected end of data"


def _ref_empty_file(tmp_path):
    ref = tmp_path / "ref.csv"
    ref.write_bytes(b"")
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [[RUN, "c-1", "a"]])
    return ref, hyp, ref, "line 1: the header must be exactly clip_id,text, got 'nothing'"


MORE_INPUT_ERRORS = {"hyp-bad-clip-id": _hyp_bad_clip, "hyp-missing-file": _hyp_missing,
                     "ref-unterminated-quote": _ref_unterminated_quote, "ref-empty-file": _ref_empty_file}


@pytest.mark.parametrize("case", sorted(MORE_INPUT_ERRORS) + ["out-is-a-file"])
def test_FR_0_3_06_more_input_and_output_errors_exit_2(tmp_path, case):
    if case == "out-is-a-file":
        ref, hyp = REF_FIXTURE, HYP_FIXTURE
        out = tmp_path / "afile"
        out.write_text("keep me\n", encoding="utf-8")
        named, message = out, "exists and is not a folder"
    else:
        ref, hyp, named, message = MORE_INPUT_ERRORS[case](tmp_path)
        out = tmp_path / "out"
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", out)
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert proc.stderr.startswith("ERROR:") and proc.stdout == ""
    assert str(named) in proc.stderr and message in proc.stderr, proc.stderr
    if case == "out-is-a-file":
        assert out.read_text(encoding="utf-8") == "keep me\n"
    else:
        assert not out.exists()
