# AGENTS.md — Global AI Assistant & Token Conservation Protocol for Gametech Unli Fiber

## 🎯 Primary Directive: The Aider-Style Sniper Workflow

All AI assistants (Antigravity, Gemini, Aider, Cursor, Continue) operating in this repository **MUST** follow these ironclad, surgical, token-conserving rules to prevent credit depletion, eliminate context bloat, and maintain codebase hygiene across all team members and devices:

---

### ⚡ THE ZERO-SCAN DEBUGGING LAW (Save Maximum Credits)

0. **THE FRESHNESS LAW (Automatic Git Pull First)**:
   * **MANDATORY FIRST STEP**: Before editing or diagnosing code on ANY task, the AI **MUST** run `git pull origin main`. Team members switch devices and work in parallel; coding on a stale branch causes merge conflicts, lost work, and duplicate debugging.

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

4. **USE THE BLUEPRINTS (Never Scan Models or Routes)**:
   * Need database model fields, foreign keys, URL routes, background tasks, or Mikrotik contracts?
   * **NEVER** read the full `gametech_architecture_map.txt` (83KB / 2,174 lines / ~20K+ tokens). Use `grep_search` to find the specific model, route, or task name within it.
   * **NEVER** scan `billing/models.py` (2,000+ lines), `views/`, or multiple apps to figure out relationships.

5. **USE THE FILING & LOCATION DIRECTORY (`gametech_filing_index.md`)**:
   * Need to know where a view, template, modal, API endpoint, or service belongs?
   * Inspect `gametech_filing_index.md`. It maps every feature to its exact files and gives standardized step-by-step recipes for adding or fixing modals, APIs, signals, and background tasks.

6. **CHECK THE ERROR RUNBOOK FIRST (`gametech_error_runbook.md`)**:
   * Before investigating any reported bug, UI defect, or freeze, **ALWAYS** check `gametech_error_runbook.md`.
   * If the symptom matches a known pattern (e.g. grey screen, white Select2 dropdown, stuck telemetry dots `...`, Mikrotik timeout), jump directly to the diagnosed target files and execute the verified 1-step fix.

7. **SURGICAL IN-PLACE EDITS & THE PONYTAIL LADDER**:
   * **ALWAYS** use targeted replacement tools (`replace_file_content` / diffs) to edit ONLY the 2–15 lines with the bug.
   * **NEVER** rewrite an entire file or re-emit hundreds of unchanged lines.
   * **THE PONYTAIL MANDATE (Write Less, Delete More)**: Every time code is added, edited, or debugged, apply the ladder before writing:
     1. **YAGNI**: Reject speculative abstractions, unrequested boilerplate, and unnecessary wrappers.
     2. **Reuse**: Check for existing project helpers/patterns before writing new logic.
     3. **Stdlib/Native First**: Use Python, Django, or browser built-ins before reaching for custom helpers or new libraries.
     4. **Shortest Working Diff**: One line before ten. Deletion over addition. Fix the root cause once at the source rather than patching multiple callers.

8. **THE 3-STEP ESCALATION PROTOCOL (Hard Ceiling on Debugging Depth)**:
   * **Step 1**: `grep_search` for the exact symbol, function, class, or error string.
   * **Step 2**: Read 50–80 line slice of the found file.
   * **Step 3**: If still unclear → **STOP**. Ask: _"Can you paste the browser console error, the exact URL, or the specific file/function name?"_
   * **FORBIDDEN**: Continuing past 3 steps by opening additional files or running broad scans.

9. **AUTOMATIC DEPLOYMENT & PRODUCTION SYNC (Zero Deployment Lag)**:
   * Once changes are made and verified locally:
     1. Stage modified files (`git add <files>`).
     2. Commit with conventional commit message (`feat(...)`, `fix(...)`).
     3. Push to `origin main`.
     4. Pull on production droplet: `ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"`.
     5. If Python code, templates, or settings were modified, restart the Gunicorn container: `ssh root@143.198.207.144 "docker restart gametech-billing-system_web_1"`.

10. **CONTINUOUS RUNBOOK ENRICHMENT**:
    * Whenever an AI solves a novel bug or architecture quirk not yet documented, it **MUST** append a new `ERR-XXX` entry to `gametech_error_runbook.md` before finishing the task.

11. **URL-TO-FILE FAST MAP (Kill the "where is this page?" guesswork)**:
    * When the user pastes a URL (e.g. `http://143.198.207.144/portal/dashboard/`), **resolve it by checking `gametech_filing_index.md` URL column FIRST**.
    * **FORBIDDEN**: Grepping through `urls.py`, scanning template directories, or opening `views.py` to find which page a URL maps to.
    * The filing index already maps: URL → View → Template → Models in a single row.

12. **DOCKER-FIRST ERROR CAPTURE (Hard-Mandated for ALL 500 Errors)**:
    * For **ANY** Server Error (500), the AI **MUST** run this command first, before opening any code:
      ```
      ssh root@143.198.207.144 "docker logs --tail 50 gametech-billing-system_web_1 2>&1 | tail -30"
      ```
    * The traceback gives the exact file and line number. Only after reading the traceback may the AI open the pinpointed file.
    * **FORBIDDEN**: Guessing the cause by reading view/model files before checking logs.

13. **TEMPLATE INCLUDE-CHAIN VERIFICATION (Stop Orphan Partial Bugs)**:
    * When creating or editing a template partial (e.g. `_modal_ticket.html`), **ALWAYS verify it is actually included** in a parent template.
    * Use: `grep_search` for the partial filename within the parent template folder.
    * If it's not included anywhere → add the `{% include %}` tag in the parent orchestrator. Otherwise the partial is dead code and the feature will be invisible.

14. **REDIS/CACHE VERIFY BEFORE REWRITING LOGIC**:
    * If a feature uses Redis cache (e.g. active sessions, telemetry, online status) and data is not appearing:
      * **FIRST** verify Redis has the expected keys:
        ```
        ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli KEYS 'pattern*'"
        ```
      * **DO NOT** rewrite Python view/signal logic until you confirm whether the cache key exists, is empty, or is missing.

15. **THE NO-REPEAT-FAILURE WALL (Max 2 Attempts Per Approach)**:
    * If the AI attempts a fix and it **DOESN'T WORK**, it **MUST NOT** retry the same approach.
    * Instead: (a) check `docker logs` for the NEW error, (b) ask the user for browser console output, or (c) pivot to an entirely different approach.
    * **Maximum 2 attempts** on the same bug using the same strategy before escalating to the user with a clear diagnosis of what was tried and what failed.

16. **STATIC FILE COLLECTSTATIC GUARD (CSS/JS Production Sync)**:
    * After modifying ANY file inside `static/` (CSS, JS, images), the deployment step **MUST** include:
      ```
      ssh root@143.198.207.144 "docker exec gametech-billing-system_web_1 python manage.py collectstatic --noinput"
      ```
    * **FORBIDDEN**: Pushing static file changes without running `collectstatic`. Changes will appear locally but be invisible in production.

17. **API RESPONSE SHAPE VERIFICATION (Frontend-Backend Contract)**:
    * When debugging "data not showing" or "API returns empty/wrong data":
      1. **FIRST** hit the API endpoint directly via `curl` or browser to see the actual JSON shape.
      2. **THEN** compare with what the frontend JS `fetch()` handler expects (e.g. `data.uplinks` vs `data.router_uplink_status`).
      * **DO NOT** rewrite backend view logic before confirming the response contract matches the frontend consumer.

18. **BATCH COMMITS FOR MULTI-FILE CHANGES (Minimize Deploy Cycles)**:
    * When a task involves 3+ file edits:
      1. Make ALL edits first.
      2. Single `git add` + `git commit` + `git push`.
      3. Single production `git pull` + single container restart.
    * **FORBIDDEN**: Running `docker restart` more than once per task unless debugging requires a mid-task verification.

19. **TIME-BOUNDED CONTAINER LOGS (Read Fresh, Not Stale)**:
    * When checking production logs for a 500 error, prefer `--since` over `--tail` to avoid stale noise from hours ago:
      ```
      ssh root@143.198.207.144 "docker logs --since 2m gametech-billing-system_web_1 2>&1 | tail -40"
      ```
    * Use `--tail 50` only when the error timing is unknown. Use `--since 2m` when you just reproduced the error.

20. **JS EVENT DELEGATION FOR DYNAMIC ELEMENTS (Stop Dead Handlers)**:
    * When adding JS event handlers for elements inside dynamically-loaded content (Select2 dropdowns, AJAX-populated lists, modal content):
      * **ALWAYS** use event delegation: `$(document).on('change', '#selector', handler)` instead of `$('#selector').on('change', handler)`.
      * Verify the handler fires by adding a temporary `console.log()` check before writing complex logic.
    * Elements rendered after `$(document).ready()` will NOT have directly-bound handlers — delegation is mandatory.

21. **THE CACHE SYNC MANDATE (Prevent Zombie Data)**:
    * Whenever an AI edits a view that changes a user's state (Login, Logout, Disable Account, Suspend, Delete, Payment status change):
      * **MUST** verify if there is a corresponding Redis cache key that needs to be explicitly invalidated (`cache.delete()` or removed from a dict-style cache).
      * **NEVER** assume Django's default session handler will clear custom Redis metrics. Django sessions and custom cache keys are independent systems.
    * Use the **Redis Cache Key Registry** below to identify affected keys instantly.

22. **GIT ARCHEOLOGY BAN (Never Explore History to Understand Code)**:
    * **FORBIDDEN**: Running `git log`, `git reflog`, `git diff`, `git show`, or `git blame` to understand how a feature works or to guess a bug's origin.
    * **ALLOWED**: `git pull origin main` (mandatory first step), `git add`, `git commit`, `git push` (deployment), and `git status` (pre-commit check).
    * **EXCEPTION**: Only use `git log -S` if the user explicitly asks to track down a regression from a known commit or date range.
    * Rely entirely on the current state of the file as pinpointed by `gametech_filing_index.md` and `gametech_architecture_map.txt`.

23. **REDIS CACHE KEY REGISTRY (Zero-Grep Cache Debugging)**:
    * When debugging cache/stale-data issues, look up the key here first. **NEVER** grep the codebase for `cache.set` or `cache.get`.

    | Cache Key Pattern | Purpose | TTL | Set By | Invalidated By |
    |---|---|---|---|---|
    | `active_portal_customers` | Dict of `{customer_id: timestamp}` for logged-in portal users | 600s (10min) | `customer_portal/views.py`, `billing/middleware.py`, `billing/views/auth.py` | `customer_portal/views.py` (portal_logout), `billing/middleware.py` (cleanup) |
    | `seen_customer_{id}` | Last-activity timestamp for a specific portal customer | 300s (5min) | `customer_portal/views.py`, `billing/views/auth.py` | Expires naturally; removed from `active_portal_customers` dict when missing |
    | `seen_user_{id}` | Last-activity timestamp for a staff/admin user | 86400s (30 days) | `billing/middleware.py` | Expires naturally |
    | `live_monitoring_data` | Cached Mikrotik live monitoring API response | 30s | `billing/views/api/dashboard.py`, `billing/tasks.py` | Overwritten on each poll cycle |
    | `dashboard_stats_{date}` | Cached dashboard statistics for a specific date | 300s (5min) | `billing/views/dashboard.py` | Expires naturally |

24. **THE 400-LINE CIRCUIT BREAKER LAW (Just-In-Time Operation Cleanup)**:
    * **THE TRIGGER**: Whenever an AI touches, edits, or diagnoses a bug in ANY file that exceeds **400 lines** (template, script, or view):
      * **FORBIDDEN**: Appending new code or speculative patches to an already bloated file.
      * **MANDATORY**: Perform an opportunistic "Operation Cleanup" on that specific file:
        1. Slices the file into focused partials/modules under **250 lines** each using the Orchestrator Pattern (`{% include %}` tags or sub-modules).
        2. Applies Ponytail to cut dead code, redundant intervals, and duplicate library calls.
        3. Verifies tag parity (`div_diff: 0, script_diff: 0`).
    * **TOKEN ECONOMICS (One-Time Investment, Permanent Dividend)**:
      * **NEVER** run broad scans to split files across the entire repo at once (prevents credit depletion).
      * Clean oversized files **ONLY as they are naturally touched by ongoing user tasks**.
      * The modularization cost is paid **exactly once**. Every future AI task on that feature permanently saves **70–80% of tokens** by reading small, focused partials instead of monoliths.

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

### 💡 3. The Prompt Translation Mandate (Burden on the AI)

The human team members will write **vague, plain-English prompts** (e.g., *"The online staff counter is stuck"*, *"I can't click the add-on button"*, *"The router is offline"*). 

**The AI MUST NOT expect the user to reference documentation, files, or endpoints.**

Instead, the AI MUST silently perform this internal translation step BEFORE taking any action:
1. **Receive Human Prompt**: *"The staff counter is stuck"*
2. **Consult Indexes**: The AI internally looks up "staff counter" in `GEMINI.md` (Triage Router) and `gametech_filing_index.md` (UI→API Map).
3. **Map to Target**: The AI discovers this maps to `/api/online-staff/` and `billing/views/auth.py`.
4. **Execute Sniper Fix**: The AI jumps directly to the target file.

If the AI asks the user *"Which file is that in?"* or *"Can you point me to the endpoint?"*, **the AI has failed**. The indexes already contain all the answers.
