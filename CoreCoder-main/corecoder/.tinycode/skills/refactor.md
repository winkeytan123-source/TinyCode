---
name: refactor
description: "Refactoring workflow: analyze structure, identify code smells, apply safe transformations, verify with tests."
tools: [read_file, edit_file, glob, grep, bash]
---

# Refactoring Workflow

When the user asks to refactor code, follow this structured process:

## 1. Analyze
- Read the target file(s) completely
- Identify code smells: long functions, duplication, poor naming, tight coupling
- Check for existing tests

## 2. Plan
- List each change as a discrete step
- Prioritize: naming → extraction → structure → patterns
- Keep each step small and independently verifiable

## 3. Execute
- Make one change at a time
- After each change, run relevant tests to confirm no regressions
- Use `edit_file` for targeted changes, never full rewrites

## 4. Verify
- Run the full test suite
- Check that the code still follows project conventions
- Summarize all changes made

## Principles
- **Boy Scout Rule**: leave the code cleaner than you found it
- **Small steps**: each edit should be atomic and reversible
- **Test before and after**: never refactor without a safety net
