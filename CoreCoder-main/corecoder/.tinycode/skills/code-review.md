---
name: code-review
description: "Code review checklist: correctness, security, performance, readability, and test coverage analysis."
tools: [read_file, grep, glob]
---

# Code Review Skill

When the user asks to review code, perform a systematic analysis:

## Review Checklist

### 1. Correctness
- Does the code do what it's supposed to?
- Are there edge cases not handled? (null, empty, overflow, boundary)
- Are error paths handled properly?

### 2. Security
- SQL injection, XSS, command injection risks?
- Secrets or credentials hardcoded?
- Input validation and sanitization?
- Proper authentication/authorization?

### 3. Performance
- Any O(n²) or worse algorithms where O(n) is possible?
- Unnecessary database queries or API calls?
- Memory leaks or unbounded allocations?

### 4. Readability
- Clear naming? Functions do one thing?
- Consistent style with the rest of the codebase?
- Comments where logic is non-obvious?

### 5. Testing
- Are the changes covered by tests?
- Do the tests cover edge cases?
- Are the tests readable and maintainable?

## Output Format
Present findings as a prioritized list:
- 🔴 **Critical**: Must fix before merge
- 🟡 **Warning**: Should fix, potential issues
- 🟢 **Suggestion**: Nice to have improvements
