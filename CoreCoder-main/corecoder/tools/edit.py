"""Search-and-replace file editing (Claude Code's key innovation).

The core idea: instead of sending whole-file rewrites or line-number patches,
the LLM specifies an *exact* substring to find and its replacement. The
substring must appear exactly once in the file, which eliminates ambiguity
and makes edits safe and reviewable.
"""

import difflib
from pathlib import Path

from .base import Tool

# track files changed this session for /diff
_changed_files: set[str] = set()


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Edit a file by replacing an exact string match. "
        "old_string must appear exactly once in the file for safety. "
        "Include enough surrounding context to ensure uniqueness."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to find (must be unique in file)",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }

    def execute(self, file_path: str, old_string: str, new_string: str) -> str:
        try:
            p = Path(file_path).expanduser().resolve()
            if not p.exists():
                return f"Error: {file_path} not found"

            content = p.read_text()
            occurrences = content.count(old_string)

            if occurrences == 0:
                preview = content[:500] + ("..." if len(content) > 500 else "")
                return (
                    f"Error: old_string not found in {file_path}.\n"
                    f"File starts with:\n{preview}"
                )
            if occurrences > 1:
                return (
                    f"Error: old_string appears {occurrences} times in {file_path}. "
                    f"Include more surrounding lines to make it unique."
                )
            # 只替换第一次出现，保证唯一性
            new_content = content.replace(old_string, new_string, 1)
            # 写入到文件（全量覆盖写入）
            p.write_text(new_content)
            _changed_files.add(str(p))

            # generate a unified diff so the user/LLM can see exactly what changed
            diff = _unified_diff(content, new_content, str(p))
            return f"Edited {file_path}\n{diff}"
        except Exception as e:
            return f"Error: {e}"


def _unified_diff(old: str, new: str, filename: str, context: int = 3) -> str:
    """Generate a compact unified diff between old and new file content."""
    # keepends=True保留换行符("AAA\nBBB\nCCC"->["AAA\n", "BBB\n", "CCC"])
    # difflib.unified_diff 需要按行比较，而且要求每行自带换行符，这样才能正确生成 diff 格式
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    # a/和b/前缀：Git的约定，a/表示原始版本，b/表示新版本
    # n=context：控制显示多少行上下文（默认3行），帮助定位变更位置
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}", tofile=f"b/{filename}",
        n=context,
    )
    result = "".join(diff)
    # truncate enormous diffs
    if len(result) > 3000:
        result = result[:2500] + "\n... (diff truncated)\n"
    return result
