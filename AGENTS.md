# AGENTS.md — Global AI Assistant & Token Conservation Protocol for Gametech Unli Fiber

## 🎯 Primary Directive: The Aider-Style Sniper Workflow

All AI assistants (Antigravity, Gemini, Aider, Cursor, Continue) operating in this repository **MUST** follow these ironclad, surgical, token-conserving rules to prevent credit depletion, eliminate context bloat, and maintain codebase hygiene across all team members and devices:

---

### 🛡️ 1. Absolute Token Preservation Rules (Save User Credits)

1. **Targeted Scoping (The 1-File Principle)**:
   * Focus **strictly** on the specific file(s) mentioned in the prompt.
   * Do **NOT** explore unrelated directories, views, or models "just in case". If the user asks about a button in `_hero.html`, do not touch or read `views.py`.
2. **Never Read Monolithic Files**:
   * **FORBIDDEN**: Reading 300+ line files without slice constraints.
   * **MANDATORY**: Use `grep_search` to pinpoint the exact line number of the symbol, class, or tag.
   * Read **only** the required slice (e.g. `StartLine: 40, EndLine: 90`, max 50–80 lines).
3. **Leverage the Architecture Blueprint First**:
   * For database models, fields, foreign keys, URL routes, background Celery tasks, and hardware contracts, inspect `gametech_architecture_map.txt` (~2,082 lines / ~8.5K tokens).
   * **NEVER** run recursive directory scans or build 1-million-token context dumps.
4. **Surgical In-Place Replacements Only**:
   * **ALWAYS** use targeted line replacement tools (`replace_file_content` / targeted diffs).
   * **NEVER** rewrite an entire file or re-emit hundreds of unchanged lines.
5. **Zero Verbose Code Dumps in Chat**:
   * Do **not** regurgitate full files or large code blocks in chat responses. Provide a concise explanation of what was changed, line references, and a clickable file link.
6. **The 3-Tool Turn Limit**:
   * Stop exploratory "wandering". If you cannot locate an issue after 2–3 pinpoint searches, stop and ask the user for the exact file or URL instead of recursively crawling the repo.

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
