"""Tests for the Skill system: SkillManager, Skill parsing, SkillTool, ListSkillsTool."""

import textwrap
from pathlib import Path

import pytest

from corecoder.skill import Skill, SkillManager, _parse_skill_file, _read_body
from corecoder.tools import get_tool, ALL_TOOLS
from corecoder.tools.skill import SkillTool, ListSkillsTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def skills_dir(tmp_path):
    """Create a temporary skills directory with sample skill files."""
    skills = tmp_path / "skills"
    skills.mkdir()

    (skills / "refactor.md").write_text(textwrap.dedent("""\
        ---
        name: refactor
        description: "Refactoring workflow"
        tools: [read_file, edit_file]
        ---
        # Refactoring Steps
        1. Analyze
        2. Refactor
        3. Verify
    """), encoding="utf-8")

    (skills / "debug.md").write_text(textwrap.dedent("""\
        ---
        name: debug
        description: "Debugging workflow"
        ---
        # Debug Steps
        1. Reproduce
        2. Isolate
        3. Fix
    """), encoding="utf-8")

    (skills / "review.md").write_text(textwrap.dedent("""\
        ---
        description: "Code review checklist"
        ---
        # Review Checklist
    """), encoding="utf-8")

    return skills


@pytest.fixture
def skill_manager(skills_dir):
    """Create a SkillManager pointing to the temp skills directory."""
    return SkillManager(skills_dir=skills_dir)


# ---------------------------------------------------------------------------
# Skill data model
# ---------------------------------------------------------------------------

class TestSkill:
    def test_defaults(self):
        s = Skill(name="test", description="desc", path="/tmp/fake.md")
        assert s.tools == []
        assert s.content == ""
        assert s.is_loaded() is False

    def test_load(self, skills_dir):
        path = skills_dir / "refactor.md"
        s = Skill(name="refactor", description="desc", path=str(path))
        content = s.load()
        assert "Refactoring Steps" in content
        assert s.is_loaded() is True

    def test_load_is_idempotent(self, skills_dir):
        path = skills_dir / "refactor.md"
        s = Skill(name="refactor", description="desc", path=str(path))
        first = s.load()
        second = s.load()
        assert first == second


# ---------------------------------------------------------------------------
# SkillManager - discovery
# ---------------------------------------------------------------------------

class TestSkillManagerDiscovery:
    def test_discovers_all_skills(self, skill_manager):
        assert len(skill_manager.list_skills()) == 3

    def test_skill_names(self, skill_manager):
        names = {s.name for s in skill_manager.list_skills()}
        assert names == {"refactor", "debug", "review"}

    def test_get_existing(self, skill_manager):
        s = skill_manager.get("refactor")
        assert s is not None
        assert s.description == "Refactoring workflow"

    def test_get_nonexistent(self, skill_manager):
        assert skill_manager.get("nonexistent") is None

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert SkillManager(skills_dir=d).list_skills() == []

    def test_nonexistent_dir(self, tmp_path):
        assert SkillManager(skills_dir=tmp_path / "nope").list_skills() == []


# ---------------------------------------------------------------------------
# SkillManager - parsing
# ---------------------------------------------------------------------------

class TestSkillManagerParsing:
    def test_parses_tools(self, skill_manager):
        assert skill_manager.get("refactor").tools == ["read_file", "edit_file"]

    def test_no_tools_field(self, skill_manager):
        assert skill_manager.get("debug").tools == []

    def test_name_fallback_to_filename(self, skill_manager):
        assert skill_manager.get("review").name == "review"


# ---------------------------------------------------------------------------
# SkillManager - lazy loading
# ---------------------------------------------------------------------------

class TestSkillLazyLoading:
    def test_not_loaded_after_discovery(self, skill_manager):
        s = skill_manager.get("refactor")
        assert s.is_loaded() is False
        assert s.content == ""

    def test_load_skill_loads_content(self, skill_manager):
        skill_manager.load_skill("refactor")
        s = skill_manager.get("refactor")
        assert s.is_loaded() is True
        assert "Refactoring Steps" in s.content

    def test_load_nonexistent_returns_none(self, skill_manager):
        assert skill_manager.load_skill("nonexistent") is None


# ---------------------------------------------------------------------------
# SkillManager - summary for prompt
# ---------------------------------------------------------------------------

class TestSkillSummary:
    def test_contains_all_skills(self, skill_manager):
        summary = skill_manager.summary_for_prompt()
        assert "refactor" in summary
        assert "debug" in summary
        assert "review" in summary

    def test_contains_descriptions(self, skill_manager):
        summary = skill_manager.summary_for_prompt()
        assert "Refactoring workflow" in summary

    def test_contains_load_instruction(self, skill_manager):
        assert "load_skill" in skill_manager.summary_for_prompt()

    def test_empty_when_no_skills(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert SkillManager(skills_dir=d).summary_for_prompt() == ""


# ---------------------------------------------------------------------------
# _parse_skill_file
# ---------------------------------------------------------------------------

class TestParseSkillFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "t.md"
        f.write_text('---\nname: myskill\ndescription: "A test"\ntools: [bash]\n---\nBody')
        s = _parse_skill_file(f)
        assert s.name == "myskill"
        assert s.description == "A test"
        assert s.tools == ["bash"]

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "t.md"
        f.write_text("# No frontmatter")
        assert _parse_skill_file(f) is None

    def test_unclosed_frontmatter(self, tmp_path):
        f = tmp_path / "t.md"
        f.write_text('---\nname: x\ndescription: "missing')
        assert _parse_skill_file(f) is None

    def test_no_description(self, tmp_path):
        f = tmp_path / "t.md"
        f.write_text('---\nname: x\n---\nBody')
        assert _parse_skill_file(f) is None

    def test_nonexistent_file(self, tmp_path):
        assert _parse_skill_file(tmp_path / "ghost.md") is None

    def test_single_quoted_values(self, tmp_path):
        f = tmp_path / "t.md"
        f.write_text("---\nname: x\ndescription: 'quoted'\n---\nBody")
        assert _parse_skill_file(f).description == "quoted"


# ---------------------------------------------------------------------------
# _read_body
# ---------------------------------------------------------------------------

class TestReadBody:
    def test_after_frontmatter(self, tmp_path):
        f = tmp_path / "t.md"
        f.write_text("---\nname: x\n---\nHello World")
        assert "Hello World" in _read_body(str(f))

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "t.md"
        f.write_text("No frontmatter")
        assert _read_body(str(f)) == "No frontmatter"

    def test_nonexistent_file(self):
        assert _read_body("/nonexistent/path.md") == ""


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

class TestToolRegistration:
    def test_skill_tools_in_all_tools(self):
        names = {t.name for t in ALL_TOOLS}
        assert "load_skill" in names
        assert "list_skills" in names

    def test_get_load_skill(self):
        assert isinstance(get_tool("load_skill"), SkillTool)

    def test_get_list_skills(self):
        assert isinstance(get_tool("list_skills"), ListSkillsTool)

    def test_valid_schemas(self):
        for name in ["load_skill", "list_skills"]:
            s = get_tool(name).schema()
            assert s["type"] == "function"
            assert "name" in s["function"]


# ---------------------------------------------------------------------------
# SkillTool (load_skill)
# ---------------------------------------------------------------------------

class TestSkillTool:
    def _make(self, sm) -> SkillTool:
        t = SkillTool()
        t._skill_manager = sm
        return t

    def test_load_existing(self, skill_manager):
        result = self._make(skill_manager).execute(skill_name="refactor")
        assert "Refactoring Steps" in result
        assert "# Skill: refactor" in result

    def test_load_nonexistent(self, skill_manager):
        result = self._make(skill_manager).execute(skill_name="nope")
        assert "Error" in result
        assert "not found" in result

    def test_shows_available_on_error(self, skill_manager):
        result = self._make(skill_manager).execute(skill_name="nope")
        assert "refactor" in result

    def test_uninitialized(self):
        result = SkillTool().execute(skill_name="any")
        assert "not initialized" in result


# ---------------------------------------------------------------------------
# ListSkillsTool (list_skills)
# ---------------------------------------------------------------------------

class TestListSkillsTool:
    def _make(self, sm) -> ListSkillsTool:
        t = ListSkillsTool()
        t._skill_manager = sm
        return t

    def test_lists_all(self, skill_manager):
        result = self._make(skill_manager).execute()
        assert "refactor" in result
        assert "debug" in result
        assert "review" in result

    def test_shows_not_loaded(self, skill_manager):
        assert "not loaded" in self._make(skill_manager).execute()

    def test_shows_loaded(self, skill_manager):
        skill_manager.load_skill("refactor")
        assert "loaded" in self._make(skill_manager).execute()

    def test_empty(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        sm = SkillManager(skills_dir=d)
        assert "No skills" in self._make(sm).execute()

    def test_uninitialized(self):
        assert "not initialized" in ListSkillsTool().execute()


# ---------------------------------------------------------------------------
# Integration: Agent with SkillManager
# ---------------------------------------------------------------------------

class TestAgentSkillIntegration:
    def test_agent_has_skill_manager(self):
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert agent.skill_manager is not None

    def test_system_prompt_includes_skills(self):
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert "load_skill" in agent._system

    def test_custom_skills_dir(self, skills_dir):
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"), skills_dir=skills_dir)
        names = {s.name for s in agent.skill_manager.list_skills()}
        assert names == {"refactor", "debug", "review"}

    def test_wires_skill_tool(self):
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert get_tool("load_skill")._skill_manager is agent.skill_manager

    def test_wires_list_skills_tool(self):
        from corecoder.agent import Agent
        from corecoder.llm import LLM
        agent = Agent(llm=LLM(model="test", api_key="fake"))
        assert get_tool("list_skills")._skill_manager is agent.skill_manager
