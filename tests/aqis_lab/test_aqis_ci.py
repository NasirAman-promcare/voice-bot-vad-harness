"""FR-0.0-10 (amended) and FR-0.0-11 (amended): .github/workflows/aqis-lab-ci.yml.

Job `lab`: sets up the Colab Python, installs the lock with hashes, runs the fast lab suite and the gate (with
the WP ID from the pull request title on pull requests). Job `harness-regression`: provisions the harness,
runs its tests and fails on any regression against the provisioned baseline. Neither job can change or trigger
another workflow."""
import os
import re
import subprocess

import yaml

from aqis_testutil import FAST_MARKERS, LAB_MARKERS, ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "aqis-lab-ci.yml"


def load():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1 reads the bare key `on` as boolean True.
    triggers = doc.get("on", doc.get(True))
    return doc, triggers


def steps(job="lab"):
    doc, _ = load()
    return doc["jobs"][job]["steps"]


def run_scripts(job="lab"):
    return [s.get("run", "") for s in steps(job)]


def test_FR_0_0_10_ci_triggers_push_and_pull_request():
    doc, triggers = load()
    keys = set(triggers) if isinstance(triggers, dict) else set(triggers if isinstance(triggers, list) else [triggers])
    assert keys == {"push", "pull_request"}
    assert set(doc["jobs"]) == {"lab", "harness-regression", "lab-network"}  # lab-network: WP-0.9 DEBT-019


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
    for job in ("lab", "harness-regression"):
        # No other installation route that could bypass the hashed locks.
        assert not any(re.search(r"\bpip install\b|uv pip install|setup-python", s) for s in run_scripts(job))
        assert not any(str(s.get("uses", "")).startswith("actions/setup-python") for s in steps(job))


def test_FR_0_0_10_ci_runs_fast_suite_with_exact_markers():
    expected = " and ".join(f"not {m}" for m in LAB_MARKERS)
    assert expected == FAST_MARKERS
    commands = [s for s in run_scripts("lab") if "-m pytest" in s]
    assert commands == [f'.venv/bin/python -m pytest tests/aqis_lab -q -m "{expected}"']


def _wp_step():
    found = [s for s in steps() if "PR_TITLE" in (s.get("env") or {})]
    assert len(found) == 1, "exactly one step reads the pull request title"
    return found[0]


def test_FR_0_0_10_ci_takes_wp_from_pr_title():
    step = _wp_step()
    assert step["if"] == "github.event_name == 'pull_request'"
    assert step["env"] == {"PR_TITLE": "${{ github.event.pull_request.title }}"}
    assert "${{" not in step["run"], "GitHub expressions go through env, never inline in the script"
    gate_steps = [s for s in steps() if "tools.audit.gate" in s.get("run", "")]
    assert len(gate_steps) == 1
    names = [s.get("name") for s in steps()]
    assert names.index(step["name"]) < names.index(gate_steps[0]["name"])


def _parse_title(tmp_path, title):
    env_file = tmp_path / "github_env"
    env_file.write_text("", encoding="utf-8")
    env = dict(os.environ, PR_TITLE=title, GITHUB_ENV=str(env_file))
    proc = subprocess.run(["bash", "-e", "-c", _wp_step()["run"]], env=env, capture_output=True, text=True, timeout=30)
    return proc, env_file.read_text(encoding="utf-8")


def test_FR_0_0_10_pr_title_parser(tmp_path):
    for title, wp in (("WP-0.0 Guardrails and audit tooling", "WP-0.0"), ("WP-0.12: contracts", "WP-0.12"),
                      ("WP-1.3", "WP-1.3")):
        proc, written = _parse_title(tmp_path, title)
        assert proc.returncode == 0, (title, proc.stderr)
        assert written == f"WP_ID={wp}\n", (title, written)
    for title in ("Guardrails and audit tooling", "WP-0.0x tooling", "wp-0.0 lower case", "[WP-0.0] brackets",
                  "WP-0 missing number", "WP-0.0\nWP_ID=injected",
                  # the ID must start the title (audit F11): an ID later in the title is not the PR's WP
                  "Guardrails WP-0.0", "Fix typo, see WP-0.3 notes", " WP-0.0 leading space"):
        proc, written = _parse_title(tmp_path, title)
        assert proc.returncode != 0, title
        assert written == "" and "ERROR:" in proc.stderr, title


def test_FR_0_0_10_ci_gate_base_selection():
    gate_steps = [s for s in steps() if "tools.audit.gate" in s.get("run", "")]
    step = gate_steps[0]
    assert step["env"] == {"EVENT_NAME": "${{ github.event_name }}", "BASE_REF": "${{ github.base_ref }}"}
    script = step["run"]
    assert "${{" not in script, "GitHub expressions go through env, never inline in the script"
    assert 'if [ "$EVENT_NAME" = "pull_request" ]; then' in script
    assert '.venv/bin/python -m tools.audit.gate --base "origin/$BASE_REF" --wp "$WP_ID"' in script
    assert '.venv/bin/python -m tools.audit.gate --base "origin/main"' in script


def test_FR_0_0_11_ci_has_harness_regression_job():
    doc, _ = load()
    job = doc["jobs"]["harness-regression"]
    assert job["runs-on"] == "ubuntu-24.04"
    job_steps = job["steps"]
    checkout = [s for s in job_steps if str(s.get("uses", "")).startswith("actions/checkout@")]
    assert checkout and checkout[0]["with"]["fetch-depth"] == 0, "the corpus is read from git history"
    scripts = run_scripts("harness-regression")
    order = [next(i for i, s in enumerate(scripts) if needle in s) for needle in (
        "bash aqis_lab/deploy/harness_provision.sh",
        ".venv-harness/bin/python -m pytest tests/regression",
        ".venv-harness/bin/python -m tools.harness.regression_check --junit")]
    assert order == sorted(order)
    tests_script = scripts[order[1]]
    assert '--junitxml="$RUNNER_TEMP/harness_junit.xml"' in tests_script
    assert '--junit "$RUNNER_TEMP/harness_junit.xml"' in scripts[order[2]]
    assert not any(s.get("continue-on-error") for s in job_steps)


def test_FR_0_0_10_ci_cannot_change_or_trigger_other_workflows():
    doc, _ = load()
    assert doc["permissions"] == {"contents": "read"}
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("workflow_run", "workflow_call", "repository_dispatch", "workflow_dispatch", "gh workflow",
                      "/dispatches", "uses: ./.github", "git push", "secrets."):
        assert forbidden not in text, forbidden
    for job in doc["jobs"]:
        assert "permissions" not in doc["jobs"][job], "jobs inherit the read-only workflow permissions"
        for s in steps(job):
            uses = str(s.get("uses", ""))
            assert uses == "" or uses.split("@")[0] in ("actions/checkout", "astral-sh/setup-uv"), uses
    lab_workflows = sorted(p.name for p in WORKFLOW.parent.glob("aqis-lab-*.yml"))
    assert lab_workflows == ["aqis-lab-ci.yml"]
