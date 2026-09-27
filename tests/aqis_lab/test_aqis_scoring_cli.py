"""The `score` command's printed report: both variants labelled (FR-0.3-03), corpus WER and the mean (FR-0.3-05)."""
import csv
import re

import jiwer
import pytest

from aqis_scoring_testutil import HYP_FIXTURE, KEEP_NAME, MAIN_NAME, NORMALISER_VERSION, REF_FIXTURE, run_score

from aqis_lab.scoring.normalise import normalise, normalise_keep_disfluencies

# Word counts of the 12 fixture clips, counted by hand from the fixture texts and NORMALISATION.md
# (clip: reference words, substitutions, deletions, insertions):
#   c01 6 0 0 0 | c02 4 1 0 0 | c03 6 0 2 0 | c04 3 0 0 1 | c05 3 0 0 0 (main) / 4 0 1 0 (keep "um")
#   c06 3 0 0 0 ($25) | c07 0 0 0 1 (empty reference) | c08 0 0 0 0 (main: "uh" removed, empty) / 1 0 1 0 (keep)
#   c09 3 0 3 0 | c10 4 0 0 0 ("i do not know") | c11 2 0 0 0 | c12 4 0 0 0 ("line one line 2")
HAND = {
    "main": dict(utterances=12, empty=2, ref=38, s=1, d=5, i=2, h=32,
                 per_utt=[0, 1 / 4, 2 / 6, 1 / 3, 0, 0, 1, 0, 0, 0]),
    "disfluency_aware": dict(utterances=12, empty=1, ref=40, s=1, d=7, i=2, h=32,
                             per_utt=[0, 1 / 4, 2 / 6, 1 / 3, 1 / 4, 0, 1, 1, 0, 0, 0]),
}
NAMES = {"main": MAIN_NAME, "disfluency_aware": KEEP_NAME}
NORMALISERS = {"main": normalise, "disfluency_aware": normalise_keep_disfluencies}


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    proc = run_score("--ref", REF_FIXTURE, "--hyp", HYP_FIXTURE, "--out", tmp_path_factory.mktemp("cli") / "out")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def block(report, variant):
    m = re.search(rf"^variant {variant} \(normaliser (\S+) (\S+)\)\n((?:  .*\n)+)", report, re.M)
    assert m, report
    return m.group(1), m.group(2), m.group(3)


def fixture_texts(variant):
    with open(REF_FIXTURE, encoding="utf-8", newline="") as fh:
        refs = {r["clip_id"]: r["text"] for r in csv.DictReader(fh)}
    with open(HYP_FIXTURE, encoding="utf-8", newline="") as fh:
        hyps = {r["clip_id"]: r["text"] for r in csv.DictReader(fh)}
    clips = sorted(refs)
    return [NORMALISERS[variant](refs[c]) for c in clips], [NORMALISERS[variant](hyps[c]) for c in clips]


def test_FR_0_3_03_cli_prints_both_labelled_variants(report):
    assert report.index("variant main ") < report.index("variant disfluency_aware ")
    for variant in ("main", "disfluency_aware"):
        name, version, _ = block(report, variant)
        assert (name, version) == (NAMES[variant], NORMALISER_VERSION)
    # The filler clips make the two variants differ.
    assert block(report, "main")[2] != block(report, "disfluency_aware")[2]


@pytest.mark.parametrize("variant", ["main", "disfluency_aware"])
def test_FR_0_3_05_cli_prints_corpus_and_mean_labelled(report, variant):
    _, _, text = block(report, variant)
    hand = HAND[variant]
    errors = hand["s"] + hand["d"] + hand["i"]
    assert f"  utterances {hand['utterances']}, empty references {hand['empty']}\n" in text
    assert (f"  corpus WER {errors / hand['ref']:.6f} = {errors} errors / {hand['ref']} reference words "
            f"(S {hand['s']}, D {hand['d']}, I {hand['i']}, H {hand['h']})\n") in text
    mean = sum(hand["per_utt"]) / len(hand["per_utt"])
    assert (f"  mean per-utterance WER {mean:.6f} over {len(hand['per_utt'])} utterances "
            f"(not the corpus WER; {hand['empty']} undefined)\n") in text
    refs, hyps = fixture_texts(variant)
    chars = jiwer.process_characters(refs, hyps)
    char_errors = chars.substitutions + chars.deletions + chars.insertions
    ref_chars = chars.hits + chars.substitutions + chars.deletions
    assert (f"  corpus CER {char_errors / ref_chars:.6f} = {char_errors} errors / {ref_chars} reference characters "
            f"(S {chars.substitutions}, D {chars.deletions}, I {chars.insertions}, H {chars.hits})\n") in text
    # The corpus WER is not the mean of the per-utterance WERs.
    assert f"{errors / hand['ref']:.6f}" != f"{mean:.6f}"


def test_FR_0_3_05_cli_prints_undefined_rates(tmp_path):
    from aqis_scoring_testutil import write_csv
    ref = write_csv(tmp_path / "ref.csv", ["clip_id", "text"], [["c-1", "um"]])
    hyp = write_csv(tmp_path / "hyp.csv", ["run_card_id", "clip_id", "text"], [["a" * 64, "c-1", "hello"]])
    proc = run_score("--ref", ref, "--hyp", hyp, "--out", tmp_path / "out")
    assert proc.returncode == 0, proc.stderr
    _, _, text = block(proc.stdout, "main")
    assert "  corpus WER undefined = 1 errors / 0 reference words (S 0, D 0, I 1, H 0)\n" in text
    assert "  mean per-utterance WER undefined over 0 utterances (not the corpus WER; 1 undefined)\n" in text
    assert "  corpus CER undefined = 5 errors / 0 reference characters (S 0, D 0, I 5, H 0)\n" in text


def test_FR_0_3_06_cli_lists_written_files(report):
    last = report.rstrip("\n").splitlines()[-1]
    assert re.fullmatch(r"wrote \S+/scores\.parquet, \S+/scores\.csv, \S+/summary\.json", last), last
