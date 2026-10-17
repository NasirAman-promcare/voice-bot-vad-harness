"""WP-1.1 ruler tests 1: reference cleaning per source and the seeded, speaker-balanced slice selection.

Expected values are worked out by hand from the rules in docs/specs/sprints/WP-1.1-S1-asr-benchmark.md section 2.
"""
import collections

import pytest

from aqis_lab.bench import select, sources

RULES = {
    "strip": {"laugh": r"<laugh>", "breath": r"\[breath\]"},
    "drop_if": {"overlap": r"<overlap>", "unintelligible": r"<unintelligible>|\(\(\s*\)\)", "foreign": r"<foreign>"},
}
UTT_CFG = {"min_s": 1.0, "max_s": 30.0, "min_ref_words": 3}


def utt(number, speaker, duration=5.0, text="one two three four", **meta):
    return {"utt_id": f"u{number:04d}", "speaker": speaker, "cluster": speaker, "duration_s": duration,
            "ref_clean": text, "meta": dict(meta)}


# ---- cleaning ------------------------------------------------------------------------------------------------
def test_s1_clean_strips_listed_tags_and_collapses_spaces():
    result = sources.clean_reference("hello <laugh> there [breath] friend", RULES)
    assert result.text == "hello there friend"
    assert result.dropped is None
    assert result.unknown_tags == ()
    assert result.stripped == ("laugh", "breath")


@pytest.mark.parametrize("raw,reason", [("<overlap> yes please", "overlap"), ("I said (( )) ok", "unintelligible"),
                                        ("so <foreign> bonjour", "foreign"), ("a <unintelligible> b", "unintelligible")])
def test_s1_clean_drops_marked_utterances_with_the_rule_name(raw, reason):
    result = sources.clean_reference(raw, RULES)
    assert result.dropped == reason
    assert result.text is None


def test_s1_clean_reports_tags_no_rule_covers():
    result = sources.clean_reference("ok <cough> fine [noise] yes", RULES)
    assert result.unknown_tags == ("<cough>", "[noise]")


def test_s1_clean_text_without_tags_is_unchanged():
    assert sources.clean_reference("He takes 500 mg twice daily.", RULES).text == "He takes 500 mg twice daily."


def test_s1_clean_text_empty_after_stripping_is_dropped_as_empty():
    result = sources.clean_reference(" <laugh> ", RULES)
    assert result.dropped == "empty"


def test_s1_cleaner_counts_every_rule_it_applies():
    cleaner = sources.Cleaner(RULES)
    for raw in ["a <laugh> b", "c <laugh> d <laugh>", "<overlap> e", "<overlap> f", "<foreign> g", "plain words"]:
        cleaner.apply(raw)
    assert dict(cleaner.stripped) == {"laugh": 2}   # one utterance counted once per rule
    assert dict(cleaner.dropped) == {"overlap": 2, "foreign": 1}
    assert cleaner.seen == 6
    assert cleaner.report() == {"seen": 6, "kept": 3, "dropped": {"overlap": 2, "foreign": 1},
                                "stripped": {"laugh": 2}, "unknown_tags": {}}


def test_s1_cleaner_tallies_unknown_tags_across_utterances():
    cleaner = sources.Cleaner(RULES)
    cleaner.apply("x <cough> y")
    cleaner.apply("<cough> z <sniff>")
    assert cleaner.report()["unknown_tags"] == {"<cough>": 2, "<sniff>": 1}
    with pytest.raises(sources.UnknownTagsError, match=r"<cough>.*<sniff>"):
        cleaner.require_no_unknown_tags("edacc")


# ---- selection -----------------------------------------------------------------------------------------------
def test_s1_round_robin_takes_one_per_speaker_per_round():
    items = [utt(i, "A") for i in range(5)] + [utt(10 + i, "B") for i in range(2)] + [utt(20, "C")]
    chosen = select.round_robin(items, 6, seed=7, salt="s")
    counts = collections.Counter(x["speaker"] for x in chosen)
    assert counts == {"A": 3, "B": 2, "C": 1}                       # rounds: ABC, AB, A
    assert len({x["utt_id"] for x in chosen}) == 6
    assert [x["speaker"] for x in chosen[:3]].count("A") == 1 and len({x["speaker"] for x in chosen[:3]}) == 3


def test_s1_round_robin_is_deterministic_for_a_seed_and_changes_with_it():
    items = [utt(i, f"S{i % 7}") for i in range(70)]
    first = [x["utt_id"] for x in select.round_robin(items, 20, seed=1, salt="s")]
    assert first == [x["utt_id"] for x in select.round_robin(list(reversed(items)), 20, seed=1, salt="s")]
    assert first != [x["utt_id"] for x in select.round_robin(items, 20, seed=2, salt="s")]


def test_s1_round_robin_returns_everything_when_fewer_than_n():
    items = [utt(i, "A") for i in range(3)]
    assert len(select.round_robin(items, 10, seed=1, salt="s")) == 3


def test_s1_select_slice_applies_length_and_word_filters():
    pool = [utt(1, "A", duration=0.5), utt(2, "B", duration=31.0), utt(3, "C", text="two words"),
            utt(4, "D"), utt(5, "E", duration=1.0), utt(6, "F", duration=30.0)]
    got = select.select_slice("us_conv", {"n": 3}, pool, UTT_CFG, seed=3)
    assert sorted(x["utt_id"] for x in got.items) == ["u0004", "u0005", "u0006"]   # 1 s and 30 s are inside the range
    assert got.notes == []


def test_s1_select_slice_slice_overrides_length_range():
    pool = [utt(1, "A", duration=2.0), utt(2, "B", duration=10.0), utt(3, "C", duration=25.0)]
    got = select.select_slice("numbers", {"n": 10, "min_s": 3.0, "max_s": 20.0}, pool, UTT_CFG, seed=3)
    assert [x["utt_id"] for x in got.items] == ["u0002"]


def test_s1_select_slice_n_caps_and_notes_a_short_source():
    pool = [utt(i, f"S{i}") for i in range(8)]
    assert len(select.select_slice("a", {"n": 5}, pool, UTT_CFG, seed=1).items) == 5
    short = select.select_slice("a", {"n": 50}, pool, UTT_CFG, seed=1)
    assert len(short.items) == 8
    assert short.notes == ["a: only 8 utterances qualify, 50 asked for; the real N is 8"]


def test_s1_select_slice_filters_l1_and_entities():
    pool = [utt(1, "A", l1="Hindi"), utt(2, "B", l1="Mainstream US English"), utt(3, "C", l1="Urdu"),
            utt(4, "D", l1="Sinhalese")]
    got = select.select_slice("sa_conv", {"n": 10, "l1": ["Hindi", "Urdu", "Sinhalese", "Indian English"]}, pool,
                              UTT_CFG, seed=1)
    assert sorted(x["utt_id"] for x in got.items) == ["u0001", "u0003", "u0004"]
    med = [utt(1, "A", entities=[{"category": "drug", "text": "aspirin"}]), utt(2, "B", entities=[]), utt(3, "C")]
    got = select.select_slice("medical", {"n": 10, "require_entities": True}, med, UTT_CFG, seed=1)
    assert [x["utt_id"] for x in got.items] == ["u0001"]


def test_s1_select_slice_digit_token_filter_counts_normalised_reference_tokens():
    pool = [utt(1, "A", text="call 555 1234 now"), utt(2, "B", text="the number 7 only"),
            utt(3, "C", text="pay twenty five dollars by the 3rd of may"), utt(4, "D", text="no digits at all here")]
    got = select.select_slice("numbers", {"n": 10, "min_digit_tokens": 2}, pool, UTT_CFG, seed=1)
    # u0001 has the tokens 555 and 1234; u0003 normalises to "pay $25 by the 3rd of may" (tokens $25 and 3rd); u0002 has one
    assert sorted(x["utt_id"] for x in got.items) == ["u0001", "u0003"]


def test_s1_select_slice_stratifies_by_the_stratum_field():
    pool = ([utt(i, f"R{i}", stratum="read") for i in range(10)] + [utt(20 + i, f"S{i}", stratum="spontaneous")
            for i in range(10)] + [utt(40 + i, f"E{i}", stratum="everyday") for i in range(10)])
    got = select.select_slice("sa_india", {"n": 9, "stratify": {"read": 2, "spontaneous": 3, "everyday": 4}}, pool,
                              UTT_CFG, seed=5)
    assert collections.Counter(x["meta"]["stratum"] for x in got.items) == {"read": 2, "spontaneous": 3, "everyday": 4}


def test_s1_select_slice_without_a_stratum_field_picks_plainly_and_says_so():
    pool = [utt(i, f"S{i}") for i in range(10)]
    got = select.select_slice("sa_india", {"n": 4, "stratify": {"read": 1, "spontaneous": 2, "everyday": 1}}, pool,
                              UTT_CFG, seed=5)
    assert len(got.items) == 4
    assert got.notes == ["sa_india: no stratum field in the source; selected without stratification"]


def test_s1_select_slice_telephone_turns_half_caller_half_agent_digits_first():
    pool = []
    for i in range(12):
        pool.append(utt(i, f"C{i}", role="caller", text="my number is 5551234 thanks"))
    for i in range(12):
        pool.append(utt(100 + i, f"C{i}", role="caller", text="yes that is right thanks"))
    for i in range(12):
        pool.append(utt(200 + i, f"A{i}", role="agent", text="your balance is 120 dollars today"))
    for i in range(12):
        pool.append(utt(300 + i, f"A{i}", role="agent", text="anything else I can help with"))
    spec = {"n": 16, "balance_roles": True, "digits_first": True}
    got = select.select_slice("us_phone", spec, pool, UTT_CFG, seed=9).items
    assert collections.Counter(x["meta"]["role"] for x in got) == {"caller": 8, "agent": 8}
    digit = [x for x in got if any(ch.isdigit() for ch in x["ref_clean"])]
    assert len(digit) == 8                                           # digit turns first, up to half the slice
    for role in ("caller", "agent"):
        assert sum(1 for x in digit if x["meta"]["role"] == role) == 4


def test_s1_select_slice_is_deterministic_for_a_seed():
    pool = [utt(i, f"S{i % 9}") for i in range(90)]
    a = select.select_slice("us_conv", {"n": 30}, pool, UTT_CFG, seed=11)
    b = select.select_slice("us_conv", {"n": 30}, list(reversed(pool)), UTT_CFG, seed=11)
    assert [x["utt_id"] for x in a.items] == [x["utt_id"] for x in b.items]


def test_s1_select_slice_prefix_is_still_speaker_balanced():
    pool = [utt(i, f"S{i % 5}") for i in range(50)]
    items = select.select_slice("us_conv", {"n": 25}, pool, UTT_CFG, seed=2).items
    for take in (5, 10, 15):
        counts = collections.Counter(x["speaker"] for x in items[:take])
        assert max(counts.values()) - min(counts.values()) <= 0 and len(counts) == 5
