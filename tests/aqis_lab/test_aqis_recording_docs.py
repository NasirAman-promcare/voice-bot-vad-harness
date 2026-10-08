"""WP-0.8 FR-0.8-01 to FR-0.8-03: the consent form, the campaign A recording guide and the session form.

Expected values come from the spec (docs/specs/phase-0/WP-0.8-consent-fillers-targets.md), the owner's approval
(docs/approvals/WP-0.8.md) and the committed sources (docs/specs/sources/), never from the document under test.
"""
import re

import csv

import pytest

from aqis_docs_testutil import APPROVAL, ROOT, SOURCES, owner_blanks, read, sections, sentences, table_with, words

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
    """The owner's answer to question 6 (`label` a to f) in docs/approvals/WP-0.8.md, without its final period."""
    m = re.search(rf"^\s*\* \({label}\) [^:]+: (.+)$", APPROVAL.read_text(encoding="utf-8"), re.M)
    assert m, label
    return m.group(1).strip().rstrip(".")


def _flat(text):
    return re.sub(r"\s+", " ", text).strip()


def expected_owner_fact_sections():
    """{section: exact text} for the consent form's owner-fact sections, built from the approval's wording.

    The owner's words (question 6 (a), (b), (c), (e), and question 5 for the signed form) fill the slots; the rest is
    the form's fixed connecting prose. A section that differs in any word, including one added beside the owner's
    wording, does not match (WP-0.8-F01, F03).
    """
    approval = APPROVAL.read_text(encoding="utf-8")
    assert re.search(r"^- Question 5 \(Consent scheme\):.*Signed consent forms kept offline by owner\.", approval, re.M)
    services, github = _approval_fact("b").split(". ")
    window, outcome = _approval_fact("e").split("; ")
    return {
        "Why we are recording":
            f"The AQIS Test Lab checks how well voice bot software works. We use your recordings for "
            f"{_approval_fact('c')}. For example, we test how well software hears when you speak, writes down what "
            f"you say and reads your tone of voice.",
        "How we store your recordings":
            f"Your recordings are stored and processed only in {services}. {github}. The lab owner keeps this signed "
            f"form offline, apart from your recordings.",
        "Who can see them": f"{_approval_fact('a')} can see or hear your recordings.",
        "Your right to withdraw":
            f"Taking part is your choice. You can withdraw {window}, and you do not need to give a reason. To "
            f"withdraw, contact us and give your consent reference. Your recordings will then be {outcome}.",
    }


def expected_tick_boxes():
    window = _approval_fact("e").split("; ")[0]
    return ["I have read this form, or someone has read it to me.", f"I am {_approval_fact('d')}.",
            "I agree to be recorded for the purpose above.", f"I understand that I can withdraw {window}."]


def owner_fact_problems(text):
    """Why the consent form's owner facts differ from the approval's wording, section by section, or []."""
    found = sections(text, 2)
    problems = []
    for heading, expected in expected_owner_fact_sections().items():
        actual = _flat(found.get(heading, ""))
        if actual != _flat(expected):
            problems.append(f"section {heading!r} is {actual!r}, expected {_flat(expected)!r}")
    # The whole consent block participants tick and sign (WP-0.8-F09): every non-empty line, in order, is the intro
    # line, one of the 4 expected tick boxes (unticked; any list marker is read as a tick box, as GitHub renders it),
    # or one of the Name, Signature and Date fill-in lines. Nothing else may appear.
    expected = ([("text", "Tick each box that is true for you.")] + [("box", " ", b) for b in expected_tick_boxes()]
                + [("field", f) for f in ("Name", "Signature", "Date")])
    actual = []
    for line in found.get("Your consent", "").splitlines():
        line = line.strip()
        if not line:
            continue
        box = re.match(r"^[-*+] \[([ xX])\] (.+)$", line)
        field = re.fullmatch(r"(Name|Signature|Date): _{4,}", line)
        if box:
            actual.append(("box", box.group(1), _flat(box.group(2))))
        elif field:
            actual.append(("field", field.group(1)))
        else:
            actual.append(("text", _flat(line)))
    if actual != expected:
        problems.append(f"consent block {actual!r}, expected {expected!r}")
    return problems


def test_FR_0_8_01_owner_facts_appear_as_given():
    # Facts only the owner can give (approval questions 5 and 6, docs/approvals/WP-0.8.md) appear in their own sections
    # and tick boxes exactly as the owner wrote them, with nothing changed or added (WP-0.8-F01, F02, F03).
    assert owner_fact_problems(read(CONSENT)) == []


# The auditor's round 1 breaks (docs/progress/WP-0.8/AUDIT.md): M1h changes the owner's withdrawal window in its own
# section only (the tick box keeps it); E1 to E3 add promises the owner never made beside the owner's wording.
OWNER_FACT_BREAKS = {
    "M1h-window-14-days": ("You can withdraw within 30 days of recording,", "You can withdraw within 14 days of recording,"),
    "E1-wider-access": ("raters/evaluators can see or hear your recordings.",
                        "raters/evaluators can see or hear your recordings, and our technology partners may also hear them."),
    "E2-training-and-sale": ("error diagnosis for voice bot pipelines.",
                             "error diagnosis for voice bot pipelines, and to train and sell speech models."),
    "E3-deletion-deadline": ("deleted from active dataset pools.",
                             "deleted from active dataset pools within 7 days of your request."),
    "tick-box-window": ("- [ ] I understand that I can withdraw within 30 days of recording.",
                        "- [ ] I understand that I can withdraw at any time."),
    "tick-box-age": ("- [ ] I am 18 years or older.", "- [ ] I am 16 years or older."),
    "services-added": ("Google Colab, and Oracle Cloud VM.", "Google Colab, Oracle Cloud VM, and a paid speech API."),
    # Round 2 audit (WP-0.8-F09): additions to the consent block participants tick and sign.
    "X1-consent-block-sentence": ("Tick each box that is true for you.",
                                  "Tick each box that is true for you.\n\nBy signing, you also agree that our technology "
                                  "partners may hear your recordings."),
    "X2-extra-tick-box-star": ("- [ ] I understand that I can withdraw within 30 days of recording.",
                               "- [ ] I understand that I can withdraw within 30 days of recording.\n* [ ] I agree that "
                               "our technology partners may hear my recordings."),
    "X2-extra-tick-box-plus-checked": ("- [ ] I agree to be recorded for the purpose above.",
                                       "- [ ] I agree to be recorded for the purpose above.\n+ [x] I agree that our "
                                       "technology partners may hear my recordings."),
    # Round 2 audit (WP-0.8-F10): a whole sentence appended after the owner's wording, which a check that only looks
    # for the expected text inside the section would accept.
    "X3-appended-sentence": ("raters/evaluators can see or hear your recordings.",
                             "raters/evaluators can see or hear your recordings.\n\nOur technology partners may also "
                             "hear them."),
    # WP-0.8-F12 (DEBT-026, closed in WP-0.9): a pre-ticked expected box, and a promise added to a fill-in line.
    "Y1-pre-ticked-expected-box": ("- [ ] I agree to be recorded for the purpose above.",
                                   "- [x] I agree to be recorded for the purpose above."),
    "Y4-signature-line-addition": ("Signature: ______________________________",
                                   "Signature: ______________________________ (by signing you also agree that our "
                                   "technology partners may hear your recordings)"),
}


@pytest.mark.parametrize("name", sorted(OWNER_FACT_BREAKS))
def test_FR_0_8_01_owner_fact_check_rejects_changed_window_and_additions(name):
    # WP-0.8-F01 and F03: a changed owner value, or a promise added beside the owner's wording, must be reported.
    text = read(CONSENT)
    old, new = OWNER_FACT_BREAKS[name]
    assert text.count(old) == 1, name
    assert owner_fact_problems(text.replace(old, new)) != [], name


# --- FR-0.8-02: the campaign A recording guide -----------------------------------------------------------------------

GUIDE = "docs/recording/RECORDING_GUIDE.md"
BUILD_PLAN = SOURCES / "AQIS_Test_Lab_Build_Plan.md"
# FR-0.8-02's list, with the guide heading for each (PLAN.md, "Recording guide").
GUIDE_SECTIONS = [
    ("80-prompt structure by family", "The 80 prompts"),
    ("device guidance", "Phone"),
    ("room guidance", "Rooms and background noise"),
    ("file naming", "File naming"),
    ("format", "Format"),
    ("transfer", "Transfer"),
    ("quality checks", "Quality checks"),
]
FILE_NAME_RE = re.compile(r"[a-z0-9-]+\.wav")          # the registry importer's rule, restated (finding 4)
SPEAKERS = 22                                           # Build Plan, Campaign A


def approval_answer(label):
    """The text of the owner's answer to BLK-014 item `label` (A to G) in docs/approvals/WP-0.8.md."""
    m = re.search(rf"^\s*\* \({label}\) [^:]+: (.+)$", APPROVAL.read_text(encoding="utf-8"), re.M)
    assert m, label
    return m.group(1).strip()


def build_plan_families():
    """[(count, family name)] from the Build Plan's Campaign A list, in order."""
    body = BUILD_PLAN.read_text(encoding="utf-8").split("### Campaign A", 1)[1].split("###", 1)[0]
    return [(int(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^\s+\d+\. (\d+) (.+)$", body, re.M)]


def guide_sections():
    return sections(read(GUIDE), 2)


def families():
    return table_with(guide_sections()["The 80 prompts"], "Family ID", "Family", "Prompts")


def id_list(text, prefix):
    return re.findall(rf"`({prefix}-[a-z0-9-]+)`", text)


def test_FR_0_8_02_guide_has_every_required_section():
    found = guide_sections()
    for item, heading in GUIDE_SECTIONS:
        assert heading in found and words(found[heading]), f"section for {item} ({heading!r}) missing or empty"


def test_FR_0_8_02_prompt_families_total_80():
    rows = families()
    assert sum(int(r["Prompts"]) for r in rows) == 80
    assert [r["Family ID"] for r in rows] == [f"`f{i}`" for i in range(1, len(rows) + 1)]


def test_FR_0_8_02_prompt_families_match_the_build_plan():
    expected = build_plan_families()
    assert sum(n for n, _ in expected) == 80 and len(expected) == 7
    assert [(int(r["Prompts"]), r["Family"].lower()) for r in families()] == [(n, f.lower()) for n, f in expected]
    about = guide_sections()["About campaign A"]
    assert f"{SPEAKERS} speakers" in about and "about 30 minutes" in about and "own phones" in about


def _all_file_names():
    pattern = "<speaker-id>-<family-id>-<NN>.wav"
    body = guide_sections()["File naming"]
    assert f"`{pattern}`" in body and "`ca-s001-f2-07.wav`" in body
    names = []
    for speaker in range(1, SPEAKERS + 1):
        for row in families():
            for n in range(1, int(row["Prompts"]) + 1):
                names.append(pattern.replace("<speaker-id>", f"ca-s{speaker:03d}")
                             .replace("<family-id>", row["Family ID"].strip("`")).replace("<NN>", f"{n:02d}"))
    return names


def test_FR_0_8_02_file_names_are_valid_and_unique():
    names = _all_file_names()
    assert len(names) == SPEAKERS * 80 == len(set(names))
    assert all(FILE_NAME_RE.fullmatch(n) for n in names)
    assert "ca-s001-f2-07.wav" in names
    # The file stem becomes the clip_id (owner importer): none may clash with a clip already in the registry.
    with open(ROOT / "data" / "registry" / "sources.csv", encoding="utf-8", newline="") as fh:
        registered = {row["clip_id"] for row in csv.DictReader(fh)}
    assert not {n[:-len(".wav")] for n in names} & registered


def test_FR_0_8_02_delivered_format_is_the_working_format():
    overview = (ROOT / "docs" / "specs" / "phase-0" / "00-PHASE-0-OVERVIEW.md").read_text(encoding="utf-8")
    working = re.search(r"working format is (.+?)\.\n", overview).group(1)          # "16 kHz, mono, 16-bit PCM WAV"
    body = guide_sections()["Format"]
    assert working in body
    assert "16 kHz mono 16-bit PCM WAV" in approval_answer("C") and "original kept" in approval_answer("C")
    assert "original" in body and "kept" in body


def quality_checks():
    return table_with(guide_sections()["Quality checks"], "Check", "How", "Pass rule")


def test_FR_0_8_02_every_quality_check_has_a_pass_rule():
    rows = quality_checks()
    assert rows and all(r["Check"] and r["How"] and r["Pass rule"] for r in rows)
    rules = " ".join(r["Pass rule"] for r in rows).replace("−", "-")
    # Every threshold of the owner's answer D, as the owner wrote it.
    thresholds = re.findall(r"(-?\d+(?:\.\d+)?) ?(%|dBFS|s)(?![A-Za-z])", approval_answer("D"))
    assert sorted(thresholds) == sorted([("0.1", "%"), ("-30", "dBFS"), ("-1", "dBFS"), ("0.3", "s")])
    for number, unit in thresholds:
        assert re.search(rf"(?<![\d.-]){re.escape(number)} ?{re.escape(unit)}(?![A-Za-z])", rules), (number, unit)
    assert "verbatim" in approval_answer("D") and "word for word" in rules


def test_FR_0_8_02_owner_values_appear_as_given():
    guide = re.sub(r"\s+", " ", read(GUIDE))
    a, b, g = approval_answer("A"), approval_answer("B"), approval_answer("G")
    assert "11 quiet room speakers, 11 everyday noise speakers" in a
    assert "11 speakers in a quiet room" in guide and "11 speakers in an everyday noise room" in guide
    for phrase in ("MyDrive/AQIS_LAB/campaign_a/raw/", "tar.gz"):
        assert phrase in b and phrase in guide, phrase
    for phrase in ("10-15 cm", "no headset"):
        assert phrase in g and phrase in guide, phrase


def test_FR_0_8_02_choice_lists_equal_the_owner_lists():
    found = guide_sections()
    noise = table_with(found["Rooms and background noise"], "Noise ID", "Noise source")
    accents = table_with(found["Accent groups"], "Accent ID", "Accent group")
    assert [r["Noise ID"].strip("`") for r in noise] == re.findall(r"ns-[a-z]+", approval_answer("E"))
    assert [r["Accent ID"].strip("`") for r in accents] == re.findall(r"acc-[a-z-]+[a-z]", approval_answer("F"))
    rooms = table_with(found["Rooms and background noise"], "Room ID", "Room")
    assert [r["Room ID"].strip("`") for r in rooms] == ["room-quiet", "room-everyday-noise"]


def test_FR_0_8_02_guide_has_no_owner_blank_left():
    # Every value the guide needs came from the owner (BLK-014); none is left open and none is invented.
    assert owner_blanks(read(GUIDE)) == []


# --- FR-0.8-03: the session form -------------------------------------------------------------------------------------

SESSION = "docs/recording/SESSION_FORM.md"
# FR-0.8-03's six fields, then the two of deviation D1.
SESSION_FIELDS = ["Speaker ID", "Device", "Room", "Noise source", "Accent group", "Consent reference",
                  "Session date (UTC)", "Notes"]
IDENTIFYING = re.compile(r"\b(?:name|e-?mail|phone number|address|birth|age)\b", re.I)


def session_fields():
    return {r["Field"]: r for r in table_with(read(SESSION), "Field", "Entry", "How to fill")}


def test_FR_0_8_03_session_form_has_every_field():
    fields = session_fields()
    assert sorted(fields) == sorted(SESSION_FIELDS)
    assert all(fields[f]["Entry"] and fields[f]["How to fill"] for f in SESSION_FIELDS)


def test_FR_0_8_03_choices_equal_the_recording_guide_lists():
    fields = session_fields()
    found = guide_sections()
    guide_lists = {
        "Room": [r["Room ID"].strip("`") for r in table_with(found["Rooms and background noise"], "Room ID", "Room")],
        "Noise source": [r["Noise ID"].strip("`")
                         for r in table_with(found["Rooms and background noise"], "Noise ID", "Noise source")],
        "Accent group": [r["Accent ID"].strip("`") for r in table_with(found["Accent groups"], "Accent ID",
                                                                        "Accent group")],
    }
    prefixes = {"Room": "room", "Noise source": "ns", "Accent group": "acc"}
    for field, expected in guide_lists.items():
        assert id_list(fields[field]["Entry"], prefixes[field]) == expected, field


def test_FR_0_8_03_speaker_id_and_consent_reference_formats_match_the_guide():
    fields = session_fields()
    ids = guide_sections()["Speaker IDs and consent references"]
    assert "`ca-sNNN`" in ids and "`ca-cNNN`" in ids                       # approval question 5
    assert "ca-s___" in fields["Speaker ID"]["Entry"] and "ca-c___" in fields["Consent reference"]["Entry"]
    assert "YYYY-MM-DD" in fields["Session date (UTC)"]["How to fill"]


def test_FR_0_8_03_asks_for_no_identifying_details():
    for field, row in session_fields().items():
        assert not IDENTIFYING.search(field), field
    # The device field asks for the phone's make and model, never the speaker's phone number.
    assert "make and model" in session_fields()["Device"]["How to fill"]
