"""FR-0.0-10: .github/workflows/aqis-lab-ci.yml sets up the Colab Python, installs the lock with hashes,
runs the fast lab suite and the gate, on push and pull request, without touching other workflows."""
import re

import yaml

from aqis_testutil import FAST_MARKERS, LAB_MARKERS, ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "aqis-lab-ci.yml"


def load():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1 reads the bare key `on` as boolean True.
    triggers = doc.get("on", doc.get(True))
    return doc, triggers


def steps():
    doc, _ = load()
    jobs = doc["jobs"]
    assert len(jobs) == 1, "one job expected"
    return next(iter(jobs.values()))["steps"]


def run_scripts():
    return [s.get("run", "") for s in steps()]


def test_FR_0_0_10_ci_triggers_push_and_pull_request():
    _, triggers = load()
    keys = set(triggers) if isinstance(triggers, dict) else set(triggers if isinstance(triggers, list) else [triggers])
    assert keys == {"push", "pull_request"}


def test_FR_0_0_10_ci_bootstraps_probe_python_and_hashed_lock():
    all_steps = steps()
    checkout = [s for s in all_steps if str(s.get("uses", "")).startswith("actions/checkout@")]
    assert checkout and checkout[0]["with"]["fetch-depth"] == 0, "full history needed for merge-base and origin/main"
    uv = [s for s in all_steps if str(s.get("uses", "")).startswith("astral-sh/setup-uv@")]
    assert uv and str(uv[0]["with"]["version"]) == "0.8.17"
    scripts = run_scripts()
    boot = [i for i, s in enumerate(scripts) if s.strip() == "bash aqis_lab/deploy/dev_bootstrap.sh"]
    assert boot, "CI must build .venv with the same bootstrap as development (probe Python, hash-checked lock)"
    version = [i for i, s in enumerate(scripts) if ".venv/bin/python -m aqis_lab version" in s]
    assert version and version[0] > boot[0]
    # No other installation route that could bypass the hashed lock.
    assert not any(re.search(r"\bpip install\b|uv pip install|setup-python", s) for s in scripts)
    assert not any(str(s.get("uses", "")).startswith("actions/setup-python") for s in all_steps)


def test_FR_0_0_10_ci_runs_fast_suite_with_exact_markers():
    expected = " and ".join(f"not {m}" for m in LAB_MARKERS)
    assert expected == FAST_MARKERS
    commands = [s for s in run_scripts() if "-m pytest" in s]
    assert commands == [f'.venv/bin/python -m pytest tests/aqis_lab -q -m "{expected}"']


def test_FR_0_0_10_ci_gate_base_selection():
    gate_steps = [s for s in steps() if "tools.audit.gate" in s.get("run", "")]
    assert len(gate_steps) == 1
    step = gate_steps[0]
    assert step["env"] == {"EVENT_NAME": "${{ github.event_name }}", "BASE_REF": "${{ github.base_ref }}"}
    script = step["run"]
    assert "${{" not in script, "GitHub expressions go through env, never inline in the script"
    assert 'if [ "$EVENT_NAME" = "pull_request" ]; then BASE="origin/$BASE_REF"; else BASE="origin/main"; fi' in script
    assert '.venv/bin/python -m tools.audit.gate --base "$BASE"' in script


def test_FR_0_0_10_ci_cannot_change_or_trigger_other_workflows():
    doc, _ = load()
    assert doc["permissions"] == {"contents": "read"}
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("workflow_run", "workflow_call", "repository_dispatch", "workflow_dispatch", "gh workflow",
                      "/dispatches", "uses: ./.github", "git push", "secrets."):
        assert forbidden not in text, forbidden
    for s in steps():
        uses = str(s.get("uses", ""))
        assert uses == "" or uses.split("@")[0] in ("actions/checkout", "astral-sh/setup-uv"), uses
    lab_workflows = sorted(p.name for p in WORKFLOW.parent.glob("aqis-lab-*.yml"))
    assert lab_workflows == ["aqis-lab-ci.yml"]
