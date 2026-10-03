"""Shared checks for the WP-0.1 Tier 2 VAD transport baseline (docs/baselines/tier2_vad/<date>/).

A baseline folder holds the owner's raw outputs in raw/ and Claude's SUMMARY.md beside them
(docs/progress/WP-0.1/PLAN.md, "Required raw items" and "SUMMARY.md layout"). Two checks:

- raw_problems(folder): is raw/ complete and consistent (items R1 to R8), and does the Raw inventory in SUMMARY.md
  list exactly the files that are there?
- summary_problems(folder): does every number in SUMMARY.md cite a Sources row, and does every Sources row resolve,
  in the raw file it names, to exactly the value shown?

Both return a list of problem strings (empty means the check passed), so the self-tests can run them on edited
copies. Every expected value is read or recomputed from the raw files here, never taken from SUMMARY.md.
"""
import ast
import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

import yaml

from aqis_testutil import ROOT

BASELINES = ROOT / "docs" / "baselines" / "tier2_vad"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
APPROVAL = ROOT / "docs" / "approvals" / "WP-0.1.md"
HARNESS_BRIDGE_CONFIG = ROOT / "webrtc_bridge" / "bridge_config.yaml"

REQUIRED_ITEMS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")
OTHER_ITEM = "other"
AUDIO_SUFFIXES = (".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".webm")
RECORD_TYPES = ("run_context", "scoring_clip", "tier2_pipeline_latency", "clip_failure")
CONFIG_KEYS_IN_RUN_CONTEXT = ("active_adapters", "concurrency_mode", "scoring_grid_ms", "hardware_policy",
                              "tiers_to_run")
# R3: tracked files a Tier 2 run (or its console capture) may leave changed. run.log: owner ruling, BLK-016 (b).
R3_ALLOWED_CHANGES = ("config/run_config.yaml", "notebooks/02_tier2_live_pipeline.ipynb",
                      "notebooks/03_report.ipynb", "run.log")
R3_ALLOWED_PREFIXES = ("results/run_output/",)
R3_ALLOWED_UNTRACKED_PREFIX = "docs/baselines/tier2_vad/"
# R4: the points the network description must answer (PLAN.md, R4), as labels at the start of a list item.
R4_POINTS = {
    "where Jitsi ran": r"Jitsi (?:Meet )?Server",
    "Jitsi version": r"Jitsi Version",
    "where the bots ran": r"Speaker and Listener Bots",
    "network path": r"Network Path",
    "TURN relay": r"TURN Relay",
    "impairment": r"Impairment",
    "start time (UTC)": r"Start Time",
    "end time (UTC)": r"End Time",
}
# The report row the approval names as a known quirk: the run-context record listed as an adapter (approval, R6).
REPORT_NON_OPERATING_POINT = "orchestrator"

SUMMARY_SECTIONS = ("Run", "Setup", "VADs", "Conditions", "Headline metrics per VAD", "Run health",
                    "Owner's statement", "Raw inventory", "Sources")
# Numbers there are locators, sizes and hashes (checked by inventory_hash_problems and resolve_sources), or the
# owner's statement quoted word for word from docs/approvals/WP-0.1.md (checked against the approval).
UNCHECKED_SECTIONS = ("Owner's statement", "Raw inventory", "Sources")
SOURCES_COLUMNS = ("ID", "Value", "File", "Kind", "Locator", "Formula and inputs", "Rounding")
INVENTORY_COLUMNS = ("Item", "File", "Bytes", "SHA-256", "What it is")
CITE_RE = re.compile(r"\[(S\d+)\]")
CITED_NUMBER_RE = re.compile(r"(?<![\w.\-])(-?\d+(?:\.\d+)?)((?:\s?\[S\d+\])+)")
CITED_CODE_RE = re.compile(r"`([^`\n]+)`((?:\s?\[S\d+\])+)")
CODE_RE = re.compile(r"`[^`\n]*`")
FIXED_TERMS = ("Tier 2", "WP-0.1", "FR-0.1-01", "FR-0.1-02", "FR-0.1-03", "AT-0.1-01",
               "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "F1")
NO_FILE = "—"          # the File cell of a derived row computed only from other source IDs ('expr')
DERIVED_OPS = ("count", "sum", "mean", "median", "count_null", "count_negative")
ROUNDING_RE = re.compile(r"^(exact|(\d) dp)$")


# ---------------------------------------------------------------------------------------------- folders and files
def baseline_folders():
    """Every dated baseline folder under docs/baselines/tier2_vad/."""
    return sorted(p for p in BASELINES.iterdir() if p.is_dir() and DATE_RE.match(p.name))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def read_records(path):
    """The JSON records of a JSONL file, in order; raises ValueError naming the line that is not valid JSON."""
    out = []
    for n, line in enumerate(read_text(path).splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{Path(path).name}:{n}: empty line")
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{Path(path).name}:{n}: not valid JSON ({exc})") from exc
    return out


def get_path(obj, dotted):
    """obj['a']['b'] for 'a.b'; a missing key raises KeyError naming the dotted path."""
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def matches(record, where):
    for key, want in where.items():
        try:
            if get_path(record, key) != want:
                return False
        except KeyError:
            return False
    return True


def notebook_output_text(nb, cell, output):
    """The text of one output of one cell: stream text, or the text/markdown (else text/plain) of display data."""
    out = nb["cells"][cell]["outputs"][output]
    if out["output_type"] == "stream":
        text = out["text"]
    else:
        data = out["data"]
        text = data.get("text/markdown", data.get("text/plain"))
    return "".join(text) if isinstance(text, list) else text


def notebook_texts(nb):
    """(cell, output, text) for every output of every code cell."""
    for c, cell in enumerate(nb["cells"]):
        for o in range(len(cell.get("outputs", []))):
            try:
                yield c, o, notebook_output_text(nb, c, o)
            except (KeyError, TypeError):
                continue


def pipe_table(text, first_header):
    """Rows of the first pipe table in text whose first header cell is first_header, as {header: cell}."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        cells = split_row(line)
        if cells and cells[0] == first_header and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$",
                                                                                   lines[i + 1].strip()):
            rows = []
            for row in lines[i + 2:]:
                if not row.strip().startswith("|"):
                    break
                vals = split_row(row)
                if len(vals) != len(cells):
                    raise ValueError(f"table row has {len(vals)} cells, header has {len(cells)}: {row!r}")
                rows.append(dict(zip(cells, vals)))
            return cells, rows
    raise ValueError(f"no table with first header {first_header!r}")


def split_row(line):
    line = line.strip()
    if not (line.startswith("|") and line.endswith("|")):
        return None
    return [c.strip() for c in line[1:-1].split("|")]


# ---------------------------------------------------------------------------------------------- SUMMARY.md reading
def summary_sections(text):
    """{heading: body} for the '## ' headings of SUMMARY.md."""
    out, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^## +(.+?) *$", line)
        if m:
            current = m.group(1)
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def strip_code(cell):
    m = re.fullmatch(r"`(.*)`", cell.strip())
    return m.group(1) if m else cell.strip()


def sources_table(text):
    """{ID: row} from the Sources table; a duplicate ID or a wrong header raises ValueError."""
    body = summary_sections(text).get("Sources")
    if body is None:
        raise ValueError("SUMMARY.md has no '## Sources' section")
    header, rows = pipe_table(body, "ID")
    if tuple(header) != SOURCES_COLUMNS:
        raise ValueError(f"Sources columns are {header}, expected {list(SOURCES_COLUMNS)}")
    out = {}
    for row in rows:
        if row["ID"] in out:
            raise ValueError(f"Sources ID {row['ID']} appears twice")
        out[row["ID"]] = {k: strip_code(v) if k in ("Value", "File", "Locator") else v for k, v in row.items()}
    return out


def inventory_table(text):
    body = summary_sections(text).get("Raw inventory")
    if body is None:
        raise ValueError("SUMMARY.md has no '## Raw inventory' section")
    header, rows = pipe_table(body, "Item")
    if tuple(header) != INVENTORY_COLUMNS:
        raise ValueError(f"Raw inventory columns are {header}, expected {list(INVENTORY_COLUMNS)}")
    return [{k: strip_code(v) for k, v in row.items()} for row in rows]


def inventory_files(folder):
    """{item: [file names]} from the Raw inventory of folder/SUMMARY.md."""
    out = {}
    for row in inventory_table(read_text(folder / "SUMMARY.md")):
        out.setdefault(row["Item"], []).append(row["File"])
    return out


# ---------------------------------------------------------------------------------------------- raw folder (R1-R8)
def operating_points(run_config):
    """The adapter IDs a run of this configuration writes: webrtc_vad expands to one ID per aggressiveness mode."""
    out = []
    for adapter in run_config["active_adapters"]:
        if adapter == "webrtc_vad":
            out += [f"webrtc_vad_mode{m}" for m in run_config["webrtc_aggressiveness_modes"]]
        else:
            out.append(adapter)
    return out


def utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def raw_problems(folder):
    """Problems with folder/raw against the required items R1 to R8 and the Raw inventory of SUMMARY.md."""
    raw = folder / "raw"
    problems = []
    if not raw.is_dir():
        return [f"{raw}: raw folder is missing"]
    try:
        listed = inventory_files(folder)
    except (OSError, ValueError) as exc:
        return [f"{folder / 'SUMMARY.md'}: cannot read the Raw inventory ({exc})"]
    present = sorted(p.name for p in raw.iterdir())
    for name in present:
        if (raw / name).is_dir():
            problems.append(f"raw/{name}: a folder; raw/ must hold only files")
        if name.lower().endswith(AUDIO_SUFFIXES):
            problems.append(f"raw/{name}: audio file in raw/ (no audio may be committed)")
    named = [f for files in listed.values() for f in files]
    for item in listed:
        if item not in REQUIRED_ITEMS + (OTHER_ITEM,):
            problems.append(f"Raw inventory: unknown item {item!r}")
    for name in sorted(set(present) - set(named)):
        problems.append(f"raw/{name}: present but not in the Raw inventory")
    for name in sorted({n for n in named if named.count(n) > 1}):
        problems.append(f"Raw inventory: raw/{name} listed more than once")
    for item in REQUIRED_ITEMS:
        files = listed.get(item, [])
        if not files:
            problems.append(f"{item} missing: no file listed for it in the Raw inventory")
        for name in files:
            if not (raw / name).is_file():
                problems.append(f"{item} missing: raw/{name} does not exist")
    if any(p.startswith(tuple(f"{i} missing" for i in REQUIRED_ITEMS)) for p in problems):
        return problems

    def one(item):
        return raw / listed[item][0]

    for item in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        if len(listed[item]) != 1:
            problems.append(f"{item}: exactly one file expected, the Raw inventory lists {listed[item]}")
    if len(listed["R8"]) != 2:
        problems.append(f"R8: the speaker and the listener log expected, the Raw inventory lists {listed['R8']}")
    if problems:
        return problems

    # R5 first: every other item is checked against the run it names.
    try:
        records = read_records(one("R5"))
    except (OSError, ValueError) as exc:
        return problems + [f"R5 raw/{one('R5').name}: {exc}"]
    contexts = [r for r in records if r.get("record_type") == "run_context"]
    run_ids = sorted({r.get("run_id") for r in records})
    if len(contexts) != 1:
        problems.append(f"R5 raw/{one('R5').name}: {len(contexts)} run_context records, exactly one expected")
    if len(run_ids) != 1:
        problems.append(f"R5 raw/{one('R5').name}: records of {len(run_ids)} runs {run_ids}, exactly one expected")
    for n, r in enumerate(records, 1):
        if r.get("record_type") not in RECORD_TYPES:
            problems.append(f"R5 raw/{one('R5').name}:{n}: unknown record_type {r.get('record_type')!r}")
    if problems:
        return problems
    run_id, context = run_ids[0], contexts[0]
    clip_records = [r for r in records if r["record_type"] != "run_context"]

    # R1
    try:
        cfg = yaml.safe_load(read_text(one("R1")))
    except (OSError, yaml.YAMLError) as exc:
        return problems + [f"R1 raw/{one('R1').name}: not readable YAML ({exc})"]
    if not isinstance(cfg, dict):
        return problems + [f"R1 raw/{one('R1').name}: not a YAML mapping"]
    if "tier2" not in (cfg.get("tiers_to_run") or []):
        problems.append(f"R1 raw/{one('R1').name}: tiers_to_run {cfg.get('tiers_to_run')} does not include tier2")
    if not run_id.startswith(f"{cfg.get('run_id')}_"):
        problems.append(f"R1 raw/{one('R1').name}: run_id {cfg.get('run_id')!r} does not start the records' "
                        f"run ID {run_id!r}")
    for key in CONFIG_KEYS_IN_RUN_CONTEXT:
        if cfg.get(key) != context["payload"].get(key):
            problems.append(f"R1 raw/{one('R1').name}: {key} = {cfg.get(key)!r}, but the run_context record "
                            f"says {context['payload'].get(key)!r}")
    points = operating_points(cfg)
    in_records = sorted({r["adapter_id"] for r in clip_records})
    if sorted(points) != in_records:
        problems.append(f"R5 raw/{one('R5').name}: operating points {in_records}, the configuration gives "
                        f"{sorted(points)}")
    expected = None
    log_text = read_text(one("R7")) if one("R7").suffix != ".ipynb" else None
    m = re.search(r"Loaded manifest '[^']*' \((\d+) clips", log_text or "")
    if m:
        expected = int(m.group(1)) - int(cfg.get("warmup_clip_count", 0))
    failures = [r for r in clip_records if r["record_type"] == "clip_failure"]
    if failures:
        problems.append(f"R5 raw/{one('R5').name}: {len(failures)} clip_failure records; the run is not full "
                        f"(PLAN.md: report and ask)")
    for point in points:
        for rtype in ("scoring_clip", "tier2_pipeline_latency"):
            n = sum(1 for r in clip_records if r["adapter_id"] == point and r["record_type"] == rtype)
            if expected is None or n != expected:
                problems.append(f"R5 raw/{one('R5').name}: {n} {rtype} records for {point}, expected {expected} "
                                f"(manifest clips in the run log minus warmup_clip_count)")

    # R2
    try:
        bridge = yaml.safe_load(read_text(one("R2")))
        harness_keys = set(yaml.safe_load(read_text(HARNESS_BRIDGE_CONFIG)))
    except (OSError, yaml.YAMLError) as exc:
        return problems + [f"R2 raw/{one('R2').name}: not readable YAML ({exc})"]
    if not isinstance(bridge, dict):
        problems.append(f"R2 raw/{one('R2').name}: not a YAML mapping")
    else:
        for key in sorted(harness_keys - set(bridge)):
            problems.append(f"R2 raw/{one('R2').name}: key {key!r} of webrtc_bridge/bridge_config.yaml is missing")

    # R3
    lines = read_text(one("R3")).splitlines()
    if not lines or not re.fullmatch(r"[0-9a-f]{40}", lines[0].strip()):
        problems.append(f"R3 raw/{one('R3').name}:1: not a 40-character git commit")
    for n, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        m = re.match(r"^(..) (.+)$", line)
        if not m:
            problems.append(f"R3 raw/{one('R3').name}:{n}: not a `git status --porcelain` line: {line!r}")
            continue
        status, path = m.group(1), m.group(2)
        if status == "??":
            if not path.startswith(R3_ALLOWED_UNTRACKED_PREFIX):
                problems.append(f"R3 raw/{one('R3').name}:{n}: untracked {path} outside "
                                f"{R3_ALLOWED_UNTRACKED_PREFIX}")
        elif path not in R3_ALLOWED_CHANGES and not path.startswith(R3_ALLOWED_PREFIXES):
            problems.append(f"R3 raw/{one('R3').name}:{n}: changed tracked file {path} is not one a run writes "
                            f"(harness not run exactly as it is)")

    # R4
    network = read_text(one("R4"))
    answers = {}
    for point, label in R4_POINTS.items():
        m = re.search(rf"^- {label}:[ \t]*(\S.*)$", network, re.M)
        if not m:
            problems.append(f"R4 raw/{one('R4').name}: does not answer '{point}' (a '- {label}:' line)")
        else:
            answers[point] = m.group(1).strip()
    first_clip = min(utc(r["timestamp_utc"]) for r in clip_records)
    last_clip = max(utc(r["timestamp_utc"]) for r in clip_records)
    first_any = min(utc(r["timestamp_utc"]) for r in records)
    for point, test in (("start time (UTC)", lambda t: t <= first_any.replace(microsecond=0)),
                        ("end time (UTC)", lambda t: t.timestamp() + 1 > last_clip.timestamp())):
        if point in answers:
            try:
                when = datetime.strptime(answers[point], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
            except ValueError:
                problems.append(f"R4 raw/{one('R4').name}: {point} {answers[point]!r} is not 'YYYY-MM-DD HH:MM:SS UTC'")
                continue
            if not test(when):
                problems.append(f"R4 raw/{one('R4').name}: {point} {answers[point]} does not enclose the records "
                                f"({first_any.isoformat()} to {last_clip.isoformat()})")

    # R6
    try:
        report = json.loads(read_text(one("R6")))
    except (OSError, ValueError) as exc:
        return problems + [f"R6 raw/{one('R6').name}: not a readable notebook ({exc})"]
    texts = list(notebook_texts(report))
    found = [t for _, _, t in texts if "Discovered Run ID(s):" in t]
    if len(found) != 1:
        problems.append(f"R6 raw/{one('R6').name}: {len(found)} 'Discovered Run ID(s):' outputs, one expected")
    else:
        m = re.search(r"Discovered Run ID\(s\):\s*(\[.*?\])", found[0])
        ids = ast.literal_eval(m.group(1)) if m else None
        if ids != [run_id]:
            problems.append(f"R6 raw/{one('R6').name}: report run IDs {ids}, expected exactly [{run_id!r}]")
    summary_rows = None
    for _, _, t in texts:
        try:
            summary_rows = pipe_table(t, "Adapter / Operating Point")[1]
            break
        except ValueError:
            continue
    if summary_rows is None:
        problems.append(f"R6 raw/{one('R6').name}: no 'Adapter / Operating Point' summary table")
    else:
        rows = sorted(r["Adapter / Operating Point"] for r in summary_rows
                      if r["Adapter / Operating Point"] != REPORT_NON_OPERATING_POINT)
        if rows != sorted(points):
            problems.append(f"R6 raw/{one('R6').name}: summary rows {rows}, expected one per operating point "
                            f"{sorted(points)}")

    # R7
    if log_text is None:
        problems.append(f"R7 raw/{one('R7').name}: the run log must be a text log")
    else:
        for needle in [f"Loaded run configuration for run_id: '{run_id}'",
                       f"=== Benchmark Run '{run_id}' Completed Successfully ==="] + \
                      [f"Tier 2 Completed for '{p}': Evaluated" for p in points]:
            if needle not in log_text:
                problems.append(f"R7 raw/{one('R7').name}: no line containing {needle!r}")

    # R8 (owner ruling BLK-016 (c): the logs cover every clip evaluation record)
    for name in listed["R8"]:
        stamps = re.findall(r"^\[(\d{4}-\d{2}-\d{2}T[^\]]+)\]", read_text(raw / name), re.M)
        if not stamps:
            problems.append(f"R8 raw/{name}: no time-stamped lines")
            continue
        if not (utc(stamps[0]) <= first_clip and utc(stamps[-1]) >= last_clip):
            problems.append(f"R8 raw/{name}: covers {stamps[0]} to {stamps[-1]}, not every clip record "
                            f"({first_clip.isoformat()} to {last_clip.isoformat()})")
    if not any("speaker" in n for n in listed["R8"]) or not any("listener" in n for n in listed["R8"]):
        problems.append(f"R8: expected a speaker and a listener log, the Raw inventory lists {listed['R8']}")
    return problems


def inventory_hash_problems(folder):
    """Each inventory row's bytes and SHA-256 equal the raw file's (FR-0.1-03: raw files never edited)."""
    problems = []
    for row in inventory_table(read_text(folder / "SUMMARY.md")):
        path = folder / "raw" / row["File"]
        if not path.is_file():
            problems.append(f"raw/{row['File']}: listed in the Raw inventory but missing")
            continue
        if row["Bytes"] != str(path.stat().st_size):
            problems.append(f"raw/{row['File']}: {path.stat().st_size} bytes, the Raw inventory says {row['Bytes']}")
        if row["SHA-256"] != sha256(path):
            problems.append(f"raw/{row['File']}: SHA-256 {sha256(path)}, the Raw inventory says {row['SHA-256']}")
    return problems


# ---------------------------------------------------------------------------------------------- Sources resolution
class SourceError(Exception):
    """A Sources row cannot be resolved in its raw file."""


def _fmt(value):
    return value if isinstance(value, str) else json.dumps(value)


def _text_value(lines, loc, value):
    n = loc["line"]
    if not 1 <= n <= len(lines):
        raise SourceError(f"line {n} does not exist ({len(lines)} lines)")
    line = lines[n - 1]
    if "after" in loc:
        idx = line.find(loc["after"])
        if idx < 0:
            raise SourceError(f"line {n} has no {loc['after']!r}")
        rest = line[idx + len(loc["after"]):].lstrip()
        if not (rest.startswith(value) and not re.match(r"[\w.]", rest[len(value):len(value) + 1] or " ")):
            raise SourceError(f"line {n}: after {loc['after']!r} comes {rest[:len(value) + 12]!r}, not {value!r}")
        return value
    if not re.search(rf"(?<![\w.]){re.escape(value)}(?![\w])", line):
        raise SourceError(f"line {n} does not contain {value!r}: {line[:200]!r}")
    return value


def _derived(records, loc):
    where = loc["where"]
    selected = [r for r in records if matches(r, where)]
    op = loc["op"]
    if op == "count":
        return len(selected)       # zero is a real count, for example of clip_failure records
    if not selected:
        raise SourceError(f"no record matches {where}")
    try:
        values = [get_path(r, loc["field"]) for r in selected]
    except KeyError as exc:
        raise SourceError(f"field {exc} missing in a matching record") from exc
    if op == "count_null":
        return sum(1 for v in values if v is None)
    present = [v for v in values if v is not None]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in present):
        raise SourceError(f"field {loc['field']} is not numeric in every matching record")
    if op == "count_negative":
        return sum(1 for v in present if v < 0)
    if not present:
        raise SourceError(f"field {loc['field']} has no non-null value")
    if op == "sum":
        return sum(present) if all(isinstance(v, int) for v in present) else math.fsum(present)
    if op == "mean":
        return math.fsum(present) / len(present)
    if op == "median":
        return statistics.median(present)
    raise SourceError(f"unknown op {op!r}")


def _expr(expr, values):
    """Evaluate an arithmetic expression over source IDs (S12 + S13, numbers, + - * / and brackets)."""
    tree = ast.parse(expr, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if b == 0:
                raise SourceError(f"division by zero in {expr!r}")
            return a / b
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and re.fullmatch(r"S\d+", node.id):
            if node.id not in values:
                raise SourceError(f"{expr!r} uses {node.id}, which is not resolved")
            return values[node.id]
        raise SourceError(f"{expr!r}: only source IDs, numbers and + - * / are allowed")
    return ev(tree)


def shown(value, rounding):
    """The text a computed value must show under its rounding: exact, or Python round(x, n) to n decimals."""
    m = ROUNDING_RE.match(rounding)
    if not m:
        raise SourceError(f"rounding {rounding!r} is not 'exact' or '<n> dp'")
    if m.group(2) is None:
        if isinstance(value, float) and not value.is_integer():
            raise SourceError(f"value {value!r} is not whole, so 'exact' rounding cannot show it")
        return str(int(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else _fmt(value)
    n = int(m.group(2))
    return f"{round(value, n):.{n}f}"


def resolve_sources(folder, sources=None):
    """({ID: computed value}, [problems]) for every Sources row of folder/SUMMARY.md, read from folder/raw."""
    raw = folder / "raw"
    if sources is None:
        sources = sources_table(read_text(folder / "SUMMARY.md"))
    cache, values, problems = {}, {}, []

    def load(name, kind):
        key = (name, kind)
        if key not in cache:
            path = raw / name
            if kind == "lines":
                cache[key] = read_text(path).splitlines()
            elif kind == "yaml":
                cache[key] = yaml.safe_load(read_text(path))
            elif kind == "jsonl":
                cache[key] = read_records(path)
            else:
                cache[key] = json.loads(read_text(path))
        return cache[key]

    def by_number(sid):
        return int(sid[1:])

    pending = sorted(sources, key=by_number)
    for _ in range(len(pending) + 1):
        if not pending:
            break
        later = []
        for sid in pending:
            row = sources[sid]
            where = f"{sid} (raw/{row['File']} {row['Locator']})"
            try:
                loc = json.loads(row["Locator"])
                if not isinstance(loc, dict):
                    raise SourceError("the locator is not a JSON object")
                if row["File"] != NO_FILE and not (raw / row["File"]).is_file():
                    raise SourceError(f"raw/{row['File']} is missing")
                if row["Kind"] == "direct":
                    value = _resolve_direct(row, loc, load)
                    if value != row["Value"]:
                        raise SourceError(f"the source gives {value!r}, SUMMARY.md shows {row['Value']!r}")
                    values[sid] = _as_number(row["Value"])
                elif row["Kind"] == "derived":
                    if "expr" in loc:
                        if row["File"] != NO_FILE:
                            raise SourceError(f"an 'expr' row reads no file; File must be {NO_FILE!r}")
                        missing = [s for s in re.findall(r"S\d+", loc["expr"]) if s not in values]
                        if any(s in sources and s in pending for s in missing):
                            later.append(sid)
                            continue
                        computed = _expr(loc["expr"], values)
                    else:
                        if not row["File"].endswith(".jsonl"):
                            raise SourceError("a derived row without 'expr' must read a .jsonl file")
                        computed = _derived(load(row["File"], "jsonl"), loc)
                    text = shown(computed, row["Rounding"])
                    if text != row["Value"]:
                        raise SourceError(f"{row['Formula and inputs']} gives {computed!r}, shown under "
                                          f"'{row['Rounding']}' as {text!r}; SUMMARY.md shows {row['Value']!r}")
                    values[sid] = computed
                else:
                    raise SourceError(f"kind {row['Kind']!r} is not 'direct' or 'derived'")
            except (SourceError, OSError, ValueError, KeyError, IndexError, TypeError, yaml.YAMLError) as exc:
                problems.append(f"{where}: {exc}")
        if later == pending:
            problems += [f"{sid}: its expression refers to rows that never resolve" for sid in later]
            break
        pending = later
    return values, problems


def _as_number(text):
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _resolve_direct(row, loc, load):
    name = row["File"]
    if name.endswith(".jsonl"):
        records = load(name, "jsonl")
        selected = [r for r in records if matches(r, loc["where"])]
        if len(selected) != 1:
            raise SourceError(f"{len(selected)} records match {loc['where']}, exactly one expected")
        try:
            return _fmt(get_path(selected[0], loc["field"]))
        except KeyError as exc:
            raise SourceError(f"field {exc} missing") from exc
    if name.endswith((".yaml", ".yml")):
        cur = load(name, "yaml")
        keys = loc["key"] if isinstance(loc["key"], list) else [loc["key"]]
        for k in keys:
            try:
                cur = cur[k]
            except (KeyError, IndexError, TypeError) as exc:
                raise SourceError(f"key path {keys} not found") from exc
        return _fmt(cur)
    if name.endswith(".ipynb"):
        nb = load(name, "notebook")
        try:
            text = notebook_output_text(nb, loc["cell"], loc["output"])
        except (KeyError, IndexError) as exc:
            raise SourceError(f"cell {loc['cell']} output {loc['output']} not found") from exc
        if "row" in loc:
            header, rows = pipe_table(text, loc["first_header"])
            hits = [r for r in rows if r[header[0]] == loc["row"]]
            if len(hits) != 1 or loc["col"] not in header:
                raise SourceError(f"no single row {loc['row']!r} with column {loc['col']!r}")
            cell = hits[0][loc["col"]]
            value = re.sub(r"\s*(ms|\(N=\d+\))$", "", cell).strip()
            return value
        return _text_value(text.splitlines(), loc, row["Value"])
    return _text_value(load(name, "lines"), loc, row["Value"])


# ---------------------------------------------------------------------------------------------- body citations
def body_text(text):
    """SUMMARY.md without the sections whose numbers are locators, sizes and hashes, and without HTML comments."""
    out, excluded = [], False
    for line in text.splitlines():
        if line.startswith("# "):
            continue
        m = re.match(r"^## +(.+?) *$", line)
        if m:
            excluded = m.group(1) in UNCHECKED_SECTIONS
            continue
        if not excluded:
            out.append(line)
    return re.sub(r"<!--.*?-->", "", "\n".join(out), flags=re.S)


def citation_problems(text, sources, identifiers):
    """Every number in the body cites a source whose Value it equals; every Sources row is cited at least once.

    identifiers: code spans that may contain digits without a citation (file names, run ID, operating points).
    """
    problems, cited = [], set()
    body = body_text(text)
    for lineno, line in enumerate(body.splitlines(), 1):
        rest = line
        for m in CITED_CODE_RE.finditer(line):
            for sid in CITE_RE.findall(m.group(2)):
                cited.add(sid)
                if sid not in sources:
                    problems.append(f"`{m.group(1)}` cites {sid}, which is not in Sources")
                elif sources[sid]["Value"] != m.group(1):
                    problems.append(f"`{m.group(1)}` cites {sid}, whose Value is {sources[sid]['Value']!r}")
        rest = CITED_CODE_RE.sub(" ", rest)
        for m in CODE_RE.finditer(rest):
            span = m.group(0)[1:-1]
            if re.search(r"\d", span) and span not in identifiers:
                problems.append(f"code span `{span}` holds a digit but is not cited and not a known identifier")
        rest = CODE_RE.sub(" ", rest)
        for m in CITED_NUMBER_RE.finditer(rest):
            for sid in CITE_RE.findall(m.group(2)):
                cited.add(sid)
                if sid not in sources:
                    problems.append(f"{m.group(1)} cites {sid}, which is not in Sources")
                elif sources[sid]["Value"] != m.group(1):
                    problems.append(f"{m.group(1)} cites {sid}, whose Value is {sources[sid]['Value']!r}")
        rest = CITED_NUMBER_RE.sub(" ", rest)
        for term in FIXED_TERMS:
            rest = re.sub(rf"(?<![\w.-]){re.escape(term)}(?![\w.-])", " ", rest)
        if re.search(r"\d", rest):
            problems.append(f"body line {lineno}: a number without a citation: {line.strip()[:160]!r}")
    for sid in sorted(set(sources) - cited, key=lambda s: int(s[1:])):
        problems.append(f"{sid} is in Sources but no number in SUMMARY.md cites it")
    return problems


def summary_problems(folder, identifiers):
    """Citation problems plus every Sources row that does not resolve to its shown value."""
    text = read_text(folder / "SUMMARY.md")
    try:
        sources = sources_table(text)
    except ValueError as exc:
        return [str(exc)]
    _, problems = resolve_sources(folder, sources)
    return citation_problems(text, sources, identifiers) + problems
