"""Sprint 2 emotion models on four classes: label mapping, a classical acoustic baseline, and the model wrappers.

CAPABILITIES:
  CAP-S2-020: map_scores() turns a model's own label list and scores into the four operational classes (neutral, anger, sadness,
    happiness), keeping the four, dropping every other label and renormalising; crema_label() maps CREMA-D codes to the same
    classes [tests: test_s2_nine_class_scores_are_restricted_to_the_four_classes_and_renormalised,
    test_s2_labels_are_read_after_the_slash_and_in_any_case, test_s2_short_superb_labels_map_too,
    test_s2_labels_missing_a_target_class_are_an_error, test_s2_crema_d_labels_map_to_the_four_classes_and_other_emotions_are_left_out]
  CAP-S2-021: acoustic_features() gives seven classical features of a clip (mean F0, F0 spread and range in semitones, RMS mean
    and spread, syllable rate, voiced ratio); LogisticRegression is the small seeded classifier the baseline trains on them
    [tests: test_s2_pitch_of_a_steady_tone_is_its_frequency, test_s2_pitch_variation_in_semitones_of_two_alternating_tones,
    test_s2_rms_features_of_a_known_amplitude, test_s2_speaking_rate_counts_energy_bursts_per_second,
    test_s2_silence_has_no_pitch_and_zero_voiced_ratio, test_s2_logistic_regression_separates_four_clusters_and_is_deterministic]
  CAP-S2-022: Emotion2Vec, Wav2Vec2Emotion and AcousticBaseline give four class scores for an int16 16 kHz clip; the model
    libraries load when a wrapper is built [no unit test: the models need weights and a GPU stack; the Colab emotion notebook
    runs them]
INPUTS AND OUTPUTS: int16 mono 16 kHz arrays and label lists in; numpy score vectors in CLASSES order out; EmotionError.
CONTRACTS: brief sections 3.4 and 4.
INVARIANTS:
  - Scores are over the four classes only; a model with no label for one of them is refused, never padded.
  - The baseline trains on feature vectors given to fit(), so the caller controls which actors it sees.
NOT IN SCOPE:
  - Choosing which clips are scored (aqis_lab/live/prep.py) and the metrics (aqis_lab/live/score.py).
CHANGE LOG:
  2026-10-24 WP-1.2 created.
"""
import numpy as np

from aqis_lab.bench import lib

CLASSES = ("neutral", "anger", "sadness", "happiness")
SR = 16000
FEATURES = ("f0_mean_hz", "f0_std_semitones", "f0_range_semitones", "rms_mean", "rms_std", "syllable_rate_hz", "voiced_ratio")

_ALIASES = {"neutral": "neutral", "neu": "neutral", "calm": "neutral",
            "anger": "anger", "angry": "anger", "ang": "anger",
            "sadness": "sadness", "sad": "sadness",
            "happiness": "happiness", "happy": "happiness", "hap": "happiness"}
_CREMA = {"NEU": "neutral", "ANG": "anger", "SAD": "sadness", "HAP": "happiness"}


class EmotionError(ValueError):
    """An emotion model's labels or scores cannot be mapped to the four classes."""


def crema_label(code):
    """CREMA-D emotion code (ANG, DIS, FEA, HAP, NEU, SAD) to a class; disgust and fear are not operational classes."""
    return _CREMA.get(str(code).strip().upper())


def map_scores(labels, scores):
    """Scores of the four classes in CLASSES order, renormalised to sum to 1; any other label is dropped."""
    if len(labels) != len(scores):
        raise EmotionError(f"{len(labels)} labels but {len(scores)} scores")
    found = {}
    for label, value in zip(labels, scores):
        name = _ALIASES.get(str(label).split("/")[-1].strip().lower())
        if name is not None:
            found[name] = found.get(name, 0.0) + float(value)
    missing = [c for c in CLASSES if c not in found]
    if missing:
        raise EmotionError(f"the model has no label for {', '.join(missing)} (labels: {list(labels)})")
    out = np.array([found[c] for c in CLASSES], dtype=float)
    total = out.sum()
    if not total > 0:
        raise EmotionError("the four class scores sum to zero")
    return out / total


# ---- classical acoustic features ----------------------------------------------------------------------------------
FRAME_MS, HOP_MS = 25, 10
PITCH_FRAME_MS = 40
F0_MIN_HZ, F0_MAX_HZ = 60.0, 400.0
VOICED_CORRELATION = 0.5
SILENT_RMS = 1e-3                                   # of full scale: below this a frame has no pitch
ONSET_FRACTION = 0.5                                # of the peak energy: a syllable nucleus starts when energy rises past it


def _frames(x, length, hop):
    n = 1 + (len(x) - length) // hop if len(x) >= length else 0
    if n <= 0:
        return np.zeros((0, length))
    return np.stack([x[i * hop:i * hop + length] for i in range(n)])


def _frame_f0(frame, rate):
    """F0 of one frame by autocorrelation, or None when the frame is silent or not periodic."""
    frame = frame - frame.mean()
    r0 = float(np.dot(frame, frame))
    if r0 <= 0:
        return None
    lo, hi = int(rate / F0_MAX_HZ), int(rate / F0_MIN_HZ)
    full = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
    seg = full[lo:hi + 1] / r0
    peak = float(seg.max())
    if peak < VOICED_CORRELATION:
        return None
    # the first local maximum within 10% of the highest: the shortest period, not a multiple of it
    k = next(i for i in range(len(seg)) if seg[i] >= 0.9 * peak
             and (i == 0 or seg[i] >= seg[i - 1]) and (i == len(seg) - 1 or seg[i] >= seg[i + 1]))
    lag = lo + k
    if 0 < k < len(seg) - 1:                         # parabolic refinement of the peak
        a, b, c = seg[k - 1], seg[k], seg[k + 1]
        denom = a - 2 * b + c
        if denom != 0:
            lag += 0.5 * (a - c) / denom
    return rate / lag


def acoustic_features(x, rate=SR):
    """Seven classical features of an int16 or float clip in [-1, 1]."""
    x = np.asarray(x)
    x = x.astype(np.float64) / 32768.0 if x.dtype.kind in "iu" else x.astype(np.float64)
    hop = int(rate * HOP_MS / 1000)
    energy_frames = _frames(x, int(rate * FRAME_MS / 1000), hop)
    rms = np.sqrt((energy_frames ** 2).mean(axis=1)) if len(energy_frames) else np.zeros(0)
    pitch_frames = _frames(x, int(rate * PITCH_FRAME_MS / 1000), hop)
    f0 = [None if np.sqrt((f ** 2).mean()) < SILENT_RMS else _frame_f0(f, rate) for f in pitch_frames]
    voiced = np.array([v for v in f0 if v is not None])
    if len(voiced):
        semitones = 12.0 * np.log2(voiced / np.median(voiced))
        f0_mean, f0_std = float(voiced.mean()), float(semitones.std())
        lo, hi = np.percentile(12.0 * np.log2(voiced), [10, 90])
        f0_range = float(hi - lo)
    else:
        f0_mean = f0_std = f0_range = 0.0
    nuclei = 0
    if len(rms) and rms.max() > 0:
        above = rms > ONSET_FRACTION * rms.max()
        nuclei = int(above[0]) + int((above[1:] & ~above[:-1]).sum())
    seconds = len(x) / rate
    return {"f0_mean_hz": f0_mean, "f0_std_semitones": f0_std, "f0_range_semitones": f0_range,
            "rms_mean": float(rms.mean()) if len(rms) else 0.0, "rms_std": float(rms.std()) if len(rms) else 0.0,
            "syllable_rate_hz": nuclei / seconds if seconds else 0.0,
            "voiced_ratio": len(voiced) / len(pitch_frames) if len(pitch_frames) else 0.0}


class LogisticRegression:
    """Multinomial logistic regression on standardised features: full-batch gradient descent, L2, seeded start."""

    def __init__(self, l2=1e-2, iterations=500, seed=0, rate=0.5):
        self.l2, self.iterations, self.seed, self.rate = l2, iterations, seed, rate

    @staticmethod
    def _softmax(z):
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def fit(self, X, y, n_classes=None):
        X, y = np.asarray(X, dtype=float), np.asarray(y, dtype=int)
        self.mean_, self.scale_ = X.mean(axis=0), X.std(axis=0)
        self.scale_[self.scale_ == 0] = 1.0
        Z = (X - self.mean_) / self.scale_
        k = n_classes or int(y.max()) + 1
        rng = np.random.default_rng(self.seed)
        self.w_ = rng.normal(0, 0.01, (Z.shape[1], k))
        self.b_ = np.zeros(k)
        onehot = np.eye(k)[y]
        for _ in range(self.iterations):
            p = self._softmax(Z @ self.w_ + self.b_)
            g = (p - onehot) / len(Z)
            self.w_ -= self.rate * (Z.T @ g + self.l2 * self.w_)
            self.b_ -= self.rate * g.sum(axis=0)
        return self

    def predict_proba(self, X):
        return self._softmax(((np.asarray(X, dtype=float) - self.mean_) / self.scale_) @ self.w_ + self.b_)


# ---- model wrappers (need weights; run on Colab) ------------------------------------------------------------------
def _float(x):
    x = np.asarray(x)
    return x.astype(np.float32) / 32768.0 if x.dtype.kind in "iu" else x.astype(np.float32)


class Emotion2Vec:
    """emotion2vec+ through FunASR, loaded from Hugging Face; the nine-way output is mapped to four classes."""

    def __init__(self, hf_id, revision=None):
        funasr = lib("funasr")
        kwargs = {"model": hf_id, "hub": "hf", "disable_update": True}
        if revision:
            kwargs["model_revision"] = revision
        self.model = funasr.AutoModel(**kwargs)

    def scores(self, x):
        out = self.model.generate(_float(x), granularity="utterance", extract_embedding=False)
        return map_scores(out[0]["labels"], out[0]["scores"])


class Wav2Vec2Emotion:
    """A Hugging Face audio-classification head with a label per class (superb/wav2vec2-base-superb-er)."""

    def __init__(self, hf_id, revision=None, device="cpu"):
        transformers, torch = lib("transformers"), lib("torch")
        self.torch, self.device = torch, device
        self.extractor = transformers.AutoFeatureExtractor.from_pretrained(hf_id, revision=revision)
        self.model = transformers.AutoModelForAudioClassification.from_pretrained(hf_id, revision=revision).to(device).eval()
        self.labels = [self.model.config.id2label[i] for i in range(self.model.config.num_labels)]

    def scores(self, x):
        inputs = self.extractor(_float(x), sampling_rate=SR, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            probs = self.torch.softmax(self.model(**inputs).logits[0].float(), dim=-1).cpu().numpy()
        return map_scores(self.labels, probs)


class AcousticBaseline:
    """The seven acoustic features and a logistic regression trained on the clips given to fit()."""

    def __init__(self, seed=0):
        self.classifier = LogisticRegression(l2=1e-2, iterations=500, seed=seed)

    @staticmethod
    def vector(x):
        f = acoustic_features(x)
        return [f[k] for k in FEATURES]

    def fit(self, clips, labels):
        self.classifier.fit([self.vector(c) for c in clips], [CLASSES.index(label) for label in labels], len(CLASSES))
        return self

    def scores(self, x):
        return self.classifier.predict_proba([self.vector(x)])[0]
