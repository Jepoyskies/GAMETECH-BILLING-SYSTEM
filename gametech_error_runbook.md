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
| **ERR-013** | Logged-out Customer Still Showing as Active in Topbar Live Monitoring Dropdown | `billing/views/auth.py`, `customer_portal/views.py`, `billing/middleware.py` | Session / Cache |
| **ERR-015** | Accidental Horizontal Scrollbar / Clunky Windows Scrollbars in Topbar Notifications Dropdown | `_topbar.html`, `_scripts.html`, `components.css` | Frontend (CSS) |
| **ERR-016** | Suspended Customer Retaining Stale Expiration Date in UI & Mikrotik Secret Comment | `billing/models.py`, `_info_cards.html`, `actions.py`, `crud.py` | Model / UI |

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
  * NOC dashboard displays `Offline`, `API Unreachable`, or `ping: Timeout` on the Router Uplink KPI card even when an active Mikrotik router is online.
* **Root Causes**:
  1. **Index 0 Hardcode**: Frontend `_scripts.html` was hardcoded to `d.routers[0]`. When multiple routers exist (e.g. Mikrotik B offline, Mikrotik A online), the offline router shadowed the online router regardless of the `#routerFilter` selection.
  2. **Single Packet Timeout**: `api_router_uplink` only sent `count: 1`. An initial ARP resolution or momentary drop immediately reported 100% loss/Timeout.
  3. **Missing Default Route on Router**: Physical router missing `0.0.0.0/0` route in `/ip/route` results in `status: 'no route to host'`.
* **Exact Target Files**:
  * `billing/views/api/network.py` (`api_router_uplink`)
  * `billing/templates/billing/live_monitoring/_scripts.html`
* **1-Step Diagnosis & Fix**:
  1. In `api_router_uplink`, send `count: 2`, parse successful packets for `avg-rtt`, and include `"ip": device.ip_address`.
  2. In `_scripts.html`, respect `document.getElementById('routerFilter').value`. If `"ALL"`, display active status if any router is online (`Online (1/2)`), or match specific selected router IP.

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

### ERR-008: Live Monitoring Displays Raw PPPoE Username Instead of Customer Account Name
* **Symptoms**:
  * On `/live-monitoring/`, the Top User KPI card and Live Traffic Table display the raw RouterOS PPPoE username (e.g. `lab_test`) instead of the subscriber's account name (`Jep&Jill`).
* **Root Causes**:
  * `get_live_monitoring_data_sync` in `billing/utils.py` queries active PPPoE sessions from Mikrotik API (`au.get("name")`) without joining to `Customer.objects` on `pppoe_username`.
* **Exact Target Files**:
  * `billing/utils.py` (`get_live_monitoring_data_sync`)
  * `billing/templates/billing/live_monitoring/_scripts.html` (`updateSummary`, `applyFilter`, `openCustomerLiveChart`)
* **1-Step Fix**:
  * In `billing/utils.py`: Pre-query a bulk map of `pppoe_username` -> `{"id": c.id, "full_name": c.full_name}` using `.values()` and assign `customer_name` and `customer_id` to each record in `users`.
  * In `_scripts.html`: Render `u.customer_name || u.user` prominently with `u.user • u.ip` as secondary caption, while keeping `u.user` as the RouterOS lookup key for live charts.

---

### ERR-009: Server Error (500) on Setup Profiles or Sync Manager (`ModuleNotFoundError: network_manager.views.sync_services`)
* **Symptoms**:
  * Clicking "Setup Profiles" (`/devices/devices/<id>/setup-profiles/`) or "Sync Manager" (`/devices/devices/<id>/sync/`) immediately throws `Server Error (500)`.
  * Traceback shows `ModuleNotFoundError: No module named 'network_manager.views.sync_services'`.
* **Root Causes**:
  * In `network_manager/views/devices.py` and `network_manager/views/sync.py`, code imported `from .sync_services import MikrotikAPI as MikrotikSyncAPI`. Because views are in the `network_manager.views` subpackage, Python looked for `network_manager/views/sync_services.py` instead of the root module `network_manager/sync_services.py`.
* **Exact Target Files**:
  * `network_manager/views/devices.py` (`setup_router_profiles`)
  * `network_manager/views/sync.py` (`sync_manager`, `sync_push_user`, `sync_autofix_user`, `sync_delete_user`, `sync_bulk_action`)
* **1-Step Fix**:
  * Change `from .sync_services import MikrotikAPI as MikrotikSyncAPI` to `from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI`.

---

### ERR-010: Server Error (500) on Customer Portal Dashboard (`TemplateSyntaxError: Invalid block tag 'static'`)
* **Symptoms**:
  * Navigating to `/portal/dashboard/` throws `Server Error (500)`.
  * Traceback shows `django.template.exceptions.TemplateSyntaxError: Invalid block tag on line X: 'static'. Did you forget to register or load this tag?`.
* **Root Causes**:
  * Partial templates included via `{% include %}` (e.g. `customer_portal/portal_dashboard/_navbar.html`, `_hero.html`, `_scripts.html`) use `{% static %}` tags without having `{% load static %}` declared at the top of the partial file. Django does not implicitly pass registered template tag libraries to included partials when parsed individually.
* **Exact Target Files**:
  * `customer_portal/templates/customer_portal/portal_dashboard/_navbar.html`
  * `customer_portal/templates/customer_portal/portal_dashboard/_hero.html`
  * `customer_portal/templates/customer_portal/portal_dashboard/_scripts.html`
* **1-Step Fix**:
  * Add `{% load static %}` at line 1 of every partial template that references `{% static ... %}`.

---

### ERR-011: Server Error (500) on Submit Ticket (`ImportError: cannot import name 'ClientConcern' from 'dispatch.models'`)
* **Symptoms**:
  * Submitting a support ticket via `/portal/submit-ticket/` throws `Server Error (500)`.
  * Traceback shows `ImportError: cannot import name 'ClientConcern' from 'dispatch.models'`.
* **Root Causes**:
  * `customer_portal/views.py` (`submit_ticket`) attempted to import a non-existent model `ClientConcern`. In Gametech Dispatch, client tickets and concerns are stored in `DispatchRecord` (with `source_tab='CLIENT_CONCERNS'`) and `MonitoringRecord` (with `tab_type='CLIENT_CONCERNS'`).
* **Exact Target Files**:
  * `customer_portal/views.py` (`submit_ticket`)
* **1-Step Fix**:
  * Create `DispatchRecord` and `MonitoringRecord` with `source_tab='CLIENT_CONCERNS'`, linked to `customer`, a generated ticket number, default admin `csr`, and appropriate `ConfigOption` statuses.

---

### ERR-012: Topbar Notification Dropdown Stuck on "Loading updates..." Spinner Loop
* **Symptoms**:
  * Clicking the notification bell in the top navigation shows a permanent loading spinner with "Loading updates..." and never displays any notifications.
* **Root Causes**:
  * The topbar markup included the `#notifLoading` placeholder in `_topbar.html`, but lacked JavaScript in `_scripts.html` to fetch `/api/notifications/`, hide `#notifLoading`, and render the notification cards into `#notifList`.
* **Exact Target Files**:
  * `billing/templates/billing/base/_topbar.html`
  * `billing/templates/billing/base/_scripts.html`
  * `static/css/theme/components.css`
* **1-Step Fix**:
  * Implement `fetchNotifications()`, `markNotificationRead()`, and `markAllNotificationsRead()` in `_scripts.html` calling `/api/notifications/` with CSRF headers, and bind `onclick="fetchNotifications()"` on `#notificationDropdown` in `_topbar.html`.

### ERR-013: Logged-out Customer Still Showing as Active in Topbar Live Monitoring Dropdown
* **Symptoms**:
  * Even after a subscriber logs out of the Customer Portal, they continue to be listed under the "Customer" tab with an "Active" badge in the top navigation "Currently Logged In" dropdown.
* **Root Causes**:
  1. `online_staff_api` queried `Session.objects.filter(expire_date__gte=now)` and unconditionally appended `active_customer_ids.add(int(cid))` without checking if `seen_customer_{cid}` was still alive in cache or if the session was active. Because Django sessions have a 14-day expiry, any prior session row created in the past 2 weeks caused the customer to remain permanently active.
  2. `portal_logout` and `custom_logout_view` only called `request.session.flush()`, which only deleted the current cookie's session row, leaving any older database sessions with `customer_id` orphaned in the database.
  3. `custom_logout_view` (/logout/) lacked cleanup for customer portal cache keys and database sessions.
* **Exact Target Files**:
  * `billing/views/auth.py` (`online_staff_api`, `custom_logout_view`, `unified_login_view`)
  * `customer_portal/views.py` (`portal_logout`, `portal_login`)
  * `billing/middleware.py` (`ActiveUserMiddleware`)
* **1-Step Fix**:
  * In `online_staff_api`, only accept customers whose `seen_customer_{cid}` cache key is present and active (< 300s). Remove unconditional database session fallbacks.
  * In `portal_logout` and `custom_logout_view`, delete all database sessions matching `customer_id` and explicitly delete `seen_customer_{customer_id}` and remove from `active_portal_customers` cache.
  * In `ActiveUserMiddleware`, parse string timestamps safely and prune `active_portal_customers` cache of any customer whose `seen_customer_{cid}` key has expired or was removed.

---

### ERR-014: Sync Manager Dark Mode Contrast Failure (White-on-White Table Headers & Light Filter Bar)
* **Symptoms**:
  * On `/devices/devices/<id>/sync/`, in dark mode, table headers (`<thead> <th>`) have a bright white/grey background (`#f8f9fc`) with white text, rendering column labels completely invisible.
  * The filter bar (`.filter-bar`) appears as a bright, translucent white stripe across dark cards.
  * Table rows (`<td>`) use dark grey text (`#5a5c69`) unreadable against dark backgrounds, and hover turns rows blinding white.
* **Root Causes**:
  * `network_manager/templates/network_manager/sync_manager.html` defined inline `<style>` rules with hardcoded light-mode hex colors (`#ffffff`, `#f8f9fc`, `#5a5c69`, `#edf2f9`) on `.sync-card`, `.filter-bar`, and `.table th`/`.table td`, overriding Gametech design tokens and lacking dark-mode adaptation.
* **Exact Target Files**:
  * `network_manager/templates/network_manager/sync_manager.html` (`<style>`, filter bar selects, `.sync-card-footer`)
* **1-Step Fix**:
  * Replace hardcoded hex values with `--gt-surface`, `--gt-surface-2`, `--gt-surface-3`, `--gt-border`, `--gt-text`, and `--gt-text-muted` tokens. Use `.sync-card table.dataTable thead th` with `!important` to enforce dark headers, and style DataTables controls and `.sync-card-footer` cleanly.

---

### ERR-015: Accidental Horizontal Scrollbar & Clunky Native Scrollbars in Topbar Notification Dropdown
* **Symptoms**:
  * An ugly horizontal scrollbar `< [=======] >` appears across the bottom of the notifications dropdown above the "View All Notifications" link.
  * Windows native 17px scrollbars render inside the dropdown, breaking layout and creating a clunky double-scroll sensation.
* **Root Causes**:
  * `#notifList` and `#onlineStaffList` containers in `_topbar.html` were defined with `overflow-y: auto;` without explicitly specifying `overflow-x: hidden;`. By CSS specification, setting `overflow-y: auto` causes `overflow-x` to default to `auto`.
  * Dynamic notification cards had inner flex elements using class `min-w-0` without a matching CSS declaration, preventing proper flex text shrinkage/truncation when the 17px vertical scrollbar appeared.
  * Absence of custom scrollbar rules allowed default OS scrollbars to consume container width and trigger horizontal overflow.
* **Exact Target Files**:
  * `billing/templates/billing/base/_topbar.html`
  * `billing/templates/billing/base/_scripts.html`
  * `static/css/theme/components.css`
* **1-Step Fix**:
  * Add `overflow-x: hidden !important;` to `.gt-notif-body`, `#notifList`, and `#onlineStaffList`.
  * Declare `.min-w-0 { min-width: 0 !important; }` and inline `style="min-width: 0; overflow: hidden;"` on flex containers.
  * Add sleek 5px webkit and Firefox scrollbar rules (`scrollbar-width: thin;`, `height: 0px !important;`) with dark/light mode transparent tracks and rounded pill thumbs.

---

### ERR-016: Suspended Customer Retaining Stale Expiration Date in UI & Mikrotik Secret Comment
* **Symptoms**:
  * An account is set to "Suspended" (via edit form, force suspend, or auto-suspend), but the Expiration Date in the customer profile still displays a future date (e.g. `Apr 25, 2027 03:38 AM`).
  * The physical Mikrotik router's PPP secret comment still contains `exp <Date>` rather than `exp None`.
* **Root Causes**:
  * Updating a customer's status to `suspended` in `crud.py` or `actions.py` updated `customer.status` without clearing `customer.expires_at = None`.
  * The template `_info_cards.html` formatted `customer.expires_at` whenever not None, ignoring the suspended state.
* **Exact Target Files**:
  * `billing/models.py` (`Customer.save`)
  * `billing/templates/billing/view_customer/_info_cards.html`
  * `billing/templates/billing/view_customer/_modals.html` (`#editExpirationModal`)
  * `billing/views/customers/crud.py` (`edit_customer`)
  * `billing/views/customers/actions.py` (`customer_force_suspend`, `edit_customer_expiration`)
* **1-Step Fix**:
  * In `Customer.save()`, enforce `if self.status == 'suspended' and not getattr(self, '_preserve_expiration', False): self.expires_at = None`. Include `expires_at` in `update_fields` if present.
  * In `_info_cards.html`, render `<span class="text-muted">None</span>` if `customer.status == 'suspended' or not customer.expires_at`.
  * In `actions.py` (`edit_customer_expiration`), support clearing expiration to `None` when the date input is cleared/submitted empty.

---

### ERR-017: Horizontal Scrollbar Appears Inside DataTables or Table Responsive Containers
* **Symptoms**:
  * A small horizontal scrollbar appears at the bottom of a table container even when the table fits perfectly on the screen.
  * Attempting to scroll it moves the table only a few pixels left and right.
* **Root Causes**:
  * Bootstrap `.row` elements apply negative margins (`margin-left: -var(--bs-gutter-x); margin-right: -var(--bs-gutter-x);`). When nested inside a `.table-responsive` div without compensating padding, the row width exceeds 100%, forcing the container to overflow horizontally.
  * DataTables `autoWidth: true` (default) calculates column widths aggressively, which can trigger native overflow.
* **Exact Target Files**:
  * `network_manager/templates/network_manager/<feature>/_styles.html`
  * `network_manager/templates/network_manager/<feature>/_scripts.html`
* **1-Step Fix**:
  * In `_styles.html`, strip margins from nested rows and force bounds:
    ```css
    .table-responsive .row { margin-left: 0 !important; margin-right: 0 !important; width: 100% !important; }
    .table-responsive { overflow-x: hidden !important; }
    ```
  * In `_scripts.html`, initialize DataTables with `autoWidth: false`.

---

### ERR-018: Internet Drops Immediately When Transferring Customer to New Router in System
* **Symptoms**:
  * The admin changes a customer's `mikrotik_device` in the UI (or uses Sync Manager "Move").
  * Even though the physical cables haven't been swapped yet, the customer's internet drops immediately.
* **Root Causes**:
  * The `post_save` signal performs an "Orphan Cleanup" on the old router using `api.delete_pppoe_user()`.
  * By default, deleting a PPPoE secret also kicks the active session on the old router to enforce the deletion, which drops the physical connection.
* **Exact Target Files**:
  * `billing/signals.py` (`sync_customer_to_mikrotik`)
  * `network_manager/services/users.py` (`delete_pppoe_user`)
* **1-Step Fix**:
  * In `billing/signals.py`, pass `kick_active=False` during the orphan cleanup: `old_api.delete_pppoe_user(instance.pppoe_username, kick_active=False)`. This removes the secret (preventing future logins) but leaves the current active session running until the hardware is swapped.

---

### ERR-019: Server Error (500) on Cignal Dashboard (`TemplateSyntaxError: 'humanize'` & `NoReverseMatch: 'add_on_requests'`)
* **Symptoms**:
  * Navigating to `/cignal-dashboard/` results in a `Server Error (500)`.
  * Traceback shows `django.template.exceptions.TemplateSyntaxError: 'humanize' is not a registered tag library` or `NoReverseMatch: Reverse for 'add_on_requests' not found`.
* **Root Causes**:
  1. `django.contrib.humanize` is not listed in `INSTALLED_APPS`, causing `{% load humanize %}` and `|intcomma` filters to throw `TemplateSyntaxError`.
  2. The URL name for Add-On requests is `add_on_payments`, but the template referenced non-existent `add_on_requests`.
* **Exact Target Files**:
  * `billing/templates/billing/cignal_dashboard.html`
* **1-Step Fix**:
  * In `billing/templates/billing/cignal_dashboard.html`, remove `{% load humanize %}` and `|intcomma` filter usages.
  * Update reverse URL tag from `{% url 'add_on_requests' %}` to `{% url 'add_on_payments' %}`.

### ERR-020: Active Customer Displayed as Red 'Active' with Ban Icon & 'Reconnect' Button in Customer Portal
* **Symptoms**:
  * An active subscriber with a valid expiration date logs into `/portal/dashboard/`.
  * "Next Due Date" displays `<span class="text-danger fw-bold"><i class="fas fa-ban me-1"></i>Active</span>` (red with a ban icon) instead of their actual expiration date.
  * The main payment button shows red `RECONNECT / PAY BILL NOW` instead of normal `PAY BILL NOW`.
  * The payment modal says "Reconnect Account" with an account disconnected warning.
* **Root Causes**:
  * Django templates evaluate `in` as string substring search when checked against literal comma-separated strings: `{% if customer.status in 'suspended,expired,inactive' %}`.
  * Because `'active'` is a substring of `'inactive'`, `'active' in 'suspended,expired,inactive'` evaluates to `True`!
* **Exact Target Files**:
  * `customer_portal/views.py` (`portal_dashboard`)
  * `customer_portal/templates/customer_portal/portal_dashboard/_left_column.html`
  * `customer_portal/templates/customer_portal/portal_dashboard/_right_column.html`
  * `customer_portal/templates/customer_portal/portal_dashboard/_modals.html`
  * `customer_portal/templates/customer_portal/portal_dashboard/_scripts.html`
* **1-Step Fix**:
  * In `customer_portal/views.py`, compute a strict boolean `is_account_suspended = customer.status in ['suspended', 'expired', 'inactive']` and pass it to context.
  * In the portal templates and JS, replace all occurrences of `{% if customer.status in 'suspended,expired,inactive' %}` with `{% if is_account_suspended %}`.

### ERR-021: Server Error (500) on Cignal Dashboard When Pending Applications Exist (`VariableDoesNotExist: Failed lookup for key [username]`)
* **Symptoms**:
  * `/cignal-dashboard/` loads fine when there are zero pending Cignal applications.
  * As soon as a subscriber submits a Cignal Play or Cignal Box request via the customer portal, visiting `/cignal-dashboard/` crashes with `Server Error (500)`.
  * Traceback shows `django.template.base.VariableDoesNotExist: Failed lookup for key [username] in <Customer: ...>` or `AttributeError: 'Customer' object has no attribute 'username'`.
* **Root Causes**:
  * In `billing/templates/billing/cignal_dashboard.html`, the customer link inside the applications table rendered `{{ app.customer.full_name|default:app.customer.username }}`.
  * In Django template filter expressions, arguments (like `app.customer.username`) are evaluated strictly without silent suppression.
  * The `Customer` model in Gametech has `pppoe_username`, not `username`. Because `Customer` lacked a `username` attribute, Django failed to resolve the filter argument and raised `VariableDoesNotExist`.
* **Exact Target Files**:
  * `billing/models.py` (`Customer`)
  * `billing/templates/billing/cignal_dashboard.html`
### ERR-022: Customer Profile Shows Disconnected / Offline After Router Transfer While Still Active on Old Router
* **Symptoms**:
  * A customer is transferred from Router A to Router B in the system (via Sync Manager, Customer List, or Edit Profile).
  * In the Customer Profile (`/customers/view/<id>/`), the status dot is red and says "Disconnected", even though the subscriber's modem is actively online on Router A.
  * Clicking "Kick Session" in the profile fails with "No active session found".
* **Root Causes**:
  * `api_customer_mikrotik_status` in `billing/views/api/network.py` and `customer_kick_session` in `billing/views/customers/actions.py` queried ONLY `customer.mikrotik_device` (Router B).
  * Because the secret was removed on Router A without kicking (`kick_active=False` from ERR-018), the session remained on Router A, invisible to Router B.
* **Exact Target Files**:
  * `billing/views/api/network.py` (`api_customer_mikrotik_status`)
  * `billing/views/customers/actions.py` (`customer_kick_session`, `bulk_transfer_router`)
  * `billing/signals.py` (`sync_customer_to_mikrotik`)
  * `billing/templates/billing/view_customer/_scripts.html`
  * `network_manager/sync_services.py` (`get_all_pppoe_users`)
* **1-Step Fix**:
  * In `billing/views/api/network.py`, if status is Disconnected on assigned router, check `live_monitoring_data` cache and other routers. If found active, report `mt_status: "Connected"`, `is_different_router: True`, and `connected_router_name`.
  * In `customer_kick_session`, if session not on assigned router, search and kick on other routers.
  * In `bulk_transfer_router` and transfer modals, provide a `kick_now` option (default checked) to immediately disconnect the old router session so the modem reconnects to the new router right away.

---

### ERR-023: OpenStreetMap Map Tiles Blocked with 403 Access Blocked (`osm.wiki/Blocked`)
* **Symptoms**:
  * In customer profiles (`/customers/view/<id>/`), customer edit/add, or Geo Map (`/geomap/`), map tiles fail to load.
  * Map displays repeated 403 tile warning images stating: `Access blocked: App is not following the tile usage policy of OpenStreetMap's volunteer-run servers: osm.wiki/Blocked`.
* **Root Causes**:
  * OpenStreetMap (`tile.openstreetmap.org`) has enforced strict rate-limiting and User-Agent policies against direct web requests from web applications.
* **Exact Target Files**:
  * `billing/templates/billing/view_customer/_scripts.html`
  * `billing/templates/billing/geomap.html`
  * `billing/templates/billing/edit_customer.html`
  * `billing/templates/billing/add_customer.html`
  * `network_manager/templates/network_manager/nap_form.html`
* **1-Step Fix**:
  * Replace `tile.openstreetmap.org` with CartoDB Voyager (`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png`) for light mode and Dark Matter (`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`) for dark mode with `subdomains: 'abcd'` and maxZoom: 20.

---

### ERR-024: False-Positive "Offline (Router Off)" on Isolated or Lab MikroTik Routers
* **Symptoms**:
  * In customer profiles (`/customers/view/<id>/`), a customer without an active PPPoE tunnel displays `● Offline (Router Off)` instead of `● Disconnected (Inactive)`, even though the MikroTik router is online and communicating via API.
* **Root Causes**:
  * `api_customer_mikrotik_status` in `billing/views/api/network.py` executed a RouterOS ping to `8.8.8.8` whenever a customer had no active session.
  * On lab routers or isolated subnets lacking a direct WAN internet gateway, `ping 8.8.8.8` returns `status: "no route to host"`.
  * The code treated `no route to host` identically to a lost uplink timeout, erroneously overriding the customer's status to `Offline (Router Off)`.
* **Exact Target Files**:
  * `billing/views/api/network.py` (`api_customer_mikrotik_status`)
* **1-Step Fix**:
  * Exclude `no route to host` from the router ping loss check so isolated routers without public internet routes are not diagnosed as offline, accurately leaving disconnected subscribers as `Disconnected (Inactive)`.

---

### ERR-025: Dark Mode Overridden by body:not(.dark-mode) Selector Specificity Trap
* **Symptoms**:
  * On `/cignal-dashboard/`, toggling Dark Mode turns the topbar and sidebar dark, but cards and tables remain bright white, with light/washed-out text and unreadable table headers.
* **Root Causes**:
  * Gametech's theme toggle attaches `.dark-mode` to `document.documentElement` (`<html class="dark-mode">`), NOT `<body>`.
  * Selectors written as `body:not(.dark-mode) .card` matched 100% of the time (even in dark mode) because `body` never carried the `.dark-mode` class, overriding dark mode styling.
* **Exact Target Files**:
  * `billing/templates/billing/cignal_dashboard/_styles.html`
  * `billing/templates/billing/base.html`
  * `billing/templates/billing/base/_scripts.html`
* **1-Step Fix**:
  * Remove `body:not(.dark-mode)` selectors and use standard base styles for light mode with `.dark-mode` overrides for dark mode. Ensure `base.html` and `_scripts.html` synchronize `.dark-mode` onto both `documentElement` and `document.body`.

---

### ERR-026: Third-Party Carto Basemap Watermark ("API KEY REQUIRED carto.com/basemaps/apikey")
* **Symptoms**:
  * In customer profiles (`/customers/view/<id>/`), customer edit/add (`/customers/edit/<id>/`, `/customers/add/`), Geo Map (`/geomap/`), or NAP box forms (`/network/naps/add/`), Leaflet maps render with giant diagonal watermark text: `"API KEY REQUIRED carto.com/basemaps/apikey"`.
* **Root Causes**:
  * Carto CDN deprecated open raster basemap endpoints (`cartocdn.com/dark_all/` and `cartocdn.com/rastertiles/voyager/`), enforcing mandatory registered API keys and rendering watermark overlays when accessed without authorization tokens.
* **Exact Target Files**:
  * `billing/templates/billing/edit_customer.html`
  * `billing/templates/billing/add_customer.html`
  * `billing/templates/billing/view_customer/_scripts.html`
  * `billing/templates/billing/geomap.html`
  * `network_manager/templates/network_manager/nap_form.html`
  * `billing/templates/billing/base/_styles.html`
* **1-Step Fix**:
  * Switch `L.tileLayer` across all map templates to OpenStreetMap Foundation (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`).
  * Add a global hardware-accelerated CSS inversion filter in `billing/templates/billing/base/_styles.html` (`html.dark-mode .leaflet-tile-pane { filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7); }`) so standard OSM tiles cleanly adapt to dark slate mode without needing separate dark raster tile providers or API keys.

---

### ERR-027: Form Select Dropdowns Rendering Light Mode / Illegible White Options in Dark Mode
* **Symptoms**:
  * In Customer Edit (`/customers/edit/<id>/`) and Customer Add (`/customers/add/`), `<select>` dropdowns (Account Type, Agent, Mikrotik Device, Subscription Plan, Barangay) render in browser light mode or display an unstyled white option list with invisible/washed-out white text.
* **Root Causes**:
  * Native `<select>` elements lack explicit `<option>` and `<optgroup>` dark mode background colors (`#1a1d2d`), causing OS/browser select popups to fallback to default white.
  * Semi-transparent `rgba(15,23,42,0.5)` backgrounds on `.plan-form-control` trigger browser light popup behavior.
  * TomSelect initialization uncaught exceptions on `<optgroup>` elements halted dropdown transformation across remaining form selects.
* **Exact Target Files**:
  * `billing/templates/billing/base/_styles.html`
  * `static/css/theme/tokens_and_base.css`
  * `static/css/theme/components.css`
  * `billing/templates/billing/edit_customer.html`
  * `billing/templates/billing/add_customer.html`
* **1-Step Fix**:
  * Define opaque `#1a1d2d` dark background and `#f8fafc` text for `.plan-form-control`, `select.plan-form-control option`, `select.plan-form-control optgroup`, and TomSelect `.ts-control` / `.ts-dropdown`.
  * Style focus state with system primary blue (`border-color: #38bdf8; box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25)`).
  * Wrap TomSelect initialization in `try ... catch` and skip `sortField` on `<optgroup>` dropdowns.

---

### ERR-028: Multi-Subscription Cignal Tracking & Manual Payment/Expiration Synchronization
* **Symptoms**:
  * Customers with multiple Cignal boxes or subscriptions (e.g. Living Room TV, Master Bedroom) could only store a single scalar account number in `Customer.cignalplay_no` / `cignalbox_no`.
  * No standard modal existed to record partial installments or flexible manual reloads without automated Cignal API integration.
* **Root Causes**:
  * `CignalPlay` model lacked explicit `account_name`, `account_number`, `addon_type`, `amount_paid`, and `expiration_date` fields, relying on customer-level scalar strings.
  * Payment submission lacked a unified atomic workflow to log `Payment` transactions alongside Cignal expiration increments.
* **Exact Target Files**:
  * `billing/models.py` (`CignalPlay`)
  * `billing/migrations/0041_cignalplay_account_fields.py`
  * `billing/views/cignal_dashboard.py` (`process_cignal_payment`)
  * `billing/templates/billing/partials/_cignal_payment_modal.html`
  * `billing/templates/billing/view_customer/_info_cards.html` & `_modals.html`
  * `billing/templates/billing/cignal_dashboard.html`
* **1-Step Fix**:
  * Expand `CignalPlay` with `account_name`, `account_number`, `addon_type`, `amount_paid`, `expiration_date` (ForeignKey to Customer with property aliases and `save()` date sync).
  * Create `_cignal_payment_modal.html` with target account `<select>`, vanilla JS quick-fill pills (₱149, ₱399, ₱250, ₱3000), expiration date picker with +30/+60 day steppers, and wrap `process_cignal_payment` in `transaction.atomic()` to simultaneously log `Payment`, audit log, and update Cignal validity.

---

## 📝 How to Add a New Error Entry

1. Assign a new `ERR-XXX` identifier.
2. Fill in: **Symptoms**, **Root Causes**, **Exact Target Files**, and **1-Step Fix**.
3. Keep entries short, actionable, and sniper-focused.


