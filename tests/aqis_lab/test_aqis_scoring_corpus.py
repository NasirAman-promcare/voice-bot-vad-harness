"""FR-0.3-05 (corpus WER and CER, and the labelled mean) and FR-0.3-03 (both variants scored and labelled)."""
import pytest

from aqis_lab.scoring import wer as W
from aqis_lab.scoring.normalise import DISFLUENCY_AWARE, MAIN

RUN = "c" * 64
PANGRAM = "the quick brown fox jumps over the lazy dog"  # 9 words, 43 characters


def test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words():
    scores = W.score_corpus([("c-1", "yes", "no"), ("c-2", PANGRAM, PANGRAM)], RUN)
    main = W.corpus_summary(scores)["main"]
    # 1 error over 1 + 9 reference words; the mean of the per-utterance WERs (1.0 and 0.0) would be 0.5.
    assert (main.errors, main.ref_words) == (1, 10)
    assert main.corpus_wer == 1 / 10
    assert main.mean_utterance_wer == 0.5
    assert main.corpus_wer != main.mean_utterance_wer


def test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled():
    scores = W.score_corpus([("c-1", "yes", "no"), ("c-2", PANGRAM, PANGRAM), ("c-3", "", "extra")], RUN)
    main = W.corpus_summary(scores)["main"]
    assert main.utterances == 3 and main.empty_references == 1 and main.utterances_with_wer == 2
    assert main.corpus_wer == 2 / 10
    assert main.mean_utterance_wer == (1.0 + 0.0) / 2
    labelled = main.as_dict()
    assert labelled["corpus_wer"] == 2 / 10 and labelled["mean_utterance_wer"] == 0.5
    assert labelled["utterances_with_wer"] == 2 and labelled["empty_references"] == 1


def test_FR_0_3_05_corpus_wer_undefined_without_reference_words():
    scores = W.score_corpus([("c-1", "", "hello"), ("c-2", "um", "")], RUN)
    summary = W.corpus_summary(scores)
    main = summary["main"]
    assert main.ref_words == 0 and main.insertions == 1
    assert main.corpus_wer is None and main.mean_utterance_wer is None and main.corpus_cer is None
    # In the disfluency-aware score "um" is a real one-word reference, deleted.
    keep = summary["disfluency_aware"]
    assert (keep.ref_words, keep.deletions, keep.insertions) == (1, 1, 1)
    assert keep.corpus_wer == 2 / 1


def test_FR_0_3_05_corpus_cer_is_total_errors_over_total_reference_characters():
    scores = W.score_corpus([("c-1", "yes", "no"), ("c-2", PANGRAM, PANGRAM)], RUN)
    main = W.corpus_summary(scores)["main"]
    # "yes" against "no": 2 substitutions and 1 deletion; the pangram is exact.
    assert (main.char_errors, main.ref_chars) == (3, 3 + len(PANGRAM))
    assert main.corpus_cer == 3 / (3 + len(PANGRAM))
    assert (main.char_hits, main.char_substitutions, main.char_deletions, main.char_insertions) == (
        len(PANGRAM), 2, 1, 0)


def test_FR_0_3_05_summary_totals_are_sums_of_utterances():
    pairs = [("c-1", "Um, I have twenty-five dollars.", "I have 25 dollars"), ("c-2", "uh-huh", "huh"),
             ("c-3", "Hello there", "hello the air"), ("c-4", "", "noise")]
    scores = W.score_corpus(pairs, RUN)
    for variant, summary in W.corpus_summary(scores).items():
        mine = [s for s in scores if s.variant == variant]
        assert summary.utterances == len(mine) == 4
        for field in ("hits", "substitutions", "deletions", "insertions", "errors"):
            assert getattr(summary, field) == sum(getattr(s.words, field) for s in mine)
            assert getattr(summary, "char_" + field) == sum(getattr(s.chars, field) for s in mine)
        assert summary.ref_words == sum(s.words.ref_len for s in mine)
        assert summary.hyp_words == sum(s.words.hyp_len for s in mine)
        assert summary.ref_chars == sum(s.chars.ref_len for s in mine)
        assert summary.hyp_chars == sum(s.chars.hyp_len for s in mine)
        assert summary.corpus_wer == summary.errors / summary.ref_words


def test_FR_0_3_03_both_variants_scored_and_labelled():
    scores = W.score_corpus([("c-2", "um hello", "hello"), ("c-1", "hello", "hello")], RUN)
    assert [(s.clip_id, s.variant) for s in scores] == [
        ("c-1", "disfluency_aware"), ("c-1", "main"), ("c-2", "disfluency_aware"), ("c-2", "main")]
    by_key = {(s.clip_id, s.variant): s for s in scores}
    assert by_key[("c-2", "main")].normaliser_name == MAIN.name
    assert by_key[("c-2", "disfluency_aware")].normaliser_name == DISFLUENCY_AWARE.name
    assert by_key[("c-2", "main")].wer == 0.0
    assert by_key[("c-2", "disfluency_aware")].words.deletions == 1
    summary = W.corpus_summary(scores)
    assert list(summary) == ["main", "disfluency_aware"]
    assert summary["main"].normaliser_name == MAIN.name and summary["main"].errors == 0
    assert summary["disfluency_aware"].normaliser_name == DISFLUENCY_AWARE.name
    assert summary["disfluency_aware"].errors == 1


def test_FR_0_3_05_score_corpus_rejects_duplicate_clip_and_non_text():
    with pytest.raises(ValueError, match="c-1"):
        W.score_corpus([("c-1", "a", "a"), ("c-1", "b", "b")], RUN)
    with pytest.raises(TypeError):
        W.score_corpus([("c-1", None, "a")], RUN)
    with pytest.raises(ValueError, match="no utterances"):
        W.corpus_summary([])
