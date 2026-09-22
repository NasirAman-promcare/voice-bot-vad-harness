"""
reporting.py

One Job:
    Read persisted raw evaluation records from storage/results_store.py and automatically
    generate cross-adapter benchmark comparison tables, SNR/loudness sensitivity curves,
    latency triplet summaries, and an editable strengths/weaknesses skeleton write-up.

Automatic & Dynamic Generation:
    - Zero hardcoded model names, numbers, or conclusions: every table row, category column,
      and narrative finding is dynamically derived from whatever records currently exist in
      the results store.
    - Notebook 03 (`notebooks/03_report.ipynb`) imports this module to render reports and
      provides the interactive workspace where human reviewers refine the generated skeleton.

Three Distinct Latency Metrics (Never Collapsed):
    Maintains the architectural separation of latency into three independent numbers:
      1. Algorithmic Compute Latency (Tier 1 inline frame execution time: p50, p95, p99 ms).
      2. Live Onset Latency (Tier 2 speech start -> first positive detection in ms).
      3. Live Offset / Hangover Latency (Tier 2 speech end -> non-speech transition in ms).

Multi-Version & Partial Store Handling:
    - If results from multiple corpus/manifest versions coexist in the store, the report
      groups runs by manifest version hash with explicit isolation warnings.
    - If only a subset of operating points have been evaluated, missing cells are rendered
      as explicit markers ('— (Not Yet Run)') rather than blank zeros.

What this module must NEVER do:
    - Never hardcode specific VAD model names or vendor identifiers as string literals.
    - Never write or persist permanent files directly (persistence belongs to results_store.py).
    - Never average or blend onset latency, offset latency, and algorithmic latency together.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union

import numpy as np

from corpus.manifest import VALID_CATEGORIES
from scoring.vad_scorer import get_loudness_bucket, get_snr_bucket
from storage.results_store import ResultsStore

logger = logging.getLogger(__name__)


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class AdapterAggregateMetrics:
     """Aggregated performance metrics for one discovered adapter operating point."""
     adapter_id: str
     library_version: str
     total_clips: int
     # Classification metrics
     total_frames: int
     precision: Optional[float]
     recall: Optional[float]
     f1: Optional[float]
     accuracy: float
     specificity: float
     false_positive_rate: float
     false_negative_rate: Optional[float]


@dataclass(frozen=True)
class SensitivityCurvePoint:
    """A single bucket point along an SNR or Loudness sensitivity curve."""
    bucket_label: str
    clip_count: int
    f1: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    false_positive_rate: Optional[float]


@dataclass(frozen=True)
class BenchmarkReport:
    """
    Master generated report bundle for a specific run or manifest version dataset.
    """
    report_timestamp_utc: str
    run_ids: Tuple[str, ...]
    manifest_versions: Tuple[str, ...]
    discovered_adapters: Tuple[str, ...]
    summary_metrics: Dict[str, AdapterAggregateMetrics]
    category_matrix: Dict[str, Dict[str, Optional[float]]]  # category -> adapter_id -> F1
    snr_curves: Dict[str, List[SensitivityCurvePoint]]      # adapter_id -> points
    loudness_curves: Dict[str, List[SensitivityCurvePoint]] # adapter_id -> points
    skeleton_writeup_markdown: str
    version_warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the report into a JSON-compatible dictionary."""
        return asdict(self)


# ==============================================================================
# Metric Aggregation Helpers
# ==============================================================================

def _aggregate_confusion_counts(raw_metrics_list: Sequence[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float], Optional[float], float, float, float, Optional[float], int]:
    """Computes precision, recall, f1, accuracy, specificity, fpr, fnr from raw counts with None for undefined."""
    if not raw_metrics_list:
        return None, None, None, 1.0, 1.0, 0.0, None, 0

    tp = sum(int(m.get("tp", 0)) for m in raw_metrics_list)
    fp = sum(int(m.get("fp", 0)) for m in raw_metrics_list)
    tn = sum(int(m.get("tn", 0)) for m in raw_metrics_list)
    fn = sum(int(m.get("fn", 0)) for m in raw_metrics_list)
    total_frames = tp + fp + tn + fn

    gt_pos = tp + fn
    gt_neg = tn + fp
    pred_pos = tp + fp

    if gt_pos == 0:
        precision = None
        recall = None
        f1 = None
        fnr = None
    else:
        precision = float(tp / pred_pos) if pred_pos > 0 else 0.0
        recall = float(tp / gt_pos)
        f1 = float(2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0.0 else 0.0
        fnr = float(fn / gt_pos)

    accuracy = float((tp + tn) / total_frames) if total_frames > 0 else 1.0
    specificity = float(tn / gt_neg) if gt_neg > 0 else 1.0
    fpr = float(fp / gt_neg) if gt_neg > 0 else 0.0

    return precision, recall, f1, accuracy, specificity, fpr, fnr, total_frames


# ==============================================================================
# Markdown Table Formatting Utilities
# ==============================================================================

def _format_markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Formats a list of headers and rows into an aligned Markdown table string."""
    if not rows:
        return "*No data available for table.*"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = "| " + " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers))) + " |"
    sep_line = "|-" + "-|-".join("-" * col_widths[i] for i in range(len(headers))) + "-|"
    body_lines = [
        "| " + " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(headers))) + " |"
        for row in rows
    ]

    return "\n".join([header_line, sep_line] + body_lines)


# ==============================================================================
# Skeleton Write-Up Generator
# ==============================================================================

def _generate_skeleton_writeup(
    discovered_adapters: Sequence[str],
    summary_metrics: Dict[str, AdapterAggregateMetrics],
    category_matrix: Dict[str, Dict[str, Optional[float]]],
    manifest_versions: Sequence[str],
) -> str:
    """
    Builds the auto-generated, editable Markdown strengths/weaknesses skeleton.

    Explicitly tagged with editable markers for human completion in 03_report.ipynb.
    """
    lines: List[str] = [
        "<!-- ============================================================================== -->",
        "<!-- [AUTO-GENERATED SKELETON WRITE-UP — EDITABLE BY REVIEWER IN 03_REPORT.IPYNB]   -->",
        "<!-- Generated fresh from results store. Modify sections below for final reporting. -->",
        "<!-- ============================================================================== -->",
        "",
        "# Executive Summary & Comparative VAD Analysis",
        f"*Generated on: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*  ",
        f"*Evaluated Corpus Version(s): {', '.join(manifest_versions)}*",
        "",
        "## 1. High-Level Summary Findings",
        "<!-- REVIEWER EDIT: Summarize primary takeaway regarding latency vs accuracy tradeoffs -->",
    ]

    if not discovered_adapters:
        lines.append("\n*No adapter results discovered in the store.*")
        return "\n".join(lines)

    for adapter_id in discovered_adapters:
        m = summary_metrics.get(adapter_id)
        if m is None:
            continue

        # Determine best and worst acoustic category from category matrix
        adapter_cat_f1s = [
            (cat, score_map.get(adapter_id))
            for cat, score_map in category_matrix.items()
            if score_map.get(adapter_id) is not None
        ]
        adapter_cat_f1s.sort(key=lambda x: x[1] if x[1] is not None else -1.0, reverse=True)

        best_cat_str = f"{adapter_cat_f1s[0][0]} (F1: {adapter_cat_f1s[0][1]:.3f})" if adapter_cat_f1s else "N/A"
        worst_cat_str = f"{adapter_cat_f1s[-1][0]} (F1: {adapter_cat_f1s[-1][1]:.3f})" if adapter_cat_f1s else "N/A"

        algo_lat_str = f"{m.algorithmic_p95_ms:.2f} ms" if m.algorithmic_p95_ms is not None else "N/A (Offline bench not run)"
        onset_lat_str = f"{m.live_onset_mean_ms:.1f} ms" if m.live_onset_mean_ms is not None else "N/A (Live tier not run)"
        offset_lat_str = f"{m.live_offset_mean_ms:.1f} ms" if m.live_offset_mean_ms is not None else "N/A (Live tier not run)"

        f1_label = f"{m.f1:.3f}" if m.f1 is not None else "N/A"
        prec_label = f"{m.precision:.3f}" if m.precision is not None else "N/A"
        rec_label = f"{m.recall:.3f}" if m.recall is not None else "N/A"
        lines.extend([
            f"\n### Operating Point: `{adapter_id}` (`{m.library_version}`)",
            f"- **Overall Accuracy**: F1 = **{f1_label}** | Precision = **{prec_label}** | Recall = **{rec_label}**",
            "- **Latency Triplet**:",
            f"  - *Algorithmic Compute (p95)*: {algo_lat_str}",
            f"  - *Pipeline Onset Latency (mean)*: {onset_lat_str}",
            f"  - *Pipeline Offset/Hangover (mean)*: {offset_lat_str}",
            "- **Identified Strengths**:",
            f"  - Peak category performance on: **{best_cat_str}**",
            f"  - Silence false-positive rate: **{m.silence_fpr:.3f}**" if m.silence_fpr is not None else "  - Silence FPR: Untested",
            "- **Identified Weaknesses & Failure Modes**:",
            f"  - Lowest category performance on: **{worst_cat_str}**",
            f"  - Quiet/whispered speech miss rate (FNR): **{m.quiet_fnr:.3f}**" if m.quiet_fnr is not None else "  - Quiet speech FNR: Untested",
            f"  - Unresolved hangover instances: **{m.unresolved_hangover_clips_count} clip(s)**",
            "<!-- REVIEWER EDIT: Add qualitative acoustic observations for this adapter below -->",
            "> *Reviewer Note:* ",
            "",
        ])

    lines.extend([
        "## 2. Cross-Model Tradeoff Recommendations",
        "<!-- REVIEWER EDIT: Final deployment recommendations (e.g. edge CPU vs high-noise vs low-latency) -->",
        "- **Lowest Algorithmic Compute Overhead**: ",
        "- **Fastest Pipeline Interactivity (Lowest Onset)**: ",
        "- **Highest Noise Robustness**: ",
        "",
        "<!-- ============================================================================== -->",
        "<!-- END OF SKELETON WRITE-UP                                                        -->",
        "<!-- ============================================================================== -->",
    ])

    return "\n".join(lines)


# ==============================================================================
# Public Report Generator
# ==============================================================================

def generate_report(
     results_store: ResultsStore,
     run_id: Optional[str] = None,
     manifest_version: Optional[str] = None,
     tier: Optional[str] = None,
 ) -> BenchmarkReport:
    """
    Generates a full BenchmarkReport from raw records in the ResultsStore.
 
    Args:
         results_store: Instance of ResultsStore to read raw records from.
         run_id: Optional run ID filter.
         manifest_version: Optional manifest version filter.
         tier: Optional tier filter ('tier1' or 'tier2').
    """
    raw_records = list(results_store.read_raw_records(run_id=run_id))
    if manifest_version is not None:
        raw_records = [r for r in raw_records if r.get("manifest_version") == manifest_version]
    if tier is not None:
        raw_records = [
            r for r in raw_records
            if r.get("payload", {}).get("tier") == tier or tier in r.get("record_type", "")
        ]
     
    # 1. Discover distinct metadata dimensions
    discovered_runs = sorted(list({r.get("run_id") for r in raw_records if r.get("run_id")}))
    discovered_versions = sorted(list({r.get("manifest_version") for r in raw_records if r.get("manifest_version")}))
    discovered_adapters = sorted(list({r.get("adapter_id") for r in raw_records if r.get("adapter_id") and r.get("adapter_id") != "audio_profiler"}))

    version_warning: Optional[str] = None
    if len(discovered_versions) > 1:
        version_warning = (
            f"WARNING: Results store contains records across {len(discovered_versions)} "
            f"distinct manifest versions ({discovered_versions}). Metrics reflect combined runs."
        )
        logger.warning("[reporting] %s", version_warning)

    # 2. Partition records by adapter
    adapter_scoring_records: Dict[str, List[Dict[str, Any]]] = {aid: [] for aid in discovered_adapters}
    adapter_algo_latencies: Dict[str, List[float]] = {aid: [] for aid in discovered_adapters}
    adapter_onset_latencies: Dict[str, List[float]] = {aid: [] for aid in discovered_adapters}
    adapter_offset_latencies: Dict[str, List[float]] = {aid: [] for aid in discovered_adapters}
    adapter_fn_counts: Dict[str, int] = {aid: 0 for aid in discovered_adapters}
    adapter_unresolved_hangover_counts: Dict[str, int] = {aid: 0 for aid in discovered_adapters}
    adapter_library_versions: Dict[str, str] = {aid: "unknown" for aid in discovered_adapters}

    for r in raw_records:
        aid = r.get("adapter_id")
        if aid not in adapter_scoring_records:
            continue

        rtype = r.get("record_type")
        payload = r.get("payload", {})
        adapter_library_versions[aid] = r.get("vad_library_version", "unknown")

        if rtype == "scoring_clip":
            adapter_scoring_records[aid].append(payload)

        elif rtype == "tier1_algorithmic_latency":
            p95 = payload.get("p95_compute_ms")
            if p95 is not None:
                adapter_algo_latencies[aid].append(float(p95))

        elif rtype == "tier2_pipeline_latency":
            onset = payload.get("mean_onset_latency_ms")
            offset = payload.get("mean_offset_hangover_latency_ms")
            if onset is not None:
                adapter_onset_latencies[aid].append(float(onset))
            else:
                if payload.get("has_speech", True):
                    adapter_fn_counts[aid] += 1

            if offset is not None:
                adapter_offset_latencies[aid].append(float(offset))
            else:
                if payload.get("has_speech", True):
                    adapter_unresolved_hangover_counts[aid] += 1

    # 3. Compute Summary Metrics per Adapter
    summary_metrics: Dict[str, AdapterAggregateMetrics] = {}

    for aid in discovered_adapters:
        scoring_list = adapter_scoring_records[aid]
        raw_m_list = [c.get("metrics", {}) for c in scoring_list if "metrics" in c]

        prec, rec, f1, acc, spec, fpr, fnr, tot_frames = _aggregate_confusion_counts(raw_m_list)

        # Silence-only FPR
        silence_records = [c.get("metrics", {}) for c in scoring_list if c.get("category") == "silence-only"]
        silence_fpr = _aggregate_confusion_counts(silence_records)[5] if silence_records else None

        # Quiet speech FNR
        quiet_records = [c.get("metrics", {}) for c in scoring_list if c.get("category") == "quiet/whispered speech"]
        quiet_fnr = _aggregate_confusion_counts(quiet_records)[6] if quiet_records else None

        # Latency statistics
        algo_lat_p95 = float(np.mean(adapter_algo_latencies[aid])) if adapter_algo_latencies[aid] else None
        onset_mean = float(np.mean(adapter_onset_latencies[aid])) if adapter_onset_latencies[aid] else None
        onset_median = float(np.median(adapter_onset_latencies[aid])) if adapter_onset_latencies[aid] else None
        offset_mean = float(np.mean(adapter_offset_latencies[aid])) if adapter_offset_latencies[aid] else None
        offset_median = float(np.median(adapter_offset_latencies[aid])) if adapter_offset_latencies[aid] else None

        summary_metrics[aid] = AdapterAggregateMetrics(
            adapter_id=aid,
            library_version=adapter_library_versions[aid],
            total_clips=len(scoring_list),
            total_frames=tot_frames,
            precision=round(prec, 3) if prec is not None else None,
            recall=round(rec, 3) if rec is not None else None,
            f1=round(f1, 3) if f1 is not None else None,
            accuracy=round(acc, 3),
            specificity=round(spec, 3),
            false_positive_rate=round(fpr, 3),
            false_negative_rate=round(fnr, 3) if fnr is not None else None,
            silence_fpr=round(silence_fpr, 3) if silence_fpr is not None else None,
            quiet_fnr=round(quiet_fnr, 3) if quiet_fnr is not None else None,
            algorithmic_p95_ms=round(algo_lat_p95, 2) if algo_lat_p95 is not None else None,
            live_onset_mean_ms=round(onset_mean, 1) if onset_mean is not None else None,
            live_onset_median_ms=round(onset_median, 1) if onset_median is not None else None,
            live_offset_mean_ms=round(offset_mean, 1) if offset_mean is not None else None,
            live_offset_median_ms=round(offset_median, 1) if offset_median is not None else None,
            false_negative_clips_count=adapter_fn_counts[aid],
            unresolved_hangover_clips_count=adapter_unresolved_hangover_counts[aid],
        )

    # 4. Compute Category Breakdown Matrix
    all_categories = sorted(VALID_CATEGORIES)
    category_matrix: Dict[str, Dict[str, Optional[float]]] = {cat: {} for cat in all_categories}

    for cat in all_categories:
        for aid in discovered_adapters:
            cat_clips = [c.get("metrics", {}) for c in adapter_scoring_records[aid] if c.get("category") == cat]
            if cat_clips:
                cat_f1 = _aggregate_confusion_counts(cat_clips)[2]
                category_matrix[cat][aid] = round(cat_f1, 3)
            else:
                category_matrix[cat][aid] = None  # Explicit untested state

    # 5. Compute SNR & Loudness Sensitivity Curves
    snr_bucket_order = ["< 0 dB", "0 to 10 dB", "10 to 20 dB", ">= 20 dB", "N/A (Clean / Non-noisy)"]
    loud_bucket_order = ["< -25 LUFS (Quiet)", "-25 to -15 LUFS (Nominal)", ">= -15 LUFS (Loud/Clipped)", "N/A (Unspecified)"]

    snr_curves: Dict[str, List[SensitivityCurvePoint]] = {}
    loudness_curves: Dict[str, List[SensitivityCurvePoint]] = {}

    for aid in discovered_adapters:
        # SNR Curve points
        snr_pts = []
        for b_label in snr_bucket_order:
            b_clips = [
                c.get("metrics", {}) for c in adapter_scoring_records[aid]
                if get_snr_bucket(c.get("target_snr_db")) == b_label
            ]
            if b_clips:
                p, r, f1, _, _, fpr, _, _ = _aggregate_confusion_counts(b_clips)
                snr_pts.append(SensitivityCurvePoint(b_label, len(b_clips), round(f1, 3), round(p, 3), round(r, 3), round(fpr, 3)))
            else:
                snr_pts.append(SensitivityCurvePoint(b_label, 0, None, None, None, None))
        snr_curves[aid] = snr_pts

        # Loudness Curve points
        loud_pts = []
        for l_label in loud_bucket_order:
            l_clips = [
                c.get("metrics", {}) for c in adapter_scoring_records[aid]
                if get_loudness_bucket(c.get("target_loudness_lufs")) == l_label
            ]
            if l_clips:
                p, r, f1, _, _, fpr, _, _ = _aggregate_confusion_counts(l_clips)
                loud_pts.append(SensitivityCurvePoint(l_label, len(l_clips), round(f1, 3), round(p, 3), round(r, 3), round(fpr, 3)))
            else:
                loud_pts.append(SensitivityCurvePoint(l_label, 0, None, None, None, None))
        loudness_curves[aid] = loud_pts

    # 6. Generate Editable Skeleton Write-Up
    skeleton_md = _generate_skeleton_writeup(
        discovered_adapters=discovered_adapters,
        summary_metrics=summary_metrics,
        category_matrix=category_matrix,
        manifest_versions=discovered_versions,
    )

    return BenchmarkReport(
        report_timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        run_ids=tuple(discovered_runs),
        manifest_versions=tuple(discovered_versions),
        discovered_adapters=tuple(discovered_adapters),
        summary_metrics=summary_metrics,
        category_matrix=category_matrix,
        snr_curves=snr_curves,
        loudness_curves=loudness_curves,
        skeleton_writeup_markdown=skeleton_md,
        version_warning=version_warning,
    )


# ==============================================================================
# Formatted Markdown Export Functions
# ==============================================================================

def render_overall_summary_table(report: BenchmarkReport) -> str:
    """Renders the master cross-adapter comparison table in Markdown."""
    headers = [
        "Adapter / Operating Point", "Version", "F1", "Precision", "Recall",
        "FPR (Silence)", "FNR (Quiet)", "Algorithmic p95", "Onset Latency", "Offset Hangover"
    ]
    rows = []
    for aid in report.discovered_adapters:
        m = report.summary_metrics.get(aid)
        if m is None or m.total_clips == 0:
            rows.append([aid, "—", "— (Not Yet Run)", "—", "—", "—", "—", "—", "—", "—"])
            continue

        algo_str = f"{m.algorithmic_p95_ms:.2f} ms" if m.algorithmic_p95_ms is not None else "—"
        onset_str = f"{m.live_onset_mean_ms:.1f} ms" if m.live_onset_mean_ms is not None else "—"
        offset_str = f"{m.live_offset_mean_ms:.1f} ms" if m.live_offset_mean_ms is not None else "—"
        silence_str = f"{m.silence_fpr:.3f}" if m.silence_fpr is not None else "—"
        quiet_str = f"{m.quiet_fnr:.3f}" if m.quiet_fnr is not None else "—"

        f1_str = f"{m.f1:.3f}" if m.f1 is not None else "—"
        prec_str = f"{m.precision:.3f}" if m.precision is not None else "—"
        rec_str = f"{m.recall:.3f}" if m.recall is not None else "—"
        rows.append([
             aid,
             m.library_version,
             f1_str,
             prec_str,
             rec_str,
             silence_str,
             quiet_str,
             algo_str,
             onset_str,
             offset_str,
         ])

    return _format_markdown_table(headers, rows)


def render_category_matrix_table(report: BenchmarkReport) -> str:
    """Renders the category breakdown F1 matrix across all adapters in Markdown."""
    headers = ["Category"] + list(report.discovered_adapters)
    rows = []
    for cat in sorted(VALID_CATEGORIES):
        row = [cat]
        for aid in report.discovered_adapters:
            f1_val = report.category_matrix.get(cat, {}).get(aid)
            if f1_val is None:
                row.append("—")
            else:
                row.append(f"{f1_val:.3f}")
        rows.append(row)

    return _format_markdown_table(headers, rows)


def render_snr_sensitivity_table(report: BenchmarkReport) -> str:
    """Renders the SNR sensitivity curve table across all adapters in Markdown."""
    headers = ["SNR Bucket"] + [f"{aid} (F1)" for aid in report.discovered_adapters]
    snr_bucket_order = ["< 0 dB", "0 to 10 dB", "10 to 20 dB", ">= 20 dB", "N/A (Clean / Non-noisy)"]
    rows = []

    for b_label in snr_bucket_order:
        row = [b_label]
        for aid in report.discovered_adapters:
            pts = report.snr_curves.get(aid, [])
            pt = next((p for p in pts if p.bucket_label == b_label), None)
            if pt is None or pt.f1 is None:
                row.append("—")
            else:
                row.append(f"{pt.f1:.3f} (N={pt.clip_count})")
        rows.append(row)

    return _format_markdown_table(headers, rows)


def render_full_report_markdown(report: BenchmarkReport) -> str:
    """Combines all comparison tables and the skeleton write-up into a unified Markdown document."""
    parts = []
    if report.version_warning:
        parts.append(f"> **Notice**: {report.version_warning}\n")

    parts.append("## Table 1: Cross-VAD Benchmark Master Summary")
    parts.append(render_overall_summary_table(report))
    parts.append("\n## Table 2: Category Breakdown Matrix (F1 Score)")
    parts.append(render_category_matrix_table(report))
    parts.append("\n## Table 3: SNR Sensitivity Sweep (F1 Score)")
    parts.append(render_snr_sensitivity_table(report))
    parts.append("\n" + report.skeleton_writeup_markdown)

    return "\n".join(parts)