"""Parity of two smoke bundles: transcript hashes and WER per clip and in total, every difference listed (FR-0.7-08).

CAPABILITIES:
  CAP-PARITY-001: load_bundle() reads a bundle folder or its .tar and checks it against BUNDLE.json: bundle version 1.0, exactly the listed files (no file missing or extra) and every file's SHA-256 and size; any problem is a ParityInputError naming the file [tests: test_FR_0_7_08_damaged_bundle_is_input_error, test_FR_0_7_08_reads_folder_and_tar_alike]
  CAP-PARITY-002: compare() compares every transcript task present in both bundles (vosk-batch must be in both): the clip sets and each clip's text_sha256; and every score table present in both: each clip's and variant's WER (a row missing on one side is a difference) and each variant's corpus WER, errors, reference words and corpus CER; a task or table in one bundle only is named, never hidden; score tables are read from a copy in Arrow-owned memory, so nothing Arrow releases at interpreter exit needs the Python interpreter (a Python-owned buffer there deadlocked the exit) [tests: test_FR_0_7_08_identical_bundles_report_no_difference, test_FR_0_7_08_reports_every_per_clip_difference, test_FR_0_7_08_total_wer_difference_reported, test_FR_0_7_08_bundle_without_vosk_batch_is_input_error, test_FR_0_7_08_task_in_one_bundle_only_is_named_not_hidden, test_FR_0_7_08_parity_process_always_exits]
  CAP-PARITY-003: report_lines() prints both bundles' facts (target, platform, machine, commit, locks), one DIFFERENT line per difference (item, clip or total, field, A value, B value) and a summary line [tests: test_FR_0_7_08_reports_every_per_clip_difference, test_FR_0_7_08_identical_bundles_report_no_difference]
INPUTS AND OUTPUTS: two bundle paths in; a Report and printable lines out; ParityInputError on an unusable bundle.
CONTRACTS: bundle format in docs/runs/PHASE0_SMOKE.md; score table 1.0.
INVARIANTS:
  - Every difference found is listed; nothing is summarised away or ignored.
  - Only checked bundles are compared.
NOT IN SCOPE:
  - Producing bundles (aqis_lab/smoke.py).
CHANGE LOG:
  2026-09-30 WP-0.7 FR-0.7-08 created.
"""
import hashlib
import io
import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

BUNDLE_VERSION = "1.0"
REQUIRED_TASK = "vosk-batch"
TOTAL_FIELDS = ("corpus_wer", "errors", "ref_words", "corpus_cer")


class ParityInputError(RuntimeError):
    """A bundle cannot be read or does not match its BUNDLE.json (exit 2)."""


@dataclass
class Bundle:
    name: str
    meta: dict
    files: dict              # {path inside the bundle: bytes}


@dataclass(frozen=True)
class Difference:
    item: str                # a task (transcripts) or a score table
    clip: str                # a clip ID, or "total"
    field: str
    a: object
    b: object

    def line(self):
        shown = lambda v: v if isinstance(v, str) else repr(v)
        return f"DIFFERENT {self.item} {self.clip} {self.field} A={shown(self.a)} B={shown(self.b)}"


@dataclass
class Report:
    a: Bundle
    b: Bundle
    differences: list = field(default_factory=list)
    compared: dict = field(default_factory=dict)       # item -> "<n> clips" (tasks) or "<n> rows" (tables)
    only: list = field(default_factory=list)           # "item is only in A (name)"


def _read_tree(path):
    path = Path(path)
    if path.is_dir():
        return path.name, {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    if path.is_file():
        try:
            with tarfile.open(path) as tar:
                members = [m for m in tar.getmembers() if m.isfile()]
                tops = {m.name.split("/", 1)[0] for m in tar.getmembers()}
                if len(tops) != 1 or any("/" not in m.name for m in members):
                    raise ParityInputError(f"{path}: a bundle archive holds exactly one bundle folder")
                name = tops.pop()
                return name, {m.name.split("/", 1)[1]: tar.extractfile(m).read() for m in members}
        except tarfile.TarError as exc:
            raise ParityInputError(f"{path}: not a bundle archive ({exc})") from exc
    raise ParityInputError(f"{path} is neither a bundle folder nor a bundle archive")


def load_bundle(path):
    """The checked bundle at `path` (folder or .tar)."""
    name, files = _read_tree(path)
    if "BUNDLE.json" not in files:
        raise ParityInputError(f"{path}: no BUNDLE.json")
    try:
        meta = json.loads(files.pop("BUNDLE.json").decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ParityInputError(f"{path}: BUNDLE.json is unreadable ({exc})") from exc
    if not isinstance(meta, dict) or meta.get("bundle_version") != BUNDLE_VERSION or \
            not isinstance(meta.get("files"), dict):
        raise ParityInputError(f"{path}: BUNDLE.json is not bundle version {BUNDLE_VERSION}")
    listed = meta["files"]
    for rel in sorted(set(files) - set(listed)):
        raise ParityInputError(f"{path}: {rel} is in the bundle but not in BUNDLE.json")
    for rel, info in sorted(listed.items()):
        if rel not in files:
            raise ParityInputError(f"{path}: {rel} is listed in BUNDLE.json but missing")
        data = files[rel]
        if len(data) != info.get("bytes") or hashlib.sha256(data).hexdigest() != info.get("sha256"):
            raise ParityInputError(f"{path}: {rel} does not match its SHA-256 and size in BUNDLE.json")
    return Bundle(name=meta.get("name", name), meta=meta, files=files)


def _transcripts(bundle, task):
    rows = {}
    for number, line in enumerate(bundle.files[f"runs/{task}/results.jsonl"].decode("utf-8").splitlines(), 1):
        row = json.loads(line)
        if row["clip_id"] in rows:
            raise ParityInputError(f"{bundle.name}: runs/{task}/results.jsonl line {number} repeats {row['clip_id']}")
        rows[row["clip_id"]] = row["text_sha256"]
    return rows


def _text_tasks(bundle):
    tasks = set()
    for rel, data in bundle.files.items():
        parts = rel.split("/")
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "results.jsonl":
            first = data.split(b"\n", 1)[0]
            if first and "text_sha256" in json.loads(first):
                tasks.add(parts[1])
    return tasks


def _tables(bundle):
    return {rel.split("/")[1] for rel in bundle.files if rel.startswith("scores/") and rel.endswith("/summary.json")}


def _scores(bundle, table):
    # The bytes are copied into memory Arrow owns first. Arrow's pool threads can hold the last reference to a buffer
    # until interpreter exit; releasing a Python-owned buffer there needs the GIL and deadlocks the exit, releasing
    # Arrow-owned memory does not.
    owned = pa.BufferOutputStream()
    owned.write(bundle.files[f"scores/{table}/scores.parquet"])
    with pq.ParquetFile(pa.BufferReader(owned.getvalue())) as scores:
        rows = scores.read().to_pylist()
    summary = json.loads(bundle.files[f"scores/{table}/summary.json"].decode("utf-8"))
    return {(r["clip_id"], r["variant"]): r["wer"] for r in rows}, summary["variants"]


def compare(a, b):
    """A Report listing every difference between two checked bundles."""
    report = Report(a=a, b=b)
    tasks_a, tasks_b = _text_tasks(a), _text_tasks(b)
    for bundle, tasks in ((a, tasks_a), (b, tasks_b)):
        if REQUIRED_TASK not in tasks:
            raise ParityInputError(f"bundle {bundle.name} has no {REQUIRED_TASK} transcripts to compare")
    for label, only, bundle in (("A", tasks_a - tasks_b, a), ("B", tasks_b - tasks_a, b)):
        report.only += [f"{task} is only in {label} ({bundle.name})" for task in sorted(only)]
    for task in sorted(tasks_a & tasks_b):
        ta, tb = _transcripts(a, task), _transcripts(b, task)
        clips = sorted(set(ta) | set(tb))
        report.compared[task] = f"{len(clips)} clips"
        for clip in clips:
            if clip not in tb or clip not in ta:
                report.differences.append(Difference(task, clip, "clip", "present" if clip in ta else "missing",
                                                     "present" if clip in tb else "missing"))
            elif ta[clip] != tb[clip]:
                report.differences.append(Difference(task, clip, "text_sha256", ta[clip], tb[clip]))
    tables_a, tables_b = _tables(a), _tables(b)
    for label, only, bundle in (("A", tables_a - tables_b, a), ("B", tables_b - tables_a, b)):
        report.only += [f"score table {t} is only in {label} ({bundle.name})" for t in sorted(only)]
    for table in sorted(tables_a & tables_b):
        (wa, sa), (wb, sb) = _scores(a, table), _scores(b, table)
        keys = sorted(set(wa) | set(wb))
        report.compared[table] = f"{len(keys)} rows"
        for clip, variant in keys:
            if (clip, variant) not in wa or (clip, variant) not in wb:
                report.differences.append(Difference(table, clip, f"{variant} row",
                                                     "present" if (clip, variant) in wa else "missing",
                                                     "present" if (clip, variant) in wb else "missing"))
            elif wa[(clip, variant)] != wb[(clip, variant)]:
                report.differences.append(Difference(table, clip, f"{variant} wer", wa[(clip, variant)],
                                                     wb[(clip, variant)]))
        for variant in sorted(set(sa) | set(sb)):
            for name in TOTAL_FIELDS:
                va, vb = sa.get(variant, {}).get(name), sb.get(variant, {}).get(name)
                if va != vb:
                    report.differences.append(Difference(table, "total", f"{variant} {name}", va, vb))
    return report


def _facts(label, bundle):
    m, meta = bundle.meta.get("machine") or {}, bundle.meta
    locks = ", ".join(f"{l['file']} {l['sha256'][:12]}" for l in meta.get("locks", []))
    return (f"{label}: {bundle.name}: target {meta.get('target')}, platform {meta.get('platform')}, "
            f"{m.get('cpu_model')} {m.get('architecture')}, commit {meta.get('git', {}).get('commit')}, locks {locks}")


def report_lines(report):
    lines = [_facts("A", report.a), _facts("B", report.b)]
    lines += [f"not compared: {text}" for text in report.only]
    lines += [d.line() for d in report.differences]
    compared = "; ".join(f"{item}: {n}" for item, n in report.compared.items())
    if report.differences:
        lines.append(f"parity: {len(report.differences)} difference(s) ({compared})")
    else:
        lines.append(f"parity: identical ({compared})")
    return lines
