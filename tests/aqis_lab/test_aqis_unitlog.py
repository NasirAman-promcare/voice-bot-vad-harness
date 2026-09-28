"""FR-0.5-07: each Colab session appends platform, GPU type, start and end UTC and estimated units to units.csv."""
import csv
import io
import json
import subprocess
import sys
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

import pytest
import yaml

from aqis_lab import unitlog
from aqis_runner_testutil import SMOKE_PACK, stand_in_drive, tree_snapshot
from aqis_testutil import ROOT

RATES_FILE = ROOT / "config" / "aqis_lab" / "colab_rates.yaml"
OWNER_SOURCE = "AQIS Test Lab Build Plan (Colab GPUs features and pricing, March 2026)"
HEADER = ["session_id", "platform", "gpu_type", "start_utc", "end_utc", "end_basis", "hours", "runtime",
          "units_per_hour", "estimated_units", "rate_source"]


def machine(gpu=None):
    return {"platform": "colab", "gpu": gpu, "cpu_model": "Intel(R) Xeon(R) CPU @ 2.20GHz", "architecture": "x86_64",
            "os": "Ubuntu 22.04.4 LTS", "python_version": "3.13.15"}


def committed_rates():
    data = yaml.safe_load(RATES_FILE.read_text(encoding="utf-8"))
    return {r["runtime"]: Fraction(r["units_per_hour"]) for r in data["rates"]}


def expected_units(start, end, rate):
    """hours x rate, rounded half-even to 4 places, computed with fractions from the two timestamps."""
    parse = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
    delta = parse(end) - parse(start)
    hours = Fraction(delta.days * 86400 * 10 ** 6 + delta.seconds * 10 ** 6 + delta.microseconds, 3600 * 10 ** 6)
    q = lambda f: str((Decimal(f.numerator) / Decimal(f.denominator)).quantize(Decimal("0.0001"), ROUND_HALF_EVEN))
    return q(hours), q(hours * rate)


def rows(mount):
    text = (mount / "MyDrive" / "AQIS_LAB" / "logs" / "units.csv").read_text(encoding="utf-8")
    table = list(csv.reader(io.StringIO(text)))
    assert table[0] == HEADER
    return [dict(zip(HEADER, r)) for r in table[1:]]


@pytest.fixture
def lab(tmp_path):
    mount = stand_in_drive(tmp_path)
    (mount / "MyDrive" / "AQIS_LAB" / "logs").mkdir()
    return mount


@pytest.mark.parametrize("gpu, start, end", [
    ("Tesla T4", "2026-09-28T10:00:00.000000Z", "2026-09-28T12:30:00.000000Z"),
    (None, "2026-09-28T10:00:00.000000Z", "2026-09-28T10:45:00.000000Z"),
    ("NVIDIA A100-SXM4-40GB", "2026-09-28T23:10:00.250000Z", "2026-09-29T00:17:13.750000Z"),
    ("NVIDIA L4", "2026-09-28T08:00:00.000000Z", "2026-09-28T08:00:01.000000Z"),
])
def test_FR_0_5_07_appends_row_with_estimate_from_rate_table(lab, gpu, start, end):
    rates = unitlog.load_rates(RATES_FILE)
    unitlog.start_session(lab, machine(gpu), rates, now=start)
    row = unitlog.end_session(lab, rates, now=end)
    runtime = gpu or "cpu"
    hours, units = expected_units(start, end, committed_rates()[runtime])
    written = rows(lab)
    assert written == [row]
    assert row["platform"] == "colab" and row["gpu_type"] == (gpu or "")
    assert row["start_utc"] == start and row["end_utc"] == end and row["end_basis"] == "end-command"
    assert row["hours"] == hours and row["estimated_units"] == units and row["runtime"] == runtime
    assert Fraction(row["units_per_hour"]) == committed_rates()[runtime]
    assert row["rate_source"] == OWNER_SOURCE


def test_FR_0_5_07_append_never_rewrites_existing_rows(lab):
    rates = unitlog.load_rates(RATES_FILE)
    csv_path = lab / "MyDrive" / "AQIS_LAB" / "logs" / "units.csv"
    unitlog.start_session(lab, machine("Tesla T4"), rates, now="2026-09-28T10:00:00.000000Z")
    unitlog.end_session(lab, rates, now="2026-09-28T11:00:00.000000Z")
    first = csv_path.read_bytes()
    unitlog.start_session(lab, machine(None), rates, now="2026-09-28T12:00:00.000000Z")
    unitlog.end_session(lab, rates, now="2026-09-28T12:06:00.000000Z")
    second = csv_path.read_bytes()
    assert second.startswith(first) and len(second) > len(first)
    assert [r["estimated_units"] for r in rows(lab)] == ["1.1900", "0.0080"]
    csv_path.write_text("some,other,file\n", encoding="utf-8")
    unitlog.start_session(lab, machine(None), rates, now="2026-09-28T13:00:00.000000Z")
    with pytest.raises(unitlog.UnitLogError):
        unitlog.end_session(lab, rates, now="2026-09-28T13:01:00.000000Z")
    assert csv_path.read_text(encoding="utf-8") == "some,other,file\n", "never appends to a file of another shape"


def test_FR_0_5_07_unknown_runtime_type_is_an_error(lab):
    rates = unitlog.load_rates(RATES_FILE)
    before = tree_snapshot(lab)
    with pytest.raises(unitlog.UnitLogError) as err:
        unitlog.start_session(lab, machine("NVIDIA H100 80GB HBM3"), rates, now="2026-09-28T10:00:00.000000Z")
    assert "NVIDIA H100 80GB HBM3" in str(err.value) and "colab_rates.yaml" in str(err.value)
    assert tree_snapshot(lab) == before


@pytest.mark.parametrize("text, words", [
    ('schema_version: "1.0"\nrates:\n  - {runtime: cpu, units_per_hour: "0.08"}\n', "source"),
    ('schema_version: "1.0"\nrates:\n  - {runtime: cpu, units_per_hour: "0.08", source: ""}\n', "source"),
    ('schema_version: "1.0"\nrates:\n  - {runtime: cpu, units_per_hour: "-1", source: s}\n', "positive"),
    ('schema_version: "1.0"\nrates:\n  - {runtime: cpu, units_per_hour: 0.08, source: s}\n', "string"),
    ('schema_version: "1.0"\nrates:\n  - {runtime: cpu, units_per_hour: "0.08", source: s}\n'
     '  - {runtime: cpu, units_per_hour: "0.09", source: s}\n', "twice"),
])
def test_FR_0_5_07_every_rate_names_its_source(tmp_path, text, words):
    for rate in yaml.safe_load(RATES_FILE.read_text(encoding="utf-8"))["rates"]:
        assert isinstance(rate["source"], str) and rate["source"].strip()
    bad = tmp_path / "rates.yaml"
    bad.write_text(text, encoding="utf-8")
    with pytest.raises(unitlog.UnitLogError) as err:
        unitlog.load_rates(bad)
    assert words in str(err.value)


def test_FR_0_5_07_committed_rates_equal_owner_figures():
    # docs/approvals/WP-0.5.md: cpu 0.08, Tesla T4 1.19, NVIDIA L4 1.71, NVIDIA A100-SXM4-40GB 5.40 units per hour
    assert committed_rates() == {"cpu": Fraction("0.08"), "Tesla T4": Fraction("1.19"), "NVIDIA L4": Fraction("1.71"),
                                 "NVIDIA A100-SXM4-40GB": Fraction("5.40")}
    data = yaml.safe_load(RATES_FILE.read_text(encoding="utf-8"))
    assert {r["source"] for r in data["rates"]} == {OWNER_SOURCE}
    loaded = unitlog.load_rates(RATES_FILE)
    assert {k: Fraction(str(v.units_per_hour)) for k, v in loaded.items()} == committed_rates()


def test_FR_0_5_07_unclosed_session_is_closed_at_next_start(lab):
    rates = unitlog.load_rates(RATES_FILE)
    unitlog.start_session(lab, machine("Tesla T4"), rates, now="2026-09-28T10:00:00.000000Z")
    unitlog.touch(lab, now="2026-09-28T10:20:00.000000Z")
    unitlog.touch(lab, now="2026-09-28T10:40:00.000000Z")
    # the runtime died here without `unitlog end`
    closed, opened = unitlog.start_session(lab, machine(None), rates, now="2026-09-28T13:00:00.000000Z")
    assert closed is not None and closed["end_utc"] == "2026-09-28T10:40:00.000000Z"
    assert closed["end_basis"] == "last-seen" and closed["hours"] == "0.6667"
    assert closed["estimated_units"] == expected_units("2026-09-28T10:00:00.000000Z", "2026-09-28T10:40:00.000000Z",
                                                       Fraction("1.19"))[1]
    assert opened["start_utc"] == "2026-09-28T13:00:00.000000Z" and opened["gpu_type"] is None
    assert [r["end_basis"] for r in rows(lab)] == ["last-seen"]
    unitlog.end_session(lab, rates, now="2026-09-28T13:30:00.000000Z")
    assert [r["end_basis"] for r in rows(lab)] == ["last-seen", "end-command"]
    with pytest.raises(unitlog.UnitLogError):
        unitlog.end_session(lab, rates, now="2026-09-28T14:00:00.000000Z")        # no open session any more


def test_FR_0_5_07_run_and_doctor_keep_last_seen_current(lab, tmp_path):
    rates = unitlog.load_rates(RATES_FILE)
    start = "2000-01-01T00:00:00.000000Z"                       # before any real clock reading
    unitlog.start_session(lab, machine(None), rates, now=start)
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "run", "--task", "clip-stats", "--pack", str(SMOKE_PACK),
                           "--out", str(tmp_path / "run"), "--seed", "0", "--work-dir", str(tmp_path / "work"),
                           "--drive-mount", str(lab)], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr
    path = lab / "MyDrive" / "AQIS_LAB" / "logs" / unitlog.OPEN_SESSION
    state = json.loads(path.read_text(encoding="utf-8"))
    assert state["state"] == "open" and state["start_utc"] == start and state["last_seen_utc"] > start
    after_run = state["last_seen_utc"]
    proc = subprocess.run([sys.executable, "-m", "aqis_lab", "doctor", "--target", "colab", "--drive-mount", str(lab),
                           "--out", str(tmp_path / "doctor")], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 1, proc.stderr          # this VM is not Colab: the platform row fails
    assert json.loads(path.read_text(encoding="utf-8"))["last_seen_utc"] > after_run


def test_FR_0_5_07_refuses_outside_colab(lab):
    before = tree_snapshot(lab)
    for action in ("start", "end"):
        proc = subprocess.run([sys.executable, "-m", "aqis_lab", "unitlog", action, "--drive-mount", str(lab)],
                              cwd=ROOT, capture_output=True, text=True, timeout=300)
        assert proc.returncode == 2 and "Colab" in proc.stderr and "cloud-vm" in proc.stderr
    assert tree_snapshot(lab) == before


def test_FR_0_5_07_writes_only_under_aqis_lab_logs(lab):
    rates = unitlog.load_rates(RATES_FILE)
    before = set(tree_snapshot(lab))
    unitlog.start_session(lab, machine("Tesla T4"), rates, now="2026-09-28T10:00:00.000000Z")
    unitlog.touch(lab, now="2026-09-28T10:05:00.000000Z")
    unitlog.end_session(lab, rates, now="2026-09-28T10:10:00.000000Z")
    assert set(tree_snapshot(lab)) - before == {"MyDrive/AQIS_LAB/logs/units.csv",
                                                f"MyDrive/AQIS_LAB/logs/{unitlog.OPEN_SESSION}"}
