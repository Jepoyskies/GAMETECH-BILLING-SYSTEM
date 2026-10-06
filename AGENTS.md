# AGENTS.md — Global AI Assistant & Token Conservation Protocol for Gametech Unli Fiber

> **BEFORE ANY WORK**: read `SESSION_STARTUP.md` for 30-second orientation, then `docs/WORKING_RULES.md` in full and follow it completely, including Rule 0 (Logic Freeze) and Rule 1 (Scope Lock). Then read `docs/SPEC.md` for the business requirements, `docs/BUILD_LOG.md` (tail) for what has been built so far, and `docs/FEATURE_INVENTORY.md` before touching any page's UI or actions. These files are the single source of truth for this project across all AI tools (Antigravity, OpenCode, or any other). Do not duplicate their content here; always read the live files.

> **NEW DOCUMENTATION** (added 2026-09-30):
> - `SESSION_STARTUP.md` — 30-second AI session orientation checklist
> - `PAGE_FREEZE_REGISTRY.md` — Single source of truth for frozen pages
> - `DECISION_LOG.md` — Architectural decisions (don't re-litigate)
> - `COMMON_TASKS.md` — Copy-paste recipes for common tasks
> - `gametech_error_runbook.md` — Now includes ERR-080 (DB Backup fix)

---

## 🌐 Project Overview

* **Project**: Gametech Unli Fiber — Comprehensive ISP Billing, Subscriber Management, and Field Operations Platform (Cagayan de Oro).
* **Tech Stack**:
  * **Backend**: Django 6.1 (Python 3.10), PostgreSQL 15, Redis 7 (caching & broker), Celery + Celery Beat (background tasks/cron).
  * **Frontend**: Vanilla HTML5/CSS, Bootstrap 5, custom Gametech dark/light design system tokens, jQuery, Chart.js.
  * **Infrastructure**: Docker & Docker Compose V2 on DigitalOcean Droplet (Ubuntu), Windows PowerShell local dev host.
  * **Networking**: Direct Socket RouterOS API connections to live physical MikroTik routers (PPPoE / Queues / Uplinks).
* **Main Django Applications**:
  * `billing`: Subscriber accounts, subscription plans, payment transactions, rebates, invoices, agent portal, commissions/incentives, accounting reports.
  * `network_manager`: MikroTik router pool, live telemetry monitoring, PPPoE secret provisioning, bandwidth profiles, automatic sync/reconciliation.
  * `customer_portal`: Subscriber self-service dashboard (account balance, payment instructions, invoices, support tickets).
  * `dispatch`: Technician dispatch operations, installation pipelines, field job ticketing, outage and maintenance tracking.
* **How to Run Tests**:
  * **DO NOT run the test suite inside the `gametech-web` production container.** The droplet is 1 vCPU / 1.9 GB and already hosts Postgres, Redis, Celery and Celery Beat. Building a test database in that container is enough to destabilise it, leaving `gametech-web` down and the site offline (see ERR-082). This instruction previously told AI tools to do exactly that.
  * **Run tests on a local dev machine, or in a dedicated throwaway container** that is not serving production.
  * **Cheap production sanity check only** (safe, does not build a test DB):
    ```bash
    ssh root@143.198.207.144 "docker exec gametech-web python manage.py check"
    ssh root@143.198.207.144 "docker exec gametech-web python manage.py migrate --check"
    ```
  * **Verify a single view renders** (cheap, read-only) using the RequestFactory pattern in Rule 29b.
  * **Local AST Python Syntax Validation** (Zero dependencies on Windows host):
    ```powershell
    python -m py_compile path/to/file.py
    ```

---

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
     * **DO** inspect the exact error traceback first via `docker logs --tail 30 gametech-web` or browser console error.
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
     5. If Python code, templates, or settings were modified, restart the Gunicorn container: `ssh root@143.198.207.144 "docker restart gametech-web"`.

10. **CONTINUOUS RUNBOOK ENRICHMENT**:
    * Whenever an AI solves a novel bug or architecture quirk not yet documented, it **MUST** append a new `ERR-XXX` entry to `gametech_error_runbook.md` before finishing the task.

11. **URL-TO-FILE FAST MAP (Kill the "where is this page?" guesswork)**:
    * When the user pastes a URL (e.g. `http://143.198.207.144/portal/dashboard/`), **resolve it by checking `gametech_filing_index.md` URL column FIRST**.
    * **FORBIDDEN**: Grepping through `urls.py`, scanning template directories, or opening `views.py` to find which page a URL maps to.
    * The filing index already maps: URL → View → Template → Models in a single row.

12. **DOCKER-FIRST ERROR CAPTURE (Hard-Mandated for ALL 500 Errors)**:
    * For **ANY** Server Error (500), the AI **MUST** run this command first, before opening any code:
      ```
      ssh root@143.198.207.144 "docker logs --tail 50 gametech-web 2>&1 | tail -30"
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
        ssh root@143.198.207.144 "docker exec gametech-redis redis-cli KEYS 'pattern*'"
        ```
      * **DO NOT** rewrite Python view/signal logic until you confirm whether the cache key exists, is empty, or is missing.

15. **THE NO-REPEAT-FAILURE WALL (Max 2 Attempts Per Approach)**:
    * If the AI attempts a fix and it **DOESN'T WORK**, it **MUST NOT** retry the same approach.
    * Instead: (a) check `docker logs` for the NEW error, (b) ask the user for browser console output, or (c) pivot to an entirely different approach.
    * **Maximum 2 attempts** on the same bug using the same strategy before escalating to the user with a clear diagnosis of what was tried and what failed.

16. **STATIC FILE COLLECTSTATIC GUARD (CSS/JS Production Sync)**:
    * After modifying ANY file inside `static/` (CSS, JS, images), the deployment step **MUST** include:
      ```
      ssh root@143.198.207.144 "docker exec gametech-web python manage.py collectstatic --noinput"
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
      ssh root@143.198.207.144 "docker logs --since 2m gametech-web 2>&1 | tail -40"
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

22b. **THE DASHBOARD FREEZE LAW (Baseline Is Untouchable)**:
    * **THE PRINCIPLE**: The Dashboard is the finished, hand-authored design of this product and is the **visual baseline every other page must be made to match**. It is NOT a refactor target. It belongs to another contributor.
    * **FORBIDDEN**: Editing, "cleaning up", re-tokening, re-fonting, or restyling ANY file in `billing/templates/billing/dashboard/` or `billing/templates/billing/dashboard.html`.
    * **FORBIDDEN**: Swapping its fonts, hex values, spacing, radii, or the sidebar/topbar chrome it relies on — even for an "obvious improvement" or to remove a hardcoded colour.
    * **MECHANICAL GUARD**: `base.html` wraps the page-chrome stylesheets in `{% block gt_theme %}`, and `dashboard.html` empties that block. Therefore `static/css/gt/components.css`, `surfaces.css` and `legacy.css` are NOT loaded on the Dashboard. Keep it that way: any new shared stylesheet that carries page chrome belongs inside `{% block gt_theme %}`, never outside it.
    * **ALLOWED**: Reading the Dashboard to extract its design values (gold `#F9B233`/`#fbae1a`, navy `#0f172a`→`#1e3a8a`, indigo card `rgba(53,51,205,.2)`, radii 24/28/12px, Montserrat-style display numerals) and reproducing them on OTHER pages.
    * **VERIFY BEFORE COMMITTING**: `git diff --stat -- billing/templates/billing/dashboard/` must be EMPTY for any UI task. If it is not, revert it before pushing.

23. **REDIS CACHE KEY REGISTRY (Zero-Grep Cache Debugging)**:
    * When debugging cache/stale-data issues, look up the key here first. **NEVER** grep the codebase for `cache.set` or `cache.get`.

    | Cache Key Pattern | Purpose | TTL | Set By | Invalidated By |
    |---|---|---|---|---|
    | `active_portal_customers` | Dict of `{customer_id: timestamp}` for logged-in portal users | 600s (10min) | `customer_portal/views.py`, `billing/middleware.py`, `billing/views/auth.py` | `customer_portal/views.py` (portal_logout), `billing/middleware.py` (cleanup) |
    | `seen_customer_{id}` | Last-activity timestamp for a specific portal customer | 300s (5min) | `customer_portal/views.py`, `billing/views/auth.py` | Expires naturally; removed from `active_portal_customers` dict when missing |
    | `seen_user_{id}` | Last-activity timestamp for a staff/admin user | 86400s (30 days) | `billing/middleware.py` | Expires naturally |
    | `live_monitoring_data` | Cached Mikrotik live monitoring API response | 30s | `billing/views/api/dashboard.py`, `billing/tasks.py` | Overwritten on each poll cycle |
    | `dashboard_stats_{date}` | Cached dashboard statistics for a specific date | 300s (5min) | `billing/views/dashboard.py` | Expires naturally |
    | `active_pppoe_usernames_set` | Set of connected PPPoE usernames from Mikrotik routers | 30s | `billing/views/api/network.py`, `billing/views/customers/list.py` | Overwritten on each poll/request cycle |
    | `api_router_uplink_payload` | Cached router uplink status response | 25s | `billing/views/api/network.py` | Overwritten on each poll |
    | `api_active_pppoe_usernames_payload` | Cached active usernames response | 20s | `billing/views/api/network.py` | Overwritten on each poll |
    | `api_offline_users_payload` | Cached offline-customer list (hits every router) | 30s | `billing/views/api/network.py` | Overwritten on each poll |
    | `api_network_alerts_payload` | Cached device/barangay/customer/ticket alerts | 30s | `billing/views/api/network.py` | Overwritten on each poll |
    | `analytics_dashboard_{date}` | Cached analytics KPIs (MRR, revenue, churn) | 300s | `billing/views/analytics.py` | Expires naturally |
    | `router_unreachable_{id}` | Circuit breaker flag; fail fast without touching the socket | 45s | `network_manager/services/base.py` | Deleted on successful connect |

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

25. **THE DUAL ENCYCLOPEDIA & TOPBAR CHANGELOG LAW**:
    * Whenever an AI updates the development encyclopedia (`billing/templates/billing/changelog.html`), it **MUST** simultaneously update the topbar rocket dropdown changelog in `billing/templates/billing/base/_topbar.html`.
    * Keep the topbar summary concise with bullet cards (`gt-cl-card`) highlighting the main features of that day's build, and transfer the `<span class="badge bg-success">Latest Build</span>` badge to the newest date.

26. **THE POWERSHELL SYNTAX LAW (Zero Syntax Retries on Windows)**:
    * **MANDATORY**: The user's system runs Windows PowerShell. **NEVER** chain terminal commands with bash-style `&&` (which causes `ParserError: The token '&&' is not a valid statement separator`).
    * **ALWAYS** chain commands with a semicolon `;`:
      ```powershell
      git add -A; git commit -m "feat(...)"; git push origin main
      ```

27. **LOCAL PYTHON AST SYNTAX COMPILATION PROTOCOL**:
    * **CRITICAL CONTEXT**: The local Windows host system does NOT have the Django virtual environment activated (Django runs inside the Docker container on Linux).
    * **FORBIDDEN**: Running `python manage.py check` or management commands directly on the host shell (causes `ModuleNotFoundError: No module named 'django'`).
    * **MANDATORY**: For instantaneous local Python syntax checks with 0 dependencies, use Python's built-in AST compiler:
      ```powershell
      python -m py_compile path/to/file.py
      ```
    * For full Django system/migration checks, execute them directly inside the droplet container via SSH:
      ```bash
      ssh root@143.198.207.144 "docker exec gametech-web python manage.py check"
      ```

28. **CANONICAL MODEL & TABLE NOMENCLATURE MATRIX**:
    * The database models in this system have precise names that differ from colloquial English. Always use the canonical model name:
      * **Payments**: Model is `Payment` (DB table `billing_payment`), NOT `PaymentLog`.
      * **Cignal Subscriptions**: Model is `CignalPlay` (DB table `cignal_play`), NOT `CignalSubscription`.
      * **Add-on Pricing Tiers**: Model is `AddonPlan` (DB table `billing_addonplan`), NOT `Addon`.
      * **General Audit Overrides**: Model is `AuditLog` (DB table `billing_auditlog`).
      * **System Entity Event Logs**: Model is `SystemLog` (DB table `billing_systemlog`).
    * **NEVER** guess or hallucinate model names. Check `gametech_filing_index.md` or `gametech_architecture_map.txt`.

29. **THE POWERSHELL SSH PYTHON PIPING STANDARD (Zero Syntax Escaping Retries)**:
    * **CRITICAL CONTEXT**: When executing multi-statement Python verification code remotely on the droplet container via SSH from a Windows PowerShell host, inline `python -c "import ...; ..."` fails because PowerShell intercepts semicolons, quotes, and parentheses.
    * **MANDATORY**: ALWAYS pipe the Python script directly into `manage.py shell` via stdin:
      ```powershell
      "<python_script_string>" | ssh root@143.198.207.144 "docker exec -i gametech-web python manage.py shell"
      ```
    * Guarantees 100% clean remote execution without quote or parenthesis escaping errors.
    * **Rule 29b (Headless RequestFactory Auth Guard & HTML Response Protocol)**:
      * When using Django `RequestFactory` to test views protected by `@login_required` via headless Python scripts, always assign a mock staff user `req.user = User.objects.filter(is_staff=True).first()` to prevent `AttributeError: 'WSGIRequest' object has no attribute 'user'` crashes.
      * Note that standard Django views wrapped in decorators return `HttpResponse` (not `TemplateResponse`), so accessing `resp.context_data` will raise `AttributeError`.
      * **MANDATORY VERIFICATION TEMPLATE**: Validate headless view rendering using `resp.content.decode('utf-8')`:
        ```powershell
        @'
        from django.test import RequestFactory
        from django.contrib.auth import get_user_model
        from billing.views.subscriptions import subscription_plans_view

        User = get_user_model()
        rf = RequestFactory()
        req = rf.get('/subscriptions/')
        req.user = User.objects.filter(is_staff=True).first()
        resp = subscription_plans_view(req)
        html = resp.content.decode('utf-8')
        print("STATUS:", resp.status_code)
        print("ASSERTION:", "Expected String" in html)
        '@ | ssh root@143.198.207.144 "docker exec -i gametech-web python manage.py shell"
        ```

30. **THE REUSABLE MODAL & PARTIAL VARIABLE GUARD LAW (Zero Orphan Variable Crashes)**:
    * **THE TRIGGER**: When creating or modifying partial templates (modals, cards, action popups) that can be included both on detail views (where `customer` exists in context) and index/dashboard views (where `customer` is absent):
    * **FORBIDDEN**: Using unquoted variable names as filter arguments (e.g. `{{ target_customer.full_name|default:customer.full_name }}` or `{% with cust=target_customer|default:customer %}`). Django evaluates filter arguments dynamically; when `customer` is not in context, this throws `VariableDoesNotExist: Failed lookup for key [customer]`.
    * **MANDATORY**: Use explicit conditional blocks:
      ```html
      {% if target_customer %}{{ target_customer.full_name }}{% elif customer %}{{ customer.full_name }}{% else %}Default{% endif %}
      ```
      or provide default values explicitly in the `{% include %}` call: `{% include "..." with customer=None %}`.

31. **THE MODEL STATUS PROPERTY LAW (Compute State in Models, Not Templates)**:
    * **THE PRINCIPLE**: When an entity's lifecycle state (Active, Expired, Suspended, Expiring Soon) depends on timestamps or multiple fields (e.g. `CignalPlay` comparing `expiration_date` vs `end_date` against `timezone.now()`):
    * **FORBIDDEN**: Duplicating verbose timestamp math or custom filters across different templates.
    * **MANDATORY**: Define a lightweight `@property def is_active(self)` directly on the Django model. Templates must simply check `{% if item.is_active %}`. Ensures single-source-of-truth status across Dashboard, Profile, and Customer Portal.

32. **THE CONTAINER PORT & COMPOSE HEALING PROTOCOL**:
    * **ROUTINE DEPLOYS VS. COMPOSE HEALING**:
      * For routine code/template updates, **STRICTLY** use `docker restart gametech-web`. It is fast, clean, and avoids invoking Docker Compose.
      * **ONLY** invoke Docker Compose if container ports drop or Nginx returns `502 Bad Gateway` (e.g. `docker ps` lacks `0.0.0.0:8000->8000`).
    * **DOCKER COMPOSE V2 SYNTAX STANDARD (No Hyphens)**:
      * When Compose healing is required, **ALWAYS** use modern Compose V2 syntax: `docker compose up -d` (with a space).
      * **FORBIDDEN**: Using legacy `docker-compose` (with hyphen, v1.29). Legacy Compose v1.29 crashes on modern Docker Engine v26+ with `KeyError: 'ContainerConfig'` when inspecting pruned container metadata, and freezes automated deployments with interactive prompts (`Continue with the new image? [yN]`).
    * **MANDATORY HEALING COMMAND**:
      ```bash
      ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && docker compose up -d"
      ```
      This guarantees all dependent containers (Postgres, Redis, Celery, Web) and their port bindings (`0.0.0.0:8000->8000`) are fully re-established.

32v2. **THE ROUTINE DEPLOYMENT RESTART STANDARD (Fast & Safe)**:
    * **STANDARD ROUTINE COMMAND**:
      ```bash
      ssh root@143.198.207.144 "docker restart gametech-web"
      ```
    * Never chain `docker compose up` to routine restarts unless port drops have been verified.

33. **THE POWERSHELL STDIN PIPE PROTOCOL (Zero Parsing Failures on Windows)**:
    * **CRITICAL CONTEXT**: When executing local Python one-liners on Windows PowerShell, PowerShell intercepts and mishandles quotation marks, semicolons, curly braces, and regex backslashes in `-c "..."` commands, causing cryptic `ParserError` or `UnexpectedToken` exceptions.
    * **MANDATORY**: Local PowerShell commands that execute Python must either use single-quoted outer strings without inner quote conflicts or pipe the raw script directly into `python -` via stdin (using single-quotes or PowerShell here-strings `@' ... '@`):
      ```powershell
      'content = open("file.html", "r", encoding="utf-8").read(); print(len(content))' | python -
      ```
      Or for multi-line scripts:
      ```powershell
      @'
      import re
      content = open("file.html", "r", encoding="utf-8").read()
      print(len(content))
      '@ | python -
      ```
      * Guarantees 100% clean local Python execution without shell quote escaping failures.

34. **THE STAGED CHUNKING PROTOCOL (Monolith File Truncation Guard)**:
    * **THE PRINCIPLE**: When modifying or refactoring monolith files that exceed **1,000 lines** (e.g., `changelog.html`, `gametech_error_runbook.md`, legacy views):
    * **FORBIDDEN**: Attempting a single massive diff replacing hundreds of lines at once. Large single-block edits cause tool token truncation, context overflows, or regex mismatch failures.
    * **MANDATORY**: Chunk edits into 3–4 staged replacements of **150–250 lines** each. Run automated div parity validation (`<div\b` count == `</div>` count) after every single stage before proceeding to the next chunk.

35. **THE STATUS VOCABULARY LAW (Hardware vs. Billing vs. Installation Tri-Domain Disambiguation)**:
    * **THE PRINCIPLE**: Never conflate hardware connectivity states, customer billing lifecycle states, or physical installation states. They represent three completely independent and orthogonal domains:
      * **1. Hardware Connectivity**: `Connected` (active PPPoE/DHCP session on MikroTik router) vs `Offline` (no active session).
      * **2. Billing Lifecycle**: `Active` (paid up/valid date), `Expiring Soon` (near expiry), `Expired` (past due), `Suspended` (manually or auto-locked), `Inactive` (decommissioned/churned).
      * **3. Physical Installation State**: `Installed` (active physical line on-premises) vs `Pending Installation` (awaiting technician dispatch/setup).
      * **Outage (Critical Actionable State)**: `Active but Offline` (or `Paid but Offline`) — customers who are fully installed and paid/active in billing, but disconnected/offline on the router. This represents a technical issue or fiber break requiring immediate technician dispatch.
    * **FORBIDDEN**: 
      * Inferring or guessing installation state from null expiration dates (`expires_at is None`) or billing status.
      * Labeling active billing accounts as `"Disconnected (Inactive)"` or treating offline hardware as an inactive subscription. Always preserve the three distinct domains across models, badges, APIs, and reports.

36. **THE QUERYSET PRIORITY ORDERING LAW (Outage-First Triage)**:
    * **THE PRINCIPLE**: In any administrative view listing customers or subscriptions (`/customers/`, `/subscriptions/`), subscribers requiring immediate intervention MUST appear at the top of the list by default.
    * **MANDATORY**: Annotate querysets with a conditional `status_order` pushing critical actionable states (Outages / Active but Offline) to rank `0`:
      ```python
      from django.db.models import Case, When, Value, IntegerField

      customers = customers.annotate(
          status_order=Case(
              When(status='active', is_connected=False, then=Value(0)),  # Outage: Active but Offline
              When(status='active', is_connected=True, then=Value(1)),   # Normal: Active & Connected
              When(status='expiring', then=Value(2)),
              When(status='expired', then=Value(3)),
              When(status='suspended', then=Value(4)),
              default=Value(5),
              output_field=IntegerField(),
          )
      ).order_by('status_order', '-created_at')
      ```
    * Guarantees that dispatchers and support staff instantly see subscribers experiencing outages without manual filtering.

37. **THE SUBSCRIBER PROVISIONING & ROUTER IMPORT PROTOCOL**:
    * **THE PRINCIPLE**: Any customer account created or imported into the system MUST explicitly declare its `installation_status`.
    * **MANDATORY ROUTER IMPORT RULES**:
      * **MikroTik Router Sync & Bulk Import** (`network_manager/views/devices.py`, `network_manager/views/sync.py`): MUST explicitly pass `installation_status='installed'` and `installed_at=timezone.now()` to `Customer.objects.create()`. Router secrets represent live physical lines and must NEVER be created as pending installation.
      * **Manual Add Customer** (`billing/views/customers/crud.py`): MUST provide a clear setup selector (`Installed / Existing Subscriber` vs `For Installation / New Applicant`).
      * **Agent Form**: Automatically defaults to `installation_status='pending'` awaiting dispatch.

38. **THE FULL-STACK ATOMIC BATCHING STANDARD (Speed & Turn Optimization)**:
    * **THE PRINCIPLE**: When implementing full-stack features touching Models, Migrations, Views, and Templates, avoid sequential 1-file micro-edits that deplete tokens and cause round-trip latency.
    * **MANDATORY BATCHING WORKFLOW**: Group edits into **3 cohesive stages**:
      * **Stage 1 (Backend & DB)**: Model changes + migration file + backend CRUD views in one batch.
      * **Stage 2 (Frontend & Templates)**: Form inputs + modal partials + list/view templates in one batch.
      * **Stage 3 (Deploy & Verify)**: Single commit + single git pull + migration run + container restart.
    * Cuts tool turns by 75% while maintaining surgical precision.

39. **THE REAL-WORLD BUSINESS & ACCOUNTING REALITY CHECK (The "No Blind Execution" Law)**:
    * **THE MANDATE**: Senior developers often describe features from high-level abstract theory without knowing day-to-day ISP counter operations, cash collection, or field dispatch realities.
    * **MANDATORY PRE-EXECUTION AUDIT**: Before executing ANY prompt that changes workflows, schemas, or accounting:
      1. **Cash & Ledger Integrity**: Any monetary transaction (Cignal installments, monthly load, upgrades, installation fees) MUST create a verified `Payment` receipt row and update customer balances. NEVER allow floating counters (e.g. `installments_paid`) without financial transaction tracking.
      2. **Front-Desk Counter Workflow**: NEVER hide or remove fields required for on-the-spot applicant scheduling (e.g. installation dates, first due date, barangay).
      3. **Bidirectional Sync**: When bridging two systems (e.g. CRM Customer Profile ↔ Dispatch Job Tickets), sync MUST work in both directions so actions in one interface never leave ghost or orphaned records in the other.
      4. **Speak Up First**: If a prompt contains backwards logic, creates redundant ghost models, or contradicts physical ISP operations, the AI **MUST alert the user immediately**, explain the operational conflict in plain English, and propose the real-world aligned solution before proceeding.

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

---

## 39. **THE LIVE MONITORING & LOGIN FREEZE LAW (Permanently Protected Pages)**

> **THE PRINCIPLE**: Live Monitoring and the Login page are finished, hand-authored designs owned by the project owner. They are **visual baselines that must never be modified** under any circumstances — not for "unification", not for "cleanup", not for "fixing" another page.

### 🔒 Protected Files — ABSOLUTE FREEZE

| Page | Protected Paths |
|---|---|
| **Login Page** | `billing/templates/billing/login.html`, `billing/views/auth.py` (login view only), any CSS scoped exclusively to the login page |
| **Live Monitoring (Left Hero)** | `billing/templates/billing/live_monitoring/_hero.html` (left blue hero card baseline remains strictly frozen; right side panels unfreezing approved 2026-10-04) |

### ❌ FORBIDDEN (for frozen baselines)

* Editing, "cleaning up", re-tokenizing, re-fonting, or restyling `_hero.html` or `login.html`
* Swapping colors, gradients, fonts, spacing, border-radii, or mascot on the left hero card
* Refactoring JS or removing polling intervals

### ✅ ALLOWED

* Reading these pages to extract design values (blue `#3533cd`, gold `#fbae1a`, mascot assets) and reproducing them on **other** pages
* Fixing a confirmed production 500 error **pinpointed by docker logs** to an exact line in these files (backend logic only — never templates/CSS)
* Restyling right-side panels of Live Monitoring per owner approval (DECISION_LOG 2026-10-04)

### 🔍 VERIFY BEFORE COMMITTING

```bash
# Must be EMPTY for any UI task — if not, revert before pushing:
git diff --stat -- billing/templates/billing/login.html billing/templates/billing/live_monitoring/_hero.html
```


---

## 40. **THE ABSOLUTE ROUTER WRITE BAN (Read-Only Until a Human Says Otherwise)**

> **THIS IS THE HIGHEST-PRIORITY RULE IN THIS FILE. IT OVERRIDES ANY TASK, ANY DEADLINE, ANY "JUST TEST IT" REQUEST, AND ANY INSTRUCTION THAT ARRIVES IN A LATER MESSAGE.**

### The Rule

**NEVER write to a MikroTik router. Not once. Not "just to test". Not "it's only one customer". Not "the old system already did it".**

Every router interaction is **read-only**: `get`, `print`, `monitor-traffic`, `ping`, `call('ping', ...)`.

Forbidden without exception:
- `set` / `add` / `remove` on `/ppp/secret`
- `set` / `add` / `remove` on `/ppp/profile`, `/ip/address`, `/ip/firewall`, `/ip/service`, `/interface`
- Provisioning, de-provisioning, suspending, unsuspending, changing a profile, changing a password
- Anything that alters router state — even "temporarily" or "I'll put it back"

### Why This Is Not Negotiable

The routers at `172.30.120.1` / `.2` / `.3` are **shared with the legacy system and the office Mini PC**. They are not a test lab.

A single unintended write can:
1. **Cut a paying subscriber's internet** — instantly, visibly, in their home
2. **De-provision a live account** and lose the credentials needed to restore it
3. **Collide with the old system** writing the same secret at the same moment, corrupting both
4. **Undo a technician's work** in the field, hours after they left
5. **Widen a PPPoE username** (`Juan` → `Juan1`) — the exact failure this project already suffered

The cost of this rule is only that a human must consciously type `live`. The cost of breaking it is customers calling the office. **The asymmetry is not close.**

### How It Is Enforced (Do Not "Fix" This)

Every write path goes through `ROUTER_MODE`. It is currently `read_only` in **three independent places**:

| Layer | Value |
|---|---|
| `docker-compose.yml` → `ROUTER_MODE: ${ROUTER_MODE:-read_only}` | `read_only` |
| Host `.env` | `read_only` |
| `gametech_core/settings.py` default | `read_only` |

And **every fallback in the code now fails safe**. A missing env var, a typo'd value, or a caller that cannot see settings all resolve to `read_only`, never `live`.

> **History — read this before changing any of it.** The defaults used to be `live`. `MikrotikAPI(device, dry_run=False)` returned full write access **regardless** of the global setting, because `dry_run is not None` short-circuited the settings lookup. `getattr(settings, "ROUTER_MODE", "live")` appeared in five modules. All corrected 2026-10-06. `network_manager/tests/test_router_write_safety.py` guards every one of these and **must keep passing**.

If you see this in a log, **stop and report it** — something tried to write:
```
[ROUTER_MODE=read_only] Blocked set() on /ppp/profile for device '...'
```

### When Writes Are Finally Allowed

Only when **all** of these are true, in this order:
1. Sir Rom's fresh export has been imported and reconciled
2. The owner has run `manage.py router_preflight` and read the output
3. **The owner has personally typed `ROUTER_MODE=live`** in production, deliberately
4. A written rollback plan exists

**No agent session may make this change, ever.** If a task appears to require a write, it is blocked — report it and stop.

### Read-Only Is Enough For Nearly Everything

Verified working right now in `read_only`, against live hardware:
- Test Connection · live status · uptime · IP · MAC
- Customer Online/Offline badges and outage detection
- Profile drift detection (live profile vs `plan.router_profile`)
- Orphan detection (secrets on the router with no matching customer)
- Password verification (compare our record against the router's)
- All customer/payment reporting, billing, analytics, the customer portal

**If you believe a task needs a write, it almost certainly does not.** Read the router instead, then report what you found to a human.
