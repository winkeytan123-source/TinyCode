"""Project-level instruction files (.TINYCODE.md).

Similar to Claude Code's .CLAUDE.md, a .TINYCODE.md file provides
project-specific instructions that the agent MUST follow when working
in that project.  The content is injected into the system prompt.

Search order (first found wins per level):
  1. <cwd>/.TINYCODE.md                          — project-level (highest priority)
  2. <cwd>/.tinycode/.TINYCODE.md                — project-level (in .tinycode dir)
  3. <corecoder>/.tinycode/.TINYCODE.md          — built-in defaults

If both project-level and built-in files exist, both are included
(built-in first, project second) so project rules can override defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


# The built-in .tinycode directory lives alongside this module
_BUILT_IN_DIR = Path(__file__).parent / ".tinycode"


def find_instruction_files(cwd: str | Path | None = None) -> list[Path]:
    """Find all .TINYCODE.md files in priority order.

    Returns a list of absolute paths, ordered from lowest to highest
    priority (built-in first, project last).
    """
    if cwd is None:
        cwd = Path.cwd()
    else:
        cwd = Path(cwd)

    results: list[Path] = []

    # 1. Built-in: corecoder/.tinycode/.TINYCODE.md
    built_in = _BUILT_IN_DIR / ".TINYCODE.md"
    if built_in.is_file():
        results.append(built_in.resolve())

    # 2. Project in .tinycode dir: cwd/.tinycode/.TINYCODE.md
    project_tinycode = cwd / ".tinycode" / ".TINYCODE.md"
    if project_tinycode.is_file():
        results.append(project_tinycode.resolve())

    # 3. Project root: cwd/.TINYCODE.md (or .tinycode.md)
    for name in [".TINYCODE.md", ".tinycode.md"]:
        project_root = cwd / name
        if project_root.is_file():
            results.append(project_root.resolve())
            break

    return results


def load_instruction_content(paths: list[Path]) -> str:
    """Read and concatenate instruction file contents.

    Returns the combined content, or empty string if no files found.
    """
    parts = []
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"[From: {path.name}]\n{content}")
        except (OSError, UnicodeDecodeError):
            continue
    return "\n\n".join(parts)


def build_instruction_section(cwd: str | Path | None = None) -> str:
    """Build the full instruction section for the system prompt.

    Returns a formatted string with all found .TINYCODE.md content,
    or an empty string if no instruction files exist.
    """
    paths = find_instruction_files(cwd)
    if not paths:
        return ""

    content = load_instruction_content(paths)
    if not content:
        return ""

    return (
        "# Project Instructions (.TINYCODE.md)\n"
        "The following project-specific instructions MUST be followed. "
        "They take precedence over general guidelines when there is a conflict.\n\n"
        f"{content}\n"
    )
