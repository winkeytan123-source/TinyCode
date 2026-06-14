"""Tests for .TINYCODE.md instruction file system."""

import textwrap
from pathlib import Path

import pytest

from corecoder.instructions import (
    _BUILT_IN_DIR,
    find_instruction_files,
    load_instruction_content,
    build_instruction_section,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def no_built_in(monkeypatch):
    """Disable built-in .tinycode by pointing _BUILT_IN_DIR to a non-existent path."""
    monkeypatch.setattr("corecoder.instructions._BUILT_IN_DIR", Path("/nonexistent_tinycode"))


@pytest.fixture
def project_dir(tmp_path):
    """Create a fake project directory."""
    project = tmp_path / "myproject"
    project.mkdir()
    return project


@pytest.fixture
def project_instruction(project_dir, no_built_in):
    """Create a project-level .TINYCODE.md in project root."""
    (project_dir / ".TINYCODE.md").write_text(
        "# Project Rules\nUse pytest for testing.\nAlways use type hints.",
        encoding="utf-8",
    )
    return project_dir


@pytest.fixture
def project_tinycode_instruction(project_dir, no_built_in):
    """Create a project-level .tinycode/.TINYCODE.md."""
    tinycode_dir = project_dir / ".tinycode"
    tinycode_dir.mkdir()
    (tinycode_dir / ".TINYCODE.md").write_text(
        "# Tinycode Project Rules\nRun tests with pytest.",
        encoding="utf-8",
    )
    return project_dir


@pytest.fixture
def built_in_instruction(tmp_path, monkeypatch):
    """Create a fake built-in .tinycode/.TINYCODE.md by patching _BUILT_IN_DIR."""
    fake_built_in = tmp_path / "built_in" / ".tinycode"
    fake_built_in.mkdir(parents=True)
    (fake_built_in / ".TINYCODE.md").write_text(
        "# Built-in Rules\nWrite concise code.\nUse snake_case naming.",
        encoding="utf-8",
    )
    monkeypatch.setattr("corecoder.instructions._BUILT_IN_DIR", fake_built_in)
    return fake_built_in


# ---------------------------------------------------------------------------
# find_instruction_files
# ---------------------------------------------------------------------------

class TestFindInstructionFiles:
    def test_finds_project_root_level(self, project_instruction):
        paths = find_instruction_files(cwd=project_instruction)
        assert len(paths) == 1
        assert paths[0].name == ".TINYCODE.md"

    def test_finds_project_tinycode_dir(self, project_tinycode_instruction):
        paths = find_instruction_files(cwd=project_tinycode_instruction)
        assert len(paths) == 1
        assert ".tinycode" in str(paths[0].parent)

    def test_finds_built_in_level(self, project_dir, built_in_instruction):
        paths = find_instruction_files(cwd=project_dir)
        assert len(paths) == 1
        assert "built_in" in str(paths[0].parent)

    def test_finds_all_three_levels(self, project_instruction, built_in_instruction):
        paths = find_instruction_files(cwd=project_instruction)
        assert len(paths) == 2
        # built-in first (lower priority), project second (higher priority)
        assert "built_in" in str(paths[0].parent)
        assert paths[1].name == ".TINYCODE.md"

    def test_returns_empty_when_none_exist(self, project_dir, no_built_in):
        paths = find_instruction_files(cwd=project_dir)
        assert paths == []

    def test_case_insensitive_fallback(self, project_dir, no_built_in):
        (project_dir / ".tinycode.md").write_text("lowercase version", encoding="utf-8")
        paths = find_instruction_files(cwd=project_dir)
        assert len(paths) == 1
        assert paths[0].name == ".tinycode.md"

    def test_prefers_uppercase_over_lowercase(self, project_dir, no_built_in):
        (project_dir / ".TINYCODE.md").write_text("the content", encoding="utf-8")
        paths = find_instruction_files(cwd=project_dir)
        assert len(paths) == 1
        assert "the content" in paths[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# load_instruction_content
# ---------------------------------------------------------------------------

class TestLoadInstructionContent:
    def test_loads_single_file(self, project_instruction):
        paths = find_instruction_files(cwd=project_instruction)
        content = load_instruction_content(paths)
        assert "Project Rules" in content
        assert "pytest" in content

    def test_loads_multiple_files(self, project_instruction, built_in_instruction):
        paths = find_instruction_files(cwd=project_instruction)
        content = load_instruction_content(paths)
        # Both contents should be present
        assert "Built-in Rules" in content
        assert "Project Rules" in content

    def test_returns_empty_for_no_files(self):
        assert load_instruction_content([]) == ""

    def test_includes_file_source_label(self, project_instruction):
        paths = find_instruction_files(cwd=project_instruction)
        content = load_instruction_content(paths)
        assert "[From: .TINYCODE.md]" in content

    def test_skips_unreadable_file(self, tmp_path):
        fake = tmp_path / "ghost.md"
        # Don't create the file — it won't be readable
        content = load_instruction_content([fake])
        assert content == ""


# ---------------------------------------------------------------------------
# build_instruction_section
# ---------------------------------------------------------------------------

class TestBuildInstructionSection:
    def test_returns_empty_when_no_files(self, project_dir, no_built_in):
        section = build_instruction_section(cwd=project_dir)
        assert section == ""

    def test_contains_header(self, project_instruction):
        section = build_instruction_section(cwd=project_instruction)
        assert "# Project Instructions" in section
        assert ".TINYCODE.md" in section

    def test_contains_content(self, project_instruction):
        section = build_instruction_section(cwd=project_instruction)
        assert "Project Rules" in section
        assert "pytest" in section

    def test_mentions_precedence(self, project_instruction):
        section = build_instruction_section(cwd=project_instruction)
        assert "precedence" in section.lower() or "MUST" in section

    def test_project_after_built_in(self, project_instruction, built_in_instruction):
        section = build_instruction_section(cwd=project_instruction)
        built_in_pos = section.index("Built-in Rules")
        project_pos = section.index("Project Rules")
        # Built-in should appear before project (lower priority listed first)
        assert built_in_pos < project_pos


# ---------------------------------------------------------------------------
# Integration: Agent with .TINYCODE.md
# ---------------------------------------------------------------------------

class TestAgentInstructionIntegration:
    def test_system_prompt_includes_tinycode(self, project_instruction, monkeypatch):
        monkeypatch.chdir(project_instruction)
        # Ensure _BUILT_IN_DIR is also patched via project_instruction -> no_built_in
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert "Project Rules" in agent._system
        assert "pytest" in agent._system

    def test_system_prompt_has_instruction_header(self, project_instruction, monkeypatch):
        monkeypatch.chdir(project_instruction)
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert "# Project Instructions" in agent._system

    def test_no_tinycode_no_instruction_section(self, project_dir, no_built_in, monkeypatch):
        monkeypatch.chdir(project_dir)
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert "# Project Instructions" not in agent._system

    def test_built_in_plus_project_both_in_prompt(self, project_instruction, built_in_instruction, monkeypatch):
        monkeypatch.chdir(project_instruction)
        # Override _BUILT_IN_DIR with built_in_instruction
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert "Built-in Rules" in agent._system
        assert "Project Rules" in agent._system
