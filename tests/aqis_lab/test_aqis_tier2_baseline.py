"""WP-0.1: Tier 2 VAD transport baseline (docs/baselines/tier2_vad/<date>/raw/ and SUMMARY.md).

FR-0.1-01: raw/ holds every required item R1 to R8 (docs/progress/WP-0.1/PLAN.md, "Required raw items"), consistent
with each other, and the Raw inventory lists exactly the files that are there.
FR-0.1-02: every number in SUMMARY.md cites a Sources row that resolves, in its raw file, to the value shown.
FR-0.1-03: the WP adds only SUMMARY.md beside the owner's raw/, and leaves the raw files byte for byte as committed.

Expected values come from the raw files (and, for the owner's statement, from docs/approvals/WP-0.1.md), never from
SUMMARY.md. The harness metric formulas are recomputed here from reporting.py's definitions (_aggregate_confusion_counts
and the per-clip latency means) and compared with the harness's own report and run log.
"""
import json
import math
import re
import shutil

import pytest

from aqis_baseline_testutil import (APPROVAL, BASELINES, DATE_RE, INVENTORY_COLUMNS, RECORD_TYPES,
                                    REPORT_NON_OPERATING_POINT,
                                    REQUIRED_ITEMS, ROUNDING_RE, SUMMARY_SECTIONS, baseline_folders, inventory_files,
                                    inventory_hash_problems, notebook_texts, pipe_table,
                                    raw_problems, read_records, read_text, resolve_sources, sources_table,
                                    summary_problems, summary_sections, citation_problems, binding_problems)

AUDIO_MAGIC = (b"RIFF", b"fLaC", b"OggS", b"ID3", b"\x1aE\xdf\xa3")
HEADLINE_FIRST_HEADER = "Operating point"
# Headline columns and the kinds of source each must cite (PLAN.md, "Headline metrics per VAD operating point").
HEADLINE_SOURCES = {
    "F1": ("report", "log", "derived"),
    "Precision": ("report", "log", "derived"),
    "Recall": ("report", "log", "derived"),
    "FPR (silence-only)": ("report", "derived"),
    "FNR (quiet/whispered)": ("report", "derived"),
    "Onset mean (ms)": ("report", "derived"),
    "Onset median (ms)": ("derived",),
    "Offset hangover mean (ms)": ("report", "derived"),
    "Offset hangover median (ms)": ("derived",),
    "Wall-clock pipeline mean (ms)": ("derived",),
    "Wall-clock pipeline median (ms)": ("derived",),
    "Clips scored": ("log", "derived"),
    "Clips with no onset": ("derived",),
    "Clips with no resolved hangover": ("derived",),
}


def folders():
    found = baseline_folders()
    assert found, f"no dated baseline folder under {BASELINES}"
    return found


def item_file(folder, item):
    return folder / "raw" / inventory_files(folder)[item][0]


def run_records(folder):
    return read_records(item_file(folder, "R5"))


def points_of(folder):
    return sorted({r["adapter_id"] for r in run_records(folder) if r["record_type"] != "run_context"})


def identifiers(folder):
    """Code spans that may hold digits without a citation: the baseline folder's date, raw file names, the run ID,
    operating point IDs and the harness record types."""
    records = run_records(folder)
    return ({folder.name} | {p.name for p in (folder / "raw").iterdir()} | {r["run_id"] for r in records}
            | set(points_of(folder)) | set(RECORD_TYPES))


def kind_of(row):
    """report, log, network, config or records for a direct row; derived for a derived row."""
    if row["Kind"] == "derived":
        return "derived"
    name = row["File"]
    return {".ipynb": "report", ".log": "log", ".md": "network", ".yaml": "config",
            ".jsonl": "records", ".txt": "harness"}[name[name.rindex("."):]]


# ---------------------------------------------------------------------------------------------- FR-0.1-01
def test_FR_0_1_01_raw_folder_has_every_required_item():
    for folder in folders():
        listed = inventory_files(folder)
        for item in REQUIRED_ITEMS:
            assert listed.get(item), f"{folder.name}: {item} has no file in the Raw inventory"
            for name in listed[item]:
                path = folder / "raw" / name
                assert path.is_file() and path.stat().st_size > 0, f"{folder.name}: {item} raw/{name} missing or empty"
        assert [p for p in raw_problems(folder) if " missing" in p] == []


def test_FR_0_1_01_inventory_lists_every_raw_file():
    for folder in folders():
        rows = pipe_table(summary_sections(read_text(folder / "SUMMARY.md"))["Raw inventory"], "Item")
        assert tuple(rows[0]) == INVENTORY_COLUMNS
        listed = [r["File"].strip("`") for r in rows[1]]
        present = sorted(p.name for p in (folder / "raw").iterdir())
        assert sorted(listed) == present, f"{folder.name}: inventory {sorted(listed)} != raw/ {present}"


def test_FR_0_1_01_raw_files_agree_on_the_run():
    for folder in folders():
        assert raw_problems(folder) == []


def test_FR_0_1_01_raw_folder_holds_no_audio():
    for folder in folders():
        for path in sorted((folder / "raw").iterdir()):
            head = path.read_bytes()[:4]
            assert not head.startswith(AUDIO_MAGIC), f"{path.name} starts like an audio file ({head!r})"
            assert path.suffix.lower() not in (".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".webm")


def test_FR_0_1_01_check_reports_each_missing_item(tmp_path):
    """Must-catch 2: a missing raw file is reported as missing, and no number citing it is accepted."""
    for folder in folders():
        listed = inventory_files(folder)
        sources = sources_table(read_text(folder / "SUMMARY.md"))
        for item in REQUIRED_ITEMS:
            for name in listed[item]:
                copy = tmp_path / f"{folder.name}-{item}-{name}"
                shutil.copytree(folder, copy)
                (copy / "raw" / name).unlink()
                problems = raw_problems(copy)
                assert f"{item} missing: raw/{name} does not exist" in problems, problems
                citing = [sid for sid, row in sources.items() if row["File"] == name]
                reported = "\n".join(summary_problems(copy, identifiers(folder)))
                for sid in citing:
                    assert f"{sid} (raw/{name}" in reported and "is missing" in reported, (sid, reported[:500])


# ---------------------------------------------------------------------------------------------- FR-0.1-02
def test_FR_0_1_02_summary_has_every_section():
    statement = re.search(r'"(Negative wall-clock pipeline latencies.+?)"', read_text(APPROVAL), re.S).group(1)
    for folder in folders():
        text = read_text(folder / "SUMMARY.md")
        assert list(summary_sections(text)) == list(SUMMARY_SECTIONS)
        owner = summary_sections(text)["Owner's statement"]
        assert "owner's statement" in owner.lower()
        assert " ".join(statement.split()) in " ".join(owner.replace(">", " ").split())


def test_FR_0_1_02_every_number_cites_a_source():
    for folder in folders():
        text = read_text(folder / "SUMMARY.md")
        assert citation_problems(text, sources_table(text), identifiers(folder)) == []


def test_FR_0_1_02_every_number_matches_its_cited_source():
    for folder in folders():
        values, problems = resolve_sources(folder)
        assert problems == []
        assert len(values) == len(sources_table(read_text(folder / "SUMMARY.md")))


def test_FR_0_1_02_derived_numbers_show_formula_inputs_and_rounding():
    for folder in folders():
        rows = sources_table(read_text(folder / "SUMMARY.md"))
        for sid, row in rows.items():
            loc = json.loads(row["Locator"])
            if row["Kind"] == "direct":
                assert row["Rounding"] == "as shown", sid
                continue
            assert row["Kind"] == "derived", sid
            assert ROUNDING_RE.match(row["Rounding"]), (sid, row["Rounding"])
            formula = row["Formula and inputs"]
            if "expr" in loc:
                assert loc["expr"] in formula, (sid, formula)
                for ref in re.findall(r"S\d+", loc["expr"]):
                    assert ref in rows, (sid, ref)
            else:
                assert formula.startswith(loc["op"] + "("), (sid, formula)
                if loc["op"] != "count":
                    assert f"`{loc['field']}`" in formula, (sid, formula)
                for key, value in loc["where"].items():
                    assert f"{key} = {value}" in formula, (sid, key, formula)


def test_FR_0_1_02_headline_metrics_cover_every_operating_point():
    for folder in folders():
        text = read_text(folder / "SUMMARY.md")
        rows = sources_table(text)
        header, table = pipe_table(summary_sections(text)["Headline metrics per VAD"], HEADLINE_FIRST_HEADER)
        assert header[1:] == list(HEADLINE_SOURCES)
        assert sorted(r[HEADLINE_FIRST_HEADER].strip("`") for r in table) == points_of(folder)
        for r in table:
            for col, kinds in HEADLINE_SOURCES.items():
                cited = re.findall(r"\[(S\d+)\]", r[col])
                assert sorted(kind_of(rows[s]) for s in cited) == sorted(kinds), (r[HEADLINE_FIRST_HEADER], col)


def test_FR_0_1_02_cells_cite_their_own_row_and_column():
    """WP-0.1-F1: each table cell cites exactly the Sources of its row's operating point or category and of its
    column's metric (report column, run-log label, or record field and selection, through 'expr' formulas)."""
    for folder in folders():
        assert binding_problems(folder) == []


def _harness_metrics(records, point):
    """reporting.py's Tier 2 summary metrics for one operating point, recomputed from the records."""
    clips = [r["payload"] for r in records if r["record_type"] == "scoring_clip" and r["adapter_id"] == point]
    lat = [r["payload"] for r in records if r["record_type"] == "tier2_pipeline_latency" and r["adapter_id"] == point]

    def sums(cs):
        return {k: sum(c["metrics"][k] for c in cs) for k in ("tp", "fp", "tn", "fn")}
    s = sums(clips)
    p, rcl = s["tp"] / (s["tp"] + s["fp"]), s["tp"] / (s["tp"] + s["fn"])
    sil = sums([c for c in clips if c["category"] == "silence-only"])
    quiet = sums([c for c in clips if c["category"] == "quiet/whispered speech"])
    onset = [x["mean_onset_latency_ms"] for x in lat if x["mean_onset_latency_ms"] is not None]
    offset = [x["mean_offset_hangover_latency_ms"] for x in lat if x["mean_offset_hangover_latency_ms"] is not None]
    return {
        "Precision": f"{round(p, 3):.3f}", "Recall": f"{round(rcl, 3):.3f}",
        "F1": f"{round(2 * p * rcl / (p + rcl), 3):.3f}",
        "FPR (Silence)": f"{round(sil['fp'] / (sil['fp'] + sil['tn']), 3):.3f}",
        "FNR (Quiet)": f"{round(quiet['fn'] / (quiet['fn'] + quiet['tp']), 3):.3f}",
        "Onset Latency": f"{round(math.fsum(onset) / len(onset), 1):.1f} ms",
        "Offset Hangover": f"{round(math.fsum(offset) / len(offset), 1):.1f} ms",
        "clips": str(len(clips)),
    }


def test_FR_0_1_02_report_log_and_records_agree():
    """The harness report (R6) and run log (R7) state what the records (R5) give under reporting.py's formulas."""
    for folder in folders():
        records = run_records(folder)
        report = json.loads(read_text(item_file(folder, "R6")))
        table = None
        for _, _, t in notebook_texts(report):
            if t.lstrip().startswith("| Adapter / Operating Point"):
                table = {r["Adapter / Operating Point"]: r for r in pipe_table(t, "Adapter / Operating Point")[1]}
        assert table is not None
        log = read_text(item_file(folder, "R7"))
        for point in points_of(folder):
            want = _harness_metrics(records, point)
            for col in ("F1", "Precision", "Recall", "FPR (Silence)", "FNR (Quiet)", "Onset Latency",
                        "Offset Hangover"):
                assert table[point][col] == want[col], (point, col, table[point][col], want[col])
            m = re.search(rf"Tier 2 Completed for '{point}': Evaluated (\d+) clips \| Precision: ([\d.]+) \| "
                          rf"Recall: ([\d.]+) \| F1: ([\d.]+)", log)
            assert m, point
            assert m.groups() == (want["clips"], want["Precision"], want["Recall"], want["F1"]), (point, m.groups())
        assert set(table) - set(points_of(folder)) <= {REPORT_NON_OPERATING_POINT}


def _bump_last_digit(text):
    """'0.910' -> '0.911', '9' -> '0' with a carry-free change of the last digit."""
    return text[:-1] + str((int(text[-1]) + 1) % 10)


def _edit_jsonl_direct(raw):
    path = raw / "raw_evaluations.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        r = json.loads(line)
        if r["record_type"] == "run_context":
            r["payload"]["python_version"] = _bump_last_digit(r["payload"]["python_version"])
            lines[i] = json.dumps(r)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.name


def _edit_jsonl_derived_input(raw):
    path = raw / "raw_evaluations.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        r = json.loads(line)
        if r["record_type"] == "scoring_clip":
            r["payload"]["metrics"]["tp"] += 1
            lines[i] = json.dumps(r)
            break
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.name


def _edit_yaml(raw):
    path = raw / "bridge_config.yaml"
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^opus_bitrate_bps: (\d+)$", text, re.M)
    path.write_text(text[:m.start(1)] + _bump_last_digit(m.group(1)) + text[m.end(1):], encoding="utf-8")
    return path.name


def _edit_log_line(raw):
    path = raw / "run.log"
    text = path.read_text(encoding="utf-8")
    m = re.search(r"Tier 2 Completed for '[^']+'.*\| F1: ([\d.]+)", text)
    path.write_text(text[:m.start(1)] + _bump_last_digit(m.group(1)) + text[m.end(1):], encoding="utf-8")
    return path.name


def _edit_report_cell(raw):
    path = raw / "03_report.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))
    for cell in nb["cells"]:
        for out in cell.get("outputs", []):
            md = out.get("data", {}).get("text/markdown")
            text = "".join(md) if isinstance(md, list) else md
            if text and text.lstrip().startswith("| Adapter / Operating Point"):
                lines = text.split("\n")
                cells = lines[2].split("|")
                cells[3] = cells[3].replace(cells[3].strip(), _bump_last_digit(cells[3].strip()))
                lines[2] = "|".join(cells)
                out["data"]["text/markdown"] = "\n".join(lines)
                path.write_text(json.dumps(nb), encoding="utf-8")
                return path.name
    raise AssertionError("no report summary table to edit")


@pytest.mark.parametrize("edit", [_edit_jsonl_direct, _edit_jsonl_derived_input, _edit_yaml, _edit_log_line,
                                  _edit_report_cell],
                         ids=["jsonl-direct", "jsonl-derived-input", "yaml", "log-line", "report-cell"])
def test_FR_0_1_02_check_reports_a_changed_raw_value(tmp_path, edit):
    """Must-catch 1: change one raw value in a copy; the check reports a mismatch naming the source ID and file."""
    for folder in folders():
        assert summary_problems(folder, identifiers(folder)) == []
        copy = tmp_path / folder.name
        shutil.copytree(folder, copy)
        name = edit(copy / "raw")
        problems = summary_problems(copy, identifiers(folder))
        assert problems, f"changing raw/{name} went unnoticed"
        sources = sources_table(read_text(folder / "SUMMARY.md"))
        named = {p.split(" ", 1)[0] for p in problems}
        assert any(sid in sources and sources[sid]["File"] == name for sid in named), problems


# ---------------------------------------------------------------------------------------------- FR-0.1-03
def test_FR_0_1_03_baseline_folder_holds_only_summary_and_raw():
    assert all(DATE_RE.match(p.name) and p.is_dir() for p in BASELINES.iterdir())
    for folder in folders():
        assert sorted(p.name for p in folder.iterdir()) == ["SUMMARY.md", "raw"]
        assert all(p.is_file() for p in (folder / "raw").iterdir())


def test_FR_0_1_03_raw_files_unchanged_since_inventory():
    for folder in folders():
        assert inventory_hash_problems(folder) == []
        assert len(inventory_files(folder)) >= len(REQUIRED_ITEMS)


# ---------------------------------------------------------------------------------------------- round 2 self-tests
def _header_index(lines, section, first_header):
    """Index of the header line of the first pipe table headed first_header after the '## section' heading."""
    top = lines.index(f"## {section}")
    return next(i for i in range(top, len(lines)) if lines[i].startswith(f"| {first_header} |"))


def _table_lines(lines, section, first_header):
    """Indexes of the data rows of that SUMMARY.md pipe table."""
    start = _header_index(lines, section, first_header)
    out = []
    for i in range(start + 2, len(lines)):
        if not lines[i].startswith("|"):
            break
        out.append(i)
    return out


def _cells(line):
    return line.split("|")


def _swap_rows(section, first_header, a, b):
    """Swap every cell but the first between the rows labelled a and b; the row labels stay."""
    def edit(lines):
        rows = {_cells(lines[i])[1].strip().strip("`"): i for i in _table_lines(lines, section, first_header)}
        ca, cb = _cells(lines[rows[a]]), _cells(lines[rows[b]])
        lines[rows[a]] = "|".join(ca[:2] + cb[2:])
        lines[rows[b]] = "|".join(cb[:2] + ca[2:])
    return edit


def _swap_columns(section, first_header, row, col_a, col_b):
    """Swap two cells of one row."""
    def edit(lines):
        header = [c.strip() for c in _cells(lines[_header_index(lines, section, first_header)])]
        ia, ib = header.index(col_a), header.index(col_b)
        i = next(i for i in _table_lines(lines, section, first_header)
                 if _cells(lines[i])[1].strip().strip("`") == row)
        cells = _cells(lines[i])
        cells[ia], cells[ib] = cells[ib], cells[ia]
        lines[i] = "|".join(cells)
    return edit


HEADLINE = "Headline metrics per VAD"
CELL_SWAPS = {
    "headline-rows": _swap_rows(HEADLINE, "Operating point", "ten_vad", "firered_vad"),
    "headline-f1-precision": _swap_columns(HEADLINE, "Operating point", "ten_vad", "F1", "Precision"),
    "headline-mean-median": _swap_columns(HEADLINE, "Operating point", "webrtc_vad_mode1", "Onset mean (ms)",
                                          "Onset median (ms)"),
    "frame-counts": _swap_columns(HEADLINE, "Operating point (frame counts)", "ten_vad", "Σtp", "Σfp"),
    "run-health-rows": _swap_rows("Run health", "Operating point (run health)", "webrtc_vad_mode0",
                                  "webrtc_vad_mode1"),
    "category-rows": _swap_rows("Conditions", "Category", "speech + transient noise", "quiet/whispered speech"),
    "vad-library-rows": _swap_rows("VADs", "Operating point", "webrtc_vad_mode0", "webrtc_vad_mode1"),
}


@pytest.mark.parametrize("swap", list(CELL_SWAPS), ids=list(CELL_SWAPS))
def test_FR_0_1_02_check_reports_cells_in_the_wrong_row_or_column(tmp_path, swap):
    """WP-0.1-F1: a cell that cites the Sources of another row's operating point or category, or of another column's
    metric, is reported, even where the shown values happen to be equal."""
    for folder in folders():
        copy = tmp_path / folder.name
        shutil.copytree(folder, copy)
        path = copy / "SUMMARY.md"
        lines = read_text(path).split("\n")
        before = list(lines)
        CELL_SWAPS[swap](lines)
        assert lines != before
        path.write_text("\n".join(lines), encoding="utf-8")
        problems = summary_problems(copy, identifiers(folder))
        assert any("cites" in p and ("row" in p or "column" in p) for p in problems), problems[:5]


def _insert_after(heading_or_line, text):
    def edit(lines):
        i = next(i for i, line in enumerate(lines) if line.startswith(heading_or_line))
        lines.insert(i + 1, text)
    return edit


def _append_to_cell(section, first_header, row, col, text):
    def edit(lines):
        header = [c.strip() for c in _cells(lines[_header_index(lines, section, first_header)])]
        j = header.index(col)
        i = next(i for i in _table_lines(lines, section, first_header)
                 if _cells(lines[i])[header.index("File") if "File" in header else 1].strip().strip("`") == row)
        cells = _cells(lines[i])
        cells[j] = cells[j].rstrip() + text + " "
        lines[i] = "|".join(cells)
    return edit


UNCITED_INSERTS = {
    "owner-statement-outside-quote": _insert_after("## Owner's statement", "Decisions in this run arrive 15 ms early."),
    "owner-statement-second-quote": _insert_after("## Owner's statement", "> Packets were lost in 3 clips."),
    "inventory-what-it-is": _append_to_cell("Raw inventory", "Item", "raw_evaluations.jsonl", "What it is",
                                            " (1500 scored clips)"),
    "inventory-intro": _insert_after("## Raw inventory", "The folder holds 11 files."),
    "sources-intro": _insert_after("## Sources", "There are 400 rows."),
    "title": lambda lines: lines.__setitem__(0, lines[0] + " (run 2)"),
}


@pytest.mark.parametrize("insert", list(UNCITED_INSERTS), ids=list(UNCITED_INSERTS))
def test_FR_0_1_02_check_reports_uncited_numbers_in_every_section(tmp_path, insert):
    """WP-0.1-F2: only the quoted owner statement, the Bytes and SHA-256 cells and the Sources table cells are
    exempt from the citation check; an uncited number anywhere else is reported."""
    for folder in folders():
        copy = tmp_path / folder.name
        shutil.copytree(folder, copy)
        path = copy / "SUMMARY.md"
        lines = read_text(path).split("\n")
        UNCITED_INSERTS[insert](lines)
        path.write_text("\n".join(lines), encoding="utf-8")
        problems = summary_problems(copy, identifiers(folder))
        assert any("a number without a citation" in p for p in problems), problems[:5]


def _rewrite(name, fn):
    def edit(raw):
        path = raw / name
        path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")
    return edit


def _drop_records(raw):
    """Drop both records of one scored clip of one operating point (a run that is not full)."""
    path = raw / "raw_evaluations.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[1])
    keep = [l for l in lines if not (json.loads(l).get("clip_id") == first["clip_id"]
                                     and json.loads(l).get("adapter_id") == first["adapter_id"])]
    assert len(keep) == len(lines) - 2
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")


def _add_failure(raw):
    path = raw / "raw_evaluations.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    r = json.loads(lines[1])
    r.update(record_type="clip_failure", payload={"tier": "tier2", "stage": "transport", "error": "edited copy"})
    path.write_text("\n".join(lines + [json.dumps(r)]) + "\n", encoding="utf-8")


def _second_run_in_report(text):
    nb = json.loads(text)
    for cell in nb["cells"]:
        for out in cell.get("outputs", []):
            if out.get("output_type") == "stream":
                body = "".join(out["text"])
                if "Discovered Run ID(s):" in body:
                    out["text"] = re.sub(r"Discovered Run ID\(s\):(\s*)\['", r"Discovered Run ID(s):\1['older_run', '",
                                         body)
    return json.dumps(nb)


def _trim_head(text):
    """Keep only the lines stamped 09:00 UTC or later, so the log starts after the first clip record (08:00:04)."""
    kept = [l for l in text.splitlines(keepends=True) if l[1:20] >= "2026-10-03T09:00:00"]
    assert kept and len(kept) < len(text.splitlines())
    return "".join(kept)


def _drop_listener_log(raw):
    """Delete the listener log and remove its Raw inventory row (F7: it must be reported as missing)."""
    (raw / "jingle_stanzas_debug_listener.log").unlink()
    summary = raw.parent / "SUMMARY.md"
    summary.write_text("\n".join(l for l in read_text(summary).split("\n")
                                 if "`jingle_stanzas_debug_listener.log`" not in l or not l.startswith("| R8 |")),
                       encoding="utf-8")


RAW_BREAKS = {
    "R1-config-differs-from-run-context": ("R1", _rewrite("run_config.yaml", lambda t: t.replace(
        "concurrency_mode: sequential", "concurrency_mode: parallel"))),
    "R1-tier2-not-run": ("R1", _rewrite("run_config.yaml", lambda t: re.sub(r"tiers_to_run:\n- tier2",
                                                                             "tiers_to_run:\n- tier1", t))),
    "R2-key-missing": ("R2", _rewrite("bridge_config.yaml", lambda t: re.sub(r"^opus_fec_enabled:.*\n", "", t,
                                                                              flags=re.M))),
    "R3-harness-file-changed": ("R3", _rewrite("harness_version.txt", lambda t: t + " M orchestrator.py\n")),
    "R4-point-unanswered": ("R4", _rewrite("NETWORK.md", lambda t: re.sub(r"^- TURN Relay:.*\n", "", t, flags=re.M))),
    "R4-start-after-the-run-began": ("R4", _rewrite("NETWORK.md", lambda t: re.sub(
        r"Start Time: \S+ \S+ UTC", "Start Time: 2026-10-03 08:30:00 UTC", t))),
    "R5-clip-records-missing": ("R5", _drop_records),
    "R5-clip-failure": ("R5", _add_failure),
    "R6-mixed-runs": ("R6", _rewrite("03_report.ipynb", _second_run_in_report)),
    "R7-operating-point-line-missing": ("R7", _rewrite("run.log", lambda t: re.sub(
        r"^.*Tier 2 Completed for 'firered_vad'.*\n", "", t, flags=re.M))),
    "R8-log-starts-after-first-clip": ("R8", _rewrite("jingle_stanzas_debug_speaker.log", _trim_head)),
    "R8-listener-log-missing": ("R8 missing", _drop_listener_log),
}


@pytest.mark.parametrize("brk", list(RAW_BREAKS), ids=list(RAW_BREAKS))
def test_FR_0_1_01_check_reports_each_inconsistency(tmp_path, brk):
    """WP-0.1-F3 and F7: every consistency rule of raw_problems reports an edited copy, naming the item it breaks."""
    item, edit = RAW_BREAKS[brk]
    for folder in folders():
        copy = tmp_path / folder.name
        shutil.copytree(folder, copy)
        assert raw_problems(copy) == []
        edit(copy / "raw")
        problems = raw_problems(copy)
        assert problems, f"{brk} went unnoticed"
        assert all(p.startswith(item.split()[0]) for p in problems), problems
        assert any(p.startswith(item) for p in problems), problems
