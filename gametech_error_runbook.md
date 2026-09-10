# 📕 Gametech Error & Incident Runbook (Triage Matrix)

> **Purpose**: A fast-lookup registry of known system errors, symptoms, and their exact target files.  
> **Rule for AI & Developers**: **CHECK THIS FILE FIRST** whenever a user reports a bug or UI defect before scanning any code or exploring directories.

---

## 📑 Quick Symptom Index

| Issue ID | User Symptom / Error | Primary Affected Files | Category |
| :--- | :--- | :--- | :--- |
| **ERR-001** | Screen freezes / turns grey on modal click | `billing/templates/billing/<page>/_modal_*.html`, parent `*.html` | Frontend (DOM) |
| **ERR-002** | Select2 dropdown is blinding white / unstyled in dark mode | `_modal_*.html`, `static/css/theme/layout_and_darkmode.css` | Frontend (CSS) |
| **ERR-003** | Telemetry / Live Speed stuck on dots `...` or not updating | `billing/views/api/network.py`, `billing/urls.py`, `_scripts.html` | API / Routing |
| **ERR-004** | Mikrotik Router Uplink / Ping Down or Packet Loss | `network_manager/services.py`, `billing/views/network.py` | Hardware API |
| **ERR-005** | Customer payment / balance mismatch or router out of sync | `billing/signals.py`, `billing/views/payments.py` | DB / Signals |
| **ERR-006** | DigitalOcean Docker container not loading new code | `/root/GAMETECH-BILLING-SYSTEM`, Docker bind mount | Deployment |
| **ERR-007** | Server Error (500) on Changelog / Template Syntax Error | `billing/templates/billing/changelog.html` | Template Syntax |

---

## 🛠️ Detailed Incidents & Resolution Patterns

### ERR-001: Modal Opens with Grey Screen / Unclickable Backdrop Lockout
* **Symptoms**:
  * Clicking "Search Customer", "View All", or "Apply Add-on" dims the screen to dark grey.
  * The modal content is either invisible or cannot be clicked/closed.
* **Root Causes**:
  1. **Unbalanced `<div>` tags**: An opening `<div\b` without a matching `</div>` inside a modal partial breaks Bootstrap 5's modal hierarchy.
  2. **Nested Modals / Hidden Containers**: A modal partial was included *inside* another modal or inside an element with `overflow: hidden` or `display: none`.
* **Exact Target Files**:
  * `billing/templates/billing/<feature>/_modal_*.html`
  * Check parent orchestrator template (`dashboard.html`, `live_monitoring.html`, etc.)
* **1-Step Diagnosis & Fix**:
  1. Run div-balance check in terminal:
     ```powershell
     python -c "content = open('path/to/_modal.html', 'r', encoding='utf-8').read(); import re; o = len(re.findall(r'<div\b', content)); c = len(re.findall(r'</div>', content)); print(f'opens: {o}, closes: {c}, diff: {o-c}')"
     ```
  2. If `diff != 0`, find and fix the missing `</div>`.
  3. Ensure the `{% include "_modal_*.html" %}` is at the root of the parent template, NOT nested inside dashboard cards.

---

### ERR-002: Select2 Dropdown Rendered as Stark White Box in Dark Mode
* **Symptoms**:
  * In dark mode, clicking a Select2 search box pops up a blinding white dropdown with black text and white search input field.
* **Root Causes**:
  * Select2 was initialized with `theme: 'bootstrap-5'`, which generates `.select2-container--bootstrap-5`. Global dark mode CSS only targeted `.select2-container--default`.
  * Select2's `dropdownParent` appends inside the modal, requiring modal-scoped dark mode selectors.
* **Exact Target Files**:
  * `billing/templates/billing/<feature>/_modal_*.html` (embedded `<style>`)
  * `static/css/theme/layout_and_darkmode.css` (lines 630–650)
* **1-Step Fix**:
  * Apply scoped dark mode CSS targeting:
    - `.dark-mode .select2-dropdown`, `html.dark-mode .select2-dropdown` (background: `#0f172a`)
    - `.dark-mode .select2-search__field` (background: `#1e293b`, color: `#ffffff`)
    - `.dark-mode .select2-selection` (background: `#1e293b`, border: `rgba(255,255,255,0.18)`)
    - `.dark-mode .select2-results__option--highlighted` (gradient accent)

---

### ERR-003: Live Telemetry / Bandwidth / Status Stuck on Dots (`...`)
* **Symptoms**:
  * Customer details card displays `Status: ...`, `Download: ...`, `Upload: ...` and never populates live metrics.
* **Root Causes**:
  1. **Route Mismatch (404)**: JavaScript `fetch()` calls an endpoint (e.g. `/api/customer/<id>/mikrotik-status/`) that is not declared in `billing/urls.py` (which had `customers/api/status/<id>/`).
  2. **Stale Browser Cache**: Browser is still executing the old HTML/JS cached before deployment.
  3. **Unlinked Mikrotik Account**: Customer record in DB has empty `pppoe_username` or `mikrotik_device`.
* **Exact Target Files**:
  * `billing/urls.py` (route registration)
  * `billing/views/api/network.py` (`api_customer_mikrotik_status`)
  * `billing/templates/billing/<feature>/_scripts.html` (frontend `fetch()` caller)
* **1-Step Diagnosis & Fix**:
  1. Check endpoint in `billing/urls.py` and ensure both alias routes point to `views.api_customer_mikrotik_status`:
     ```python
     path("customers/api/status/<int:customer_id>/", views.api_customer_mikrotik_status),
     path("api/customer/<int:customer_id>/mikrotik-status/", views.api_customer_mikrotik_status),
     ```
  2. Test response directly via Django shell:
     ```python
     from billing.views.api.network import api_customer_mikrotik_status
     resp = api_customer_mikrotik_status.__wrapped__(request, customer_id)
     print(resp.content)
     ```
  3. Hard refresh the browser (<kbd>Ctrl</kbd> + <kbd>F5</kbd>).

---

### ERR-004: Mikrotik Router Live Uplink / Ping Down
* **Symptoms**:
  * NOC dashboard displays `API Unreachable` or `Offline (Router Off)` for routers or PPPoE users.
* **Root Causes**:
  1. RouterOS API port `8728` is unreachable from the web container or droplet IP is blocked.
  2. Router lost upstream gateway ping to `8.8.8.8`.
  3. Credentials in `MikrotikDevice` model expired or incorrect.
* **Exact Target Files**:
  * `network_manager/services.py` (`MikrotikAPI`)
  * `billing/views/network.py` (`live_monitoring_view`)
  * `billing/views/api/network.py` (`api_customer_mikrotik_status`)
* **1-Step Diagnosis & Fix**:
  1. Test API connection in Python:
     ```python
     from network_manager.services import MikrotikAPI
     from billing.models import MikrotikDevice
     dev = MikrotikDevice.objects.first()
     api = MikrotikAPI(dev)
     print(api.ping("8.8.8.8"))
     ```

---

### ERR-005: Customer Payment Mutation / Status Mismatch (Router Desync)
* **Symptoms**:
  * Payment recorded in DB, but customer status remains `expired` or Mikrotik PPPoE secret remains disabled.
* **Root Causes**:
  * Database mutation used `.update()` on a QuerySet, which **bypasses Django `post_save` signals**.
  * Missing `transaction.atomic()` with `select_for_update()`, leading to race conditions.
* **Exact Target Files**:
  * `billing/signals.py` (Mikrotik sync handlers)
  * `billing/views/payments.py` or `billing/models.py`
* **1-Step Fix**:
  * Always mutate the model instance and call `.save()`:
    ```python
    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(id=customer_id)
        customer.status = "active"
        customer.save()  # Triggers billing/signals.py to enable PPPoE on router
    ```

---

### ERR-006: DigitalOcean Container Not Loading Modified Files
* **Symptoms**:
  * Code committed and pulled on the droplet, but browser still displays old behavior.
* **Root Causes**:
  * Gunicorn worker processes running in the Docker container hold old `.pyc` bytecode in memory until gracefully reloaded or restarted.
* **Exact Target Files**:
  * Container `gametech-billing-system_web_1`
* **1-Step Fix**:
  * Restart the container on the droplet:
    ```bash
    ssh root@143.198.207.144 "docker restart gametech-billing-system_web_1"
    ```
  * Verify clean startup:
    ```bash
    ssh root@143.198.207.144 "docker logs --tail 25 gametech-billing-system_web_1"
    ```

---

### ERR-007: Server Error (500) on Template Syntax / Premature `{% endblock %}`
* **Symptoms**:
  * Navigating to `/changelog/` or a documentation/content page throws `Server Error (500)`.
  * Gunicorn log shows `TemplateSyntaxError: Invalid block tag on line XXX: 'endblock'. Did you forget to register or load this tag?`.
* **Root Causes**:
  * Raw Django template tags (e.g. `{% load static %}`, `{% endblock %}`, `{% load log_filters %}`) written inside documentation/changelog text or `<code>` tags without escaping them.
  * The Django template compiler treats them as executable tags, prematurely closing `{% block content %}` in the middle of the template.
* **Exact Target Files**:
  * `billing/templates/billing/changelog.html` (or affected template)
* **1-Step Fix**:
  * Escape literal template tags with HTML entities:
    `&#123;% load static %&#125;`, `&#123;% endblock %&#125;`.

---

## 📝 How to Add a New Error Entry

Whenever a non-obvious bug or architecture defect is resolved:
1. Assign a new `ERR-XXX` identifier.
2. Fill in: **Symptoms**, **Root Causes**, **Exact Target Files**, and **1-Step Fix**.
3. Keep entries short, actionable, and sniper-focused.
