"""Read-only tests for FIX-1 of WO-1.0-11 (FR-1.0-02, FR-1.0-13, NFR-1.0-03), written by Claude from the review.

Each test pins a gap the WO-1.0-11 acceptance tests did not catch:
- B18: a run that does not end ACCEPTED printed nothing;
- B7: the step log recorded the literal "sha" when the order had no hash attribute;
- WO-1.0-10 B6: the state file is `.relay/governor.json`;
- B20: a failed model listing was printed and then every model reported "missing";
- B16: final-fix rounds were committed and pushed before the full checks passed;
- B24: the ledger counted only accepted parts' tokens, not every reply's;
- Foundation standards 3 and 10: swallowed exceptions (the push failure, `main`'s catch-all), functions over 40
  lines and files over 400 lines.

The scratch repository, pool helpers and HTTP stand-in come from the WO-1.0-11 acceptance test.
"""
from __future__ import annotations

import ast
import hashlib
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_11 import (  # noqa: F401  (scratch and stand are fixtures)
    ORDER_REL, OUTPUTS, READ_ONLY, ROOT, STEPS, WO, WO_BRANCH, WP_BRANCH, git, good_content, scratch, stand)

SUMMARY = f"docs/outsourcing/returns/{WO}/summary.md"
RELAY_MODULES = ("router", "worktree", "ledger", "stepper", "relay")


def broken_test() -> str:
    return good_content(STEPS[0][1]).replace("assert VALUE == 5", "assert VALUE == 6")


# ---------------------------------------------------------------- B18: a report on every finish

def test_FR_1_0_02_fix01_exhausted_run_prints_its_report(scratch, stand):
    stand.script["g-one"].append(("override", {STEPS[0][1]: broken_test()}))
    proc = scratch.run(stand.url, "--attempts", "1")
    assert proc.returncode == 8, proc.stdout + proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines and "EXHAUSTED" in lines[0] and SUMMARY in proc.stdout
    assert "tests" in proc.stdout  # the checks table names the failing check


def test_FR_1_0_02_fix01_questions_run_prints_its_report(scratch, stand):
    stand.script["g-one"].append(("questions",))
    proc = scratch.run(stand.url)
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "QUESTIONS" in proc.stdout and SUMMARY in proc.stdout


def test_FR_1_0_02_fix01_integrity_run_prints_its_report(scratch, stand):
    tampering = good_content(STEPS[0][1]).replace(
        "    assert VALUE", f"    open({READ_ONLY!r}, 'a').write(chr(10) + 'CHANGED = 1' + chr(10))\n    assert VALUE")
    stand.script["g-one"].append(("override", {STEPS[0][1]: tampering}))
    proc = scratch.run(stand.url)
    assert proc.returncode == 9, proc.stdout + proc.stderr
    assert "INTEGRITY" in proc.stdout


# ---------------------------------------------------------------- B7 and WO-1.0-10 B6: real records

def test_FR_1_0_02_fix01_step_log_records_the_orders_sha256(scratch, stand):
    assert scratch.run(stand.url).returncode == 0
    order_sha = hashlib.sha256((scratch.root / ORDER_REL).read_bytes()).hexdigest()
    assert order_sha in scratch.show(WO_BRANCH, f"docs/outsourcing/returns/{WO}/steps.md")


def test_FR_1_0_02_fix01_governor_state_is_relay_governor_json(scratch, stand):
    assert scratch.run(stand.url).returncode == 0
    assert (scratch.root / ".relay/governor.json").is_file()
    assert not (scratch.root / ".relay/governor_state.json").exists()


# ---------------------------------------------------------------- B20: a failed listing is an error

class FailingListing:
    def __init__(self, status: int) -> None:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # keep test output quiet
                return

            def do_GET(self) -> None:
                data = b'{"error": {"message": "listing refused"}}'
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.mark.parametrize("status, exit_code", [(500, 10), (403, 7)], ids=["server-error", "forbidden"])
def test_FR_1_0_14_fix01_failed_listing_is_an_error_not_missing(scratch, status, exit_code):
    server = FailingListing(status)
    try:
        proc = scratch.relay(server.url, "--models")
    finally:
        server.close()
    assert proc.returncode == exit_code, proc.stdout + proc.stderr
    assert not [line for line in proc.stdout.splitlines() if "missing" in line.lower()]
    if exit_code == 7:
        assert any(line.startswith("ACCESS:") for line in proc.stdout.splitlines())


# ---------------------------------------------------------------- B16: final fixes commit only after a pass

def test_FR_1_0_02_fix01_final_fix_is_committed_only_after_checks_pass(scratch, stand):
    # The read-only test needs alpha + beta == 10; the stand-in's files give 5 + 4, so every final round fails.
    scratch.write(READ_ONLY, "from lab_demo.alpha import VALUE as ALPHA\nfrom lab_demo.beta import VALUE as BETA\n\n\n"
                             "def test_demo():\n    assert ALPHA + BETA == 10\n")
    git(scratch.root, "commit", "-qam", "read-only test that the outputs cannot pass")
    git(scratch.root, "push", "-q", "origin", WP_BRANCH)
    scratch.wp_head = scratch.sha(WP_BRANCH)
    proc = scratch.run(stand.url)
    assert proc.returncode == 8, proc.stdout + proc.stderr
    subjects = git(scratch.root, "log", "--format=%s", f"{scratch.wp_head}..{WO_BRANCH}").splitlines()
    assert subjects and not [s for s in subjects if "final fix" in s]


# ---------------------------------------------------------------- B24: the ledger counts every reply

def test_FR_1_0_02_fix01_ledger_counts_every_replys_tokens(scratch, stand):
    stand.script["g-one"].append(("override", {STEPS[0][1]: broken_test()}))
    proc = scratch.run(stand.url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    ledger = scratch.show(WO_BRANCH, f"docs/outsourcing/ledger.d/{WO}.md")
    fields = dict(re.findall(r"^([A-Za-z ]+):\s*(.*?)\s*$", ledger, re.M))
    assert int(fields["Prompt tokens"]) == stand.usage["prompt"]
    assert int(fields["Output tokens"]) == stand.usage["output"]


# ---------------------------------------------------------------- Foundation shape rules

def swallowing_handlers(tree: ast.AST) -> list[int]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"))
        reraises = any(isinstance(n, ast.Raise) for n in ast.walk(node))
        silent = all(isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)) for stmt in node.body)
        if silent or (broad and not reraises):
            found.append(node.lineno)
    return found


@pytest.mark.parametrize("name", RELAY_MODULES)
def test_FR_1_0_02_fix01_relay_modules_follow_the_shape_rules(name):
    text = (ROOT / "tools" / "outsourcing" / f"{name}.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    long_functions = [f"{node.name}:{node.lineno} ({node.end_lineno - node.lineno + 1} lines)"
                      for node in ast.walk(tree)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and node.end_lineno - node.lineno + 1 > 40]
    assert (swallowing_handlers(tree), long_functions, len(text.splitlines()) <= 400) == ([], [], True)
