"""FR-0.3-04: per-utterance alignment, counts, CER and the empty-reference rule."""
import random

import pytest

from aqis_scoring_testutil import textbook_distance

from aqis_lab.scoring import wer as W
from aqis_lab.scoring.normalise import DISFLUENCY_AWARE, MAIN


def counts(alignment):
    return (alignment.hits, alignment.substitutions, alignment.deletions, alignment.insertions)


# (reference, hypothesis, (hits, substitutions, deletions, insertions)) counted by hand; each has a single
# minimum split of the counts, so no tie-break is involved.
HAND_COUNTED = [
    ("the cat sat", "the cat sat", (3, 0, 0, 0)),
    ("the cat sat", "the bat sat", (2, 1, 0, 0)),
    ("the cat sat on the mat", "the cat on the mat", (5, 0, 1, 0)),
    ("a b", "a x b", (2, 0, 0, 1)),
    ("a b c", "", (0, 0, 3, 0)),
    ("", "a b", (0, 0, 0, 2)),
    ("a b c d", "x b c y z", (2, 2, 0, 1)),
    ("a b c", "b c d", (2, 0, 1, 1)),
    ("i i i mean", "i mean", (2, 0, 2, 0)),
]


@pytest.mark.parametrize("ref, hyp, expected", HAND_COUNTED)
def test_FR_0_3_04_hand_counted_alignments(ref, hyp, expected):
    alignment = W.align(W.words(ref), W.words(hyp))
    assert counts(alignment) == expected
    h, s, d, i = expected
    assert alignment.errors == s + d + i
    assert alignment.ref_len == h + s + d and alignment.hyp_len == h + s + i


def test_FR_0_3_04_tie_break_follows_documented_rule():
    # Hand-derived from the rule in SCORE_TABLE.md ("Alignment"): no common prefix or suffix here; tracing back
    # from the end, a deletion is taken when D[i][j] = D[i-1][j] + 1, else an insertion when
    # D[i][j-1] = D[i-1][j-1] - 1, else the diagonal step.
    # ref [a, b], hyp [b, c]: D = [[0,1,2],[1,1,2],[2,1,2]]. At (2,2): D[1][2]+1 = 3 != 2, D[2][1] = 1 != D[1][1]-1 = 0,
    # so diagonal (b/c substitution); at (1,1): diagonal again (a/b). Two substitutions, although
    # "delete a, hit b, insert c" costs 2 as well.
    assert counts(W.align(["a", "b"], ["b", "c"])) == (0, 2, 0, 0)
    # ref [a, b], hyp [c, a]: D = [[0,1,2],[1,1,1],[2,2,2]]. At (2,2): D[1][2]+1 = 2 == 2, so delete b; at (1,2):
    # not a deletion (D[0][2]+1 = 3), not an insertion (D[1][1] = 1 != D[0][1]-1 = 0), so diagonal a/a hit; then
    # (0,1) leaves one insertion (c). Two substitutions would also cost 2.
    alignment = W.align(["a", "b"], ["c", "a"])
    assert counts(alignment) == (1, 0, 1, 1)
    assert [op.kind for op in alignment.ops] == ["insertion", "hit", "deletion"]
    # A cell where both a deletion and an insertion qualify, so the order of the two checks matters.
    # ref [a, a, b, c], hyp [b, c, b] (no common prefix or suffix):
    #   D = [[0,1,2,3], [1,1,2,3], [2,2,2,3], [3,2,3,2], [4,3,2,3]]
    # (4,3): D[3][3]+1 = 3 == 3 -> delete c; (at this cell D[4][2] = 2 = D[3][2]-1 too, so an insertion-first
    # rule would insert b here instead). (3,3): no deletion (D[2][3]+1 = 4), no insertion (D[3][2] = 3 != D[2][2]-1)
    # -> hit b/b. (2,2) and (1,1): diagonal -> substitutions a/c and a/b. Counts: 1 hit, 2 substitutions, 1 deletion.
    assert counts(W.align(["a", "a", "b", "c"], ["b", "c", "b"])) == (1, 2, 1, 0)
    # The common prefix and suffix are hits before anything else is aligned.
    assert [op.kind for op in W.align(["x", "a", "y"], ["x", "b", "c", "y"]).ops][0] == "hit"


def _random_pairs(seed, count, alphabet, max_len):
    rng = random.Random(seed)
    for _ in range(count):
        size = rng.randint(1, alphabet)
        yield ([str(rng.randrange(size)) for _ in range(rng.randint(0, max_len))],
               [str(rng.randrange(size)) for _ in range(rng.randint(0, max_len))])


def test_FR_0_3_04_errors_equal_edit_distance():
    for ref, hyp in _random_pairs(404, 3000, 4, 14):
        alignment = W.align(ref, hyp)
        assert alignment.errors == textbook_distance(ref, hyp), (ref, hyp)


def test_FR_0_3_04_alignment_ops_rebuild_both_texts():
    for ref, hyp in _random_pairs(405, 2000, 5, 14):
        alignment = W.align(ref, hyp)
        ref_seen, hyp_seen = [], []
        for op in alignment.ops:
            assert op.kind in ("hit", "substitution", "deletion", "insertion")
            if op.kind in ("hit", "substitution"):
                assert (ref[op.ref_index] == hyp[op.hyp_index]) == (op.kind == "hit")
            if op.kind == "deletion":
                assert op.hyp_index is None
            if op.kind == "insertion":
                assert op.ref_index is None
            if op.ref_index is not None:
                ref_seen.append(op.ref_index)
            if op.hyp_index is not None:
                hyp_seen.append(op.hyp_index)
        # Every token appears exactly once, in order: the operations rebuild both texts.
        assert ref_seen == list(range(len(ref))) and hyp_seen == list(range(len(hyp)))
        kinds = [op.kind for op in alignment.ops]
        assert counts(alignment) == tuple(kinds.count(k) for k in ("hit", "substitution", "deletion", "insertion"))


def test_FR_0_3_04_reference_length_is_hits_subs_dels():
    for ref, hyp in _random_pairs(406, 1000, 3, 10):
        a = W.align(ref, hyp)
        assert a.ref_len == len(ref) == a.hits + a.substitutions + a.deletions
        assert a.hyp_len == len(hyp) == a.hits + a.substitutions + a.insertions
        assert a.rate == (None if not ref else a.errors / len(ref))


def test_FR_0_3_04_cer_counts_characters_including_spaces():
    score = W.score_utterance("c-1", "ab cd", "abcd", MAIN)
    assert score.ref_normalised == "ab cd" and score.hyp_normalised == "abcd"
    assert counts(score.chars) == (4, 0, 1, 0)
    assert score.chars.ref_len == 5 and score.cer == 1 / 5
    assert W.characters("ab cd") == ["a", "b", " ", "c", "d"]
    # Word level: "ab cd" against "abcd" is one substitution and one deletion.
    assert counts(score.words) == (0, 1, 1, 0) and score.wer == 1.0


def test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined():
    score = W.score_utterance("c-1", "", "Hello, world!", MAIN)
    assert score.hyp_normalised == "hello world"
    assert counts(score.words) == (0, 0, 0, 2) and score.words.ref_len == 0
    assert score.wer is None
    assert counts(score.chars) == (0, 0, 0, 11) and score.cer is None


def test_FR_0_3_04_reference_empty_after_normalisation():
    main = W.score_utterance("c-1", "Um.", "um okay", MAIN)
    assert main.ref_normalised == "" and main.hyp_normalised == "okay"
    assert counts(main.words) == (0, 0, 0, 1) and main.wer is None
    keep = W.score_utterance("c-1", "Um.", "um okay", DISFLUENCY_AWARE)
    assert keep.ref_normalised == "um" and keep.hyp_normalised == "um okay"
    assert counts(keep.words) == (1, 0, 0, 1) and keep.wer == 1.0


def test_FR_0_3_04_empty_reference_enters_corpus_totals():
    scores = W.score_corpus([("c-1", "hello world", "hello world"), ("c-2", "", "extra words")], "a" * 64)
    main = W.corpus_summary(scores)["main"]
    assert main.utterances == 2 and main.empty_references == 1
    assert (main.ref_words, main.insertions, main.errors) == (2, 2, 2)
    assert main.corpus_wer == 2 / 2
    assert main.utterances_with_wer == 1 and main.mean_utterance_wer == 0.0


def test_FR_0_3_04_both_texts_empty():
    score = W.score_utterance("c-1", "", "", MAIN)
    assert counts(score.words) == (0, 0, 0, 0) and counts(score.chars) == (0, 0, 0, 0)
    assert score.words.ops == () and score.wer is None and score.cer is None


def test_FR_0_3_04_utterance_score_records_texts_and_normaliser():
    score = W.score_utterance("clip-7", "Twenty-five dollars", "$25", MAIN, run_card_id="b" * 64)
    assert (score.clip_id, score.run_card_id, score.variant) == ("clip-7", "b" * 64, "main")
    assert (score.normaliser_name, score.normaliser_version) == (MAIN.name, MAIN.version)
    assert (score.ref_text, score.hyp_text) == ("Twenty-five dollars", "$25")
    assert score.ref_normalised == score.hyp_normalised == "$25" and score.wer == 0.0


@pytest.mark.parametrize("text", [" a", "a ", "a  b", " "])
def test_FR_0_3_04_words_rejects_text_that_is_not_normalised(text):
    with pytest.raises(ValueError, match="not a normalised text"):
        W.words(text)
    assert W.words("") == [] and W.words("a b") == ["a", "b"]
