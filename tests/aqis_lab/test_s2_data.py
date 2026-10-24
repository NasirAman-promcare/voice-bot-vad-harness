"""WP-1.2: result rows carry the trace columns, prediction files resume, and the emotion slice is class and actor balanced."""
import collections

import pytest

from aqis_lab.live import prep, results

TRACE = {"component": "vad", "model": "silero_v5", "revision": "a" * 40, "slice": "us_phone", "condition": "phone", "seed": 20261026,
         "git_commit": "b" * 40, "machine": "Ampere Altra, aarch64", "versions": '{"onnxruntime": "1.20"}',
         "utc": "2026-10-26T08:00:00Z"}


def rows(n=3):
    return results.make_rows(TRACE, [{"utt_id": f"u{i}", "value": float(i)} for i in range(n)])


def test_s2_rows_carry_every_trace_column_after_the_utterance_id():
    expected = ["utt_id", "component", "model", "revision", "slice", "condition", "seed", "git_commit", "machine", "versions", "utc"]
    got = rows()
    assert results.TRACE_COLUMNS == tuple(expected[1:])
    assert all(list(r)[:11] == expected and r["value"] == float(i) for i, r in enumerate(got))
    results.check_rows(got)


@pytest.mark.parametrize("column", results.TRACE_COLUMNS)
def test_s2_a_row_missing_a_trace_column_fails(column):
    got = rows()
    del got[1][column]
    with pytest.raises(results.RowError, match=column):
        results.check_rows(got)


@pytest.mark.parametrize("column", ["revision", "git_commit", "machine", "model", "slice", "condition"])
def test_s2_a_row_with_an_empty_trace_field_fails(column):
    got = rows()
    got[0][column] = ""
    with pytest.raises(results.RowError, match=column):
        results.check_rows(got)


def test_s2_make_rows_refuses_a_trace_missing_a_field():
    with pytest.raises(results.RowError, match="machine"):
        results.make_rows({k: v for k, v in TRACE.items() if k != "machine"}, [{"utt_id": "u"}])


def test_s2_make_rows_refuses_a_payload_without_an_utterance_id():
    with pytest.raises(results.RowError, match="utt_id"):
        results.make_rows(TRACE, [{"value": 1.0}])


def test_s2_result_file_roundtrip_and_missing_ids(tmp_path):
    path = tmp_path / "vad" / "silero_v5__us_phone__phone.parquet"
    assert results.missing_ids(path, ["u0", "u1", "u2"]) == ["u0", "u1", "u2"]
    results.write_rows(path, rows(2))
    assert results.missing_ids(path, ["u0", "u1", "u2"]) == ["u2"]
    assert [r["utt_id"] for r in results.read_rows(path)] == ["u0", "u1"]
    assert not list(path.parent.glob("*.partial"))


def test_s2_merging_keeps_old_rows_and_refuses_a_second_revision_or_a_repeat(tmp_path):
    path = tmp_path / "x.parquet"
    results.write_rows(path, rows(2))
    results.merge_rows(path, results.make_rows(TRACE, [{"utt_id": "u2", "value": 2.0}]))
    assert [r["utt_id"] for r in results.read_rows(path)] == ["u0", "u1", "u2"]
    with pytest.raises(results.RowError, match="revision"):
        results.merge_rows(path, results.make_rows(dict(TRACE, revision="c" * 40), [{"utt_id": "u3", "value": 3.0}]))
    with pytest.raises(results.RowError, match="u1"):
        results.merge_rows(path, results.make_rows(TRACE, [{"utt_id": "u1", "value": 9.0}]))


# ---- the emotion slice -----------------------------------------------------------------------------------------
def items():
    out = []
    for label in ("neutral", "anger", "sadness", "happiness"):
        for actor in range(5):
            for k in range(6):
                out.append({"utt_id": f"{label}-{actor}-{k}", "speaker": f"actor{actor}", "label": label})
    return out


def test_s2_emotion_selection_is_class_balanced_and_actor_balanced_within_a_class():
    got = prep.select_emotion(items(), per_class=10, seed=3)
    assert collections.Counter(x["label"] for x in got.items) == {"neutral": 10, "anger": 10, "sadness": 10, "happiness": 10}
    for label in ("neutral", "anger", "sadness", "happiness"):
        counts = collections.Counter(x["speaker"] for x in got.items if x["label"] == label)
        assert set(counts.values()) == {2} and len(counts) == 5          # 10 per class from 5 actors: two each


def test_s2_emotion_selection_is_deterministic_and_independent_of_input_order():
    a = prep.select_emotion(items(), 10, seed=3)
    b = prep.select_emotion(list(reversed(items())), 10, seed=3)
    assert [x["utt_id"] for x in a.items] == [x["utt_id"] for x in b.items]
    assert [x["utt_id"] for x in a.items] != [x["utt_id"] for x in prep.select_emotion(items(), 10, seed=4).items]


def test_s2_emotion_selection_takes_all_of_a_short_class_and_says_so():
    pool = [x for x in items() if x["label"] != "sadness"] + [x for x in items() if x["label"] == "sadness"][:4]
    got = prep.select_emotion(pool, per_class=10, seed=1)
    assert collections.Counter(x["label"] for x in got.items)["sadness"] == 4
    assert got.notes == ["emotion: class sadness has only 4 utterances, 10 asked for; the real N is 4"]
