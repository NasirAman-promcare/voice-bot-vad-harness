"""Request builder for relay model requests.

CAPABILITIES:
  CAP-OUTSOURCING-PROMPT: Build provider-neutral requests sent to model
    [tests: test_secret_in_request_raises, test_FR_1_0_02_mc01_missing_earlier_output_is_listed_not_sent,
    test_FR_1_0_02_mc02_secret_file_raises_naming_it,
    test_FR_1_0_02_fix_split_part_sees_the_step_files_accepted_before_it,
    test_FR_1_0_02_fix_first_split_part_and_whole_step_show_no_sibling]
INPUTS AND OUTPUTS: WorkOrder, plan, step part, worktree root in; Request or string out.
CONTRACTS: none.
INVARIANTS:
  - Raises SecretInRequest if secret-looking content or file is encountered.
NOT IN SCOPE:
  - Sending requests over the network.
CHANGE LOG:
  2026-10-10 WO-1.0-02 created.
  2026-10-10 WP-1.0 FR-1.0-02 review fix (Claude): estimated_input_tokens, the router's input estimate in tokens.
  2026-10-12 WP-1.0 FR-1.0-02 fix (Claude, FIX-B3-split-siblings): a split part also sees its step's files that come
    before it, accepted as earlier split parts.
  2026-10-12 WP-1.0 FR-1.0-03 (Claude): [tests: …] names test functions, not files (gate E3, Lab Map).
"""
from __future__ import annotations

from pathlib import Path
from tools.outsourcing import chat
from tools.outsourcing.interface import interface_view
from tools.outsourcing.records import Request, StepPart
from tools.outsourcing.secrets import secret_reasons
from tools.outsourcing.workorder import Step, WorkOrder

__all__ = ["SecretInRequest", "step_request", "with_fix_turn", "final_fix_request", "step_pack", "estimated_input_tokens"]


class SecretInRequest(Exception):
    """Raised when a file included in a request contains secret-looking features."""

    def __init__(self, path: str, reasons: list[str]) -> None:
        super().__init__(f"Secret detected in {path}: {', '.join(reasons)}")
        self.path = path
        self.reasons = reasons



def estimated_input_tokens(request: Request) -> int:
    """The offline token estimate of a request, ceil(characters / 3.5), as the router's `input_estimate` expects."""
    return -(-request.characters * 2 // 7)

def _read_file_check_secret(root: Path, rel_path: str) -> str:
    full_path = root / rel_path
    try:
        text = full_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise OSError(f"Could not read {rel_path}: {exc}") from exc

    reasons = secret_reasons(rel_path, text)
    if reasons:
        raise SecretInRequest(rel_path, reasons)
    return text


def step_request(order: WorkOrder, plan: tuple[Step, ...], part: StepPart, root: str | Path) -> Request:
    """Build a step request ChatRequest."""
    repo_root = Path(root).resolve()

    foundation_text = _read_file_check_secret(repo_root, "docs/process/outsourcing/FOUNDATION.md")
    return_format_text = _read_file_check_secret(repo_root, "docs/process/outsourcing/templates/RETURN_FORMAT.md")
    order_text = _read_file_check_secret(repo_root, order.path)

    sent_paths: list[str] = [order.path]
    missing_paths: list[str] = []
    user_parts: list[str] = [order_text]

    _add_context_and_interfaces(order, repo_root, sent_paths, user_parts)
    _add_earlier_outputs(plan, part, repo_root, sent_paths, missing_paths, user_parts)
    _add_step_block(plan, part, user_parts)

    user_parts.append(return_format_text)
    user_text = "\n\n".join(user_parts)

    chat_req = chat.ChatRequest(
        system=foundation_text,
        turns=(chat.Turn(role="user", text=user_text),),
        max_output_tokens=order.max_output_tokens,
    )

    return Request(
        chat=chat_req,
        sent_paths=tuple(sent_paths),
        missing_paths=tuple(missing_paths),
        characters=len(foundation_text) + len(user_text),
    )


def _add_context_and_interfaces(order: WorkOrder, repo_root: Path, sent_paths: list[str], user_parts: list[str]) -> None:
    context_files = tuple(order.context) + tuple(order.read_only_tests)
    for c_path in context_files:
        c_text = _read_file_check_secret(repo_root, c_path)
        sent_paths.append(c_path)
        user_parts.append(f"=== CONTEXT: {c_path} ===\n{c_text}\n=== END CONTEXT ===")

    for i_path in order.interfaces:
        i_text = _read_file_check_secret(repo_root, i_path)
        i_view = interface_view(i_path, i_text)
        sent_paths.append(i_path)
        user_parts.append(f"=== INTERFACE: {i_path} ===\n{i_view}\n=== END INTERFACE ===")


def _get_plan_partitions(plan: tuple[Step, ...], part: StepPart) -> tuple[list[str], list[str]]:
    current_part_paths = set(part.paths)
    part_step_num = None
    for s in plan:
        if any(p in current_part_paths for p in s.paths):
            part_step_num = s.number
            break

    earlier_outputs: list[str] = []
    later_outputs: list[str] = []
    for s in plan:
        if part_step_num is not None and s.number < part_step_num:
            earlier_outputs.extend(s.paths)
        elif part_step_num is not None and s.number > part_step_num:
            later_outputs.extend(s.paths)
        elif part_step_num is not None:
            first = min(s.paths.index(p) for p in part.paths if p in s.paths)
            earlier_outputs.extend(s.paths[:first])  # split parts before this one were accepted (WO-1.0-11 B13)
    return earlier_outputs, later_outputs


def _add_earlier_outputs(plan: tuple[Step, ...], part: StepPart, repo_root: Path, sent_paths: list[str], missing_paths: list[str], user_parts: list[str]) -> None:
    earlier_outputs, _ = _get_plan_partitions(plan, part)
    for out_p in earlier_outputs:
        full_p = repo_root / out_p
        if full_p.exists():
            text = _read_file_check_secret(repo_root, out_p)
            sent_paths.append(out_p)
            if out_p.endswith(".py") and not out_p.startswith("tests/"):
                iview = interface_view(out_p, text)
                user_parts.append(f"=== ACCEPTED INTERFACE: {out_p} ===\n{iview}\n=== END ACCEPTED INTERFACE ===")
            else:
                user_parts.append(f"=== ACCEPTED: {out_p} ===\n{text}\n=== END ACCEPTED ===")
        else:
            missing_paths.append(out_p)


def _add_step_block(plan: tuple[Step, ...], part: StepPart, user_parts: list[str]) -> None:
    _, later_outputs = _get_plan_partitions(plan, part)
    total_steps = len(plan)
    label_str = part.label
    curr_paths_str = ", ".join(part.paths)
    later_paths_str = ", ".join(later_outputs) if later_outputs else "none"

    step_block = (
        f"=== THIS STEP ===\n"
        f"Step {label_str} of {total_steps}. Return exactly these files, each complete: {curr_paths_str}. "
        f"Files from earlier steps are shown above; call them as shown and do not return them. "
        f"Later steps will add: {later_paths_str}. "
        f"The tests you return must pass with only the files above and the files you return now.\n"
        f"=== END THIS STEP ==="
    )
    user_parts.append(step_block)


def with_fix_turn(
    request: Request,
    answer_text: str,
    fix_text: str,
    current_files: dict[str, str],
) -> Request:
    """Append assistant answer and user fix turn to existing request."""
    new_turns = list(request.chat.turns)
    new_turns.append(chat.Turn(role="assistant", text=answer_text))

    user_parts = [fix_text]
    for c_path, c_text in current_files.items():
        reasons = secret_reasons(c_path, c_text)
        if reasons:
            raise SecretInRequest(c_path, reasons)
        user_parts.append(f"=== CURRENT: {c_path} ===\n{c_text}\n=== END CURRENT ===")

    user_turn_text = "\n\n".join(user_parts)
    new_turns.append(chat.Turn(role="user", text=user_turn_text))

    new_chat = chat.ChatRequest(
        system=request.chat.system,
        turns=tuple(new_turns),
        max_output_tokens=request.chat.max_output_tokens,
    )

    chars = len(new_chat.system) + sum(len(t.text) for t in new_chat.turns)

    return Request(
        chat=new_chat,
        sent_paths=request.sent_paths,
        missing_paths=request.missing_paths,
        characters=chars,
    )


def final_fix_request(
    order: WorkOrder,
    plan: tuple[Step, ...],
    root: str | Path,
    fix_text: str,
    focus_paths: tuple[str, ...],
) -> Request:
    """Build a new conversation for a final fix."""
    repo_root = Path(root).resolve()

    foundation_text = _read_file_check_secret(repo_root, "docs/process/outsourcing/FOUNDATION.md")
    return_format_text = _read_file_check_secret(repo_root, "docs/process/outsourcing/templates/RETURN_FORMAT.md")
    order_text = _read_file_check_secret(repo_root, order.path)

    sent_paths: list[str] = [order.path]
    missing_paths: list[str] = []
    user_parts: list[str] = [order_text]

    _add_context_and_interfaces(order, repo_root, sent_paths, user_parts)
    _add_final_fix_outputs(order, focus_paths, repo_root, sent_paths, missing_paths, user_parts)

    user_parts.append(fix_text)
    user_parts.append(return_format_text)

    user_text = "\n\n".join(user_parts)
    chat_req = chat.ChatRequest(
        system=foundation_text,
        turns=(chat.Turn(role="user", text=user_text),),
        max_output_tokens=order.max_output_tokens,
    )

    return Request(
        chat=chat_req,
        sent_paths=tuple(sent_paths),
        missing_paths=tuple(missing_paths),
        characters=len(foundation_text) + len(user_text),
    )


def _add_final_fix_outputs(
    order: WorkOrder,
    focus_paths: tuple[str, ...],
    repo_root: Path,
    sent_paths: list[str],
    missing_paths: list[str],
    user_parts: list[str],
) -> None:
    focus_set = set(focus_paths)
    for out_p in order.outputs:
        full_p = repo_root / out_p
        if full_p.exists():
            text = _read_file_check_secret(repo_root, out_p)
            sent_paths.append(out_p)
            if out_p in focus_set:
                user_parts.append(f"=== CURRENT: {out_p} ===\n{text}\n=== END CURRENT ===")
            else:
                if out_p.endswith(".py") and not out_p.startswith("tests/"):
                    iview = interface_view(out_p, text)
                    user_parts.append(f"=== ACCEPTED INTERFACE: {out_p} ===\n{iview}\n=== END ACCEPTED INTERFACE ===")
                else:
                    user_parts.append(f"=== ACCEPTED: {out_p} ===\n{text}\n=== END ACCEPTED ===")
        else:
            missing_paths.append(out_p)


def step_pack(order: WorkOrder, plan: tuple[Step, ...], part: StepPart, root: str | Path) -> str:
    """Return FOUNDATION.md followed by user turn text."""
    req = step_request(order, plan, part, root)
    return f"{req.chat.system}\n\n{req.chat.turns[0].text}"
