"""FR-0.3-01 and FR-0.3-03: the wrapped Whisper English normaliser, its fixed point, variants and identity."""
import copy
import hashlib
import importlib
import importlib.metadata as md
import io
import json
import re
import tarfile
import urllib.request
import warnings

import pytest

from aqis_scoring_testutil import (KEEP_NAME, MAIN_NAME, NORMALISATION_DOC, NORMALISER_VERSION,
                                   PINNED_WHISPER_NORMALIZER, RUN_CARD_FIXTURE, WHISPER_FILLERS, generated_texts,
                                   markdown_tables)
from aqis_testutil import parse_lock

from aqis_lab.scoring import normalise as N

# Seeded inputs for the property tests (the seeds are recorded here, per the Phase 0 randomness convention).
PROPERTY_SEED = 20260927
PROPERTY_COUNT = 20000


def whisper_class():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        from whisper_normalizer.english import EnglishTextNormalizer
    return EnglishTextNormalizer


@pytest.fixture(scope="module")
def plain_whisper():
    """The package's own normalisers, built here from the approved definition (plan, "Normalisers")."""
    cls = whisper_class()
    main = cls()
    keep = cls()
    keep.ignore_patterns = r"(?!)"
    return {"main": main, "disfluency_aware": keep}


@pytest.fixture(scope="module")
def property_texts():
    return generated_texts(PROPERTY_SEED, PROPERTY_COUNT)


def test_FR_0_3_01_exposes_name_and_version():
    assert N.MAIN.name == MAIN_NAME
    assert N.DISFLUENCY_AWARE.name == KEEP_NAME
    assert N.MAIN.version == N.DISFLUENCY_AWARE.version == NORMALISER_VERSION
    assert N.VARIANTS == {"main": N.MAIN, "disfluency_aware": N.DISFLUENCY_AWARE}
    assert N.normaliser_identity() == {"name": MAIN_NAME, "version": NORMALISER_VERSION}
    assert N.MAIN.identity() == {"name": MAIN_NAME, "version": NORMALISER_VERSION}
    assert N.DISFLUENCY_AWARE.identity() == {"name": KEEP_NAME, "version": NORMALISER_VERSION}


def test_FR_0_3_01_identity_fits_the_run_card_contract():
    from aqis_lab.contracts.canonical import compute_run_card_id
    from aqis_lab.contracts.validate import validate_run_card

    card = copy.deepcopy(json.loads(RUN_CARD_FIXTURE.read_text(encoding="utf-8")))
    card["normaliser"] = N.normaliser_identity()
    card["run_card_id"] = compute_run_card_id(card)
    validate_run_card(card)


def test_FR_0_3_01_installed_package_is_the_pinned_version():
    assert N.WHISPER_NORMALIZER_VERSION == PINNED_WHISPER_NORMALIZER
    assert parse_lock()["whisper-normalizer"]["version"] == PINNED_WHISPER_NORMALIZER
    assert md.version("whisper-normalizer") == PINNED_WHISPER_NORMALIZER
    N.check_package_version(md.version("whisper-normalizer"))


@pytest.mark.parametrize("installed", ["0.1.15", "0.1.2", "0.0.10", "0.1.1.post1"])
def test_FR_0_3_01_refuses_other_package_version(installed):
    with pytest.raises(N.NormaliserVersionError) as exc:
        N.check_package_version(installed)
    assert installed in str(exc.value) and PINNED_WHISPER_NORMALIZER in str(exc.value)


def test_FR_0_3_01_refuses_missing_package():
    with pytest.raises(N.NormaliserVersionError, match="not installed"):
        N.check_package_version(None)


def test_FR_0_3_01_equals_whisper_where_whisper_is_idempotent(plain_whisper, property_texts):
    compared = {"main": 0, "disfluency_aware": 0}
    for text in property_texts:
        for variant, whisper in plain_whisper.items():
            once = whisper(text).strip()
            if whisper(once).strip() == once:
                assert N.VARIANTS[variant](text) == once, (variant, text)
                compared[variant] += 1
    # Most generated inputs are already idempotent under plain Whisper; the comparison must not be empty.
    assert min(compared.values()) > PROPERTY_COUNT * 0.8, compared


def test_FR_0_3_01_idempotent_on_generated_inputs(property_texts):
    for text in property_texts:
        for variant, normaliser in N.VARIANTS.items():
            once = normaliser(text)
            assert normaliser(once) == once, (variant, text, once)


@pytest.mark.parametrize("text, first_pass, fixed", [
    ("minus five", "-5", "5"),
    ("oh one", "01", "one"),
    ("double oh seven", "007", "7"),
    ("$1.50", " one.50", "one.50"),
])
def test_FR_0_3_01_known_non_idempotent_inputs_reach_fixed_point(plain_whisper, text, first_pass, fixed):
    # Plan finding 4: plain Whisper is not idempotent on these inputs (a second pass changes the text).
    assert plain_whisper["main"](text) == first_pass
    assert plain_whisper["main"](first_pass) != first_pass
    for normaliser in N.VARIANTS.values():
        assert normaliser(text) == fixed
        assert normaliser(fixed) == fixed


def test_FR_0_3_01_fixed_point_raises_when_not_reached():
    with pytest.raises(N.NormalisationError) as exc:
        N.fixed_point(str.swapcase, "abc", max_passes=10)
    assert "'abc'" in str(exc.value) and "10" in str(exc.value)
    calls = []

    def settles_after_three(text):
        calls.append(text)
        return text if len(text) >= 3 else text + "x"

    assert N.fixed_point(settles_after_three, "", max_passes=4) == "xxx"
    assert len(calls) == 4
    calls.clear()
    with pytest.raises(N.NormalisationError):
        N.fixed_point(settles_after_three, "", max_passes=3)
    assert N.MAX_PASSES == 10


@pytest.mark.parametrize("value", [None, b"hello", 5, ["hello"]])
def test_FR_0_3_01_rejects_non_text_input(value):
    for normaliser in N.VARIANTS.values():
        with pytest.raises(TypeError):
            normaliser(value)
    with pytest.raises(TypeError):
        N.normalise(value)
    with pytest.raises(TypeError):
        N.normalise_keep_disfluencies(value)


def test_FR_0_3_01_output_has_single_spaces_and_no_edge_spaces(property_texts):
    for text in property_texts[:5000] + ["", "   ", "\t\n", "  Hello \n\n WORLD  "]:
        for normaliser in N.VARIANTS.values():
            out = normaliser(text)
            assert out == out.strip(), text
            assert "  " not in out, text
            assert not re.search(r"[^\S ]", out), text
    assert N.normalise("  Hello \n\n WORLD  ") == "hello world"
    assert N.normalise("") == "" and N.normalise(" \t ") == ""


@pytest.mark.parametrize("mark", ["’", "‘", "ʼ"])
def test_FR_0_3_01_typographic_apostrophes_fold_to_ascii(plain_whisper, mark):
    # Plan question 4 (approved): without folding, Whisper does not expand the contraction ("don t" for
    # U+2018/U+2019, which are punctuation; "donʼt" for U+02BC, which Unicode classes as a letter).
    assert plain_whisper["main"](f"don{mark}t") == ("don\u02bct" if mark == "\u02bc" else "don t")
    for normaliser in N.VARIANTS.values():
        assert normaliser(f"don{mark}t") == normaliser("don't") == "do not"
        assert normaliser(f"I{mark}m sure it{mark}s fine") == "i am sure it is fine"
    assert N.normalise("‘quoted’ text") == "quoted text"


def test_FR_0_3_01_module_functions_are_the_two_variants():
    for text in ("Um, I have twenty-five dollars.", "uh-huh", "hmm OK"):
        assert N.normalise(text) == N.MAIN(text)
        assert N.normalise_keep_disfluencies(text) == N.DISFLUENCY_AWARE(text)


# The original OpenAI code: openai-whisper 20250625, source archive only (plan finding 3).
OPENAI_SDIST_URL = ("https://files.pythonhosted.org/packages/35/8e/d36f8880bcf18ec026a55807d02fe4c7357da9f25aebd92f8"
                    "5178000c0dc/openai_whisper-20250625.tar.gz")
OPENAI_SDIST_SHA256 = "37a91a3921809d9f44748ffc73c0a55c9f366c85a3ef5c2ae0cc09540432eb96"


@pytest.mark.slow
@pytest.mark.network
def test_FR_0_3_01_matches_openai_whisper_original(tmp_path, monkeypatch, plain_whisper):
    data = urllib.request.urlopen(OPENAI_SDIST_URL, timeout=120).read()
    assert hashlib.sha256(data).hexdigest() == OPENAI_SDIST_SHA256
    package = tmp_path / "openai_whisper_original"
    (package / "normalizers").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        wanted = {"__init__.py", "basic.py", "english.py", "english.json"}
        found = set()
        for member in archive.getmembers():
            parts = member.name.split("/")
            if parts[-3:-1] == ["whisper", "normalizers"] and parts[-1] in wanted and member.isfile():
                (package / "normalizers" / parts[-1]).write_bytes(archive.extractfile(member).read())
                found.add(parts[-1])
        assert found == wanted
    monkeypatch.syspath_prepend(str(tmp_path))
    original = importlib.import_module("openai_whisper_original.normalizers").EnglishTextNormalizer()
    texts = generated_texts(PROPERTY_SEED + 1, 20000, max_tokens=9)
    differences = [t for t in texts if original(t) != plain_whisper["main"](t)]
    assert differences == []


def _documented_fillers():
    for heading, header, rows, _ in markdown_tables(NORMALISATION_DOC.read_text(encoding="utf-8")):
        if heading.startswith("Filler list"):
            assert header[:2] == ["Filler", "Disfluency-aware output"], header
            return [(r[0].strip("`"), r[1].strip("`")) for r in rows]
    raise AssertionError("NORMALISATION.md has no 'Filler list' table")


@pytest.mark.parametrize("filler", WHISPER_FILLERS)
def test_FR_0_3_03_main_removes_each_listed_filler(filler):
    for form in (filler, filler.upper(), filler.capitalize() + ","):
        assert N.normalise(f"well {form} yes") == "well yes"
        assert N.MAIN(f"{form} I think") == "i think"
    assert N.normalise(filler) == ""


# Whisper's spelling map writes "mhm" and "mmm" as "hmm" (english.json); the filler is kept in that spelling.
KEPT_AS = {"hmm": "hmm", "mm": "mm", "mhm": "hmm", "mmm": "hmm", "uh": "uh", "um": "um"}


@pytest.mark.parametrize("filler", WHISPER_FILLERS)
def test_FR_0_3_03_disfluency_aware_keeps_each_listed_filler(filler):
    for form in (filler, filler.upper(), filler.capitalize() + ","):
        assert N.normalise_keep_disfluencies(f"well {form} yes") == f"well {KEPT_AS[filler]} yes"
    assert N.DISFLUENCY_AWARE(filler) == KEPT_AS[filler]


def test_FR_0_3_03_documented_filler_list_matches_normaliser():
    documented = _documented_fillers()
    assert tuple(f for f, _ in documented) == WHISPER_FILLERS == N.FILLERS
    assert dict(documented) == KEPT_AS
    # The pinned class removes exactly this list; the wrapper refuses a class whose pattern differs.
    assert whisper_class()().ignore_patterns == r"\b(" + "|".join(WHISPER_FILLERS) + r")\b"
