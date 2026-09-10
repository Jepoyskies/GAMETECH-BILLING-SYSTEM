# AGENTS.md — Global AI Assistant & Token Conservation Protocol for Gametech Unli Fiber

## 🎯 Primary Directive: The Aider-Style Sniper Workflow

All AI assistants (Antigravity, Gemini, Aider, Cursor, Continue) operating in this repository **MUST** follow these ironclad, surgical, token-conserving rules to prevent credit depletion, eliminate context bloat, and maintain codebase hygiene across all team members and devices:

---

### ⚡ THE ZERO-SCAN DEBUGGING LAW (Save Maximum Credits)

1. **NO UNNECESSARY SCANNING (Hard Ban on Exploratory Crawling)**:
   * **FORBIDDEN**: Running directory scans (`list_dir`), file searches (`find_by_name`), or opening unrelated files "just to explore".
   * **FORBIDDEN**: Opening Python views/models when the user reports a frontend/template issue, and vice versa.
   * **STRICT 1-FILE SCOPE**: Touch and inspect ONLY the file(s) explicitly named in the prompt or pinpointed by an error traceback.

2. **LOG-FIRST DEBUGGING (Never Guess by Reading Code)**:
   * When diagnosing an error (500, crash, freeze, or broken button):
     * **DO NOT** guess by reading multiple files across the repository.
     * **DO** inspect the exact error traceback first via `docker logs --tail 30 gametech-billing-system_web_1` or browser console error.
     * The traceback pinpoints the EXACT file and line number in 1 step — eliminating 95% of exploratory token waste.

3. **STRICT 50–80 LINE READING LIMIT (Never Read Full Files)**:
   * **FORBIDDEN**: Reading 150+ lines of code in a single view. Ingesting full 1,000-line files burns 5,000–10,000 tokens on EVERY subsequent turn!
   * **MANDATORY**: Use `grep_search` to find the exact function, symbol, or tag.
   * Read **ONLY** the localized slice (e.g. `StartLine: 40, EndLine: 90`, max 50–80 lines).

4. **USE THE BLUEPRINT (Never Scan Models or Routes)**:
   * Need database model fields, foreign keys, URL routes, background tasks, or Mikrotik contracts?
   * Inspect `gametech_architecture_map.txt` (~2,082 lines / ~8.5K tokens).
   * **NEVER** scan `billing/models.py` (2,000+ lines), `views/`, or multiple apps to figure out relationships.

5. **CHECK THE ERROR RUNBOOK FIRST (`gametech_error_runbook.md`)**:
   * Before investigating any reported bug, UI defect, or freeze, **ALWAYS** check `gametech_error_runbook.md`.
   * If the symptom matches a known pattern (e.g. grey screen, white Select2 dropdown, stuck telemetry dots `...`, Mikrotik timeout), jump directly to the diagnosed target files and execute the verified 1-step fix.

6. **SURGICAL IN-PLACE EDITS ONLY**:
   * **ALWAYS** use targeted replacement tools (`replace_file_content` / diffs) to edit ONLY the 2–15 lines with the bug.
   * **NEVER** rewrite an entire file or re-emit hundreds of unchanged lines.

7. **THE 3-TOOL TURN LIMIT**:
   * If you cannot locate an issue after 2–3 pinpoint searches, **STOP IMMEDIATELY**. Do not crawl the repository. Ask the user for the specific file, template, or URL.

---

### 🧼 2. Codebase Cleanliness & Architecture Standards

1. **Zero Root Clutter**:
   * **NEVER** create loose test/debug scripts in the root directory (e.g. `test_x.py`, `debug.py`).
   * For ad-hoc debugging, run Python one-liners (`python -c "..."`) or place temporary files into `archived_scripts/` and delete them immediately after use.
2. **HTML Template Balance & Nesting Guard**:
   * When modifying any template partial (especially modals or cards), **ALWAYS** verify `<div>` balance (`<div\b` count == `</div>` count).
   * **NEVER** nest Bootstrap modals inside other modals or parent containers with `overflow: hidden` or `display: none` (prevents grey-screen backdrop lockouts).
3. **The Orchestrator Pattern (Strict Component Separation)**:
   * Keep parent templates (`dashboard.html`, `live_monitoring.html`, `view_customer.html`) as lightweight orchestrators composed of `{% include %}` tags.
   * Add new UI features as isolated partials (prefixed with an underscore, e.g. `_modal_x.html`, `_scripts.html`) in the page's component folder.
   * Template files must not exceed 400 lines. Python view modules must not exceed 400 lines.
4. **Financial & Mikrotik Integrity**:
   * Always wrap payment, rebate, or rollback mutations in `transaction.atomic()` with `select_for_update()`.
   * Never bypass Django signals (`billing/signals.py`) when updating customer status or expiration dates, as signals keep the physical Mikrotik routers in sync.
5. **Brand Design System Consistency**:
   * Use defined design tokens (`gt-cl-card`, `gt-modal-content`, `gt-btn`, `--gt-*` variables) and test both Light and Dark mode contrast. Never hardcode inline hex colors.

---

### 💡 3. Fast-Prompting Guide for Team Members

To get instantaneous fixes from any AI with minimal token burn, team members are encouraged to format prompts like this:
```text
Target: billing/templates/billing/live_monitoring/_hero.html
Issue: Change the Search Customer button text to 'Find User'
```
```text
Target: billing/views/customers.py (around def pay_customer_view)
Issue: Ensure discount is deducted before applying transaction fee
```
```text
Question: What models are associated with Mikrotik sync?
Context: Check gametech_architecture_map.txt
```
