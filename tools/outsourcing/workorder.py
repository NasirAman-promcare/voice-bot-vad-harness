"""Work order file parser and step planner.

CAPABILITIES:
  CAP-OUTSOURCING-004: parse and validate work order front matter and step plan
    [tests: test_FR_1_0_01_valid_order_loads_with_its_fields,
    test_FR_1_0_01_mc07_output_under_never_or_guarded_path_is_invalid,
    test_FR_1_0_01_mc09_valid_step_plan_is_numbered_in_order, test_FR_1_0_01_mc09_bad_step_plan_is_invalid,
    test_FR_1_0_01_mc09_more_than_three_outputs_without_steps_is_invalid, test_FR_1_0_01_load_valid_work_order,
    test_FR_1_0_01_invalid_front_matter_errors, test_FR_1_0_01_step_plan_valid_and_invalid]
INPUTS AND OUTPUTS: WorkOrder, Step, WorkOrderError, load_work_order, plan_steps.
CONTRACTS: WORK_ORDER.md specification.
INVARIANTS:
  - Outputs must be LAB-OWNED or FREE.
  - Step plans must cover all outputs exactly once with at most 3 non-init paths per step.
NOT IN SCOPE:
  - Executing verification commands.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
  2026-10-10 WP-1.0 FR-1.0-01 review fix (Claude): an invalid path raises WorkOrderError naming its place.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from tools.outsourcing.paths import classify, normalise

__all__ = ["WorkOrderError", "WorkOrder", "Step", "load_work_order", "plan_steps"]

REQUIRED_KEYS = {
    "id", "wp", "title", "model", "channel", "attempt_budget",
    "risk_tier", "max_output_tokens", "context", "outputs",
    "read_only_tests", "allowed_dependencies", "verify"
}
OPTIONAL_KEYS = {"interfaces", "steps"}
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS

WO_ID_PAT = re.compile(r"^WO-(\d+\.\d+)-(\d+)$")
MODEL_PAT = re.compile(r"^[a-zA-Z0-9.-]+$")


class WorkOrderError(Exception):
    """Raised when a work order file or its step plan is invalid."""


@dataclass(frozen=True)
class WorkOrder:
    id: str
    wp: str
    title: str
    model: str
    channel: str
    attempt_budget: int
    risk_tier: str
    max_output_tokens: int
    context: tuple[str, ...]
    outputs: tuple[str, ...]
    read_only_tests: tuple[str, ...]
    allowed_dependencies: tuple[str, ...]
    verify: tuple[str, ...]
    interfaces: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    body: str = ""
    path: str = ""


@dataclass(frozen=True)
class Step:
    number: int
    paths: tuple[str, ...]


def _normalise(path: str, where: str) -> str:
    """Normalise a path from the order, turning a path error into a WorkOrderError that names its place."""
    try:
        return normalise(path)
    except ValueError as exc:
        raise WorkOrderError(f"{where}: {exc}") from exc


def _parse_front_matter(text: str) -> tuple[dict[str, str | list[str]], str]:
    if "\t" in text:
        raise WorkOrderError("Front matter contains tabs")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise WorkOrderError("Missing starting '---' marker")

    fm_lines: list[str] = []
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
        fm_lines.append(lines[i])

    if end_idx == -1:
        raise WorkOrderError("Missing closing '---' marker")

    body = "\n".join(lines[end_idx + 1:])
    data: dict[str, str | list[str]] = {}
    current_key: str | None = None

    for line in fm_lines:
        if '"' in line or "'" in line:
            if " #" in line:
                raise WorkOrderError("Quotes and internal comments are not supported in front matter")

        content = line.split(" #", 1)[0]
        if not content.strip():
            continue

        if content.startswith("  - "):
            if current_key is None:
                raise WorkOrderError("List item without key header")
            item = content[4:].strip()
            val = data[current_key]
            if not isinstance(val, list):
                raise WorkOrderError(f"Key {current_key!r} changed to list unexpectedly")
            val.append(item)
        elif not content.startswith(" ") and ":" in content:
            key, value = content.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key in data:
                raise WorkOrderError(f"Duplicate key: {key!r}")
            if key not in ALLOWED_KEYS:
                raise WorkOrderError(f"Unknown front-matter key: {key!r}")

            current_key = key
            if value == "" or value == "[]":
                data[key] = []
            else:
                data[key] = value
        else:
            raise WorkOrderError(f"Invalid front-matter line: {line!r}")

    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise WorkOrderError(f"Missing required front-matter keys: {sorted(missing)}")

    return data, body


def load_work_order(path: str | Path, repo_root: str | Path) -> WorkOrder:
    p = Path(path)
    root = Path(repo_root)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkOrderError(f"Cannot read work order at {path}: {exc}") from exc

    raw_data, body = _parse_front_matter(raw)

    def _get_list(key: str) -> tuple[str, ...]:
        v = raw_data.get(key, ())
        if isinstance(v, str):
            if not v or v == "[]":
                return ()
            return (v,)
        return tuple(v)

    wo_id = str(raw_data["id"])
    wp = str(raw_data["wp"])
    m_id = WO_ID_PAT.match(wo_id)
    if not m_id:
        raise WorkOrderError(f"Invalid order id format: {wo_id!r}")
    expected_wp = f"WP-{m_id.group(1)}"
    if wp != expected_wp:
        raise WorkOrderError(f"ID {wo_id!r} does not match wp {wp!r} (expected {expected_wp!r})")

    model = str(raw_data["model"])
    if model != "default" and not MODEL_PAT.match(model):
        raise WorkOrderError(f"Invalid model name: {model!r}")

    channel = str(raw_data["channel"])
    if channel not in ("api", "jules", "paste"):
        raise WorkOrderError(f"Invalid channel: {channel!r}")

    try:
        attempt_budget = int(raw_data["attempt_budget"])
        if not (1 <= attempt_budget <= 5):
            raise ValueError()
    except (ValueError, TypeError):
        raise WorkOrderError(f"attempt_budget must be int 1..5: {raw_data['attempt_budget']!r}")

    risk_tier = str(raw_data["risk_tier"])
    if risk_tier not in ("T1", "T2", "T3"):
        raise WorkOrderError(f"Invalid risk_tier: {risk_tier!r}")

    try:
        max_tokens = int(raw_data["max_output_tokens"])
        if max_tokens <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise WorkOrderError(f"max_output_tokens must be positive int: {raw_data['max_output_tokens']!r}")

    context = tuple(_normalise(x, "context") for x in _get_list("context"))
    outputs = tuple(_normalise(x, "outputs") for x in _get_list("outputs"))
    read_only_tests = tuple(_normalise(x, "read_only_tests") for x in _get_list("read_only_tests"))
    verify = tuple(_get_list("verify"))
    allowed_deps = tuple(_get_list("allowed_dependencies"))
    interfaces = tuple(_normalise(x, "interfaces") for x in _get_list("interfaces"))
    steps = tuple(_get_list("steps"))

    if not outputs:
        raise WorkOrderError("outputs list cannot be empty")
    if not verify:
        raise WorkOrderError("verify list cannot be empty")

    for out_p in outputs:
        classification = classify(out_p, root)
        if classification in ("NEVER", "GUARDED"):
            raise WorkOrderError(f"Output path {out_p!r} is protected ({classification})")
        if out_p.startswith("tests/aqis_lab/breaks/"):
            raise WorkOrderError(f"Output path {out_p!r} is under tests/aqis_lab/breaks/")

    sections = [("outputs", outputs), ("context", context), ("interfaces", interfaces), ("read_only_tests", read_only_tests)]
    seen: dict[str, str] = {}
    for sec_name, paths in sections:
        for item_path in paths:
            if item_path in seen:
                raise WorkOrderError(f"Path {item_path!r} appears in both {seen[item_path]} and {sec_name}")
            seen[item_path] = sec_name

    for ctx_p in context + interfaces + read_only_tests:
        if not (root / ctx_p).exists():
            raise WorkOrderError(f"Required file does not exist in repository: {ctx_p}")

    for iface_p in interfaces:
        if not iface_p.endswith(".py"):
            raise WorkOrderError(f"Interface path must end in .py: {iface_p}")

    rel_path = str(p.relative_to(root)) if p.is_absolute() and p.is_relative_to(root) else str(p)

    return WorkOrder(
        id=wo_id, wp=wp, title=str(raw_data["title"]), model=model, channel=channel,
        attempt_budget=attempt_budget, risk_tier=risk_tier, max_output_tokens=max_tokens,
        context=context, outputs=outputs, read_only_tests=read_only_tests,
        allowed_dependencies=allowed_deps, verify=verify, interfaces=interfaces,
        steps=steps, body=body, path=rel_path
    )


def plan_steps(order: WorkOrder) -> tuple[Step, ...]:
    def _is_init(p: str) -> bool:
        return p.endswith("/__init__.py") or p == "__init__.py"

    if order.steps:
        if len(order.steps) > 10:
            raise WorkOrderError(f"Too many steps: {len(order.steps)} (max 10)")

        step_objects: list[Step] = []
        all_step_paths: list[str] = []

        for idx, s_raw in enumerate(order.steps, start=1):
            parts = [p.strip() for p in s_raw.split(",")]
            if any(p == "" for p in parts):
                raise WorkOrderError(f"Step {idx} contains empty element or trailing comma: {s_raw!r}")

            norm_parts = tuple(_normalise(p, f"step {idx}") for p in parts)
            non_init = [p for p in norm_parts if not _is_init(p)]
            if len(non_init) > 3:
                raise WorkOrderError(f"Step {idx} has more than 3 non-init paths: {non_init}")

            for p in norm_parts:
                if p not in order.outputs:
                    raise WorkOrderError(f"Step {idx} names path not in outputs: {p}")
                if p in all_step_paths:
                    raise WorkOrderError(f"Path {p} appears in multiple steps")
                all_step_paths.append(p)

            step_objects.append(Step(number=idx, paths=norm_parts))

        missing = set(order.outputs) - set(all_step_paths)
        if missing:
            raise WorkOrderError(f"Step plan misses output paths: {sorted(missing)}")

        return tuple(step_objects)

    non_init_outputs = [p for p in order.outputs if not _is_init(p)]
    if len(non_init_outputs) > 3:
        raise WorkOrderError("Order has more than 3 non-init outputs; add a steps list")

    return (Step(number=1, paths=order.outputs),)
