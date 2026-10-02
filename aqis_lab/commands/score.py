"""The `score` command: score hypotheses against references and write the score table.

CAPABILITIES:
  CAP-SCORE-005: `python -m aqis_lab score --ref REF.csv --hyp HYP.csv --out DIR` reads strict UTF-8 CSV inputs (references `clip_id,text`; hypotheses `run_card_id,clip_id,text`, one run card, the same clips), scores every clip under both normaliser variants, writes DIR/scores.parquet, DIR/scores.csv and DIR/summary.json without ever overwriting, and prints per variant the corpus WER and CER and the separately labelled mean per-utterance WER; exit 0 when written, 2 on any usage, input or output error; on Google Drive it writes only under MyDrive/AQIS_LAB (NFR-0.5-02): another Drive --out is `ERROR:` and exit 2 before anything is written [tests: test_FR_0_3_06_input_errors_exit_2, test_FR_0_3_06_non_utf8_input_exit_2, test_FR_0_3_06_accepts_bom_and_multiline_text, test_FR_0_3_06_refuses_to_overwrite_output, test_FR_0_3_06_summary_matches_rows, test_FR_0_3_06_score_listed_by_dispatcher, test_FR_0_3_06_cli_lists_written_files, test_FR_0_3_03_cli_prints_both_labelled_variants, test_FR_0_3_05_cli_prints_corpus_and_mean_labelled, test_FR_0_3_05_cli_prints_undefined_rates, test_NFR_0_3_01_repeat_runs_give_identical_files, test_NFR_0_3_01_no_network_during_scoring, test_NFR_0_3_01_scoring_code_imports_no_network_modules, test_FR_0_3_06_one_sided_clip_is_an_input_error, test_FR_0_3_06_more_input_and_output_errors_exit_2, test_FR_0_3_06_out_folder_that_cannot_be_created_exits_2, test_NFR_0_5_02_score_refuses_drive_path_outside_aqis_lab]
INPUTS AND OUTPUTS: two CSV files and an output folder in; three files in that folder and a report on stdout
  out; `ERROR: ...` on stderr and exit 2 on failure.
CONTRACTS: docs/contracts/SCORE_TABLE.md (input formats, score table, summary file, report);
  docs/contracts/NORMALISATION.md.
INVARIANTS:
  - A missing hypothesis is an error, never an empty text; an explicitly empty text is scored.
  - Nothing is written unless every input is valid; an existing output file is never replaced, and on an
    error no output file is left behind.
  - Output files are complete when they appear: each is written under a `.part` name first, then renamed.
  - Deterministic and offline: the same inputs, in any row order, give byte-identical files; no network access.
NOT IN SCOPE:
  - Normalising, aligning and the table layout (aqis_lab/scoring/); reading event logs or pack manifests.
CHANGE LOG:
  2026-09-27 WP-0.3 FR-0.3-06 created.
  2026-09-27 WP-0.3 round 2 F01: header lists the new one-sided clip and input/output error tests (header only).
  2026-09-28 WP-0.6 DEBT-008: write_outputs creates --out inside its error handling, so a folder that cannot be
    created is `ERROR:` and exit 2 (test_FR_0_3_06_out_folder_that_cannot_be_created_exits_2).
  2026-09-30 WP-0.7 DEBT-014: write_outputs checks --out with aqis_lab.drive.check_write_path before writing; a
    Drive path outside MyDrive/AQIS_LAB is `ERROR:` and exit 2 (test_NFR_0_5_02_score_refuses_drive_path_outside_aqis_lab).
"""
import argparse
import csv
import hashlib
import io
import os
import sys
from pathlib import Path

from aqis_lab.contracts.canonical import canonical_json
from aqis_lab.scoring.normalise import NormalisationError, NormaliserVersionError
from aqis_lab.scoring.table import SCHEMA_VERSION, csv_bytes, is_clip_id, is_run_card_id, parquet_bytes, rows_from_scores
from aqis_lab.scoring.wer import corpus_summary, score_corpus

REF_HEADER = ["clip_id", "text"]
HYP_HEADER = ["run_card_id", "clip_id", "text"]
TABLE_NAMES = ("scores.parquet", "scores.csv")
SUMMARY_NAME = "summary.json"
OUTPUT_NAMES = TABLE_NAMES + (SUMMARY_NAME,)


class InputError(Exception):
    """A usage, input or output problem; reported as `ERROR: <message>` with exit code 2."""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m aqis_lab score",
        description="Score hypotheses against references under both normaliser variants (main and "
                    "disfluency-aware) and write scores.parquet, scores.csv and summary.json "
                    "(docs/contracts/SCORE_TABLE.md). Exit 0: written; 2: usage, input or output error.")
    parser.add_argument("--ref", required=True, help="reference CSV with the header clip_id,text")
    parser.add_argument("--hyp", required=True, help="hypothesis CSV with the header run_card_id,clip_id,text")
    parser.add_argument("--out", required=True, help="output folder (created if missing; existing outputs are "
                                                     "never overwritten)")
    return parser


def read_records(path, header):
    """[(first line number, fields)] of a strict UTF-8 CSV file whose first record is exactly `header`."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not UTF-8 text (invalid byte at offset {exc.start})") from exc
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    records = []
    try:
        first = next(reader, None)
        if first != header:
            raise InputError(f"{path} line 1: the header must be exactly {','.join(header)}, got "
                             f"{'nothing' if first is None else ','.join(first)!r}")
        while True:
            line = reader.line_num + 1
            fields = next(reader, None)
            if fields is None:
                break
            if len(fields) != len(header):
                raise InputError(f"{path} line {line}: expected {len(header)} fields ({','.join(header)}), "
                                 f"got {len(fields)}")
            records.append((line, fields))
    except csv.Error as exc:
        raise InputError(f"{path} line {reader.line_num}: {exc}") from exc
    return records


def _clip_texts(path, records, clip_column):
    texts, lines = {}, {}
    for line, fields in records:
        clip_id, text = fields[clip_column], fields[-1]
        if not is_clip_id(clip_id):
            raise InputError(f"{path} line {line}: invalid clip_id {clip_id!r} "
                             f"(lowercase letters, digits and hyphens only)")
        if clip_id in texts:
            raise InputError(f"{path} line {line}: clip_id {clip_id!r} appears more than once "
                             f"(first on line {lines[clip_id]})")
        texts[clip_id], lines[clip_id] = text, line
    return texts


def read_inputs(ref_path, hyp_path):
    """(run_card_id, [(clip_id, reference, hypothesis)] sorted by clip_id) from the two input files."""
    refs = _clip_texts(ref_path, read_records(ref_path, REF_HEADER), 0)
    hyp_records = read_records(hyp_path, HYP_HEADER)
    run_card_ids = []
    for line, fields in hyp_records:
        if not is_run_card_id(fields[0]):
            raise InputError(f"{hyp_path} line {line}: invalid run_card_id {fields[0]!r} "
                             f"(64 lowercase hexadecimal characters)")
        if fields[0] not in run_card_ids:
            run_card_ids.append(fields[0])
    hyps = _clip_texts(hyp_path, hyp_records, 1)
    if not refs and not hyps:
        raise InputError(f"no clips to score in {ref_path} and {hyp_path}")
    if len(run_card_ids) > 1:
        raise InputError(f"{hyp_path} has more than one run_card_id: {', '.join(run_card_ids)}")
    only_ref, only_hyp = sorted(set(refs) - set(hyps)), sorted(set(hyps) - set(refs))
    if only_ref or only_hyp:
        raise InputError(f"the two files must list the same clips; only in {ref_path}: "
                         f"{', '.join(only_ref) or 'none'}; only in {hyp_path}: {', '.join(only_hyp) or 'none'}")
    return run_card_ids[0], [(clip_id, refs[clip_id], hyps[clip_id]) for clip_id in sorted(refs)]


def _rate(value):
    return "undefined" if value is None else f"{value:.6f}"


def report_lines(summaries):
    for variant, s in summaries.items():
        yield f"variant {variant} (normaliser {s.normaliser_name} {s.normaliser_version})"
        yield f"  utterances {s.utterances}, empty references {s.empty_references}"
        yield (f"  corpus WER {_rate(s.corpus_wer)} = {s.errors} errors / {s.ref_words} reference words "
               f"(S {s.substitutions}, D {s.deletions}, I {s.insertions}, H {s.hits})")
        yield (f"  mean per-utterance WER {_rate(s.mean_utterance_wer)} over {s.utterances_with_wer} utterances "
               f"(not the corpus WER; {s.empty_references} undefined)")
        yield (f"  corpus CER {_rate(s.corpus_cer)} = {s.char_errors} errors / {s.ref_chars} reference characters "
               f"(S {s.char_substitutions}, D {s.char_deletions}, I {s.char_insertions}, H {s.char_hits})")


def _refuse_existing(out):
    if out.exists() and not out.is_dir():
        raise InputError(f"--out {out} exists and is not a folder")
    existing = [str(out / name) for name in OUTPUT_NAMES if os.path.lexists(out / name)]
    if existing:
        raise InputError(f"output already exists: {', '.join(existing)}; the score command never overwrites "
                         f"results, choose a new --out folder")


def write_outputs(out, contents):
    """Write every {name: bytes} under a `.part` name, then rename each; nothing is left behind on failure."""
    from aqis_lab.drive import DriveError, check_write_path
    from aqis_lab.platform import PlatformError
    try:
        check_write_path(out)                  # NFR-0.5-02: on Google Drive, only under MyDrive/AQIS_LAB
    except (DriveError, PlatformError) as exc:
        raise InputError(str(exc)) from exc
    parts = {name: out / (name + ".part") for name in contents}
    done = []
    try:
        out.mkdir(parents=True, exist_ok=True)
        for name, data in contents.items():
            parts[name].write_bytes(data)
        for name in contents:
            if os.path.lexists(out / name):
                raise InputError(f"output already exists: {out / name}; nothing was replaced")
            os.rename(parts[name], out / name)
            done.append(out / name)
    except (OSError, InputError) as exc:
        for path in list(parts.values()) + done:
            if os.path.lexists(path):
                os.unlink(path)
        if isinstance(exc, InputError):
            raise
        raise InputError(f"cannot write the outputs in {out}: {exc.strerror or exc}") from exc


def main(argv):
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    try:
        _refuse_existing(out)
        run_card_id, clips = read_inputs(args.ref, args.hyp)
        try:
            scores = score_corpus(clips, run_card_id)
        except (NormaliserVersionError, NormalisationError) as exc:
            raise InputError(str(exc)) from exc
        summaries = corpus_summary(scores)
        rows = rows_from_scores(scores)
        contents = {"scores.parquet": parquet_bytes(rows), "scores.csv": csv_bytes(rows)}
        summary = {
            "schema_version": SCHEMA_VERSION,
            "run_card_id": run_card_id,
            "variants": {variant: s.as_dict() for variant, s in summaries.items()},
            "files": {name: hashlib.sha256(contents[name]).hexdigest() for name in TABLE_NAMES},
        }
        contents[SUMMARY_NAME] = canonical_json(summary)
        write_outputs(out, contents)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for line in report_lines(summaries):
        print(line)
    print("wrote " + ", ".join(str(out / name) for name in OUTPUT_NAMES))
    return 0
