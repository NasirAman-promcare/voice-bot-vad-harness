"""WP-1.1 ruler tests 5 to 9: WER and CER, entities, bootstrap, oracle, hallucination and speed.

Every expected value is worked out by hand from the definition in the sprint brief, section 5.
"""
import math

import numpy as np
import pytest

from aqis_lab.bench import score
from aqis_lab.scoring.normalise import MAIN


def rows(*triples):
    """(ref, hyp, cluster) triples as scoring input rows."""
    return [{"utt_id": f"u{i}", "ref": ref, "hyp": hyp, "cluster": cluster}
            for i, (ref, hyp, cluster) in enumerate(triples)]


def scored(*triples):
    return score.score_rows(rows(*triples))


# ---- 5. WER and CER ------------------------------------------------------------------------------------------
def test_s1_bench_scoring_uses_the_main_normaliser():
    assert score.NORMALISER is MAIN
    # Whisper's fillers (um, uh) are removed from both sides, so this pair has no error; punctuation and case vanish.
    recs = scored(("Um, the CAT sat.", "the cat sat", "a"))
    assert score.corpus(recs)["errors"] == 0


def test_s1_corpus_wer_is_total_errors_over_total_reference_words():
    # utterance 1: 6 reference words, hyp misses "the" -> 1 deletion; utterance 2: 2 reference words, hyp has 2 insertions
    recs = scored(("the cat sat on the mat", "the cat sat on mat", "a"), ("hello world", "hello there world friend", "b"))
    total = score.corpus(recs)
    assert (total["errors"], total["ref_words"], total["utterances"]) == (3, 8, 2)
    assert total["wer"] == pytest.approx(3 / 8)                   # not the mean of 1/6 and 2/2 (0.583)


def test_s1_corpus_cer_counts_characters_including_spaces():
    # "cat" -> "cut": 1 substitution over 3 characters; "a b" -> "a b": 0 over 3 -> 1 error in 6 characters
    recs = scored(("cat", "cut", "a"), ("a b", "a b", "a"))
    assert score.corpus(recs)["cer"] == pytest.approx(1 / 6)


def test_s1_corpus_wer_is_undefined_without_reference_words():
    assert score.corpus(scored(("", "", "a")))["wer"] is None


def test_s1_score_rows_rejects_a_row_missing_a_field():
    with pytest.raises(score.ScoreError, match="hyp"):
        score.score_rows([{"utt_id": "u", "ref": "x", "cluster": "a"}])


# ---- 6. entities ---------------------------------------------------------------------------------------------
def test_s1_number_accuracy_counts_reference_digit_tokens_marked_as_hits():
    # reference digit tokens: 555, 1234, 5  (the "pm" has none); the hypothesis misses 1234 (1235) -> 2 of 3
    recs = scored(("call 555 1234 at 5 pm", "call 555 1235 at 5 pm", "a"))
    assert score.number_accuracy(recs) == {"hits": 2, "total": 3, "rate": pytest.approx(2 / 3)}


def test_s1_number_accuracy_ignores_non_digit_words_and_normalises_spelled_numbers():
    # "twenty five dollars" and "$25" normalise to the same token "$25"; "ten" -> "10" is missed ("tan")
    recs = scored(("it was twenty five dollars", "it was $25", "a"), ("it was ten", "it was tan", "b"))
    assert score.number_accuracy(recs) == {"hits": 1, "total": 2, "rate": 0.5}


def test_s1_number_accuracy_is_undefined_without_digit_tokens():
    assert score.number_accuracy(scored(("no numbers here", "no numbers here", "a")))["rate"] is None


@pytest.mark.parametrize("entity,hyp,found", [
    ("metformin", "he takes metformin daily", True),
    ("Blood Pressure", "his blood pressure is high", True),
    ("chest pain", "chest", False),                               # partial match is a miss
    ("chest pain", "chest has pain", False),                      # words not contiguous
    ("blood pressure", "pressure of the blood", False),           # out of order
    ("dolo 650", "give Dolo 650 tablet", True),
    ("500 mg", "five hundred mg", True),                          # spelled numbers normalise to the same digits
    ("aspirin", "", False),
])
def test_s1_entity_found_needs_contiguous_ordered_normalised_words(entity, hyp, found):
    assert score.entity_found(entity, hyp) is found


def test_s1_entity_recall_per_category_and_overall():
    items = [("drugs", "metformin", "takes metformin"), ("drugs", "aspirin", "takes aspirin"),
             ("drugs", "zincovit", "takes zinc"), ("clinical_findings", "chest pain", "chest pain today"),
             ("clinical_findings", "fever", "no temperature")]
    got = score.entity_recall(items)
    assert got["drugs"] == {"found": 2, "total": 3, "recall": pytest.approx(2 / 3)}
    assert got["clinical_findings"] == {"found": 1, "total": 2, "recall": 0.5}
    assert got["all"] == {"found": 3, "total": 5, "recall": pytest.approx(0.6)}


def test_s1_parse_entities_reads_the_eka_json_string():
    value = '[["adequate rest", "advices", [[11, 24]]], ["azithromycin", "drugs", [[34, 44]]]]'
    assert score.parse_entities(value) == [("advices", "adequate rest"), ("drugs", "azithromycin")]
    assert score.parse_entities("[]") == [] and score.parse_entities(None) == []


@pytest.mark.parametrize("bad", ['{"a": 1}', '[["only text"]]', "not json", '[[1, 2, 3]]'])
def test_s1_parse_entities_rejects_other_shapes(bad):
    with pytest.raises(score.ScoreError):
        score.parse_entities(bad)


# ---- 7. bootstrap --------------------------------------------------------------------------------------------
def test_s1_bootstrap_same_seed_same_interval_other_seed_other_interval():
    recs = scored(*[("a b c d e f g h", "a b c d e f g x" if i % 3 == 0 else "a b c d e f x x" if i % 7 == 0
                     else "a b c d e f g h", f"s{i % 23}") for i in range(115)])
    one = score.bootstrap_ci(recs, resamples=1000, seed=5)
    assert one == score.bootstrap_ci(recs, resamples=1000, seed=5)
    assert one != score.bootstrap_ci(recs, resamples=1000, seed=6)
    assert one[0] <= score.corpus(recs)["wer"] <= one[1]


def test_s1_bootstrap_with_two_speakers_gives_exactly_their_two_wers():
    # speaker A: 1 error in 2 words; speaker B: 1 error in 98 words. Any resample of two speakers is AA, AB or BB,
    # so with probability 1/4 each extreme, the 2.5% and 97.5% points are the two single-speaker WERs.
    a = ("red blue", "red green", "A")
    b = (" ".join(["w"] * 98), " ".join(["w"] * 97 + ["x"]), "B")
    lo, hi = score.bootstrap_ci(scored(a, b), resamples=1000, seed=1)
    assert lo == pytest.approx(1 / 98) and hi == pytest.approx(1 / 2)


def test_s1_bootstrap_resamples_speakers_not_utterances():
    # one big speaker with many error-free utterances and a small one with errors: utterance-level resampling
    # would give a narrow interval, speaker-level resampling keeps the single-speaker extremes.
    big = [("a b c d", "a b c d", "big") for _ in range(30)]
    small = [("a b c d", "a b c x", "small") for _ in range(3)]
    recs = scored(*(big + small))
    by_speaker = score.bootstrap_ci(recs, resamples=1000, seed=2, unit="cluster")
    by_utterance = score.bootstrap_ci(recs, resamples=1000, seed=2, unit="utterance")
    assert by_speaker == pytest.approx((0.0, 0.25))               # speakers: big 0/120, small 3/12
    assert by_utterance[1] < by_speaker[1] - 0.05


def test_s1_bootstrap_of_identical_speakers_collapses_to_a_point():
    recs = scored(*[("a b c d", "a b c x", f"s{i}") for i in range(10)])
    lo, hi = score.bootstrap_ci(recs, resamples=1000, seed=3)
    assert lo == hi == pytest.approx(0.25)


def test_s1_bootstrap_rejects_an_unknown_unit():
    with pytest.raises(score.ScoreError):
        score.bootstrap_ci(scored(("a", "a", "s")), resamples=10, seed=1, unit="word")


def test_s1_paired_bootstrap_calls_a_clear_difference_and_a_tie():
    clusters = [f"s{i}" for i in range(20)]
    ref = "a b c d e f g h i j"
    good = [(ref, ref, c) for c in clusters]
    bad = [(ref, "a b c d e f g h x y", c) for c in clusters]
    verdict = score.paired_bootstrap(scored(*good), scored(*bad), resamples=1000, seed=4)
    assert verdict["diff"] == pytest.approx(-0.2) and verdict["verdict"] == "A beats B"
    assert verdict["ci"] == pytest.approx((-0.2, -0.2))
    same = score.paired_bootstrap(scored(*bad), scored(*bad), resamples=1000, seed=4)
    assert same["diff"] == 0 and same["verdict"] == "too close to call"
    mixed_a = [(ref, ref if i % 2 else "x b c d e f g h i j", c) for i, c in enumerate(clusters)]
    mixed_b = [(ref, "x b c d e f g h i j" if i % 2 else ref, c) for i, c in enumerate(clusters)]
    close = score.paired_bootstrap(scored(*mixed_a), scored(*mixed_b), resamples=1000, seed=4)
    assert close["verdict"] == "too close to call" and close["diff"] == pytest.approx(0)


def test_s1_paired_bootstrap_needs_the_same_utterances():
    a, b = scored(("a b", "a b", "s")), scored(("a b", "a b", "s"), ("c d", "c d", "t"))
    with pytest.raises(score.ScoreError, match="same utterances"):
        score.paired_bootstrap(a, b, resamples=10, seed=1)


def test_s1_mean_of_wers_point_and_interval_by_hand():
    # slice one: speaker A 1 error in 2 words, speaker B 1 in 98; slice two: two identical speakers at 1 in 10 (0.1).
    # Resampling two speakers gives WERs 1/98 (BB), 0.02 (AB) or 0.5 (AA) in slice one, always 0.1 in slice two, so the
    # 2.5% and 97.5% points of the mean over slices are (1/98 + 0.1) / 2 and (0.5 + 0.1) / 2.
    one = scored(("red blue", "red green", "A"), (" ".join(["w"] * 98), " ".join(["w"] * 97 + ["x"]), "B"))
    two = scored(*[(" ".join(["w"] * 10), " ".join(["w"] * 9 + ["x"]), f"T{i}") for i in range(2)])
    groups = {"one": one, "two": two}
    assert score.mean_of_wers(groups) == pytest.approx((2 / 100 + 0.1) / 2)       # slice one pooled: 2 errors in 100 words
    lo, hi = score.mean_of_wers_ci(groups, resamples=1000, seed=7)
    assert lo == pytest.approx((1 / 98 + 0.1) / 2) and hi == pytest.approx((0.5 + 0.1) / 2)
    assert (lo, hi) == score.mean_of_wers_ci(groups, resamples=1000, seed=7)


def test_s1_paired_mean_of_wers_calls_a_constant_difference():
    ref = " ".join(["w"] * 10)
    good = {g: scored(*[(ref, ref, f"c{i}") for i in range(4)]) for g in ("one", "two")}
    bad = {g: scored(*[(ref, " ".join(["w"] * 8 + ["x", "y"]), f"c{i}") for i in range(4)]) for g in ("one", "two")}
    got = score.paired_mean_of_wers(good, bad, resamples=500, seed=3)
    assert got["diff"] == pytest.approx(-0.2) and got["ci"] == pytest.approx((-0.2, -0.2)) and got["verdict"] == "A beats B"
    assert score.paired_mean_of_wers(bad, bad, resamples=500, seed=3)["verdict"] == "too close to call"
    with pytest.raises(score.ScoreError):
        score.paired_mean_of_wers(good, {"one": bad["one"]}, resamples=10, seed=1)


# ---- 8. oracle -----------------------------------------------------------------------------------------------
def test_s1_oracle_hand_example_with_three_models():
    errors = {"A": [0, 5, 5, 0], "B": [5, 1, 5, 0], "C": [3, 3, 0, 2]}
    got = score.oracle(errors, ref_words=[10, 10, 10, 10])
    assert got["best_single"] == {"models": ("C",), "errors": 8, "wer": pytest.approx(0.2)}
    assert got["oracle"] == {"models": ("A", "B", "C"), "errors": 1, "wer": pytest.approx(0.025)}  # per utterance: 0,1,0,0
    assert got["best_pair"] == {"models": ("A", "C"), "errors": 3, "wer": pytest.approx(0.075)}


def test_s1_oracle_pair_ties_resolve_to_the_first_pair_in_name_order():
    got = score.oracle({"B": [1, 0], "A": [0, 1], "C": [1, 1]}, ref_words=[5, 5])
    assert got["best_pair"]["models"] == ("A", "B") and got["best_pair"]["errors"] == 0


def test_s1_oracle_needs_two_models_and_equal_lengths():
    with pytest.raises(score.ScoreError):
        score.oracle({"A": [1]}, ref_words=[5])
    with pytest.raises(score.ScoreError):
        score.oracle({"A": [1, 2], "B": [1]}, ref_words=[5, 5])


# ---- 9. hallucination ----------------------------------------------------------------------------------------
def test_s1_hallucination_counts_only_clips_with_words_after_normalisation():
    hyps = ["", "uh", "um hmm", "Thank you.", "...", "the"]       # fillers and punctuation normalise to nothing
    got = score.hallucination(hyps)
    assert got == {"clips": 6, "with_words": 2, "rate": pytest.approx(2 / 6), "mean_words": pytest.approx(3 / 6)}


def test_s1_hallucination_of_no_clips_is_an_error():
    with pytest.raises(score.ScoreError):
        score.hallucination([])


# ---- speed ---------------------------------------------------------------------------------------------------
def test_s1_rtfx_is_total_audio_over_total_wall_time():
    assert score.rtfx([(100.0, 2.0), (50.0, 3.0)]) == pytest.approx(150 / 5)


def test_s1_latency_percentiles_use_linear_interpolation():
    values = list(range(1, 101))                                   # 1..100 ms
    got = score.latency_stats(values)
    assert got["p50"] == pytest.approx(50.5) and got["p95"] == pytest.approx(95.05)
    assert math.isclose(got["p95"], float(np.percentile(values, 95)))
