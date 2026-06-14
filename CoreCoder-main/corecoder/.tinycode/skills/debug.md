---
name: debug
description: "Debugging workflow: reproduce issue, form hypothesis, isolate root cause, verify fix, prevent regression."
tools: [read_file, edit_file, bash, grep, glob]
---

# Debugging Workflow

When the user reports a bug or error, follow this process:

## 1. Understand the Problem
- Ask for reproduction steps if not provided
- Read the error message carefully — it usually tells you exactly what's wrong
- Identify: what should happen vs. what actually happens

## 2. Reproduce
- Run the exact command or steps the user describes
- Confirm you see the same error
- If it's intermittent, try to find a reliable reproduction

## 3. Isolate
- Use binary search: comment out half the code, see if the error persists
- Add print/log statements to narrow down the execution path
- Check recent changes (git log/diff) for clues

## 4. Hypothesize & Fix
- Form a hypothesis about the root cause
- Make the minimal change to fix it
- Explain why the bug existed and why the fix works

## 5. Verify
- Run the original reproduction steps — confirm the bug is gone
- Run the full test suite to check for regressions
- Consider: could this same bug exist elsewhere?

## Common Pitfalls
- Don't fix symptoms, fix causes
- Don't make the fix bigger than necessary
- Always check: is this a code bug, a config issue, or a data problem?
