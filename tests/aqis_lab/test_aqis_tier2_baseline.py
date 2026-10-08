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

from aqis_baseline_testutil import (APPROVAL, BASELINES, DATE_RE, INVENTORY_COLUMNS, RECORD_TYPES, SourceError,
                                    run_log_clips,
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


def _citations_of(lines, section, first_header, row, col):
    header = [c.strip() for c in _cells(lines[_header_index(lines, section, first_header)])]
    i = next(i for i in _table_lines(lines, section, first_header) if _cells(lines[i])[1].strip().strip("`") == row)
    return i, header.index(col)


def _swap_citations(section, first_header, row_a, row_b, col):
    """Swap only the [S..] citations of one column between two rows whose shown values are equal, so no value
    changes and every source stays cited (an isolating case for the row binding)."""
    def edit(lines):
        (ia, j), (ib, _) = (_citations_of(lines, section, first_header, r, col) for r in (row_a, row_b))
        ca, cb = _cells(lines[ia]), _cells(lines[ib])
        va, vb = re.sub(r"\s*\[S\d+\]", "", ca[j]).strip(), re.sub(r"\s*\[S\d+\]", "", cb[j]).strip()
        assert va == vb, (va, vb)
        sa, sb = re.findall(r"\[S\d+\]", ca[j]), re.findall(r"\[S\d+\]", cb[j])
        ca[j], cb[j] = f" {va} {' '.join(sb)} ", f" {vb} {' '.join(sa)} "
        lines[ia], lines[ib] = "|".join(ca), "|".join(cb)
    return edit


def _add_citation_of(section, first_header, row, other, col):
    """Append to one cell the citation of the same column in another row whose shown value is equal."""
    def edit(lines):
        (i, j), (k, _) = (_citations_of(lines, section, first_header, r, col) for r in (row, other))
        cells, extra = _cells(lines[i]), re.findall(r"\[S\d+\]", _cells(lines[k])[j])[0]
        cells[j] = cells[j].rstrip() + f" {extra} "
        lines[i] = "|".join(cells)
    return edit


def _expr_operand_of_another_row(lines):
    """In the 'expr' Source behind firered_vad's Precision, replace its second operand by another row's Source with
    the same value, so every value still resolves and only the operand binding can catch it."""
    sources = sources_table("\n".join(lines))
    i, j = _citations_of(lines, HEADLINE, "Operating point", "firered_vad", "Precision")
    expr_ids = [s for s in re.findall(r"S\d+", _cells(lines[i])[j]) if "expr" in sources[s]["Locator"]]
    assert len(expr_ids) == 1, expr_ids
    expr_id = expr_ids[0]
    operand = list(dict.fromkeys(re.findall(r"S\d+", json.loads(sources[expr_id]["Locator"])["expr"])))[1]
    same = [s for s, r in sources.items() if s != operand and r["Value"] == sources[operand]["Value"]
            and r["Locator"] != sources[operand]["Locator"] and r["Kind"] == "derived" and "expr" not in r["Locator"]]
    assert same, f"no other Source shows {sources[operand]['Value']}"
    k = next(k for k, line in enumerate(lines) if line.startswith(f"| {expr_id} |"))
    lines[k] = re.sub(rf"\b{operand}\b", same[0], lines[k])


CELL_SWAPS.update({
    # WP-0.9 DEBT-031: one case for each part of the binding check that no case above isolates.
    "report-row-binding": _swap_citations("VADs", "Operating point", "webrtc_vad_mode0", "webrtc_vad_mode1",
                                          "Library version"),                                       # H1 (_report)
    "extra-citation": _add_citation_of("VADs", "Operating point", "webrtc_vad_mode0", "webrtc_vad_mode1",
                                       "Library version"),                                          # H4
    "expr-operand-binding": _expr_operand_of_another_row,                                           # H5 (_shape)
    # WP-0.9 DEBT-029: the manifest count cites its own category.
    "manifest-count-category": _swap_citations("Conditions", "Category", "speech + transient noise",
                                               "quiet/whispered speech", "Clips in the manifest (warm-up included)"),
})


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


def _insert_after_table(section, first_header, new_lines):
    def edit(lines):
        end = _table_lines(lines, section, first_header)[-1]
        lines[end + 1:end + 1] = ["", *new_lines]
    return edit


UNCITED_INSERTS.update({
    # WP-0.9 DEBT-030 (auditor breaks X4 and X4-inv): only the Sources table headed ID, and only the Bytes and SHA-256
    # cells of the Raw inventory table headed Item, are exempt; a second table in either section is checked.
    "sources-second-table": _insert_after_table("Sources", "ID", ["| Note | Rows |", "| --- | --- |", "| extra | 12 |"]),
    "inventory-second-table": _insert_after_table("Raw inventory", "Item", [
        "| Kind | Name | Size | Checksum | Note |", "| --- | --- | --- | --- | --- |", "| x | y | 4000 | 1234 | z |"]),
    "inventory-second-table-same-columns": _insert_after_table("Raw inventory", "Item", [
        "| Extra | File | Bytes | SHA-256 | What it is |", "| --- | --- | --- | --- | --- |",
        "| x | `y.log` | 4000 | 1234 | z |"]),
    # WP-0.9-F05: only the first table headed ID (Item), the one sources_table (inventory_table) reads, is exempt;
    # a second table with the same first header is checked like the rest of the body.
    "sources-second-table-same-header": _insert_after_table("Sources", "ID", [
        "| ID | Note |", "| --- | --- |", "| X | 4321 |"]),
    "inventory-second-table-same-header": _insert_after_table("Raw inventory", "Item", [
        "| Item | File | Bytes | SHA-256 | What it is |", "| --- | --- | --- | --- | --- |",
        "| x | `y.log` | 4000 | 1234 | z |"]),
})


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


# ---------------------------------------------------------------------------------------------- WP-0.9 DEBT-029, DEBT-031
def _repeat_row(section, first_header, row):
    def edit(lines):
        i = next(i for i in _table_lines(lines, section, first_header) if _cells(lines[i])[1].strip().strip("`") == row)
        lines.insert(i + 1, lines[i])
    return edit


def _drop_row_and_its_sources(section, first_header, row):
    """Remove one table row and the Sources rows only it cites, so nothing but the row check can notice."""
    def edit(lines):
        i = next(i for i in _table_lines(lines, section, first_header) if _cells(lines[i])[1].strip().strip("`") == row)
        cited = set(re.findall(r"\[(S\d+)\]", lines.pop(i)))
        others = "\n".join(lines)
        cited = {s for s in cited if f"[{s}]" not in others and not re.search(rf"\b{s}\b", "\n".join(
            l for l in lines if l.startswith("| S") and not l.startswith(f"| {s} |")))}
        lines[:] = [l for l in lines if not any(l.startswith(f"| {s} |") for s in cited)]
    return edit


ROW_SET_BREAKS = {
    # H3: one row per operating point; a repeated row cites only valid Sources of its own operating point.
    "headline-row-repeated": (_repeat_row(HEADLINE, "Operating point", "ten_vad"), "expected one per operating point"),
    # The Conditions table has one row per category of the run (scored records and run-log clip lines).
    "category-row-missing": (_drop_row_and_its_sources("Conditions", "Category", "music/singing"),
                             "expected one per category"),
    "category-row-repeated": (_repeat_row("Conditions", "Category", "silence-only"), "expected one per category"),
}


@pytest.mark.parametrize("brk", list(ROW_SET_BREAKS), ids=list(ROW_SET_BREAKS))
def test_FR_0_1_02_check_reports_missing_or_repeated_rows(tmp_path, brk):
    """WP-0.1-F9 (DEBT-031): a per-operating-point or per-category table must hold exactly one row for each."""
    edit, expected = ROW_SET_BREAKS[brk]
    for folder in folders():
        copy = tmp_path / folder.name
        shutil.copytree(folder, copy)
        path = copy / "SUMMARY.md"
        lines = read_text(path).split("\n")
        before = list(lines)
        edit(lines)
        assert lines != before
        path.write_text("\n".join(lines), encoding="utf-8")
        problems = summary_problems(copy, identifiers(folder))
        assert any(expected in p for p in problems), problems[:5]


CLIP_LINE = re.compile(r"Tier 2 \[(?P<point>[\w-]+)\] clip \[\d+/\d+\] '(?P<clip>[^']+)' "
                       r"\(Category: '(?P<category>[^']+)', Warmup: (?P<warmup>True|False)\)")
MANIFEST_COLUMN = "Clips in the manifest (warm-up included)"


def test_FR_0_1_02_conditions_show_clips_in_the_manifest_per_category():
    """WP-0.1-F5 (DEBT-029): the Conditions table gives each category's clip count in the manifest, warm-up clips
    included, recomputed here from the run log's clip lines; the counts add up to the manifest total."""
    for folder in folders():
        text = read_text(folder / "SUMMARY.md")
        header, rows = pipe_table(summary_sections(text)["Conditions"], "Category")
        assert MANIFEST_COLUMN in header
        log = read_text(folder / "raw" / inventory_files(folder)["R7"][0])
        per_point = {}
        for m in CLIP_LINE.finditer(log):
            per_point.setdefault(m["point"], {}).setdefault(m["category"], set()).add(m["clip"])
        counts = {p: {c: len(clips) for c, clips in cats.items()} for p, cats in per_point.items()}
        assert len({json.dumps(c, sort_keys=True) for c in counts.values()}) == 1, "operating points differ"
        expected = next(iter(counts.values()))
        shown = {r["Category"]: int(re.sub(r"\s*\[S\d+\]", "", r[MANIFEST_COLUMN])) for r in rows}
        assert shown == expected
        total = re.search(r"Corpus manifest version `[^`]+` \[S\d+\], (\d+) \[S\d+\] clips", text)
        assert total and sum(shown.values()) == int(total.group(1))
        records = read_records(folder / "raw" / inventory_files(folder)["R5"][0])
        warmups = {m["clip"] for m in CLIP_LINE.finditer(log) if m["warmup"] == "True"}
        for r in rows:  # scored clips plus warm-up clips of the category give the manifest count
            scored = {x["clip_id"] for x in records if x.get("record_type") == "scoring_clip"
                      and x["payload"]["category"] == r["Category"]}
            warm = {c for c in warmups if any(m["clip"] == c and m["category"] == r["Category"]
                                               for m in CLIP_LINE.finditer(log))}
            assert len(scored) + len(warm) == shown[r["Category"]], r["Category"]


def test_FR_0_1_02_run_log_clip_count_counts_each_clip_once():
    """DEBT-029: a clip the run log lists twice for one operating point counts once; listed twice with different
    details, it is an error rather than a guess."""
    line = "2026-10-03 07:59:12,159 [INFO] [orchestrator] Tier 2 [ten_vad] clip [1/2] '{clip}' (Category: '{cat}', " \
           "Warmup: {warm})"
    lines = [line.format(clip="a.wav", cat="clean speech", warm="True"),
             line.format(clip="a.wav", cat="clean speech", warm="True"),     # a retried clip
             line.format(clip="b.wav", cat="silence-only", warm="False"), "an unrelated log line"]
    assert run_log_clips(lines) == [
        {"operating_point": "ten_vad", "clip": "a.wav", "category": "clean speech", "warmup": True},
        {"operating_point": "ten_vad", "clip": "b.wav", "category": "silence-only", "warmup": False}]
    with pytest.raises(SourceError, match="twice with different details"):
        run_log_clips(lines + [line.format(clip="a.wav", cat="music/singing", warm="True")])
    with pytest.raises(SourceError, match="no Tier 2 clip lines"):
        run_log_clips(["an unrelated log line"])
