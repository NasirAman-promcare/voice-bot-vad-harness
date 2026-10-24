"""Turn-end detection: fixed silence timers and predictive policies on a VAD's frame decisions, and reference pauses.

CAPABILITIES:
  CAP-S2-007: FixedSilence and Predictive are endpoint policies; endpoints() runs one over a clip's speech flags and returns the
    times (ms) at which it fired. A policy decides at the end of a frame, counts silence in whole frames from the first frame
    without speech, never fires before the first speech and fires at most once per silence run. Predictive queries a
    completion probability (a model's) every query_every_ms once min_silence_ms of silence has passed, fires when it reaches
    the threshold, and falls back to firing at max_wait_ms [tests:
    test_s2_a_400_ms_pause_does_not_trigger_a_500_ms_timer_and_a_600_ms_end_pause_triggers_at_500_ms,
    test_s2_silence_before_the_first_speech_never_triggers, test_s2_one_silence_run_fires_once,
    test_s2_every_silence_run_after_speech_can_fire, test_s2_the_timer_counts_whole_frames_of_silence,
    test_s2_predictive_policy_fires_at_the_first_confident_query_after_the_minimum_silence,
    test_s2_predictive_policy_falls_back_to_the_longest_wait,
    test_s2_predictive_policy_stays_quiet_through_a_short_pause_the_model_calls_unfinished,
    test_s2_predictive_policy_rejects_queries_that_do_not_fit_the_frame_grid]
  CAP-S2-008: words_from_offsets(), pauses_from_words(), speech_segments_from_words() and turn_end_ms() turn word timings (HarperValleyBank's
    machine word offsets and durations) into the reference mid-turn pauses, speech segments and end of turn [tests:
    test_s2_pauses_are_the_gaps_between_words_of_at_least_the_minimum,
    test_s2_speech_segments_join_words_closer_than_the_merge_gap, test_s2_overlapping_words_make_no_pause_and_join_into_one_segment,
    test_s2_word_timings_from_the_harper_valley_bank_offsets_and_durations, test_s2_the_end_of_a_turn_is_the_end_of_its_last_word]
  CAP-S2-009: SmartTurn (the Pipecat Smart Turn ONNX model on the last 8 s of audio) gives the completion probability a Predictive
    policy asks for. It needs onnxruntime, transformers and the weights, so the Oracle smoke run checks it; it has no unit test.
    TEN Turn Detection is not built: see docs/progress/WP-1.2/PLAN.md.
INPUTS AND OUTPUTS: boolean speech flags per frame and a frame length in ms in; trigger times in ms out; TurnError.
CONTRACTS: brief sections 3.2 and 4 (fixed timers of 300, 500, 700 and 1000 ms; Smart Turn with a longest wait of 800 ms).
INVARIANTS:
  - Trigger times are decision times: the end of the frame at which the policy fired.
  - A policy sees the frames up to the current one only.
NOT IN SCOPE:
  - Scoring triggers against pauses (aqis_lab/live/score.py) and the VAD (aqis_lab/live/vad.py).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import numpy as np

from aqis_lab.bench import lib


class TurnError(ValueError):
    """A turn policy or reference cannot be built as asked."""


class EndpointPolicy:
    def reset(self):
        self.fired = False

    def step(self, t_end_ms, silence_ms):
        """True when the policy fires now; called once per frame with the silence so far (0 during speech)."""
        raise TurnError(f"{type(self).__name__} does not define step")


class FixedSilence(EndpointPolicy):
    def __init__(self, threshold_ms):
        self.threshold_ms = threshold_ms
        self.reset()

    def step(self, t_end_ms, silence_ms):
        return silence_ms >= self.threshold_ms


class Predictive(EndpointPolicy):
    def __init__(self, prob_fn, threshold, min_silence_ms, query_every_ms, max_wait_ms):
        self.prob_fn, self.threshold = prob_fn, threshold
        self.min_silence_ms, self.query_every_ms, self.max_wait_ms = min_silence_ms, query_every_ms, max_wait_ms
        self.reset()

    def step(self, t_end_ms, silence_ms):
        if silence_ms >= self.max_wait_ms:
            return True
        if silence_ms >= self.min_silence_ms and (silence_ms - self.min_silence_ms) % self.query_every_ms == 0:
            return self.prob_fn(t_end_ms) >= self.threshold
        return False


def endpoints(policy, speech_flags, frame_ms):
    """Trigger times (ms) of `policy` over per-frame speech flags: at most one per silence run that follows speech."""
    if isinstance(policy, Predictive):
        for name, value in (("min_silence_ms", policy.min_silence_ms), ("query_every_ms", policy.query_every_ms)):
            if value % frame_ms:
                raise TurnError(f"{name} {value} is not a multiple of the {frame_ms} ms frame")
    triggers, spoken, silent_frames, fired = [], False, 0, False
    for k, flag in enumerate(speech_flags):
        t_end = (k + 1) * float(frame_ms)
        if flag:
            spoken, silent_frames, fired = True, 0, False
            continue
        silent_frames += 1
        if spoken and not fired and policy.step(t_end, silent_frames * frame_ms):
            triggers.append(t_end)
            fired = True
    return triggers


# ---- reference pauses and segments ------------------------------------------------------------------------------
def words_from_offsets(offsets_ms, durations_ms):
    if len(offsets_ms) != len(durations_ms):
        raise TurnError(f"word offsets and durations must have the same length ({len(offsets_ms)} and {len(durations_ms)})")
    return [(int(o), int(o) + int(d)) for o, d in zip(offsets_ms, durations_ms)]


def pauses_from_words(words, min_pause_ms):
    """Gaps between consecutive words that last at least min_pause_ms, as (start, end) in ms."""
    return [(a_end, b_start) for (_, a_end), (b_start, _) in zip(words, words[1:]) if b_start - a_end >= min_pause_ms]


def speech_segments_from_words(words, merge_gap_ms):
    """Words joined into segments when the gap between them is at most merge_gap_ms."""
    segments = []
    for start, end in words:
        if segments and start - segments[-1][1] <= merge_gap_ms:
            segments[-1] = (segments[-1][0], max(segments[-1][1], end))
        else:
            segments.append((start, end))
    return segments


def turn_end_ms(words):
    if not words:
        raise TurnError("a turn with no words has no end")
    return max(end for _, end in words)


# ---- completion models -----------------------------------------------------------------------------------------
class SmartTurn:
    """Pipecat Smart Turn: P(turn complete) from the last 8 s of audio up to the query time."""

    def __init__(self, onnx_path):
        ort = lib("onnxruntime")
        options = ort.SessionOptions()
        options.inter_op_num_threads = options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(str(onnx_path), sess_options=options, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.extractor = lib("transformers").WhisperFeatureExtractor(chunk_length=8)

    def probability(self, samples16k):
        x = np.asarray(samples16k)
        x = (x.astype(np.float32) / 32768.0) if x.dtype.kind in "iu" else x.astype(np.float32)
        x = x[-8 * 16000:]
        inputs = self.extractor(x, sampling_rate=16000, return_tensors="np", padding="max_length", max_length=8 * 16000,
                                truncation=True, do_normalize=True)
        features = inputs.input_features.astype(np.float32)
        return float(self.session.run(None, {self.input_name: features})[0].reshape(-1)[0])
