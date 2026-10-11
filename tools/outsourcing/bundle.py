"""Return format bundle parser and truncation checker.

CAPABILITIES:
  CAP-OUTSOURCING-005: parse RETURN_FORMAT bundle text and check truncation signs [tests: test_FR_1_0_01_mc02_missing_end_marker_fails_import, test_FR_1_0_01_mc03_truncation_sign_fails_import, test_FR_1_0_01_mc04_questions_block_stops_import_with_exit_4, test_bundle.py]
INPUTS AND OUTPUTS: Bundle, BundleError, TruncatedBundle, parse_bundle.
CONTRACTS: RETURN_FORMAT.md specification.
INVARIANTS:
  - Markers win over fenced code blocks inside file content.
  - Any truncation sign raises TruncatedBundle.
NOT IN SCOPE:
  - File system writes.
CHANGE LOG:
  2026-10-10 WO-1.0-01 created.
  2026-10-10 WP-1.0 FR-1.0-01 review fix (Claude): path errors raise BundleError; manifest paths normalised;
    QUESTIONS split per numbered question.
  2026-10-11 WP-1.0 FR-1.0-01 BLK-1.0-07 (Claude, owner option 1): one code fence wrapping the whole reply is
    removed before parsing (RETURN_FORMAT.md); any other text outside the blocks is still refused.
  2026-10-11 WP-1.0 FR-1.0-01 BLK-1.0-08 (Claude, owner option 1): a fence wrapped tightly around one block is
    removed first, then the outer fence; unpaired fences stay and are refused.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from tools.outsourcing.paths import normalise

__all__ = ["BundleError", "TruncatedBundle", "Bundle", "parse_bundle"]

TRUNCATION_PHRASES = [
    "rest of the file",
    "remains unchanged",
    "same as before",
    "unchanged code",
    "existing code here",
    "omitted for brevity",
]


class BundleError(Exception):
    """Raised when a bundle is malformed or violates format rules."""


class TruncatedBundle(BundleError):
    """Raised when truncation signs are detected in a bundle."""


@dataclass(frozen=True)
class Bundle:
    manifest: tuple[tuple[str, str, str], ...]
    files: tuple[tuple[str, str], ...]
    dod: tuple[tuple[str, str, str], ...]
    questions: tuple[str, ...]


def _check_truncation(line: str) -> None:
    stripped = line.strip()
    if stripped in ("...", "…", "# ...", "# …", "// ...", "// …"):
        raise TruncatedBundle(f"Truncation sign detected: {line.strip()!r}")
    lower = line.lower()
    for phrase in TRUNCATION_PHRASES:
        if phrase in lower:
            raise TruncatedBundle(f"Truncation phrase detected ({phrase!r}): {line.strip()!r}")


def _parse_table_rows(lines: list[str]) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|") or not s.endswith("|"):
            continue
        cells = [c.strip() for c in s[1:-1].split("|")]
        if len(cells) < 3:
            continue
        if cells[0].lower() in ("path", "item") or cells[0].startswith("-"):
            continue
        rows.append((cells[0], cells[1], cells[2]))
    return tuple(rows)


def _manifest_path(cell: str) -> str:
    """Normalise a manifest path the same way as a FILE marker's path."""
    try:
        return normalise(cell)
    except ValueError as exc:
        raise BundleError(f"Invalid MANIFEST path {cell!r}: {exc}") from exc


def _split_questions(lines: list[str]) -> tuple[str, ...]:
    """One entry per numbered question ("1. ..."), continuation lines joined to it; unnumbered text is one entry."""
    questions: list[list[str]] = []
    for line in lines:
        numbered = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if numbered or not questions:
            questions.append([(numbered.group(1) if numbered else line).strip()])
        else:
            questions[-1].append(line.strip())
    texts = ("\n".join(part for part in q if part).strip() for q in questions)
    return tuple(text for text in texts if text)


OUTER_FENCE_RE = re.compile(r"(`{3,})[A-Za-z0-9_.+-]*")


def _strip_outer_fence(lines: list[str]) -> list[str]:
    """Remove one code fence that wraps the whole reply (RETURN_FORMAT.md); leave anything else to the parser."""
    filled = [i for i, line in enumerate(lines) if line.strip()]
    if len(filled) < 2:
        return lines
    first, last = filled[0], filled[-1]
    opening = OUTER_FENCE_RE.fullmatch(lines[first].strip())
    if opening is None or lines[last].strip() != opening.group(1):
        return lines
    return lines[first + 1:last]


OPEN_MARKER_RE = re.compile(r"=== (?:MANIFEST|DOD|QUESTIONS|FILE: .*) ===")
END_MARKER_RE = re.compile(r"=== END (?:MANIFEST|DOD|QUESTIONS|FILE) ===")


def _strip_block_fences(lines: list[str]) -> list[str]:
    """Remove each code fence wrapped tightly around one block (RETURN_FORMAT.md); unpaired fences stay."""
    drop: set[int] = set()
    in_block, opening_at, fence = False, None, None
    for i, line in enumerate(lines):
        s = line.strip()
        if not in_block:
            if OPEN_MARKER_RE.fullmatch(s):
                in_block = True
                match = OUTER_FENCE_RE.fullmatch(lines[i - 1].strip()) if i > 0 and i - 1 not in drop else None
                opening_at, fence = (i - 1, match.group(1)) if match else (None, None)
            continue
        if END_MARKER_RE.fullmatch(s):
            in_block = False
            if fence is not None and i + 1 < len(lines) and lines[i + 1].strip() == fence:
                drop.update((opening_at, i + 1))
            opening_at, fence = None, None
    return [line for i, line in enumerate(lines) if i not in drop]


def parse_bundle(text: str) -> Bundle:
    if text.startswith("\ufeff"):
        text = text[1:]

    all_lines = _strip_outer_fence(_strip_block_fences(text.splitlines()))
    for line in all_lines:
        _check_truncation(line)

    manifest_lines: list[str] = []
    dod_lines: list[str] = []
    question_lines: list[str] = []
    file_blocks: list[tuple[str, list[str]]] = []

    current_block: str | None = None
    current_file_path: str | None = None
    file_content_lines: list[str] = []

    for line in all_lines:
        s = line.strip()

        # Marker line checks
        if s == "=== MANIFEST ===":
            if current_block is not None:
                raise BundleError(f"Nested block marker === MANIFEST === inside {current_block}")
            current_block = "MANIFEST"
            continue
        elif s == "=== END MANIFEST ===":
            if current_block != "MANIFEST":
                raise BundleError("=== END MANIFEST === marker without open MANIFEST block")
            current_block = None
            continue
        elif s.startswith("=== FILE: ") and s.endswith(" ==="):
            if current_block is not None:
                raise BundleError(f"Nested block marker {s} inside {current_block}")
            path_part = s[10:-4].strip()
            if "\\" in path_part:
                raise BundleError(f"Backslash in file path: {path_part!r}")
            try:
                norm_p = normalise(path_part)
            except ValueError as exc:
                raise BundleError(f"Invalid FILE path {path_part!r}: {exc}") from exc
            current_block = "FILE"
            current_file_path = norm_p
            file_content_lines = []
            continue
        elif s == "=== END FILE ===":
            if current_block != "FILE":
                raise BundleError("=== END FILE === marker without open FILE block")
            file_blocks.append((current_file_path, file_content_lines))
            current_block = None
            current_file_path = None
            continue
        elif s == "=== DOD ===":
            if current_block is not None:
                raise BundleError(f"Nested block marker === DOD === inside {current_block}")
            current_block = "DOD"
            continue
        elif s == "=== END DOD ===":
            if current_block != "DOD":
                raise BundleError("=== END DOD === marker without open DOD block")
            current_block = None
            continue
        elif s == "=== QUESTIONS ===":
            if current_block is not None:
                raise BundleError(f"Nested block marker === QUESTIONS === inside {current_block}")
            current_block = "QUESTIONS"
            continue
        elif s == "=== END QUESTIONS ===":
            if current_block != "QUESTIONS":
                raise BundleError("=== END QUESTIONS === marker without open QUESTIONS block")
            current_block = None
            continue

        # Content lines
        if current_block == "MANIFEST":
            manifest_lines.append(line)
        elif current_block == "DOD":
            dod_lines.append(line)
        elif current_block == "QUESTIONS":
            question_lines.append(line)
        elif current_block == "FILE":
            file_content_lines.append(line)
        else:
            if s:
                raise BundleError(f"Non-blank text outside block: {line!r}")

    if current_block is not None:
        raise BundleError(f"Unclosed block: {current_block}")

    manifest_rows = _parse_table_rows(manifest_lines)
    dod_rows = _parse_table_rows(dod_lines)

    parsed_files: list[tuple[str, str]] = []
    seen_paths: set[str] = set()

    for path, raw_lines in file_blocks:
        if path in seen_paths:
            raise BundleError(f"Duplicate file path in bundle: {path!r}")
        seen_paths.add(path)

        # Remove single code fence wrapper if present
        if len(raw_lines) >= 2 and raw_lines[0].strip().startswith("```") and raw_lines[-1].strip().startswith("```"):
            raw_lines = raw_lines[1:-1]

        content_str = "\n".join(raw_lines)
        if not content_str.strip():
            raise BundleError(f"Empty file content for {path!r}")

        if not content_str.endswith("\n"):
            content_str += "\n"

        parsed_files.append((path, content_str))

    # Questions parsing
    questions = _split_questions(question_lines)

    # Manifest vs File cross checks (when no questions)
    if not questions:
        manifest_paths = {_manifest_path(r[0]) for r in manifest_rows}
        file_paths = set(seen_paths)

        missing_in_manifest = file_paths - manifest_paths
        if missing_in_manifest:
            raise BundleError(f"FILE paths missing from MANIFEST: {sorted(missing_in_manifest)}")

        missing_in_files = manifest_paths - file_paths
        if missing_in_files:
            raise BundleError(f"MANIFEST paths missing from FILE blocks: {sorted(missing_in_files)}")

    return Bundle(
        manifest=manifest_rows,
        files=tuple(parsed_files),
        dod=dod_rows,
        questions=tuple(questions),
    )
