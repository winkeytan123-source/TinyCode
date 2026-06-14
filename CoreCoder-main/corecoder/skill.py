"""Skill system - declarative task templates loaded on demand.

Each Skill is a Markdown file with YAML frontmatter:

    ---
    name: refactor
    description: "Refactoring workflow with best practices"
    tools: [read_file, edit_file, glob]
    ---
    # Detailed instructions...

At startup, only the metadata (name + description) is parsed and injected
into the system prompt.  When the LLM decides to use a skill, the full
content is loaded via the SkillTool.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    """A single skill definition parsed from a .md file."""
    name: str
    description: str
    path: str                          # absolute path to the .md file
    tools: list[str] = field(default_factory=list)  # tools this skill may use
    content: str = ""                  # full markdown body (lazy-loaded)
    _loaded: bool = False              # whether content has been loaded

    def load(self) -> str:
        """Load the full content from disk. Returns the markdown body."""
        if not self._loaded:
            self.content = _read_body(self.path)
            self._loaded = True
        return self.content

    def is_loaded(self) -> bool:
        return self._loaded


class SkillManager:
    """Manages discovery, parsing, and loading of skills."""

    def __init__(self, skills_dir: str | Path | None = None):
        # 默认从 corecoder/.tinycode/skills/ 加载
        if skills_dir is None:
            skills_dir = Path(__file__).parent / ".tinycode" / "skills"
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._discover()

    def _discover(self):
        """Scan skills directory and parse metadata from all .md files."""
        if not self.skills_dir.is_dir():
            return
        for md_file in sorted(self.skills_dir.glob("*.md")):
            skill = _parse_skill_file(md_file)
            if skill:
                self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        """Return all discovered skills."""
        return list(self._skills.values())

    def summary_for_prompt(self) -> str:
        """Generate a compact summary for the system prompt.

        Only includes name + description (no full content).
        """
        if not self._skills:
            return ""
        lines = [
            "Available Skills. Only load a skill when the user's request "
            "CLEARLY matches the trigger condition below. For general "
            "conversations, greetings, or simple questions, do NOT load "
            "any skill.",
            "",
        ]
        for skill in self._skills.values():
            lines.append(f"  - **{skill.name}**: {skill.description}")
        return "\n".join(lines)

    def load_skill(self, name: str) -> Optional[Skill]:
        """Load a skill's full content by name. Returns None if not found."""
        skill = self.get(name)
        if skill:
            skill.load()
        return skill


def _parse_skill_file(path: Path) -> Optional[Skill]:
    """Parse a .md file and extract YAML frontmatter metadata.

    Returns a Skill with metadata but content not yet loaded.
    Returns None if the file doesn't have valid frontmatter.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Must start with YAML frontmatter: --- ... ---
    if not text.startswith("---"):
        return None

    # Find closing ---
    second_fence = text.find("---", 3)
    if second_fence == -1:
        return None

    frontmatter_text = text[3:second_fence].strip()

    # Parse YAML frontmatter
    name = None
    description = ""
    tools = []

    for line in frontmatter_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "name":
                name = value
            elif key == "description":
                description = value
            elif key == "tools":
                # Parse list format: [tool1, tool2] or comma-separated
                value = value.strip("[]")
                tools = [t.strip().strip('"').strip("'") for t in value.split(",") if t.strip()]

    if not name:
        # Fallback: use filename without extension as name
        name = path.stem

    if not description:
        return None

    return Skill(
        name=name,
        description=description,
        path=str(path.resolve()),
        tools=tools,
    )


def _read_body(path: str) -> str:
    """Read the markdown body (everything after the frontmatter)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""

    if not text.startswith("---"):
        return text

    second_fence = text.find("---", 3)
    if second_fence == -1:
        return text

    return text[second_fence + 3:].strip()
