"""WP-0.8 FR-0.8-01 to FR-0.8-03: the consent form, the campaign A recording guide and the session form.

Expected values come from the spec (docs/specs/phase-0/WP-0.8-consent-fillers-targets.md), the owner's approval
(docs/approvals/WP-0.8.md) and the committed sources (docs/specs/sources/), never from the document under test.
"""
import re

from aqis_docs_testutil import APPROVAL, owner_blanks, read, sections, sentences, words

CONSENT = "docs/recording/CONSENT_FORM.md"
# FR-0.8-01's list, in order, with the plain-English heading the form uses for each (PLAN.md, "Consent form"),
# then the consent block of deviation D2.
CONSENT_SECTIONS = [
    ("purpose", "Why we are recording"),
    ("what is recorded", "What we record"),
    ("how it is stored", "How we store your recordings"),
    ("who can access it", "Who can see them"),
    ("retention period", "How long we keep them"),
    ("right to withdraw", "Your right to withdraw"),
    ("contact", "Contact"),
    ("consent block (D2)", "Your consent"),
]
RETENTION_BLANK = "how long recordings are kept"
CONTACT_BLANK = "contact email/phone"                      # approval question 6 (f), word for word
DURATION_RE = re.compile(r"\d|\b(?:day|week|month|year|decade|forever|indefinite(?:ly)?|permanent(?:ly)?)s?\b",
                         re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d ()-]{6,}\d")
LEGAL_JARGON = ("hereby", "herein", "hereinafter", "whereas", "pursuant", "notwithstanding", "aforementioned",
                "thereof", "heretofore")
# One A4 or US Letter page at 11 pt holds about 500 words; the consent block needs room (PLAN.md, "Consent form").
ONE_PAGE_WORDS = 450


def consent_sections():
    return sections(read(CONSENT), 2)


def retention_problems(text):
    """Why the retention section is not an untouched owner blank (must-catch 1), or [] when it is."""
    body = sections(text, 2).get("How long we keep them")
    if body is None:
        return ["no retention section"]
    problems = []
    if owner_blanks(body) != [RETENTION_BLANK]:
        problems.append(f"owner blanks {owner_blanks(body)!r}, expected exactly [{RETENTION_BLANK!r}]")
    rest = re.sub(r"\[OWNER DECIDES: [^\]\n]+\]", "", body)
    if DURATION_RE.search(rest):
        problems.append(f"a duration or number outside the owner blank: {DURATION_RE.search(rest).group(0)!r}")
    return problems


def contact_problems(text):
    """Why the contact is not left to the owner, or [] (approval question 6 (f))."""
    body = sections(text, 2).get("Contact")
    if body is None:
        return ["no contact section"]
    problems = []
    if CONTACT_BLANK not in owner_blanks(body):
        problems.append(f"no owner blank [OWNER DECIDES: {CONTACT_BLANK}]")
    for rx in (EMAIL_RE, PHONE_RE):
        if rx.search(text):
            problems.append(f"contact detail in the form: {rx.search(text).group(0)!r}")
    return problems


def test_FR_0_8_01_consent_form_has_every_required_section():
    found = consent_sections()
    assert list(found) == [heading for _, heading in CONSENT_SECTIONS]
    for item, heading in CONSENT_SECTIONS:
        assert words(found[heading]), f"section for {item} ({heading!r}) is empty"


def test_FR_0_8_01_retention_is_an_owner_blank_with_no_value():
    assert retention_problems(read(CONSENT)) == []


def test_FR_0_8_01_contact_is_an_owner_blank():
    assert contact_problems(read(CONSENT)) == []


def test_FR_0_8_01_blank_check_detects_a_filled_in_value():
    # The checks above are not empty: an edited copy with a value where the owner decides must fail them.
    text = read(CONSENT)
    blank = f"[OWNER DECIDES: {RETENTION_BLANK}]"
    assert text.count(blank) == 1
    assert retention_problems(text.replace(blank, "2 years")) != []
    assert retention_problems(text.replace(blank, blank + ", at most 2 years")) != []
    contact = f"[OWNER DECIDES: {CONTACT_BLANK}]"
    assert contact_problems(text.replace(contact, "lab@example.org")) != []
    assert contact_problems(text.replace(contact, "+44 20 7946 0000")) != []


def test_FR_0_8_01_fits_one_page_word_budget():
    count = len(words(read(CONSENT)))
    assert 0 < count <= ONE_PAGE_WORDS, count


def test_FR_0_8_01_plain_english_sentences_and_no_legal_jargon():
    text = read(CONSENT)
    lengths = [len(words(s)) for s in sentences(text)]
    assert lengths and sum(lengths) / len(lengths) <= 20, lengths
    assert max(lengths) <= 30, [s for s in sentences(text) if len(words(s)) > 30]
    used = [w for w in LEGAL_JARGON if re.search(rf"\b{w}\b", text, re.I)]
    assert used == []
    # Second person: the form speaks to the reader.
    assert len(re.findall(r"\byour?\b", text, re.I)) >= 10


def test_FR_0_8_01_consent_block_has_signature_date_and_consent_reference():
    text = read(CONSENT)
    block = consent_sections()["Your consent"]
    boxes = re.findall(r"^- \[ \] (.+)$", block, re.M)
    assert len(boxes) >= 3, boxes
    assert any("read this form" in b for b in boxes)
    assert any("18 years or older" in b for b in boxes)                 # approval question 6 (d)
    assert any("agree to be recorded" in b for b in boxes)
    for field in ("Name", "Signature", "Date"):
        assert re.search(rf"^{field}: _{{4,}}", block, re.M), field
    # The consent reference (approval question 5: ca-cNNN) is written on the form by the lab, never a name.
    assert re.search(r"^Consent reference[^\n]*: ca-c_{3,}", text, re.M)


def _approval_fact(label):
    m = re.search(rf"^\s*\* \({label}\) [^:]+: (.+)$", APPROVAL.read_text(encoding="utf-8"), re.M)
    assert m, label
    return m.group(1)


def test_FR_0_8_01_owner_facts_appear_as_given():
    # Facts only the owner can give (approval question 6) appear in the form as the owner wrote them. Each phrase is
    # first found in the approval, so the test cannot pass on a phrase the owner did not write.
    text = re.sub(r"\s+", " ", read(CONSENT)).lower()
    phrases = {
        "a": ["Only the AQIS test lab owner (@Nasir) and authorized project raters/evaluators"],
        "b": ["Google Drive (AQIS_LAB), Google Colab, and Oracle Cloud VM", "Audio is never stored on GitHub"],
        "c": ["Testing, benchmark measurement, and error diagnosis for voice bot pipelines"],
        "d": ["18 years or older"],
        "e": ["within 30 days of recording", "deleted from active dataset pools"],
    }
    for label, wanted in phrases.items():
        fact = _approval_fact(label)
        for phrase in wanted:
            assert phrase in fact, (label, phrase)
            assert phrase.lower() in text, (label, phrase)
