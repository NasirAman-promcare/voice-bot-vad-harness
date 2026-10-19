"""WP-1.1: the smoke check that prints hypotheses beside references and fails on empty or repeated output."""
from aqis_lab.bench import run


def check(pairs, condition="clean"):
    lines = []
    failures = run.smoke_check("m", [("numbers", condition, pairs)], log=lines.append)
    return failures, "\n".join(lines)


def test_s1_smoke_check_passes_matching_outputs_and_prints_both_texts():
    failures, text = check([("we grew revenue by five percent", "we grew revenue by 5 percent"),
                            ("costs fell in the third quarter", "costs fell in the third quarter")])
    assert failures == [] and "WARNING" not in text
    assert "REF: 'we grew revenue by five percent'" in text and "HYP: 'costs fell in the third quarter'" in text


def test_s1_smoke_check_fails_when_two_different_references_get_the_same_output():
    # the shape of the first Colab failure: two clips with different references transcribed to one text
    failures, _ = check([("compared to the same period of 2020 all segments grew", "capex almost doubled in Q3"),
                         ("we moved from 700 million backlog to 900 million", "capex almost doubled in Q3"),
                         ("our total revenues were 347 million", "during 2021 we grew capacity by 31 percent")])
    assert failures == ["m: identical output for clips with different references in numbers/clean"]


def test_s1_smoke_check_allows_one_output_for_one_repeated_reference():
    failures, _ = check([("thank you very much", "thank you very much"), ("thank you very much", "thank you very much")])
    assert failures == []


def test_s1_smoke_check_fails_on_empty_clean_output_only():
    assert check([("hello there my friend", "")])[0] == ["m: empty output for a speech clip in numbers/clean"]
    assert check([("hello there my friend", "")], condition="phone")[0] == []


def test_s1_smoke_check_warns_when_the_output_shares_under_a_third_of_the_reference_words():
    failures, text = check([("revenues for the third quarter were RMB 347.4 million", "capex almost doubled year on year")])
    assert failures == [] and "WARNING [numbers/clean]" in text
    assert "WARNING" not in check([("revenues fell", "revenues fell sharply")])[1]
    assert "WARNING" not in check([("revenues for the third quarter", "something else entirely")], "phone")[1]
