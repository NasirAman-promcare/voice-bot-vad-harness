"""Stand-in for the gh executable: answers `gh api` calls from a JSON script and records every call.

Also carries the step-1 unit tests (named test_* so pytest collects them); running
`pytest tests/aqis_lab/autonomy` must never exit with code 5 (no tests collected).

CAPABILITIES:
  CAP-AUTONOMY-003: answer `gh api` REST calls from a JSON script named by STAND_IN_GH_SCRIPT
    [tests: test_FR_1_0_05_stand_in_gh_answers_get_from_script, test_FR_1_0_05_stand_in_gh_paginates_short_page_empties_body,
    test_FR_1_0_05_stand_in_gh_fields_imply_post, test_FR_1_0_05_stand_in_gh_put_merge_invocation,
    test_FR_1_0_05_stand_in_gh_http_error_status_on_stderr_exit_1]
  CAP-AUTONOMY-004: record every invocation as one JSON line in STAND_IN_GH_LOG
    [tests: test_FR_1_0_05_stand_in_gh_records_every_call]
INPUTS AND OUTPUTS: command line arguments like the real gh; environment variables
  STAND_IN_GH_SCRIPT (JSON map "METHOD endpoint" -> {"status": int, "body": any}) and
  STAND_IN_GH_LOG (JSONL call log). Writes the answer body as JSON on stdout; HTTP errors to stderr with exit 1.
CONTRACTS: gh CLI subset: `gh api <endpoint>`, `--method/-X`, `-f/-F/--field/--raw-field` fields, `-H/--header`.
INVARIANTS:
  - Deterministic: the same script and arguments always produce the same answer.
  - Page > 1 answers are empty lists so pagination stops after a short page unless the script loops.
  - This program never touches the network; the tests run it locally with scratch files only.
NOT IN SCOPE:
  - GraphQL, `gh pr` subcommands, authentication, the merge gate itself (later steps).
CHANGE LOG:
  2026-10-10 WO-1.0-05 step 1 created.
  2026-10-10 WO-1.0-05 fix 2: pytest exited 5 (no tests collected); added test_* functions here
    because the order's outputs name no separate step-1 test module.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

__all__ = ["StandInError", "answer", "parse_invocation", "main"]

_VALUE_FLAGS = ("-f", "-F", "--field", "--raw-field", "-H", "--header", "--jq", "-q", "--template", "-t", "--input")
_FIELD_FLAGS = ("-f", "-F", "--field", "--raw-field")
_METHOD_FLAGS = ("-X", "--method")


class StandInError(Exception):
    """The stand-in cannot answer; the message goes to stderr with a non-zero exit."""


def parse_invocation(args: list[str]) -> tuple[str, str]:
    """Extract the HTTP method and endpoint from a gh-style argument list.

    Fields imply POST unless a method flag overrides. The endpoint is the first
    positional argument; a leading slash is stripped.
    """
    if not args or args[0] != "api":
        raise StandInError("stand-in gh only answers `gh api`")
    method = "GET"
    endpoint: str | None = None
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in _METHOD_FLAGS:
            if i + 1 >= len(args):
                raise StandInError(f"stand-in gh: {arg} needs a value")
            method = args[i + 1].upper()
            i += 2
            continue
        if arg in _VALUE_FLAGS:
            if i + 1 >= len(args):
                raise StandInError(f"stand-in gh: {arg} needs a value")
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        if endpoint is None:
            endpoint = arg.lstrip("/")
        i += 1
    if endpoint is None:
        raise StandInError("stand-in gh: no endpoint given")
    if method == "GET" and any(a in _FIELD_FLAGS for a in args):
        method = "POST"
    return method, endpoint


def _empty_like(body: object) -> object:
    if isinstance(body, list):
        return []
    if isinstance(body, dict):
        return {key: ([] if isinstance(value, list) else value) for key, value in body.items()}
    return body


def answer(script: dict[str, dict[str, object]], method: str, endpoint: str) -> tuple[int, object]:
    """Look up the scripted answer for a call; page > 1 returns an emptied body."""
    parts = urlsplit(endpoint)
    page = int(parse_qs(parts.query).get("page", ["1"])[0])
    key = f"{method} {parts.path}"
    if key not in script:
        raise StandInError(f"stand-in gh: no answer for {key}")
    entry = script[key]
    status = int(entry.get("status", 200))
    body = entry.get("body")
    if page > 1:
        body = _empty_like(body)
    return status, body


def main(argv: list[str]) -> int:
    """Program entry point: log the call, then print the scripted answer or an error."""
    log_path = os.environ.get("STAND_IN_GH_LOG")
    if log_path is None:
        sys.stderr.write("stand-in gh: STAND_IN_GH_LOG is not set\n")
        return 2
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(json.dumps(argv) + "\n")
    script_path = os.environ.get("STAND_IN_GH_SCRIPT")
    if script_path is None:
        sys.stderr.write("stand-in gh: STAND_IN_GH_SCRIPT is not set\n")
        return 2
    try:
        method, endpoint = parse_invocation(argv)
        with open(script_path, encoding="utf-8") as handle:
            script = json.load(handle)
        status, body = answer(script, method, endpoint)
    except StandInError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if status >= 400:
        sys.stderr.write(f"gh: HTTP {status}: {json.dumps(body)}\n")
        return 1
    sys.stdout.write(json.dumps(body))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


# ------------------------------------------------------------- step-1 unit tests (pytest collection)

STAND_IN_PROGRAM = Path(__file__).resolve()


def _run_stand_in(tmp_path: Path, script: dict[str, dict[str, object]], *args: str) -> subprocess.CompletedProcess:
    """Run the stand-in as a program with script and log files inside tmp_path."""
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    env = dict(os.environ)
    env["STAND_IN_GH_SCRIPT"] = str(script_path)
    env["STAND_IN_GH_LOG"] = str(tmp_path / "calls.jsonl")
    return subprocess.run([sys.executable, str(STAND_IN_PROGRAM), *args], capture_output=True,
                          text=True, env=env, timeout=60)


def _read_log(tmp_path: Path) -> list[list[str]]:
    log_path = tmp_path / "calls.jsonl"
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_FR_1_0_05_stand_in_gh_answers_get_from_script(tmp_path):
    script = {"GET repos/owner/scratch/pulls": {"body": [{"number": 7}]}}
    proc = _run_stand_in(tmp_path, script, "api", "repos/owner/scratch/pulls?head=owner:b&state=open")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == [{"number": 7}]


def test_FR_1_0_05_stand_in_gh_records_every_call(tmp_path):
    script = {"GET repos/owner/scratch/pulls": {"body": []}}
    _run_stand_in(tmp_path, script, "api", "repos/owner/scratch/pulls")
    _run_stand_in(tmp_path, script, "api", "repos/owner/scratch/pulls?state=open")
    assert _read_log(tmp_path) == [["api", "repos/owner/scratch/pulls"],
                                   ["api", "repos/owner/scratch/pulls?state=open"]]


def test_FR_1_0_05_stand_in_gh_paginates_short_page_empties_body(tmp_path):
    script = {"GET repos/owner/scratch/commits/abc/check-runs":
              {"body": {"total_count": 1, "check_runs": [{"name": "ci"}]}}}
    page1 = _run_stand_in(tmp_path, script, "api", "repos/owner/scratch/commits/abc/check-runs?per_page=100&page=1")
    page2 = _run_stand_in(tmp_path, script, "api", "repos/owner/scratch/commits/abc/check-runs?per_page=100&page=2")
    assert json.loads(page1.stdout)["check_runs"] == [{"name": "ci"}]
    assert json.loads(page2.stdout)["check_runs"] == []


def test_FR_1_0_05_stand_in_gh_fields_imply_post(tmp_path):
    script = {"POST repos/owner/scratch/issues/7/comments": {"body": {"id": 1}}}
    proc = _run_stand_in(tmp_path, script, "api", "repos/owner/scratch/issues/7/comments", "-f", "body=hi")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"id": 1}


def test_FR_1_0_05_stand_in_gh_put_merge_invocation(tmp_path):
    body = {"merged": True, "sha": "f" * 40, "message": "merged"}
    script = {"PUT repos/owner/scratch/pulls/7/merge": {"body": body}}
    proc = _run_stand_in(tmp_path, script, "api", "--method", "PUT", "repos/owner/scratch/pulls/7/merge",
                         "-f", "merge_method=merge", "-f", "sha=" + "a" * 40,
                         "-f", "commit_title=Merge WP-9.9: t (gate PASS)")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == body


def test_FR_1_0_05_stand_in_gh_http_error_status_on_stderr_exit_1(tmp_path):
    script = {"PUT repos/owner/scratch/pulls/7/merge": {"status": 409, "body": {"message": "no"}}}
    proc = _run_stand_in(tmp_path, script, "api", "--method", "PUT", "repos/owner/scratch/pulls/7/merge",
                         "-f", "sha=x")
    assert proc.returncode == 1
    assert "409" in proc.stderr
    assert json.dumps({"message": "no"}) in proc.stderr


def test_FR_1_0_05_stand_in_gh_missing_answer_is_an_error(tmp_path):
    proc = _run_stand_in(tmp_path, {}, "api", "repos/owner/scratch/pulls")
    assert proc.returncode == 1
    assert "no answer" in proc.stderr
    assert _read_log(tmp_path) == [["api", "repos/owner/scratch/pulls"]]


def test_FR_1_0_05_stand_in_gh_rejects_non_api_calls(tmp_path):
    proc = _run_stand_in(tmp_path, {}, "pr", "merge", "7")
    assert proc.returncode == 1
    assert "only answers" in proc.stderr


def test_FR_1_0_05_stand_in_gh_requires_environment(tmp_path):
    env = {key: value for key, value in os.environ.items() if not key.startswith("STAND_IN_GH_")}
    proc = subprocess.run([sys.executable, str(STAND_IN_PROGRAM), "api", "x"], capture_output=True,
                          text=True, env=env, timeout=60)
    assert proc.returncode == 2
    assert "STAND_IN_GH_LOG" in proc.stderr
