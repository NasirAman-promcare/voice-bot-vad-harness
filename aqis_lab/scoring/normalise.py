"""The lab's text normalisers: Whisper's English normaliser, pinned, applied until a fixed point.

CAPABILITIES:
  CAP-SCORE-001: MAIN (fillers removed) and DISFLUENCY_AWARE (fillers kept) wrap whisper-normalizer 0.1.1's EnglishTextNormalizer; typographic apostrophes fold to "'"; each normaliser repeats Whisper until the text stops changing (idempotent), refuses non-text input, a text that never settles and any other installed package version, and exposes its name and version [tests: test_FR_0_3_01_exposes_name_and_version, test_FR_0_3_01_identity_fits_the_run_card_contract, test_FR_0_3_01_installed_package_is_the_pinned_version, test_FR_0_3_01_refuses_other_package_version, test_FR_0_3_01_refuses_missing_package, test_FR_0_3_01_equals_whisper_where_whisper_is_idempotent, test_FR_0_3_01_idempotent_on_generated_inputs, test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point, test_FR_0_3_01_fixed_point_raises_when_not_reached, test_FR_0_3_01_rejects_non_text_input, test_FR_0_3_01_output_has_single_spaces_and_no_edge_spaces, test_FR_0_3_01_typographic_apostrophes_fold_to_ascii, test_FR_0_3_01_module_functions_are_the_two_variants, test_FR_0_3_03_main_removes_each_listed_filler, test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler, test_FR_0_3_03_documented_filler_list_matches_normaliser, test_FR_0_3_02_documented_example]
INPUTS AND OUTPUTS: a str in; the normalised str out (lower case, single spaces, no leading or trailing
  space, possibly empty). NormaliserVersionError, NormalisationError or TypeError on failure.
CONTRACTS: docs/contracts/NORMALISATION.md (behaviour, examples, filler list, names and versions); the
  run-card v1 `normaliser` object ({name, version}) from normaliser_identity().
INVARIANTS:
  - normalise(normalise(x)) == normalise(x) for every str x: the result is always a fixed point of one step,
    or NormalisationError is raised; never a text that is still changing.
  - Where one Whisper pass is already a fixed point, the result equals Whisper's output with its ends trimmed.
  - The two variants differ only in Whisper's filler pattern; nothing else is configured.
  - The word map is read from the installed package; no network access, clock, randomness or locale input.
  - Only the SyntaxWarning that Python 3.13 raises while compiling whisper-normalizer 0.1.1's basic.py
    (an invalid escape inside a docstring) is ignored, and only during that import.
NOT IN SCOPE:
  - Tokenising, alignment and error rates (aqis_lab/scoring/wer.py).
CHANGE LOG:
  2026-09-27 WP-0.3 FR-0.3-01 created (approved plan questions 1 to 4: fixed point, whisper-normalizer 0.1.1,
             Whisper's filler list, typographic apostrophes).
"""
import importlib.metadata
import warnings

WHISPER_NORMALIZER_DIST = "whisper-normalizer"
WHISPER_NORMALIZER_VERSION = "0.1.1"
# Version of the lab's own rules on top of Whisper (fixed point, trimmed ends, apostrophe folding).
WRAPPER_RULES_VERSION = "1"
NORMALISER_VERSION = f"{WRAPPER_RULES_VERSION}+whisper-normalizer-{WHISPER_NORMALIZER_VERSION}"

# Whisper's own filler list, in the order of its pattern (approved plan question 3).
FILLERS = ("hmm", "mm", "mhm", "mmm", "uh", "um")
WHISPER_FILLER_PATTERN = r"\b(" + "|".join(FILLERS) + r")\b"
NEVER_MATCHES = r"(?!)"

MAX_PASSES = 10
TYPOGRAPHIC_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


class NormaliserVersionError(RuntimeError):
    """The installed Whisper normaliser package is missing, another version, or not the expected code."""


class NormalisationError(ValueError):
    """Normalisation did not reach a fixed point."""


def installed_package_version():
    """The installed version of whisper-normalizer, or None when it is not installed."""
    try:
        return importlib.metadata.version(WHISPER_NORMALIZER_DIST)
    except importlib.metadata.PackageNotFoundError:
        return None


def check_package_version(installed):
    """Raise NormaliserVersionError unless `installed` is the pinned version."""
    fix = "install requirements/aqis_lab/phase0.txt (bash aqis_lab/deploy/dev_bootstrap.sh)"
    if installed is None:
        raise NormaliserVersionError(
            f"{WHISPER_NORMALIZER_DIST} is not installed; the lab needs version {WHISPER_NORMALIZER_VERSION}: {fix}")
    if installed != WHISPER_NORMALIZER_VERSION:
        raise NormaliserVersionError(
            f"{WHISPER_NORMALIZER_DIST} {installed} is installed, but the lab normaliser is pinned to "
            f"{WHISPER_NORMALIZER_VERSION} (other versions change the output): {fix}")


def fixed_point(step, text, max_passes=MAX_PASSES):
    """Apply `step` until its output equals its input, calling it at most `max_passes` times."""
    current = text
    for _ in range(max_passes):
        following = step(current)
        if following == current:
            return current
        current = following
    raise NormalisationError(f"normalisation did not reach a fixed point within {max_passes} passes for input "
                             f"{text!r}; last output {current!r}")


def _whisper_english_normaliser():
    check_package_version(installed_package_version())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        from whisper_normalizer.english import EnglishTextNormalizer
    engine = EnglishTextNormalizer()
    if engine.ignore_patterns != WHISPER_FILLER_PATTERN:
        raise NormaliserVersionError(f"{WHISPER_NORMALIZER_DIST} filler pattern is {engine.ignore_patterns!r}, "
                                     f"expected {WHISPER_FILLER_PATTERN!r}")
    return engine


class Normaliser:
    """One scoring normaliser: a name, a version and a call that returns the normalised text."""

    def __init__(self, variant, name, keeps_disfluencies):
        self.variant = variant
        self.name = name
        self.version = NORMALISER_VERSION
        self.keeps_disfluencies = keeps_disfluencies
        self._engine = None

    def __repr__(self):
        return f"Normaliser({self.variant!r}, name={self.name!r}, version={self.version!r})"

    def identity(self):
        return {"name": self.name, "version": self.version}

    def _step(self, text):
        if self._engine is None:
            engine = _whisper_english_normaliser()
            if self.keeps_disfluencies:
                engine.ignore_patterns = NEVER_MATCHES
            self._engine = engine
        return self._engine(text.translate(TYPOGRAPHIC_APOSTROPHES)).strip()

    def __call__(self, text):
        if not isinstance(text, str):
            raise TypeError(f"{self.name} normalises str only, got {type(text).__name__}")
        return fixed_point(self._step, text)


MAIN = Normaliser("main", "aqis-whisper-english", keeps_disfluencies=False)
DISFLUENCY_AWARE = Normaliser("disfluency_aware", "aqis-whisper-english-keep-disfluencies", keeps_disfluencies=True)
VARIANTS = {"main": MAIN, "disfluency_aware": DISFLUENCY_AWARE}


def normalise(text):
    """The main score's normalisation (Whisper's fillers removed)."""
    return MAIN(text)


def normalise_keep_disfluencies(text):
    """The disfluency-aware score's normalisation (fillers kept)."""
    return DISFLUENCY_AWARE(text)


def normaliser_identity():
    """The run card's `normaliser` object: the main normaliser's name and version."""
    return MAIN.identity()
