---
name: Aider-Style Sniper Workflow & Token Preservation Rules
description: Enforces strict surgical, low-token pair-programming behavior in Antigravity so team members do not burn through usage credits.
---

# Aider-Style Sniper Workflow & Token Preservation Guidelines

To prevent rapid token depletion, IDE lag, and context bloat across all team members and devices, **all AI assistants operating in this repository MUST act with surgical precision like Aider.**

---

## 1. The Golden Rules of Context & Token Preservation

### Rule 1: Never Read Whole Files Unnecessarily
* **DO NOT** execute `view_file` on large files (e.g., 500–2,500+ lines) without line range constraints.
* **ALWAYS** use `grep_search` to find the exact function, class, or HTML element first.
* **ONLY** read the specific slice (e.g. `StartLine: 45, EndLine: 95`) needed to understand and perform the task.

### Rule 2: Rely on the Architecture Map for Big-Picture Context
* For understanding data models, database foreign keys, API endpoints, background Celery tasks, and hardware bridges, refer to `gametech_architecture_map.txt` (~2,000 lines / ~8.5K tokens).
* **DO NOT** run repo-wide file tree scans, directory walks, or mass-file dumps (`gametech_context.txt` is deprecated and ignored).

### Rule 3: Single-File Scoping (The `/add` Principle)
* Treat every user prompt like an Aider request: focus strictly on the **1 or 2 target files** relevant to the user's issue.
* Do not inspect unrelated directories, apps, or background scripts unless an explicit error trace points directly to them.

### Rule 4: Surgical In-Place Edits (Aider Diff Style)
* **ALWAYS** use `replace_file_content` or `multi_replace_file_content` targeting only the specific lines being changed.
* **NEVER** rewrite an entire file or output thousands of unchanged lines in responses.

### Rule 5: Immediate Verification & Clean Git Hygiene
* After editing, verify syntax or run a pinpoint test command (e.g. `python -c "..."` or checking error traces).
* Do not leave untracked temporary or scratch files in the root directory.

---

## 2. Fast Reference for Team Members

When prompting Antigravity, team members are encouraged to use **Aider-style prompts**:
```text
Target: billing/views/dashboard.py
Task: Fix the rebate calculator so it deducts tax before applying percentage.
```
This guarantees the fastest response time, zero credit waste, and clean surgical commits.
