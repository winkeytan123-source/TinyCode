"""Skill tool - dynamically load a skill's full instructions.

When the LLM determines it needs a skill's guidance, it calls this tool
to load the full content. The loaded content is then injected into the
conversation context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Tool

if TYPE_CHECKING:
    from ..skill import SkillManager


class SkillTool(Tool):
    name = "load_skill"
    description = (
        "Load a skill's full instructions by name. "
        "Use this when you need detailed guidance from an available skill. "
        "Call list_skills first to see what's available, or check the "
        "system prompt for the list of available skills."
    )
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "The name of the skill to load",
            },
        },
        "required": ["skill_name"],
    }

    # Set by Agent.__init__ after construction
    _skill_manager: SkillManager | None = None

    def execute(self, skill_name: str) -> str:
        if self._skill_manager is None:
            return "Error: skill system not initialized"

        skill = self._skill_manager.load_skill(skill_name)
        if skill is None:
            available = [s.name for s in self._skill_manager.list_skills()]
            if available:
                return (
                    f"Error: skill '{skill_name}' not found. "
                    f"Available skills: {', '.join(available)}"
                )
            return "Error: no skills available"

        return (
            f"# Skill: {skill.name}\n\n"
            f"{skill.content}"
        )


class ListSkillsTool(Tool):
    name = "list_skills"
    description = (
        "List all available skills with their descriptions. "
        "Use this to discover what skills are available before loading one."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    _skill_manager: SkillManager | None = None

    def execute(self, **kwargs) -> str:
        if self._skill_manager is None:
            return "Error: skill system not initialized"

        skills = self._skill_manager.list_skills()
        if not skills:
            return "No skills available."

        lines = ["Available Skills:\n"]
        for skill in skills:
            status = "✓ loaded" if skill.is_loaded() else "○ not loaded"
            tools_str = f" (uses: {', '.join(skill.tools)})" if skill.tools else ""
            lines.append(f"  - **{skill.name}** [{status}]{tools_str}")
            lines.append(f"    {skill.description}\n")

        return "\n".join(lines)
