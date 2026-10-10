"""Paste pack builder assembling context and templates into a single file.

CAPABILITIES:
  CAP-OUTSOURCING-008: assemble work order context into a single paste pack [tests: test_FR_1_0_01_mc06_pack_refuses_env_file, test_FR_1_0_01_mc06_pack_refuses_private_key_content, test_FR_1_0_01_pack_of_clean_order_holds_every_part_in_order, test_pack.py]
INPUTS AND OUTPUTS: Pack, SecretRefused, PackTooLarge, build_pack.
CONTRACTS: RETURN_FORMAT.md and WORK_ORDER.md specifications.
INVARIANTS:
  - Refuses any file with secret reasons.
  - Raises PackTooLarge when total text exceeds 600,000 characters.
NOT IN SCOPE:
  - Sending text over API channels.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
  2026-10-10 WP-1.0 FR-1.0-01 review fix (Claude): read failures raise OSError, never SecretRefused.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from tools.outsourcing.secrets import secret_reasons
from tools.outsourcing.workorder import WorkOrder

__all__ = ["SecretRefused", "PackTooLarge", "Pack", "build_pack"]

MAX_PACK_CHARACTERS = 600_000


class SecretRefused(Exception):
    """Raised when a file in the pack contains secret patterns."""


class PackTooLarge(Exception):
    """Raised when the assembled pack exceeds 600,000 characters."""


@dataclass(frozen=True)
class Pack:
    text: str
    characters: int
    estimated_tokens: int


def _read_and_check_secret(path: str | Path, root: Path) -> tuple[str, str]:
    rel_path = str(path)
    abs_path = root / rel_path
    content = abs_path.read_text(encoding="utf-8")  # an OSError propagates: an unreadable file is not a secret

    reasons = secret_reasons(rel_path, content)
    if reasons:
        raise SecretRefused(f"Secret detected in {rel_path}: {'; '.join(reasons)}")

    return rel_path, content


def build_pack(order: WorkOrder, repo_root: str | Path) -> Pack:
    root = Path(repo_root).resolve()

    # Locate FOUNDATION and RETURN_FORMAT
    foundation_path = root / "docs/process/outsourcing/FOUNDATION.md"
    if not foundation_path.is_file():
        raise FileNotFoundError(f"FOUNDATION.md not found at {foundation_path}")

    return_fmt_path = root / "docs/process/outsourcing/RETURN_FORMAT.md"
    if not return_fmt_path.is_file():
        return_fmt_path = root / "docs/process/outsourcing/templates/RETURN_FORMAT.md"
    if not return_fmt_path.is_file():
        raise FileNotFoundError(f"RETURN_FORMAT.md not found at {return_fmt_path}")

    _, foundation_text = _read_and_check_secret("docs/process/outsourcing/FOUNDATION.md", root)
    _, return_fmt_text = _read_and_check_secret(return_fmt_path.relative_to(root), root)

    # Read order text
    order_file_path = root / order.path
    if order_file_path.is_file():
        _, order_text = _read_and_check_secret(order.path, root)
    else:
        order_text = order.body

    parts: list[str] = [foundation_text.rstrip("\n"), order_text.rstrip("\n")]

    context_files = list(order.context) + list(order.interfaces) + list(order.read_only_tests)

    for c_path in context_files:
        rel_p, c_text = _read_and_check_secret(c_path, root)
        wrapped = f"=== CONTEXT: {rel_p} ===\n{c_text.rstrip('\n')}\n=== END CONTEXT ==="
        parts.append(wrapped)

    parts.append(return_fmt_text.rstrip("\n"))

    full_text = "\n\n".join(parts) + "\n"
    total_chars = len(full_text)

    if total_chars > MAX_PACK_CHARACTERS:
        raise PackTooLarge(f"Pack size {total_chars} exceeds maximum allowed ({MAX_PACK_CHARACTERS})")

    estimated_tokens = math.ceil(total_chars / 3.5)

    return Pack(
        text=full_text,
        characters=total_chars,
        estimated_tokens=estimated_tokens,
    )
