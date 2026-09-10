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

## 🎯 The 5-Step Sniper Debugging Workflow

### Step 1: Check `gametech_error_runbook.md` (Zero Token Waste)
* If the user reports a known symptom (e.g. grey screen on modal, unstyled white Select2 box, stuck telemetry dots `...`, Mikrotik ping failure), check `gametech_error_runbook.md` FIRST.
* It directly maps the symptom to the exact 1–2 files and verified fix.

### Step 2: Traceback First (If Not in Runbook)
* Always inspect the server log first:
  ```bash
  ssh -o StrictHostKeyChecking=no root@143.198.207.144 "docker logs --tail 40 gametech-billing-system_web_1"
  ```
* The traceback pinpoints the **exact file** and the **exact line number**, eliminating 95% of exploratory token waste.

### Step 3: Targeted 50-Line Slice
* Use `grep_search` to pinpoint the line number if not already known from the log.
* Call `view_file` specifying `StartLine: (line - 20)` and `EndLine: (line + 30)`. Max slice size: 50–80 lines.

### Step 4: Consult `gametech_architecture_map.txt` for System Models
* If you need foreign keys, model fields, background tasks, or URL routes, read `gametech_architecture_map.txt`.
* Never scan monolithic files like `billing/models.py`.

### Step 5: Surgical In-Place Fix
* Use `replace_file_content` targeting only the lines that need changes.
* Verify syntax immediately.
* Do not leave temporary test files in the root folder.
