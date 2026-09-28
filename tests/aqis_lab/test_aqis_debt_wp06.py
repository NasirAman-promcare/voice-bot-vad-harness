"""Accepted debt that targets WP-0.6 (docs/progress/DEBT.md): DEBT-008, closed by owner decision (docs/approvals/WP-0.6.md).

DEBT-008: `score --out` into a folder that cannot be created ended with a traceback and exit 1 instead of the
documented `ERROR:` line and exit 2 (aqis_lab/commands/score.py, write_outputs).
"""
import subprocess
import sys

from aqis_testutil import ROOT

FIXTURES = ROOT / "tests" / "aqis_lab" / "fixtures" / "scoring"


def test_FR_0_3_06_out_folder_that_cannot_be_created_exits_2(tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("not a folder\n", encoding="utf-8")
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "score", "--ref", str(FIXTURES / "ref.csv"), "--hyp",
                           str(FIXTURES / "hyp.csv"), "--out", str(blocker / "sub")], cwd=ROOT, capture_output=True,
                          text=True, timeout=120)
    assert proc.returncode == 2, proc.stderr
    assert proc.stderr.startswith("ERROR: cannot write the outputs in ") and "Traceback" not in proc.stderr
    assert proc.stdout == "" and blocker.read_text(encoding="utf-8") == "not a folder\n"
