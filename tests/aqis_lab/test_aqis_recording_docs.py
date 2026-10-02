"""WP-0.8 FR-0.8-01 to FR-0.8-03: the consent form, the campaign A recording guide and the session form.

Expected values come from the spec (docs/specs/phase-0/WP-0.8-consent-fillers-targets.md), the owner's approval
(docs/approvals/WP-0.8.md) and the committed sources (docs/specs/sources/), never from the document under test.
"""
import re

import csv
import subprocess

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


# The owner gave the consent facts (question 6 (a) to (f)) in the approval committed to main at 61c50c7. The
# approval's later rewrite (b4b327e, BLK-014 answers) no longer lists them, and approves "Questions 2 to 8: as
# recommended", which does not change them. The facts are read from the owner's commit itself, which must be part of
# this branch's history (CI checks out the full history).
FACTS_COMMIT = "61c50c7"


def _owner_approval_with_facts():
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", FACTS_COMMIT, "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
    assert ancestor.returncode == 0, ancestor.stderr
    show = subprocess.run(["git", "show", f"{FACTS_COMMIT}:docs/approvals/WP-0.8.md"], cwd=ROOT,
                          capture_output=True, text=True, timeout=60, check=True)
    assert show.stdout.startswith("STATUS: APPROVED\nWP: WP-0.8\nAPPROVED-BY: owner\n")
    return show.stdout


def _approval_fact(label):
    m = re.search(rf"^\s*\* \({label}\) [^:]+: (.+)$", _owner_approval_with_facts(), re.M)
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
