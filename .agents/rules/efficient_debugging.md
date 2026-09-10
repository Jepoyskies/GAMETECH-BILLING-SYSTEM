---
name: Zero-Scan Efficient Debugging & Credit Preservation Protocol
description: Enforces log-first, zero-wandering debugging workflows to prevent credit depletion across all AI coding agents.
---

# Zero-Scan Efficient Debugging & Credit Preservation Protocol

When an issue, bug, or 500 error is reported in this repository, **all AI assistants MUST follow this log-first, zero-wandering debugging protocol** to preserve user credits and resolve issues with sniper accuracy.

---

## 🚫 What is Strictly Banned (Token Wasters)

1. **Broad Directory Scans**: Never call directory listing tools (`list_dir`) across the workspace trying to "figure out where files are".
2. **Speculative File Reading**: Never open files that were not mentioned in an error traceback or explicitly targeted by the user. If an error is in `views/dashboard.py`, do NOT open `models.py`, `urls.py`, or templates "just to be sure".
3. **Full File Dumps**: Never read files exceeding 100 lines without line constraints (`StartLine`/`EndLine`). Reading a 1,000-line file injects ~8,000 tokens into history, which gets billed on EVERY subsequent turn.
4. **Wandering Across 5+ Files**: If an issue is not located within 2 targeted searches, **STOP**. Prompt the user for the exact URL or template rather than crawling the codebase.

---

## 🎯 The 4-Step Sniper Debugging Workflow

### Step 1: Traceback First (Zero Code Scans)
* Always inspect the server log first:
  ```bash
  ssh -o StrictHostKeyChecking=no root@143.198.207.144 "docker logs --tail 40 gametech-billing-system_web_1"
  ```
  or run a direct Python test:
  ```bash
  python -c "..."
  ```
* The Python traceback tells you the **exact file** and the **exact line number**.
* This eliminates 95% of exploratory reading.

### Step 2: Targeted 50-Line Slice
* Use `grep_search` to pinpoint the line number if not already known from the log.
* Call `view_file` specifying `StartLine: (line - 20)` and `EndLine: (line + 30)`.
* Maximum slice size: 50–80 lines.

### Step 3: Consult `gametech_architecture_map.txt` for System Models
* If you need to know foreign keys, model fields, background tasks, or URL routes, read `gametech_architecture_map.txt` (~2,082 lines / ~8.5K tokens).
* Never scan monolithic model files like `billing/models.py`.

### Step 4: Surgical In-Place Fix
* Use `replace_file_content` targeting only the lines that need changes.
* Verify syntax immediately.
* Do not leave temporary test files in the root folder.
