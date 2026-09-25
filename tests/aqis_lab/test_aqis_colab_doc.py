"""FR-0.0-13: docs/colab/HARNESS_SETUP.md gives exact Colab cells: clone with the GITHUB_TOKEN secret without storing
it, then one provisioning command whose output becomes docs/environment/colab_harness_provision.txt (OC-0.0-01)."""
import base64
import re
import sys
import traceback
import types

import pytest

from aqis_testutil import ROOT, git, hermetic_git_env

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


def test_FR_0_0_13_clone_failure_never_shows_token(tmp_path, capfd, monkeypatch):
    # Audit F14: a failing clone must not reveal the token, in the error, in cell output or in a variable
    # left in the notebook. google.colab.userdata only exists on Colab; a stand-in returns a known token.
    token = "ghp_AUDIT_F14_token_value_0123456789abcdef"
    colab = types.ModuleType("google.colab")
    colab.userdata = types.SimpleNamespace(get=lambda name: token if name == "GITHUB_TOKEN" else None)
    monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    for key, value in hermetic_git_env().items():
        monkeypatch.setenv(key, value)
    cell1, cell2 = cells()[:2]
    namespace = {}
    exec(compile(cell1, "cell 1", "exec"), namespace)
    namespace["REPO"] = str(tmp_path / "no-such-repository")        # the clone fails
    namespace["WORKDIR"] = str(tmp_path / "clone")
    with pytest.raises(RuntimeError) as failure:
        exec(compile(cell2, "cell 2", "exec"), namespace)
    out, err = capfd.readouterr()
    shown = "".join(traceback.format_exception(failure.value)) + out + err
    assert namespace["BRANCH"] in str(failure.value) and namespace["REPO"] in str(failure.value)
    secrets = (token, base64.b64encode(("x-access-token:" + token).encode()).decode())
    for secret in secrets:
        assert secret not in shown
    left = [name for name, value in namespace.items() if name != "__builtins__"
            and any(secret in repr(value) for secret in secrets)]
    assert left == [], "variables still holding the token after the cell: " + ", ".join(left)
    clone = [line for line in "\n".join(cells()).splitlines() if '"clone"' in line]
    assert "check=True" not in clone[0], "CalledProcessError would print the whole command line"


def test_FR_0_0_13_oc_steps_use_pull_request_branch():
    # Audit F15: before the merge, only the pull request branch has the provisioning script.
    text = DOC.read_text(encoding="utf-8")
    oc = text[text.index("## Owner-run check OC-0.0-01"):]
    namespace = {}
    exec(compile(cells()[0], "cell 1", "exec"), namespace)
    pr_branch = "claude/hopeful-noether-yinc4e"
    steps = re.findall(r"^\d+\. (.*)$", oc, re.M)
    assert f'`BRANCH = "{pr_branch}"`' in steps[0], steps
    assert "Run cells 1 to 6" in steps[1], steps
    assert git(ROOT, "cat-file", "-t", f"HEAD:aqis_lab/deploy/harness_provision.sh").strip() == "blob"
    # the result of a wrong branch is stated
    assert f"Remote branch {namespace['BRANCH']}" not in oc
    assert "not found in upstream origin" in oc and "RuntimeError: git clone of branch" in oc
