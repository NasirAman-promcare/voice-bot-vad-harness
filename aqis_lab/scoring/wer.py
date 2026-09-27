"""Alignment, per-utterance counts and corpus-level WER and CER for normalised transcripts.

CAPABILITIES:
  CAP-SCORE-002: align() is a unit-cost Levenshtein alignment whose split into hits, substitutions, deletions and insertions follows jiwer 4.0.0 (common prefix and suffix first, then the documented traceback rule); score_utterance() and score_corpus() normalise both texts per variant and count words and characters (spaces included), with WER/CER undefined (None) for an empty reference [tests: test_FR_0_3_04_hand_counted_alignments, test_FR_0_3_04_tie_break_follows_documented_rule, test_FR_0_3_04_errors_equal_edit_distance, test_FR_0_3_04_alignment_ops_rebuild_both_texts, test_FR_0_3_04_reference_length_is_hits_subs_dels, test_FR_0_3_04_cer_counts_characters_including_spaces, test_FR_0_3_04_empty_reference_counts_insertions_and_wer_undefined, test_FR_0_3_04_reference_empty_after_normalisation, test_FR_0_3_04_both_texts_empty, test_FR_0_3_04_utterance_score_records_texts_and_normaliser, test_FR_0_3_04_words_rejects_text_that_is_not_normalised, test_FR_0_3_03_both_variants_scored_and_labelled, test_FR_0_3_05_score_corpus_rejects_duplicate_clip_and_non_text, test_FR_0_3_07_word_counts_match_jiwer_on_generated_pairs, test_FR_0_3_07_char_counts_match_jiwer_on_generated_pairs, test_FR_0_3_07_tie_heavy_pairs_match_jiwer]
  CAP-SCORE-003: corpus_summary() gives per-variant totals, corpus WER and CER as total errors over total reference words or characters (None when that total is 0), and the separately labelled unweighted mean of the defined per-utterance WERs; empty references stay in the totals [tests: test_FR_0_3_04_empty_reference_enters_corpus_totals, test_FR_0_3_05_corpus_wer_is_total_errors_over_total_reference_words, test_FR_0_3_05_mean_utterance_wer_excludes_undefined_and_is_labelled, test_FR_0_3_05_corpus_wer_undefined_without_reference_words, test_FR_0_3_05_corpus_cer_is_total_errors_over_total_reference_characters, test_FR_0_3_05_summary_totals_are_sums_of_utterances, test_FR_0_3_07_corpus_totals_and_wer_match_jiwer]
INPUTS AND OUTPUTS: token sequences, or raw reference and hypothesis texts with a clip ID, in; Alignment,
  UtteranceScore and CorpusSummary values out. ValueError or TypeError on bad input.
CONTRACTS: docs/contracts/SCORE_TABLE.md ("Alignment", "Empty references", "Corpus numbers");
  docs/contracts/NORMALISATION.md for the texts that are compared.
INVARIANTS:
  - errors = substitutions + deletions + insertions = the Levenshtein distance; ref_len = hits + substitutions
    + deletions; hyp_len = hits + substitutions + insertions.
  - Corpus WER is total errors / total reference words, never a mean of per-utterance rates.
  - No clock, randomness, environment or hash-order input: the same inputs give the same results.
NOT IN SCOPE:
  - Normalising text (aqis_lab/scoring/normalise.py) and writing tables (aqis_lab/scoring/table.py).
CHANGE LOG:
  2026-09-27 WP-0.3 FR-0.3-04 created (FR-0.3-05 corpus summary, FR-0.3-07 jiwer-compatible tie-break).
"""
import math
from dataclasses import dataclass

from aqis_lab.scoring.normalise import VARIANTS

HIT, SUBSTITUTION, DELETION, INSERTION = "hit", "substitution", "deletion", "insertion"
_DIAGONAL, _DELETE, _INSERT = 0, 1, 2


@dataclass(frozen=True)
class Op:
    """One alignment step; ref_index is None for an insertion, hyp_index is None for a deletion."""
    kind: str
    ref_index: int | None
    hyp_index: int | None


@dataclass(frozen=True)
class Alignment:
    ops: tuple
    hits: int
    substitutions: int
    deletions: int
    insertions: int

    @property
    def ref_len(self):
        return self.hits + self.substitutions + self.deletions

    @property
    def hyp_len(self):
        return self.hits + self.substitutions + self.insertions

    @property
    def errors(self):
        return self.substitutions + self.deletions + self.insertions

    @property
    def rate(self):
        """errors / ref_len, or None when the reference is empty (undefined)."""
        return None if self.ref_len == 0 else self.errors / self.ref_len


def words(text):
    """Tokens of a normalised text: its words, split on single spaces; [] for the empty text."""
    if text == "":
        return []
    tokens = text.split(" ")
    if "" in tokens:
        raise ValueError(f"not a normalised text (empty word from extra spaces): {text!r}")
    return tokens


def characters(text):
    """Tokens of a normalised text for CER: its Unicode code points, the spaces between words included."""
    return list(text)


def _align_middle(ref, hyp):
    """Operations for ref against hyp as (kind, i, j) with local indices; no common prefix or suffix assumed."""
    rows, cols = len(ref), len(hyp)
    if rows == 0 or cols == 0:
        return [(DELETION, i, None) for i in range(rows)] + [(INSERTION, None, j) for j in range(cols)]
    # trace[(i-1)*cols + j-1] is the traceback step at cell (i, j), decided when the cell is computed.
    trace = bytearray(rows * cols)
    prev = list(range(cols + 1))
    for i in range(1, rows + 1):
        token = ref[i - 1]
        cur = [i] + [0] * cols
        base = (i - 1) * cols - 1
        for j in range(1, cols + 1):
            up, left, diag = prev[j], cur[j - 1], prev[j - 1]
            best = diag if token == hyp[j - 1] else diag + 1
            if up + 1 < best:
                best = up + 1
            if left + 1 < best:
                best = left + 1
            cur[j] = best
            if best == up + 1:
                trace[base + j] = _DELETE
            elif left == diag - 1:
                trace[base + j] = _INSERT
            else:
                trace[base + j] = _DIAGONAL
        prev = cur
    ops = []
    i, j = rows, cols
    while i and j:
        step = trace[(i - 1) * cols + j - 1]
        if step == _DELETE:
            i -= 1
            ops.append((DELETION, i, None))
        elif step == _INSERT:
            j -= 1
            ops.append((INSERTION, None, j))
        else:
            i -= 1
            j -= 1
            ops.append((HIT if ref[i] == hyp[j] else SUBSTITUTION, i, j))
    while i:
        i -= 1
        ops.append((DELETION, i, None))
    while j:
        j -= 1
        ops.append((INSERTION, None, j))
    ops.reverse()
    return ops


def align(ref_tokens, hyp_tokens):
    """Minimum-edit alignment of two token sequences, with jiwer 4.0.0's choice among equal-cost alignments."""
    ref, hyp = list(ref_tokens), list(hyp_tokens)
    n, m = len(ref), len(hyp)
    prefix = 0
    while prefix < n and prefix < m and ref[prefix] == hyp[prefix]:
        prefix += 1
    suffix = 0
    while suffix < n - prefix and suffix < m - prefix and ref[n - 1 - suffix] == hyp[m - 1 - suffix]:
        suffix += 1
    ops = [Op(HIT, k, k) for k in range(prefix)]
    for kind, i, j in _align_middle(ref[prefix:n - suffix], hyp[prefix:m - suffix]):
        ops.append(Op(kind, None if i is None else i + prefix, None if j is None else j + prefix))
    ops.extend(Op(HIT, n - suffix + k, m - suffix + k) for k in range(suffix))
    tally = {HIT: 0, SUBSTITUTION: 0, DELETION: 0, INSERTION: 0}
    for op in ops:
        tally[op.kind] += 1
    return Alignment(tuple(ops), tally[HIT], tally[SUBSTITUTION], tally[DELETION], tally[INSERTION])


@dataclass(frozen=True)
class UtteranceScore:
    clip_id: str
    run_card_id: str | None
    variant: str
    normaliser_name: str
    normaliser_version: str
    ref_text: str
    hyp_text: str
    ref_normalised: str
    hyp_normalised: str
    words: Alignment
    chars: Alignment

    @property
    def wer(self):
        return self.words.rate

    @property
    def cer(self):
        return self.chars.rate


def score_utterance(clip_id, ref_text, hyp_text, normaliser, run_card_id=None):
    """Normalise both texts with `normaliser` and align them by words and by characters."""
    ref_norm = normaliser(ref_text)
    hyp_norm = normaliser(hyp_text)
    return UtteranceScore(clip_id=clip_id, run_card_id=run_card_id, variant=normaliser.variant,
                          normaliser_name=normaliser.name, normaliser_version=normaliser.version,
                          ref_text=ref_text, hyp_text=hyp_text, ref_normalised=ref_norm, hyp_normalised=hyp_norm,
                          words=align(words(ref_norm), words(hyp_norm)),
                          chars=align(characters(ref_norm), characters(hyp_norm)))


def score_corpus(pairs, run_card_id):
    """Score (clip_id, reference, hypothesis) triples under every variant, sorted by clip_id, then variant."""
    seen = set()
    scores = []
    for clip_id, ref_text, hyp_text in pairs:
        if clip_id in seen:
            raise ValueError(f"clip_id {clip_id!r} appears more than once")
        seen.add(clip_id)
        for normaliser in VARIANTS.values():
            scores.append(score_utterance(clip_id, ref_text, hyp_text, normaliser, run_card_id))
    scores.sort(key=lambda s: (s.clip_id, s.variant))
    return scores


COUNT_FIELDS = ("hits", "substitutions", "deletions", "insertions", "errors")


@dataclass(frozen=True)
class CorpusSummary:
    variant: str
    normaliser_name: str
    normaliser_version: str
    utterances: int
    empty_references: int
    ref_words: int
    hyp_words: int
    hits: int
    substitutions: int
    deletions: int
    insertions: int
    errors: int
    corpus_wer: float | None
    utterances_with_wer: int
    mean_utterance_wer: float | None
    ref_chars: int
    hyp_chars: int
    char_hits: int
    char_substitutions: int
    char_deletions: int
    char_insertions: int
    char_errors: int
    corpus_cer: float | None

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def corpus_summary(scores):
    """Per-variant corpus totals and rates, in VARIANTS order (main first), for the variants present."""
    scores = list(scores)
    if not scores:
        raise ValueError("no utterances to summarise")
    summaries = {}
    for variant in VARIANTS:
        mine = [s for s in scores if s.variant == variant]
        if not mine:
            continue
        identities = {(s.normaliser_name, s.normaliser_version) for s in mine}
        if len(identities) != 1:
            raise ValueError(f"variant {variant!r} mixes normalisers {sorted(identities)}")
        (name, version), = identities
        word_totals = {f: sum(getattr(s.words, f) for s in mine) for f in COUNT_FIELDS}
        char_totals = {f: sum(getattr(s.chars, f) for s in mine) for f in COUNT_FIELDS}
        ref_words = sum(s.words.ref_len for s in mine)
        ref_chars = sum(s.chars.ref_len for s in mine)
        defined = [s.wer for s in mine if s.wer is not None]
        summaries[variant] = CorpusSummary(
            variant=variant, normaliser_name=name, normaliser_version=version,
            utterances=len(mine), empty_references=len(mine) - len(defined),
            ref_words=ref_words, hyp_words=sum(s.words.hyp_len for s in mine), **word_totals,
            corpus_wer=None if ref_words == 0 else word_totals["errors"] / ref_words,
            utterances_with_wer=len(defined),
            mean_utterance_wer=math.fsum(defined) / len(defined) if defined else None,
            ref_chars=ref_chars, hyp_chars=sum(s.chars.hyp_len for s in mine),
            **{"char_" + f: v for f, v in char_totals.items()},
            corpus_cer=None if ref_chars == 0 else char_totals["errors"] / ref_chars)
    return summaries
