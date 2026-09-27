"""FR-0.3-07: counts match the independent implementation, the pinned jiwer, exactly."""
import importlib.metadata as md
import random

import jiwer
import pytest

from aqis_scoring_testutil import PINNED_JIWER, generated_texts
from aqis_testutil import parse_lock

from aqis_lab.scoring import wer as W
from aqis_lab.scoring.normalise import normalise

PAIR_SEED = 30703  # recorded seed of the generated pairs


def _word_pool():
    """Distinct words from real normaliser output: letters, digits and the symbols % $ £ € ¢ and '.'."""
    words = sorted({w for text in generated_texts(PAIR_SEED, 400) for w in normalise(text).split(" ") if w})
    assert len(words) >= 50
    return words


def _edit(rng, words, pool, rate):
    out = []
    for word in words:
        roll = rng.random()
        if roll < rate / 3:
            continue                                   # deletion
        if roll < 2 * rate / 3:
            out.append(rng.choice(pool))               # substitution (or a hit when the same word is drawn)
        else:
            out.append(word)
        if rng.random() < rate / 3:
            out.append(rng.choice(pool))               # insertion
    return out


def generated_pairs(seed=PAIR_SEED):
    """(kind, reference, hypothesis) as normalised texts: fixed edge cases plus seeded random pairs."""
    rng = random.Random(seed)
    pool = _word_pool()
    pairs = [("identical", "the cat sat", "the cat sat"), ("empty-reference", "", "hello there"),
             ("empty-hypothesis", "hello there", ""), ("both-empty", "", ""),
             ("repeated-words", "i i i mean it it", "i mean it"), ("repeated-words", "the the", "the the the")]
    for _ in range(20):
        ref = rng.sample(pool, rng.randint(1, 12))
        pairs.append(("identical", " ".join(ref), " ".join(ref)))
    for _ in range(10):
        pairs.append(("empty-reference", "", " ".join(rng.choices(pool, k=rng.randint(1, 6)))))
        pairs.append(("empty-hypothesis", " ".join(rng.choices(pool, k=rng.randint(1, 6))), ""))
    for _ in range(80):                                # tie-heavy: 2- or 3-word vocabularies
        vocab = rng.sample(pool, rng.choice((2, 3)))
        pairs.append(("tie-heavy", " ".join(rng.choices(vocab, k=rng.randint(0, 12))),
                      " ".join(rng.choices(vocab, k=rng.randint(0, 12)))))
    for _ in range(80):
        ref = rng.choices(pool, k=rng.randint(1, 25))
        pairs.append(("random-edits", " ".join(ref), " ".join(_edit(rng, ref, pool, rng.choice((0.1, 0.3, 0.6))))))
    for _ in range(6):
        ref = rng.choices(pool, k=300)
        pairs.append(("long", " ".join(ref), " ".join(_edit(rng, ref, pool, 0.2))))
    return pairs


def _insertion_first_counts(ref, hyp):
    """Textbook DP traceback preferring insertion, then diagonal, then deletion (not the lab's rule)."""
    n, m = len(ref), len(hyp)
    d = [[i + j if i == 0 or j == 0 else 0 for j in range(m + 1)] for i in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    i, j, h, s, dl, ins = n, m, 0, 0, 0, 0
    while i or j:
        if j and d[i][j] == d[i][j - 1] + 1:
            ins, j = ins + 1, j - 1
        elif i and j and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            h, s = (h + 1, s) if ref[i - 1] == hyp[j - 1] else (h, s + 1)
            i, j = i - 1, j - 1
        else:
            dl, i = dl + 1, i - 1
    return (h, s, dl, ins)


PAIRS = generated_pairs()


def _counts(alignment):
    return (alignment.hits, alignment.substitutions, alignment.deletions, alignment.insertions)


def _jiwer_counts(output):
    return (output.hits, output.substitutions, output.deletions, output.insertions)


def test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs():
    assert len(PAIRS) >= 200
    for kind, ref, hyp in PAIRS:
        ours = _counts(W.align(W.words(ref), W.words(hyp)))
        assert ours == _jiwer_counts(jiwer.process_words(ref, hyp)), (kind, ref, hyp)


def test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs():
    for kind, ref, hyp in PAIRS:
        ours = _counts(W.align(W.characters(ref), W.characters(hyp)))
        assert ours == _jiwer_counts(jiwer.process_characters(ref, hyp)), (kind, ref, hyp)


def test_FR_0_3_07_corpus_totals_and_wer_match_jiwer():
    clips = [(f"clip-{n}", ref, hyp) for n, (_, ref, hyp) in enumerate(PAIRS)]
    scores = W.score_corpus(clips, "d" * 64)
    for variant, summary in W.corpus_summary(scores).items():
        mine = sorted((s for s in scores if s.variant == variant), key=lambda s: s.clip_id)
        refs = [s.ref_normalised for s in mine]
        hyps = [s.hyp_normalised for s in mine]
        words = jiwer.process_words(refs, hyps)
        assert (summary.hits, summary.substitutions, summary.deletions, summary.insertions) == _jiwer_counts(words)
        assert summary.corpus_wer == jiwer.wer(refs, hyps) == words.wer
        chars = jiwer.process_characters(refs, hyps)
        assert (summary.char_hits, summary.char_substitutions, summary.char_deletions,
                summary.char_insertions) == _jiwer_counts(chars)
        assert summary.corpus_cer == jiwer.cer(refs, hyps)


def test_FR_0_3_07_generated_pairs_cover_edge_cases():
    kinds = {}
    for kind, ref, hyp in PAIRS:
        kinds.setdefault(kind, []).append((ref, hyp))
    assert set(kinds) == {"identical", "empty-reference", "empty-hypothesis", "both-empty", "repeated-words",
                          "tie-heavy", "random-edits", "long"}
    assert all(ref == "" for ref, _ in kinds["empty-reference"])
    assert all(hyp == "" and ref for ref, hyp in kinds["empty-hypothesis"])
    assert all(len(ref.split(" ")) == 300 for ref, _ in kinds["long"])
    assert len(kinds["tie-heavy"]) >= 60
    # The tie-heavy pairs really exercise the tie-break: a plain traceback that prefers insertions, then the
    # diagonal, then deletions reaches the same distance but a different S/D/I split on some of them.
    differing = sum(1 for r, h in kinds["tie-heavy"]
                    if _insertion_first_counts(W.words(r), W.words(h)) != _jiwer_counts(jiwer.process_words(r, h)))
    assert differing >= 5, differing
    symbols = set("".join(ref + hyp for _, ref, hyp in PAIRS))
    # Normalised text keeps only the number symbols Whisper keeps (it removes apostrophes).
    assert {"%", "$", "£", "€", "¢", "."} <= symbols and any(c.isdigit() for c in symbols)


def test_FR_0_3_07_jiwer_is_the_pinned_version():
    assert md.version("jiwer") == PINNED_JIWER == parse_lock()["jiwer"]["version"]


@pytest.mark.slow
def test_FR_0_3_07_tie_heavy_pairs_match_jiwer():
    rng = random.Random(PAIR_SEED + 1)
    for _ in range(20000):
        size = rng.randint(2, 4)
        ref = [f"w{rng.randrange(size)}" for _ in range(rng.randint(0, 14))]
        hyp = [f"w{rng.randrange(size)}" for _ in range(rng.randint(0, 14))]
        r, h = " ".join(ref), " ".join(hyp)
        assert _counts(W.align(ref, hyp)) == _jiwer_counts(jiwer.process_words(r, h)), (r, h)
