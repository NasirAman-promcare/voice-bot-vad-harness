"""FR-0.2-04: `python -m aqis_lab contracts validate <file> --kind event|run_card|manifest`."""
import json
import re
import subprocess
import sys

import pytest

from aqis_contracts_testutil import FIXTURES, first_event
from aqis_testutil import ROOT

REPORT_RE = re.compile(r"(line|record) (\d+): (OK|INVALID (\(document\)|/\S*): .+)")


def run_cli(*args, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "aqis_lab", "contracts", *map(str, args)], cwd=cwd,
                          capture_output=True, text=True, timeout=300)


def parse_report(stdout):
    """{number: set of pointers} ('' for the whole record) plus the summary line."""
    lines = stdout.splitlines()
    per_record = {}
    for line in lines[:-1]:
        m = REPORT_RE.fullmatch(line)
        assert m, f"unexpected report line: {line!r}"
        found = per_record.setdefault(int(m.group(2)), set())
        if m.group(3) != "OK":
            found.add("" if m.group(4) == "(document)" else m.group(4))
    return per_record, lines[-1]


def test_FR_0_2_04_cli_valid_events_exit_0():
    proc = run_cli("validate", FIXTURES / "valid_events.jsonl", "--kind", "event")
    assert proc.returncode == 0, proc.stderr
    per_record, summary = parse_report(proc.stdout)
    count = len((FIXTURES / "valid_events.jsonl").read_text(encoding="utf-8").splitlines())
    assert per_record == {n: set() for n in range(1, count + 1)}
    assert proc.stdout.splitlines()[0] == "line 1: OK"
    assert summary == f"event: {count} records, {count} valid, 0 invalid"


def test_FR_0_2_04_cli_invalid_events_exit_1_and_name_fields():
    proc = run_cli("validate", FIXTURES / "invalid_events.jsonl", "--kind", "event")
    assert proc.returncode == 1, proc.stderr
    expected = json.loads((FIXTURES / "invalid_events.expected.json").read_text(encoding="utf-8"))
    per_record, summary = parse_report(proc.stdout)
    assert {str(n): sorted(p) for n, p in per_record.items()} == expected
    invalid = sum(1 for p in expected.values() if p)
    assert summary == f"event: {len(expected)} records, {len(expected) - invalid} valid, {invalid} invalid"
    assert "line 4: INVALID /seq: required field is missing" in proc.stdout.splitlines()


@pytest.mark.parametrize("where", ["first", "middle", "last"])
def test_FR_0_2_04_cli_one_invalid_line_anywhere_fails(tmp_path, where):
    lines = (FIXTURES / "valid_events.jsonl").read_text(encoding="utf-8").splitlines()
    index = {"first": 0, "middle": len(lines) // 2, "last": len(lines) - 1}[where]
    record = json.loads(lines[index])
    record["component"] = "asr"
    lines[index] = json.dumps(record)
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    proc = run_cli("validate", path, "--kind", "event")
    assert proc.returncode == 1
    per_record, summary = parse_report(proc.stdout)
    assert {n: p for n, p in per_record.items() if p} == {index + 1: {"/component"}}
    assert summary == f"event: {len(lines)} records, {len(lines) - 1} valid, 1 invalid"


def test_FR_0_2_04_cli_unparsable_and_blank_lines_are_invalid_records(tmp_path):
    good = json.dumps(dict(first_event("final"), run_id="r", seq=0)).encode()
    later = json.dumps(dict(first_event("final"), run_id="r", seq=1)).encode()
    data = b"\n".join([good + b"\r", b"\xff\xfe not utf-8", b"", b"   ", b"\xef\xbb\xbf" + later, later, b"[1]",
                       b'{"a": 1, "a": 2}', b"NaN", later[:40]]) + b"\n"
    path = tmp_path / "mixed.jsonl"
    path.write_bytes(data)
    proc = run_cli("validate", path, "--kind", "event")
    assert proc.returncode == 1
    per_record, summary = parse_report(proc.stdout)
    assert per_record == {1: set(), 2: {""}, 3: {""}, 4: {""}, 5: {""}, 6: set(), 7: {""}, 8: {""}, 9: {""}, 10: {""}}
    assert summary == "event: 10 records, 2 valid, 8 invalid"
    out = proc.stdout
    assert "line 2: INVALID (document): not valid UTF-8" in out
    assert "line 3: INVALID (document): no JSON value" in out
    assert "line 7: INVALID (document): a event log record must be a JSON object, got array" not in out
    assert "line 7: INVALID (document): an event log record must be a JSON object, got array" in out
    assert "duplicate key 'a'" in out


def test_FR_0_2_04_cli_empty_file_fails(tmp_path):
    for kind, content in (("event", b""), ("run_card", b""), ("manifest", b"  \n")):
        path = tmp_path / f"empty-{kind}"
        path.write_bytes(content)
        proc = run_cli("validate", path, "--kind", kind)
        assert proc.returncode == 1, kind
        assert proc.stdout == f"{kind}: 0 records, 0 valid, 0 invalid\n"
        assert proc.stderr.startswith("ERROR:") and "no records" in proc.stderr


def test_FR_0_2_04_cli_run_card_and_manifest_kinds():
    expected = json.loads((FIXTURES / "invalid_expected.json").read_text(encoding="utf-8"))
    for kind, valid, invalid in (("run_card", "valid_run_card.json", ["invalid_run_card_fields.json", "invalid_run_card_id.json"]),
                                 ("manifest", "valid_manifest.json", ["invalid_manifest_fields.json"])):
        proc = run_cli("validate", FIXTURES / valid, "--kind", kind)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert proc.stdout == f"record 1: OK\n{kind}: 1 record, 1 valid, 0 invalid\n"
        for name in invalid:
            proc = run_cli("validate", FIXTURES / name, "--kind", kind)
            assert proc.returncode == 1
            per_record, summary = parse_report(proc.stdout)
            assert {1: set(expected[name])} == per_record
            assert summary == f"{kind}: 1 record, 0 valid, 1 invalid"
    # the wrong kind for a file is an invalid record, not a crash
    proc = run_cli("validate", FIXTURES / "valid_run_card.json", "--kind", "manifest")
    assert proc.returncode == 1 and "record 1: INVALID /manifest_id: required field is missing" in proc.stdout
    proc = run_cli("validate", FIXTURES / "valid_manifest.json", "--kind", "event")
    assert proc.returncode == 1                                  # a pretty-printed document is not JSON Lines


def test_FR_0_2_04_cli_missing_file_exit_2(tmp_path):
    missing = run_cli("validate", tmp_path / "nope.jsonl", "--kind", "event")
    assert missing.returncode == 2 and missing.stdout == "" and missing.stderr.startswith("ERROR: cannot read")
    folder = run_cli("validate", tmp_path, "--kind", "run_card")
    assert folder.returncode == 2 and folder.stderr.startswith("ERROR: cannot read")
    for args in (["validate", FIXTURES / "valid_run_card.json", "--kind", "card"],
                 ["validate", FIXTURES / "valid_run_card.json"],
                 ["validate", "--kind", "event"],
                 ["validate", FIXTURES / "valid_events.jsonl", "--kind", "event", "--workers", "0"],
                 ["validate", FIXTURES / "valid_events.jsonl", "--kind", "event", "--workers", "two"],
                 ["check", FIXTURES / "valid_events.jsonl"],
                 []):
        proc = run_cli(*args)
        assert proc.returncode == 2, args
        assert "usage:" in proc.stderr, args


def test_FR_0_2_04_cli_listed_by_dispatcher():
    top = subprocess.run([sys.executable, "-m", "aqis_lab", "--help"], cwd=ROOT, capture_output=True, text=True,
                         timeout=60)
    assert top.returncode == 0 and re.search(r"^\s+contracts\s+\S", top.stdout, re.M), top.stdout
    helped = run_cli("validate", "--help")
    assert helped.returncode == 0 and "--kind" in helped.stdout and "--workers" in helped.stdout


def test_FR_0_2_04_cli_uses_worker_pool_only_for_large_files(tmp_path):
    from aqis_lab.contracts.validate import POOL_MIN_RECORDS
    lines = (FIXTURES / "invalid_events.jsonl").read_bytes().splitlines()
    big = tmp_path / "big.jsonl"
    big.write_bytes(b"\n".join((lines * (POOL_MIN_RECORDS // len(lines) + 1))[:POOL_MIN_RECORDS]) + b"\n")
    pooled = run_cli("validate", big, "--kind", "event", "--workers", "2")
    single = run_cli("validate", big, "--kind", "event", "--workers", "1")
    assert pooled.returncode == single.returncode == 1
    assert pooled.stdout == single.stdout
    assert f"validating {POOL_MIN_RECORDS} records with 2 worker processes" in pooled.stderr
    assert "worker processes" not in single.stderr
    small = run_cli("validate", FIXTURES / "invalid_events.jsonl", "--kind", "event", "--workers", "2")
    assert "worker processes" not in small.stderr
