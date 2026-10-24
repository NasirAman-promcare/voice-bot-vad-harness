"""WP-1.2 ruler tests 3 and 4: false interruption rate by definition, and endpoint latency of fixed and predictive policies.

Audio is synthetic tone bursts (speech) in digital silence with known pauses, passed through a frame energy VAD, so every
trigger time is worked out by hand: a policy decides at the end of a frame, and silence is counted in whole frames from the
first frame without speech.
"""
import pytest

from aqis_lab.live import score, turn, vad
from test_s2_vad_score import EnergyVAD, tone_bursts


def speech_flags(total_ms, bursts_ms, frame_ms=20):
    return vad.run_vad(EnergyVAD(frame_ms), tone_bursts(total_ms, bursts_ms)).speech


# the multi-pause turn of ruler test 3: pauses of 400, 700 and 250 ms inside speech, then a 1500 ms end pause
BURSTS = [(0, 1000), (1400, 2000), (2700, 3500), (3750, 4500)]
PAUSES = [(1000, 1400), (2000, 2700), (3500, 3750)]
END_MS = 4500
TOTAL = 6000


@pytest.mark.parametrize("threshold,fi,latency", [(300, 2, 300), (500, 1, 500), (700, 1, 700), (1000, 0, 1000)])
def test_s2_false_interruption_rate_of_a_multi_pause_turn_matches_the_definition(threshold, fi, latency):
    flags = speech_flags(TOTAL, BURSTS)
    triggers = turn.endpoints(turn.FixedSilence(threshold), flags, 20)
    out = score.turn_outcome(triggers, PAUSES, END_MS)
    # pauses of 400, 700 and 250 ms: a timer of T ms fires inside every pause of at least T ms (a 700 ms pause fires a
    # 700 ms timer at the moment speech comes back, which the definition counts)
    assert out.pauses == 3 and out.false_interruptions == fi and out.spurious == 0
    assert out.latency_ms == pytest.approx(latency) and not out.missed_end
    assert out.false_interruptions / out.pauses == pytest.approx(fi / 3)


def test_s2_a_400_ms_pause_does_not_trigger_a_500_ms_timer_and_a_600_ms_end_pause_triggers_at_500_ms():
    flags = speech_flags(3000, [(0, 1000), (1400, 2400)])                 # 400 ms pause inside, 600 ms pause at the end
    triggers = turn.endpoints(turn.FixedSilence(500), flags, 20)
    assert triggers == [2900.0]                                           # speech ends at 2400; 2400 + 500
    out = score.turn_outcome(triggers, [(1000, 1400)], 2400)
    assert out.false_interruptions == 0 and out.latency_ms == pytest.approx(500.0)


def test_s2_silence_before_the_first_speech_never_triggers():
    flags = speech_flags(4000, [(1000, 1600)])
    assert turn.endpoints(turn.FixedSilence(300), flags, 20) == [1900.0]  # 1600 + 300, none during the leading second


def test_s2_one_silence_run_fires_once():
    flags = speech_flags(4000, [(0, 1000)])
    assert turn.endpoints(turn.FixedSilence(300), flags, 20) == [1300.0]


def test_s2_every_silence_run_after_speech_can_fire():
    flags = speech_flags(5000, [(0, 500), (1500, 2000)])
    assert turn.endpoints(turn.FixedSilence(300), flags, 20) == [800.0, 2300.0]


def test_s2_the_timer_counts_whole_frames_of_silence():
    # speech ends at 1010 ms, mid frame: the frame [1000,1020) still holds speech, so silence starts at 1020 and the
    # 300 ms timer fires at 1020 + 300
    flags = speech_flags(3000, [(0, 1010)])
    assert turn.endpoints(turn.FixedSilence(300), flags, 20) == [1320.0]


# ---- predictive policies ---------------------------------------------------------------------------------------
def test_s2_predictive_policy_fires_at_the_first_confident_query_after_the_minimum_silence():
    flags = speech_flags(4000, [(0, 2000)])
    calls = []

    def prob(t_ms):
        calls.append(t_ms)
        return 0.9 if t_ms >= 2400 else 0.2

    policy = turn.Predictive(prob, threshold=0.5, min_silence_ms=200, query_every_ms=100, max_wait_ms=800)
    assert turn.endpoints(policy, flags, 20) == [2400.0]
    assert calls == [2200.0, 2300.0, 2400.0]                              # queried at 200, 300, 400 ms of silence, then stopped


def test_s2_predictive_policy_falls_back_to_the_longest_wait():
    flags = speech_flags(4000, [(0, 2000)])
    policy = turn.Predictive(lambda t: 0.1, threshold=0.5, min_silence_ms=200, query_every_ms=100, max_wait_ms=800)
    assert turn.endpoints(policy, flags, 20) == [2800.0]


def test_s2_predictive_policy_stays_quiet_through_a_short_pause_the_model_calls_unfinished():
    flags = speech_flags(4000, [(0, 1000), (1500, 2500)])                 # 500 ms pause inside
    policy = turn.Predictive(lambda t: 0.1 if t < 2500 else 0.9, 0.5, 200, 100, 800)
    triggers = turn.endpoints(policy, flags, 20)
    assert triggers == [2700.0]      # silent through the 500 ms pause; the first query after the last speech (200 ms after 2500) says finished
    assert score.turn_outcome(triggers, [(1000, 1500)], 2500).false_interruptions == 0


def test_s2_predictive_policy_rejects_queries_that_do_not_fit_the_frame_grid():
    flags = speech_flags(2000, [(0, 500)])
    with pytest.raises(turn.TurnError, match="multiple"):
        turn.endpoints(turn.Predictive(lambda t: 0.0, 0.5, 200, 90, 800), flags, 20)


# ---- outcome of one turn -----------------------------------------------------------------------------------------
def test_s2_outcome_counts_pauses_with_a_trigger_once_and_separates_spurious_triggers():
    out = score.turn_outcome([1300.0, 1350.0, 1700.0, 4800.0], PAUSES, END_MS)
    assert out.pauses == 3 and out.false_interruptions == 1               # two triggers in the first pause count once
    assert out.spurious == 1                                              # 1700 ms is inside speech, in no pause
    assert out.latency_ms == pytest.approx(300.0)


def test_s2_outcome_without_a_trigger_after_the_end_is_a_missed_endpoint():
    out = score.turn_outcome([2300.0], PAUSES, END_MS)
    assert out.missed_end and out.latency_ms is None and out.false_interruptions == 1


def test_s2_outcome_uses_the_first_trigger_after_the_true_end():
    out = score.turn_outcome([4600.0, 5200.0], PAUSES, END_MS)
    assert out.latency_ms == pytest.approx(100.0) and out.false_interruptions == 0


# ---- summary over turns ----------------------------------------------------------------------------------------
def test_s2_turn_summary_by_hand():
    outcomes = [score.TurnOutcome("a", pauses=3, false_interruptions=1, spurious=0, latency_ms=500.0, missed_end=False),
                score.TurnOutcome("b", pauses=2, false_interruptions=0, spurious=2, latency_ms=400.0, missed_end=False),
                score.TurnOutcome("c", pauses=5, false_interruptions=2, spurious=0, latency_ms=None, missed_end=True)]
    s = score.turn_summary(outcomes, resamples=200, seed=1)
    assert s["turns"] == 3 and s["pauses"] == 10
    assert s["fir"] == pytest.approx(3 / 10)                              # (1 + 0 + 2) of (3 + 2 + 5), not a mean of rates
    assert s["latency_p50_ms"] == pytest.approx(450.0)                    # of 400 and 500
    assert s["missed_end_rate"] == pytest.approx(1 / 3) and s["spurious_per_turn"] == pytest.approx(2 / 3)
    lo, hi = s["fir_ci"]
    assert lo <= 0.3 <= hi


# ---- reference pauses and speech segments from word timings -----------------------------------------------------
WORDS = [(0, 300), (350, 700), (1100, 1500), (1520, 1900)]                # gaps of 50, 400 and 20 ms


def test_s2_pauses_are_the_gaps_between_words_of_at_least_the_minimum():
    assert turn.pauses_from_words(WORDS, min_pause_ms=200) == [(700, 1100)]
    assert turn.pauses_from_words(WORDS, min_pause_ms=50) == [(300, 350), (700, 1100)]
    assert turn.pauses_from_words(WORDS, min_pause_ms=10) == [(300, 350), (700, 1100), (1500, 1520)]


def test_s2_speech_segments_join_words_closer_than_the_merge_gap():
    assert turn.speech_segments_from_words(WORDS, merge_gap_ms=100) == [(0, 700), (1100, 1900)]
    assert turn.speech_segments_from_words(WORDS, merge_gap_ms=30) == [(0, 300), (350, 700), (1100, 1900)]
    assert turn.speech_segments_from_words(WORDS, merge_gap_ms=500) == [(0, 1900)]


def test_s2_overlapping_words_make_no_pause_and_join_into_one_segment():
    words = [(0, 500), (400, 900)]
    assert turn.pauses_from_words(words, 10) == [] and turn.speech_segments_from_words(words, 0) == [(0, 900)]


def test_s2_word_timings_from_the_harper_valley_bank_offsets_and_durations():
    # word_offsets_ms are from the segment start, word_durations_ms the length of each word
    assert turn.words_from_offsets([0, 660, 810], [330, 150, 120]) == [(0, 330), (660, 810), (810, 930)]
    with pytest.raises(turn.TurnError, match="same length"):
        turn.words_from_offsets([0, 1], [5])


def test_s2_the_end_of_a_turn_is_the_end_of_its_last_word():
    assert turn.turn_end_ms(WORDS) == 1900
    with pytest.raises(turn.TurnError, match="no words"):
        turn.turn_end_ms([])
