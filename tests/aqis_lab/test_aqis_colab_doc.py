"""FR-0.0-13: docs/colab/HARNESS_SETUP.md gives exact Colab cells: clone with the GITHUB_TOKEN secret without storing
it, then one provisioning command whose output becomes docs/environment/colab_harness_provision.txt (OC-0.0-01)."""
import re

from aqis_testutil import ROOT

DOC = ROOT / "docs" / "colab" / "HARNESS_SETUP.md"


def cells():
    return re.findall(r"^```python\n(.*?)^```", DOC.read_text(encoding="utf-8"), re.M | re.S)


def test_FR_0_0_13_colab_doc_cells_are_valid_python():
    found = cells()
    assert len(found) >= 3
    for i, code in enumerate(found, start=1):
        compile(code, f"cell {i}", "exec")          # plain Python: no shell magics that could hide a failure


def test_FR_0_0_13_token_used_only_for_the_clone_command():
    code = "\n".join(cells())
    assert 'userdata.get("GITHUB_TOKEN")' in code
    assert code.count("http.extraHeader") == 1
    clone = [line for line in code.splitlines() if '"clone"' in line]
    assert len(clone) == 1 and '"-c"' in clone[0]
    # the token never becomes part of a URL, a remote or a git config entry
    assert not re.search(r"https://[^\"'\s]*\{?token", code, re.I)
    assert not re.search(r"x-access-token:[^\"']*@", code)
    for forbidden in ('"config", "--global"', "credential.helper", "set-url", "store", "os.environ[\"GITHUB_TOKEN\"]"):
        assert forbidden not in code, forbidden
    assert "del token" in code
    # the doc proves it: no extraheader and no token in the remote after cloning
    assert re.search(r'"config", "--list", "--show-origin"', code) and "extraheader" in code.lower()


def test_FR_0_0_13_one_provisioning_command_and_report():
    code = "\n".join(cells())
    assert code.count("aqis_lab/deploy/harness_provision.sh") == 1
    assert "colab_harness_provision.txt" in code
    assert '"status", "--porcelain"' in code
    text = DOC.read_text(encoding="utf-8")
    assert "docs/environment/colab_harness_provision.txt" in text
    assert "OC-0.0-01" in text
    assert "every row PASS" in text
