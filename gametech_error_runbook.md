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
| **ERR-037** | Cignal Reload Modal pre-fills old expiration date, confusing presets with duplicate ₱399 | `billing/templates/billing/partials/_cignal_payment_modal.html`, `_cignal_payment_modal_script.html`, `cignal_dashboard.py` | Billing / UI |
| **ERR-040** | Blinding Yellow Row for Expired Customers, Unreadable Text, and Stacked Status Column Bloat | `customer_list/_styles.html`, `_table.html`, `_scripts.html`, `_hero.html` | Frontend (CSS/UI) |
| **ERR-043** | System-Wide Tab Lag, Freezes, and 499 Timeouts on Customers Directory & Profiles | `network_manager/services/base.py`, `billing/views/api/network.py`, `billing/views/customers/list.py` | Hardware API / Caching |
| **ERR-044** | Installed Customer Displayed as Active / Connected Without Payment or Expiration Date | `billing/views/customers/crud.py`, `billing/views/customers/list.py`, `billing/models.py`, `add_customer.html` | Billing / Security |

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
  * OpenStreetMap Foundation volunteer tile servers (`tile.openstreetmap.org`) strictly ban automated web apps and rate-limit IP subnets without custom registered User-Agents.
* **Exact Target Files**:
  * `billing/templates/billing/view_customer/_scripts.html`
  * `billing/templates/billing/geomap.html`
  * `billing/templates/billing/edit_customer.html`
  * `billing/templates/billing/add_customer.html`
  * `network_manager/templates/network_manager/nap_form.html`
* **1-Step Fix**:
  * Switch `L.tileLayer` across all map templates to high-capacity Google Maps tile servers (`https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}` for streets/dark, `lyrs=y` for hybrid satellite) with `subdomains: ['0', '1', '2', '3']` and `maxZoom: 20`. This permanently eliminates both OSM 403 volunteer blocks and Carto API key watermarks.

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
  * Switch `L.tileLayer` across all map templates to Google Maps (`https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}` with `className: 'dark-tiles'` for dark mode, `lyrs=y` for hybrid satellite, and `lyrs=m` for normal streets).
  * Pair with hardware-accelerated CSS inversion filter in `billing/templates/billing/base/_styles.html` (`.dark-tiles, .leaflet-tile-pane img.dark-tiles { filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7) !important; }`) for dark slate mode. Zero watermarks, zero volunteer rate limits, 100% reliable.

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

### ERR-029: Changelog Audience Duality & Topbar Dropdown Bloat
* **Symptoms**:
  * The development changelog and topbar rocket dropdown displayed dense architectural jargon (foreign keys, atomic transactions, AST compilation) that was unintelligible to business owners, CSRs, and field technicians.
  * Inlining the entire multi-week release history inside `_topbar.html` caused severe template bloat (> 350 lines), violating the 400-Line Circuit Breaker law and risking div nesting imbalances.
* **Root Causes**:
  * Single-track technical release documentation without a presentation layer for non-technical operational summaries.
  * Monolithic topbar template housing the full system release notes alongside header controls.
* **Exact Target Files**:
  * `billing/templates/billing/base/_topbar.html`
  * `billing/templates/billing/base/_topbar_changelog.html` (extracted partial)
  * `billing/templates/billing/changelog.html`
* **1-Step Fix**:
  * Extract the dropdown markup out of `_topbar.html` into `_topbar_changelog.html` and include it with `{% include "billing/base/_topbar_changelog.html" %}`.
  * Implement glassmorphic pill switch (`.gt-cl-mode-toggle`) toggling `data-cl-mode="tech"` vs `data-cl-mode="staff"` on `<html>`, persisted across page loads via `localStorage.getItem('changelog_mode')`.
  * Structure entries with `.cl-dual-content` containing `.tech-content` and `.staff-content`, ensuring legacy entries lacking staff translations remain visible in both modes.

---

### ERR-030: 1970 Unix Epoch Downtime Display Bug & Billing vs. Hardware Status Ambiguity
* **Symptoms**:
  * On `/subscriptions/`, newly provisioned or inactive subscriber secrets displayed a bizarre downtime timestamp: `Down: jan/01/1970 00:00:00`.
  * Staff confused financial account standing with physical connectivity because both `STATUS` and `ROUTER STATUS` used identical `.status-badge` pill styling.
  * On `/customers/`, top stat pills blended network terminology ("Active & Online") into billing metrics, and lacked an explicit counter for accounts inactive past 7 days.
* **Root Causes**:
  * MikroTik RouterOS returns epoch zero (`jan/01/1970 00:00:00`) for the `last-logged-out` attribute on PPP secrets that have never established an active PPPoE session.
  * Both table columns reused the same badge styles, creating visual competition between paid status and router links.
  * Customer directory aggregations lacked `inactive` aggregation for accounts expired > 7 days or suspended/inactive.
* **Exact Target Files**:
  * `billing/views/customers/list.py`
  * `billing/views/api/dashboard.py`
  * `billing/templates/billing/customer_list/_hero.html`
  * `billing/templates/billing/customer_list/_styles.html`
  * `billing/templates/billing/partials/subscription_plans_table.html`
* **1-Step Fix**:
  * In `billing/views/api/dashboard.py`, sanitize `mt_downtime` to ignore strings containing `"1970"` or default zeroes.
  * In `subscription_plans_table.html`, guard `UPTIME / DOWNTIME` with `{% elif not customer.mt_downtime or "1970" in customer.mt_downtime %}` and render a clean gray `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle"><i class="fas fa-minus-circle me-1"></i> Never Connected</span>`.
  * Visually separate statuses: Use solid badges for Billing Status (`bg-success`, `bg-warning`, `bg-danger`, `bg-secondary`) and outline badges for Router Status (`border border-success text-success`, `border border-danger text-danger`).
  * In `billing/views/customers/list.py`, aggregate `inactive=Count("id", filter=Q(status__in=["suspended", "inactive", "pull out"]) | Q(expires_at__lte=seven_days_ago))` and update `_hero.html` pills to Total Subscribers, Active Accounts, Due Soon (≤ 7D), and Inactive (> 7D).

### ERR-031: Generic "Active but Offline" Overwrite on Customer View & Router Uplink Detection
* **Symptoms**:
  * On `/customers/view/<id>/`, subscriber Live MT Status badge persistently displayed generic `Active but Offline` even when the assigned MikroTik router lost internet uplink (`Offline (Router Off)`), when area/barangay outages occurred, or when secret/router issues were present.
* **Root Causes**:
  * In `billing/views/api/network.py` (`api_customer_mikrotik_status`), router uplink ping check explicitly bypassed `'no route to host'`, failing to detect offline routers when default gateways dropped.
  * In `billing/templates/billing/view_customer/_scripts.html`, the frontend condition `if (data.is_active_offline || data.mt_status === 'Active but Offline')` hardcoded `statusContainer.innerHTML = '... Active but Offline'`, completely overwriting specific statuses like `Offline (Router Off)`, `Area Outage`, `API Unreachable`, etc.
* **Exact Target Files**:
  * `billing/views/api/network.py`
  * `billing/templates/billing/view_customer/_scripts.html`
  * `billing/templates/billing/view_customer/_info_cards.html`
  * `billing/templates/billing/customer_list/_scripts.html`
* **1-Step Fix**:
  * In `billing/views/api/network.py`, evaluate router uplink ping with `successful = [p for p in ping_res if str(p.get("packet-loss", "100")) != "100" and "avg-rtt" in p]`; if not successful, set `data["mt_status"] = "Offline (Router Off)"`. Add explicit checks for `Secret Not Found on Router`, `Disabled on Router`, `No Router Assigned`, and `No PPPoE Configured`.
  * In `_scripts.html`, dynamically render `data.mt_status || 'Active but Offline'` within the badge rather than hardcoding static text.

### ERR-032: Customers Directory Badge Double-Stacking & False Outage on Uninstalled Subscribers
* **Symptoms**:
  * On `/customers/`, subscriber rows displayed two stacked status badges (e.g. `Active but Offline` in the billing column and another live badge beneath it).
  * Brand new customers without active installations or router connections (e.g., Cardo Dalisay) were falsely flagged as `Active but Offline` NOC outages, turning their rows red (`.table-row-paid-offline`) and inflating the "Paid but Offline" top counter.
* **Root Causes**:
  * `_table.html` included a redundant server-rendered `{% if customer.is_paid_offline %} Active but Offline` badge inside the billing column while `_scripts.html` simultaneously injected a live network badge in `conn-status-indicator`.
  * `_scripts.html` and `list.py` treated any subscriber who wasn't actively streaming PPPoE traffic as an outage if `status == 'active'`, ignoring whether they had never established their first physical connection (epoch zero `1970` downtime or null expiration).
* **Exact Target Files**:
  * `billing/views/customers/list.py`
  * `billing/views/api/network.py`
  * `billing/templates/billing/customer_list/_table.html`
  * `billing/templates/billing/customer_list/_scripts.html`
  * `billing/templates/billing/view_customer/_scripts.html`
* **1-Step Fix**:
  * In `_table.html`, strip the redundant `is_paid_offline` badge from the billing status column so only true billing states (Active, Expired, Pending) are rendered, while `conn-status-indicator` handles the single hardware state.
  * In `api/network.py` (`api_active_pppoe_usernames` and `api_customer_mikrotik_status`) and `list.py`, identify uninstalled subscribers via `never_connected_usernames` (secrets with `1970` or empty last-logged-out), `status == 'pending'`, or null `expires_at`.
  * Render a calm blue `⚙️ Pending Install` pill (`bg-info-subtle`) instead of the glowing red `.table-row-paid-offline` outage highlight, and exclude them from `stats["paid_but_offline"]`.

---

### ERR-033: Active / Transferred Subscriber Falsely Labeled as 'Pending Install' & Guesswork in Connection Diagnostics
* **Symptoms**:
  * Active, paid accounts (with valid expiration dates) transferred to a new router or newly provisioned secrets displayed `⚙️ Pending Install` on `/customers/` instead of technical outage status.
  * Staff/Admins had no specific insight into whether the offline state was caused by router uplink loss, API unreachability, or an active PPPoE session still held on the previous router.
* **Root Causes**:
  * `api_active_pppoe_usernames` flagged any secret with epoch zero `1970` `last-logged-out` as `never_connected_usernames`. Because a newly transferred subscriber hasn't established a session on the target router yet, their secret defaults to `1970`, causing `_scripts.html` to evaluate `isPendingInstall = true` despite `status == 'active'` and valid expiration.
  * `list.py` excluded `never_connected_usernames` from `paid_but_offline_ids`, omitting active subscribers from the Paid but Offline top counter.
* **Exact Target Files**:
  * `billing/views/customers/list.py`
  * `billing/views/api/network.py`
  * `billing/templates/billing/customer_list/_scripts.html`
* **1-Step Fix**:
  * ⚠️ **DEPRECATION NOTICE (Superceded by ERR-034)**: The previous fallback heuristic `is_pending_install = expires_at is None` is DEPRECATED as it falsely labeled existing unbilled or imported accounts as pending installation. Always use the explicit model field `customer.installation_status == 'pending'`.
  * Populate `user_router_map` (`{username: {router_id, router_name}}`) in `/api/active-usernames/`. If a session is active on a different router than assigned in Gametech, render an amber `Active on <RouterName>` badge.
  * In `_scripts.html`, detect router uplink offline (`Offline (Router Off)`), API failure (`Offline (Router API Down)`), and isolated client disconnections with actionable diagnostic modals via `showReason()`.

---

### ERR-034: Existing / Imported Subscriber Falsely Flagged as 'Pending Install' Due to Null Expiration Date
* **Symptoms**:
  * Existing subscribers added manually without an immediate expiration date, or accounts imported from MikroTik routers, displayed a blue `⚙️ Pending Install` badge in the Customer Directory (`/customers/`) and Profile (`/customers/view/<id>/`).
  * Staff had no setup type toggle when adding a customer to indicate whether the line was already installed on-site or awaiting technician dispatch.
* **Root Causes**:
  * Telemetry logic evaluated `is_pending_install = (status == 'pending') || (!expiresAt)`. Any account without an active expiration date was assumed to be an uninstalled subscriber awaiting technician setup.
  * Router import routines (`device_sync_users_api`, `bulk_import`) did not set installation flags or timestamps on imported PPPoE accounts.
* **Exact Target Files**:
  * `billing/models.py`
  * `billing/views/customers/crud.py`
  * `billing/views/customers/actions.py`
  * `billing/views/api/network.py`
  * `network_manager/views/devices.py`
  * `network_manager/views/sync.py`
  * `billing/templates/billing/add_customer.html`
  * `billing/templates/billing/edit_customer.html`
  * `billing/templates/billing/view_customer/_header_actions.html`
  * `billing/templates/billing/view_customer/_modals.html`
  * `billing/templates/billing/customer_list/_scripts.html`
* **1-Step Fix**:
  * Add `installation_status` (`installed` vs `pending`) and `installed_at` on `Customer` (defaulting existing accounts to `installed`).
  * Update `device_sync_users_api` and `bulk_import` to explicitly set `installation_status='installed'` and `installed_at=timezone.now()`.
  * Redesign `add_customer.html` with an Account Setup Selector (Installed/Existing vs For Installation/New) with optional initial due date.
  * In `api/network.py` and `_scripts.html`, check `customer.installation_status == 'pending'` instead of relying on null expiration dates.
  * Provide a 1-click `mark_customer_installed` action button and modal on Customer View.

---

### ERR-035: Incomplete Installation Activation Workflow (Missing Plan, Upfront Payment, & Auto First Due Date)
* **Symptoms**:
  * Clicking "Mark as Installed" on a pending subscriber only prompted for installation date and manual expiration, requiring staff to navigate separately to `/pay/` to record upfront installation payments or manually calculate the next billing cycle.
* **Root Causes**:
  * `mark_customer_installed` view and modal previously only updated `installed_at` and `expires_at` without accepting plan tier adjustments, upfront payment amounts, or executing automated prorated/full-month billing math.
* **Exact Target Files**:
  * `billing/views/customers/actions.py`
  * `billing/views/customers/crud.py`
  * `billing/templates/billing/view_customer/_modals.html`
  * `billing/templates/billing/view_customer/_modal_mark_installed.html`
* **1-Step Fix**:
  * Pass `plans` in `view_customer` context.
  * Modularize the installation confirmation modal into `_modal_mark_installed.html` with Plan selection, Upfront Payment collection (amount, method, ref #), and client-side real-time auto-calculation of First Due date.
  * Update `mark_customer_installed` backend view to update `customer.plan`, create a verified `Payment` record when upfront payment is collected, and push synchronized secrets to MikroTik.

---

### ERR-036: Dispatch System CRM Hook & Field Completion Decoupling
* **Symptoms**:
  * New customer applicants registered as "Pending Installation" were invisible to field dispatchers unless manually copied into external dispatch sheets or legacy monitoring databases.
  * Completing physical fiber installation in the field did not automatically update subscriber CRM records to active/installed status.
* **Root Causes**:
  * Legacy dispatch system operated on a standalone Node.js/Prisma database without foreign key linkage to `billing.Customer` or `network_manager.MikrotikDevice`.
  * Absence of a `post_save` CRM listener to orchestrate automated ticket generation upon applicant onboarding.
* **Exact Target Files**:
  * `dispatch/models.py` (`JobTicket` model with `customer` & `mikrotik_device` FKs)
  * `dispatch/signals.py` (`auto_create_dispatch_ticket_on_pending_install`)
  * `dispatch/views.py` (`api_complete_job` auto-promoting `installation_status='installed'` and `status='active'`)
  * `dispatch/templates/dispatch/dashboard.html` (Orchestrator pattern console with CartoDB Dark Matter map)
* **1-Step Fix**:
  * Connect `post_save` signal on `Customer` to automatically generate a `JobTicket` (type `INSTALLATION`, status `PENDING`) with customer GPS coords, plan, address, and assigned MikroTik router.
  * When technicians submit technical completion specs (NAP port, cable length, optical power dBm, ONT serial) in `api_complete_job`, automatically transition the linked customer to `installed` and `active`.

### ERR-037: Cignal Reload Modal Stale Expiration Pre-Fill, Duplicate ₱399 Presets, & Router Confusion
* **Symptoms**:
  * Opening the Cignal Reload modal (`_cignal_payment_modal.html`) populated "New Expiration Date" with the subscriber's *current* expiration date instead of an extended date. Submitting without manual date entry left the subscription's expiration date unchanged.
  * Staff was confused by two duplicate ₱399 preset buttons (`₱399 Load Only` vs `₱399 Box + Load`), and hardware installment buttons were visible for app-only customers.
  * Modal helper text incorrectly claimed expiration dates synchronize across MikroTik profiles.
* **Root Causes**:
  * `cpmOnSubscriptionChange` script read `data-exp` and directly assigned `dateInput.value = exp`, pre-filling the old date without adding +30 days.
  * Presets were hardcoded in a static list regardless of subscriber hardware setup (`hardware_payment_type`).
  * Backend `process_cignal_payment` allowed box installment payments to overwrite the TV load expiration date.
* **Exact Target Files**:
  * `billing/templates/billing/partials/_cignal_payment_modal.html`
  * `billing/templates/billing/partials/_cignal_payment_modal_script.html`
  * `billing/views/cignal_dashboard.py` (`process_cignal_payment`)
* **1-Step Fix**:
  * Add a dedicated Current Subscription Status card to `_cignal_payment_modal.html` displaying current due date, plan, and hardware setup.
  * Calculate ISP-standard rollover: `New Due Date = Current Expiration + 30 Days` (if active) or `Today + 30 Days` (if expired).
  * Dynamically show/hide hardware presets based on `data-hw` and `data-inst` (< 12 months), and display live extension preview banner.
### ERR-038: Redundant Cignal Subscription Confirmation Flash Message & One-Way Dispatch Desync
* **Symptoms**:
  * Staff saving or updating Cignal subscription details was greeted by an awkward, confusing red/pink flash message: `Cignal subscription 'Cignal Subscription' updated successfully.`
  * Marking a subscriber as installed in CRM left their open installation `JobTicket` orphaned in `PENDING` in the dispatch module.
  * Completing an installation ticket via generic status change (`api_update_status`) failed to activate the customer in CRM.
* **Root Causes**:
  * `edit_cignal_subscription` formatted messages using `f"Cignal subscription '{subscription.account_name}' updated successfully."`. When `account_name` fell back to default `"Cignal Subscription"`, the wording was duplicated. Unstyled alerts inherited red/pinkish styling, making success messages look like errors.
  * `dispatch/signals.py` only listened for pending install states without auto-completing tickets when `installation_status == 'installed'`, and lacked a `post_save` listener on `JobTicket` to handle 2-way completion sync.
* **Exact Target Files**:
  * `billing/views/cignal_dashboard.py` (`edit_cignal_subscription`)
  * `billing/templates/billing/cignal_dashboard.html` (styled emerald green flash messages block)
  * `dispatch/signals.py` (`auto_create_dispatch_ticket_on_pending_install` & `sync_ticket_completion_to_customer`)
* **1-Step Fix**:
  * In `cignal_dashboard.py`, format flash message as `f"Cignal details for {customer.full_name}{label} updated successfully."` and render alerts with `#ecfdf5` background, `#059669` text, checkmark icon, and dismiss button.
  * In `dispatch/signals.py`, auto-complete open installation tickets when a customer's `installation_status` changes to `'installed'`, and register a `post_save` on `JobTicket` to promote `customer.installation_status = 'installed'` and `customer.status = 'active'` whenever an installation ticket is marked `COMPLETED`.

### ERR-039: Cignal Date vs Time Expiry Blindspot, Ghost Active Subscribers, and Archive Purge Control
* **Symptoms**:
  * Setting Cignal subscription expiration date to today with an exact time (e.g., 2:00 PM) failed to expire when that time passed; changing the date to yesterday immediately marked it expired.
  * Clearing or cancelling Cignal subscriptions still showed them in the "Active Customers" KPI count (e.g. 2 active customers despite 0 subscriptions).
  * Removed subscriptions vanished completely instead of moving to an archive bar for administrative review.
  * An unwanted vertical scrollbar appeared in the right-column "Messages & Alerts" card.
* **Root Causes**:
  * `CignalPlay.is_active` stripped the time component (`exp = exp.date()`) and compared `exp >= timezone.localdate()`, treating any expiration today as valid for the entire 24-hour calendar day regardless of the hour/minute set.
  * `cignal_dashboard_view` matched customers with non-empty legacy strings `cignalplay_no` on the `Customer` record even if `cignal_plans` count was 0, and `cancel_cignal_subscription` hard-deleted records without clearing customer legacy fields.
  * `_recent_messages.html` had a fixed inline `max-height: 400px; overflow-y: auto; scrollbar-width: thin;`.
* **Exact Target Files**:
  * `billing/models.py` (`CignalPlay.is_active`, `is_cancelled`, `cancelled_at`, `cancelled_by`)
  * `billing/migrations/0045_cignalplay_cancellation_fields.py`
  * `billing/views/cignal_dashboard.py` (`cignal_dashboard_view`, `edit_cignal_subscription`, `cancel_cignal_subscription`, `restore_cignal_subscription`, `purge_cignal_subscription`)
  * `billing/templates/billing/cignal_dashboard/_active_subscriptions.html`
  * `billing/templates/billing/cignal_dashboard/_recent_messages.html`
  * `billing/templates/billing/partials/_cignal_edit_modal.html`
* **1-Step Fix**:
  * In `CignalPlay.is_active`, compare timezone-aware `datetime >= timezone.now()`, expiring subscriptions instantaneously when their exact target time elapses.
  * Filter active customers strictly by `cignal_plans__is_cancelled=False`, and provide segmented status tabs: **Active Subscriptions**, **Ongoing Installments (₱250/mo)**, **Fully Paid**, and **Cancelled / Archive Bar**.
  * Update cancellation to soft-delete (`is_cancelled=True`, `cancelled_at=now()`, `cancelled_by=user.username`), clear legacy fields on customer if no plans remain, and restrict permanent archive purging strictly to staff/admins (`user.is_staff`).
### ERR-040: Blinding Yellow Row for Expired Customers, Unreadable Text, and Stacked Status Column Bloat
* **Symptoms**:
  * In `/customers/` (Customers Directory), rows for expired customers render as a blinding pastel yellow bar (`#fffbeb`) across the dark mode table.
  * Cell text (`juan delacruz`, email, phone, plan) is light-colored, resulting in near-zero contrast and making customer information unreadable.
  * Status column contains 3 to 4 vertically-stacked contradictory badges (e.g. green `Active` + yellow `Due Oct 11` + red glowing `Active but Offline` + white button `!`; or pink `Expired` + red `Expired Sep 15` + orange `Offline` + button `!`), ballooning row height to 90–120px.
  * In `_hero.html`, "Paid but Offline" stat card has an uneven "Alert" tag squished next to the counter number.
* **Root Causes**:
  * `_table.html` applied Bootstrap's `.table-warning` to `<tr>` when `status == 'expired'`. Bootstrap forces `--bs-table-bg: #fff3cd`, and `_styles.html` hardcoded `#fffbeb`.
  * `updateConnectionStatuses` in `_scripts.html` appended redundant `Active but Offline` or `Offline` badges and a large `22px` circle button below the static Django badge without hiding or replacing the primary billing badge.
* **Exact Target Files**:
  * `billing/templates/billing/customer_list/_table.html`
  * `billing/templates/billing/customer_list/_styles.html`
  * `billing/templates/billing/customer_list/_scripts.html`
  * `billing/templates/billing/customer_list/_scripts_bulk.html`
  * `billing/templates/billing/customer_list/_hero.html`
* **1-Step Fix**:
  * In `_table.html`, replace `.table-warning` with custom `.table-row-expired` (`rgba(244, 63, 94, 0.06)` with `3px solid #f43f5e` left accent border).
  * In `_styles.html`, hard-neutralize Bootstrap `.table-warning` and `.table-secondary` in dark mode to guarantee no bright yellow background ever renders, normalize table headers (`0.74rem`) and cells (`0.83rem`), and style `.cust-status-wrap`.
  * In `_scripts.html`, when `updateConnectionStatuses()` detects `Active but Offline`, hide the static `.cust-base-badge` and render a single high-priority pill with an inline diagnostic button (`17px`); for non-active subscribers (`expired`, `inactive`), suppress redundant `Offline` pills.
  * In `_hero.html`, remove the squished "Alert" badge so all 6 stat cards maintain identical, balanced typography.

### ERR-041: Orphaned Dispatch Tickets and Queue Counters After Customer Deletion
* **Symptoms**:
  * After deleting customers in the CRM (/customers/), the Dispatch Operations Console (/dispatch/dashboard/) continues to show tickets in the Live Operational Queue (e.g. 5 Pending, 1 In Progress, 4 Completed) even though their customer profiles were removed.
* **Root Causes**:
  * `JobTicket.customer`, `DispatchRecord.customer`, and `MonitoringRecord.customer` models are defined with `on_delete=models.SET_NULL, null=True`. When a customer is deleted in Django, Django updates `customer_id=NULL` on the tickets but leaves the `JobTicket` records in the database with their cached `client_name`.
  * No `pre_delete` or `post_delete` signal existed on `Customer` to purge associated tickets and records upon customer removal.
* **Exact Target Files**:
  * `dispatch/signals.py`
  * `dispatch/views.py` (`api_delete_ticket`)
  * `dispatch/urls.py`
  * `dispatch/templates/dispatch/_ticket_list.html`
  * `dispatch/templates/dispatch/_tab_ticket_table.html`
  * `dispatch/templates/dispatch/_scripts.html`
* **1-Step Fix**:
  * In `dispatch/signals.py`, register a `@receiver(pre_delete, sender=Customer)` hook that automatically runs `JobTicket.objects.filter(customer=instance).delete()`, `DispatchRecord.objects.filter(customer=instance).delete()`, and `MonitoringRecord.objects.filter(customer=instance).delete()`.
### ERR-042: Server Error (500) on `/logout/` or Any Page Due to Raw Git Merge Conflict Markers
* **Symptoms**:
  * Navigating to `/logout/` or loading pages throws `Internal Server Error (500)`.
  * Container logs show: `SyntaxError: leading zeros in decimal integer literals are not permitted; use an 0o prefix for octal integers` at `>>>>>>> <commit_hash>` in `customer_portal/views/dashboard.py`.
* **Root Causes**:
  * An automated or manual `git merge` or remote pull was pushed to `origin/main` containing unresolved conflict markers (`<<<<<<< HEAD`, `=======`, `>>>>>>>`).
  * Because `gametech_core/urls.py` imports `customer_portal.urls` on any URL evaluation, a syntax error in an imported view crashes Django's URL resolver globally on all requests.
* **Exact Target Files**:
  * `customer_portal/views/dashboard.py`
* **1-Step Fix**:
  * Remove the git conflict markers, clean up imports (`from django.db.models import Q`, `import datetime`, `from billing.models import ... AddOnRequest`), compile with `python -m py_compile`, and restart Gunicorn: `docker restart gametech-billing-system_web_1`.

### ERR-043: System-Wide Tab Lag, Freezes, and 499 Timeouts on Customers Directory & Profiles
* **Symptoms**:
  * Severe delay (10–30s or timeout) when navigating tabs, loading `/customers/` (Customers Directory), or opening customer profiles (`/customers/<id>/`).
  * Nginx access logs show client connection aborts (`HTTP 499 0`) for `/customers/`, `/api/active-usernames/`, and `/api/router-uplink/`.
  * Container logs flooded with `Timeout/Error connecting to Mikrotik API on <ip>: timed out` or `[Errno 101] Network is unreachable`.
* **Root Causes**:
  1. Synchronous connection attempts to unreachable or dummy router IPs (e.g. `192.168.1.1` from seed data or down physical routers) holding Gunicorn worker threads for 5–10s per socket timeout.
  2. Sequential iteration across all routers in `/api/active-usernames/`, `/api/router-uplink/`, and `customer_list` without circuit breaker failure caching or payload caching, causing complete worker starvation.
* **Exact Target Files**:
  * `network_manager/services/base.py` (`MikrotikBase`)
  * `billing/views/api/network.py` (`api_active_pppoe_usernames`, `api_router_uplink`, `api_customer_mikrotik_status`)
  * `billing/views/customers/list.py` (`customer_list`)
  * `billing/management/commands/seed.py`
* **1-Step Fix**:
  1. In `network_manager/services/base.py`, implement a Redis circuit breaker (`router_unreachable_<id>` for 45s) on connection failures and reduce socket timeout to 2.0s. If cached unreachable, fail fast immediately in 0ms.
  2. In `billing/views/api/network.py`, cache `api_router_uplink_payload` (25s) and `api_active_pppoe_usernames_payload` (20s), and skip unreachable routers immediately.
  3. In `billing/views/customers/list.py`, check existing `live_monitoring_data` or API payloads before querying physical routers, and skip cached unreachable routers.
  4. Purge any dummy or unreachable seed routers (`192.168.1.1`) from the database.

### ERR-044: Installed Customer Defaults to Active & Grants Free Internet Without Payment
* **Symptoms**:
  * Newly created customer with `installation_status = 'installed'` shows as `Active` and `Connected` in `/customers/` but `Expired` in `/subscriptions/`.
  * Subscriber is active on MikroTik router without having made any payment and has `expires_at = None`.
  * Hero count mismatch between Customers Directory and Subscriptions.
* **Root Causes**:
  1. In `add_customer.html`, selecting "Installed / Existing Subscriber" set form status to `active`.
  2. `add_customer` view defaulted status to `"active"` for installed customers without checking if payment or expiration date existed.
  3. `Customer.STATUS_CHOICES` lacked canonical `"expired"` choice, causing inconsistent querying (`c.status == 'expired'`).
  4. MikroTik provisioning enabled PPPoE secrets for all `active` accounts regardless of payment or expiration dates.
* **Exact Target Files**:
  * `billing/models.py` (`STATUS_CHOICES`)
  * `billing/views/customers/crud.py` (`add_customer`)
  * `billing/views/customers/list.py` (`customer_list`)
  * `billing/views/api/dashboard.py` (`subscription_plans_data_api`)
  * `billing/templates/billing/add_customer.html` & `edit_customer.html`
* **1-Step Fix**:
  1. Add `("expired", "Expired")` to `Customer.STATUS_CHOICES`.
  2. In `add_customer` view, if `installation_status == 'installed'` and no expiration date or payment exists, force `cust_status = "expired"`.
  3. In `add_customer.html`, update "Installed / Existing Subscriber" card to set `statusSelect.value = 'expired'` and inform staff that newly installed accounts start expired until payment is logged or force-reactivated.
  4. In `customer_list` and `subscription_plans_data_api`, include `Q(status="expired")` in expired counts and filters.
  5. Kicking/suspending the unpaid PPPoE user on MikroTik via `api.suspend_pppoe_user()`.


### ERR-045: Team Reverse Relation 'members' vs 'technicians' & Un-namespaced Dashboard URL
* **Symptoms**:
  * `AttributeError: Cannot find 'technicians' on Team object, 'technicians' is an invalid parameter to prefetch_related()` when accessing `/dispatch/management/`.
  * `django.urls.exceptions.NoReverseMatch: 'billing' is not a registered namespace` when rendering `agents.html`.
* **Root Causes**:
  * In `dispatch/models.py`, `Technician.team` foreign key declares `related_name='members'`, NOT `'technicians'`. Querying `Team.objects.prefetch_related('technicians')` or calling `team.technicians.count` fails with AttributeError.
  * In `billing/urls.py`, URL patterns are included at the root level without namespace `billing:`. Calling `{% url 'billing:dashboard' %}` raises `NoReverseMatch`.
* **Exact Target Files**:
  * `dispatch/views.py` (`management_view`)
  * `dispatch/templates/dispatch/_management_teams_techs.html`
  * `billing/templates/billing/agents.html`
* **1-Step Fix**:
  * Use `Team.objects.prefetch_related('members')` in Python views and `{{ team.members.count }}` in templates.
  * Use non-namespaced `{% url 'dashboard' %}` across all core billing templates.

### ERR-046: Dispatch Pipeline Modal Ghosting & Instant Disappearing Under Backdrop Overlay
* **Symptoms**:
  * On `/dispatch/pipeline/2-assignment/`, `/dispatch/pipeline/4-qa/`, or `/dispatch/pipeline/5-approval/`, clicking "Assign Techs", "Conduct QA", or "Review & Decide" opens a dimmed/ghosted modal dialog that immediately disappears whenever clicked.
  * Form inputs, dropdowns, and checkboxes inside the modal cannot be clicked or focused.
* **Root Causes**:
  * Bootstrap `.modal` elements were rendered directly inside `<tbody>...</tbody>` within `<div class="table-responsive">` or cards.
  * In HTML, `<div>` elements inside `<tbody>` are foster-parented or trapped in the table container's local stacking context.
  * Bootstrap attaches `.modal-backdrop` directly to `<body>` at `z-index: 1050`. Because the parent container has a lower stacking context, the backdrop renders *in front of* the modal dialog, intercepting user clicks and triggering Bootstrap's backdrop click-to-dismiss behavior.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/pipeline/2_assignment.html`
  * `dispatch/templates/dispatch/pipeline/4_qa.html`
  * `dispatch/templates/dispatch/pipeline/5_approval.html`
  * `dispatch/pipeline_views.py` (`dispatch_assignment`)
* **1-Step Fix**:
  * Move all modal definitions completely outside `<tbody>`, `<table>`, and card wrappers to the page container level right before `{% endblock %}`.
  * Provide an explicit submit button in modal footers to guarantee clean submission without depending on missing slider classes.
  * Support both `tech_ids` and `technician_ids` in `pipeline_views.py`.

### ERR-047: DataTables warning: table id=agentsDataTable - Incorrect column count (TN/18)
* **Symptoms**:
  * Browser alert popup on `/agents/`: `DataTables warning: table id=agentsDataTable - Incorrect column count. For more information about this error, please see http://datatables.net/tn/18`.
* **Root Causes**:
  * The table `agentsDataTable` declared 7 column headers in `<thead>`.
  * When no agents existed in the database, the template rendered `{% empty %} <tr><td colspan="7">...</td></tr>`.
  * DataTables client-side DOM parser does not support `colspan` on `<tbody>` rows and counts only 1 cell on row 0, detecting a mismatch against the 7 `<th>` elements and throwing Tech Note 18.
* **Exact Target Files**:
  * `billing/templates/billing/agents.html`
  * `billing/templates/billing/agents/_table.html`
  * `billing/templates/billing/agents/_scripts.html`
* **1-Step Fix**:
  * Remove `{% empty %} <tr><td colspan="7">...</td></tr>` from inside the DataTables `<tbody>`.
  * Configure DataTables `language.emptyTable` and `language.zeroRecords` to render the empty state dynamically across all columns without DOM count mismatches.

### ERR-048: Missing Staff Deletion Endpoint & Resurrect Bug
* **Symptoms**:
  * On `/staff/` (Staff & Admins directory), administrators were unable to delete staff accounts because only an "Edit" button was rendered.
  * No `delete_staff` endpoint or view existed in the system.
* **Root Causes**:
  * The system previously only implemented `add_staff` and `edit_staff` without a deletion handler or delete button.
  * In `staff_list`, Django `auth_user` records with `is_staff=True` or `is_superuser=True` are auto-synced into `SystemAdmin` records. Any deletion of `SystemAdmin` alone would cause the record to immediately reappear on the next page load if the underlying `auth_user` was not also deleted or stripped of `is_staff`.
* **Exact Target Files**:
  * `billing/views/staff.py` (`delete_staff`)
  * `billing/urls.py` (`staff/delete/<int:pk>/`)
  * `billing/templates/billing/staff_and_admins.html`
  * `billing/templates/billing/edit_staff.html`
* **1-Step Fix**:
  * Implement `delete_staff` with self-deletion protection, atomic deletion of both `SystemAdmin` and `User` (or deactivation/staff revocation if restricted by immutable dispatch foreign keys), and session cache invalidation.
  * Add confirmation-guarded Delete buttons in `staff_and_admins.html` actions column and `edit_staff.html` footer.

---

### ERR-049: Field Unit Management Django Admin Redirects & Missing CRUD/Deletion Actions
* **Symptoms**:
  * On `/dispatch/management/`, clicking "Add Account" or "Edit" on staff accounts redirected users out of Gametech into raw `/admin/auth/user/` Django admin panels.
  * Adding or editing Teams and Technicians in Tab 2 and configuring installation quotas in Tab 3 redirected to `/admin/dispatch/team/` and `/admin/dispatch/technician/`.
  * Users could not delete staff accounts, teams, or technicians on the management console.
* **Root Causes**:
  * Action buttons in `_management_accounts.html`, `_management_teams_techs.html`, and `_management_targets.html` were hardcoded with raw `href="/admin/..."` links without native modal forms or API endpoints.
  * No backend CRUD endpoints existed for `Team` and `Technician` operations in `dispatch/`.
* **Exact Target Files**:
  * `dispatch/views_management.py` (Created: handles `management_view`, `api_team_*`, `api_technician_*`, `api_technician_targets_update`, `api_config_options_*`)
  * `dispatch/views.py` (Import `views_management`, removed redundant code)
  * `dispatch/urls.py` (Mapped management API routes)
  * `dispatch/templates/dispatch/_management_accounts.html`
  * `dispatch/templates/dispatch/_management_teams_techs.html`
  * `dispatch/templates/dispatch/_management_targets.html`
  * `dispatch/templates/dispatch/_management_modals.html`
  * `dispatch/templates/dispatch/_management_scripts.html`
* **1-Step Fix**:
  * Replace `/admin/` links in Accounts tab with native Gametech `add_staff`, `edit_staff`, and `delete_staff` routes.
  * Add native Bootstrap modals (`#modal-add-team`, `#modal-edit-team`, `#modal-add-tech`, `#modal-edit-tech`, `#modal-edit-target`) and wire them up with REST API endpoints in `views_management.py` with full audit logging and confirmation prompts for deletions.

---

### ERR-050: Modal Alert Hijacked into Topbar Floating Toast on Dispatch Page Load
* **Symptoms**:
  * An amber alert box (`⚠️ This will cancel the ticket. Technician attempted to reach client 3 times with no response. If the client comes back, the agent must create a new ticket.`) unexpectedly pops up floating in the top-right corner over the topbar and page header whenever opening any tab related to dispatch (Dashboard, Internet Install, Cignal Install, etc.).
* **Root Causes**:
  * In `billing/templates/billing/base/_scripts.html`, a global DOM handler converts `.content-wrapper .alert` elements into floating toasts on page load. It only excluded alerts inside forms (`if(alert.closest('form')) return;`), but did NOT exclude alerts inside modals (`.modal`).
  * In `dispatch/templates/dispatch/_modals.html`, `#modal-mark-unreachable` did not wrap its body in a `<form>` (unlike other modals), causing its inner `.alert.alert-warning` to be selected, detached from the modal, and appended into `#toast-container` at `top: 20px; right: 20px;` on every dispatch page load.
* **Exact Target Files**:
  * `billing/templates/billing/base/_scripts.html` (Added `|| alert.closest('.modal')` to toast converter)
  * `dispatch/templates/dispatch/_modals.html` (Wrapped `#modal-mark-unreachable` in `<form id="form-mark-unreachable">`, added `style="display: none;"`)
* **1-Step Fix**:
  * Update `base/_scripts.html` line 204 to `if (alert.closest('form') || alert.closest('.modal')) return;` so modal alerts are never converted into page toasts.
  * Wrap `#modal-mark-unreachable` in `<form id="form-mark-unreachable" onsubmit="event.preventDefault();">` for structural consistency.

---

### ERR-051: Staff Edit 404 on User ID, Native confirm() Popups, Duplicate Buttons & Dispatch Pipeline Confusion
* **Symptoms**:
  * Clicking "Edit" on staff accounts in `/dispatch/management/` returned 404 Not Found (`/staff/edit/11/`).
  * Deleting staff members, tickets, or teams showed ugly native browser alert windows (`143.198.207.144 says: Are you sure...?`).
  * Master Log, Internet Install, Cignal Install, and Client Concerns headers showed two redundant buttons side-by-side (`[New Ticket]` and `[+ Add Record]`) that performed the same action, confusing staff.
  * Staff looking at Ongoing and Pending dispatch ticket rows could not tell what type of job was ongoing (Repair, Install, Cignal, Relocation).
  * Clicking "Complete" on an ongoing ticket row navigated away from the monitoring console to a duplicate-looking pipeline stage (`pipeline/4-qa/?q=TKT-...`) with an empty QA state.
  * Pipeline pages had vague "Back to Console" buttons that confused non-technical staff.
  * Creating a job ticket allowed unlinked entries or failed to autofill customer details upon selection.
* **Root Causes**:
  * `edit_staff` queried `SystemAdmin` by `pk=pk` without falling back to `User` ID, causing 404s when editing users whose `SystemAdmin` record was missing or keyed by a different ID.
  * Native JavaScript `confirm(...)` was used inline across templates instead of the project's SweetAlert2 design system.
  * Both modern `modal-create-ticket` and legacy unlinked `addRecordModal` buttons were rendered side-by-side in dispatch log headers.
  * In `_queue_tabs.html`, the "Complete" button was linked via `href="{% url 'dispatch_qa' %}?q=..."` rather than opening the in-page completion modal (`.btn-open-complete`).
  * Pipeline templates labeled return links as "Console" rather than "Back to Dispatch Dashboard".
  * Input elements in `#form-create-ticket` lacked `name` attributes matching autocomplete target selectors, preventing automatic population.
* **Exact Target Files**:
  * `billing/views/staff.py` (`edit_staff`, `delete_staff` dual ID resolution)
  * `billing/templates/billing/base/_scripts.html` (Added `window.gametechConfirm` helper & form interceptor)
  * `billing/templates/billing/staff_and_admins.html` & `billing/templates/billing/edit_staff.html`
  * `dispatch/templates/dispatch/_management_accounts.html` & `_management_scripts.html`
  * `dispatch/templates/dispatch/_queue_tabs.html` (Added Job Type badges, wired Complete button to in-place modal)
  * `dispatch/templates/dispatch/dispatch_monitoring.html`, `internet_install.html`, `cignal_install.html`, `client_concerns.html` (Removed redundant `+ Add Record` button)
  * `dispatch/templates/dispatch/pipeline/*.html` (Clarified `Back to Dispatch Dashboard` buttons)
  * `dispatch/templates/dispatch/_modals.html` & `_customer_autocomplete.html` (Full customer autofill & mandatory linking)
  * `dispatch/views.py` (`api_create_ticket` customer validation)
* **1-Step Fix**:
  * Update `edit_staff` to resolve by `SystemAdmin.id` or `User.id` and auto-sync missing records.
  * Replace all `confirm(...)` calls with `window.gametechConfirm` SweetAlert2 dialogs.
  * Remove the redundant `+ Add Record` button from headers, leaving a single `+ New Job Ticket` action.
  * Replace the pipeline redirect on the Complete button with in-page modal invocation (`.btn-open-complete`).
  * Ensure full customer selection autofill (phone, address, barangay, plan, router, GPS) and block job order creation without selecting a valid CRM customer.

---

### ERR-052: Sales Agents UI Clutter, Native confirm() Popups & Disjointed Navigation
* **Symptoms**:
  * Deleting sales agents in `/agents/` displayed native browser popups (`143.198.207.144 says: Delete this agent profile?`).
  * Deleting agents or logging out triggered unstyled native alerts.
  * Registering a new agent required leaving the directory and navigating to `/billing/add-agent/`, confusing non-technical staff.
  * The directory table had separate confusing "Qualified" (1/5) and "Cashout Status" columns that created visual clutter.
* **Root Causes**:
  * `billing/templates/billing/agents/_table.html` had inline `onsubmit="return confirm(...)"` on both mobile cards and desktop table action buttons.
  * `_sidebar.html` and `_topbar.html` logout forms used native `return confirm(...)`.
  * No in-page modal was provided for fast agent creation, forcing full page navigation.
* **Exact Target Files**:
  * `billing/templates/billing/agents/_table.html` (Replaced `confirm` with `data-confirm-delete`, merged payout status)
  * `billing/templates/billing/agents/_stats.html` (Simplified headers, wired in-page modal button)
  * `billing/templates/billing/agents/_scripts.html` (Updated DataTable column definitions to target 5)
  * `billing/templates/billing/agents/_add_agent_modal.html` (New in-page agent registration modal)
  * `billing/templates/billing/base/_sidebar.html` & `_topbar.html` (Replaced logout `confirm` with `data-confirm`)
* **1-Step Fix**:
  * Replace native confirms with `data-confirm-delete` and `data-confirm` attributes intercepted by `window.gametechConfirm`.
  * Add `_add_agent_modal.html` and include it in `agents.html` so staff register agents in 1 click without leaving the page.
  * Consolidate table columns into a readable 6-column layout with a combined "Payout Status" indicator.

### ERR-053: Missing Job Type Badges & Missing Complete Button in Stage 2 Ongoing Queue
* **Symptoms**:
  * Staff viewing the Pending Queue or Ongoing / Dispatched Jobs in Stage 2 Crew Assignment (`/dispatch/pipeline/2-assignment/`), QA (`/dispatch/pipeline/4-qa/`), or Approval (`/dispatch/pipeline/5-approval/`) could not tell what type of pending/ongoing job a ticket was (Internet Install, Repair/Concern, Cignal Box, Relocation, Migration, Pull Out).
  * Ongoing ticket rows in Stage 2 only showed the customer name and address, completely omitting the package/plan or specific client concern.
  * Staff had no button or action to mark an ongoing dispatched job as completed/finished from the Stage 2 table (only `Brief` and `Undispatch` were present).
* **Root Causes**:
  * `2_assignment.html`, `4_qa.html`, and `5_approval.html` only rendered `ticket.ticket_number`, client name, and address, omitting `ticket.ticket_type` badges and `ticket.concern` / `ticket.plan_package`.
  * `2_assignment.html` ongoing actions omitted the `.btn-open-complete` button wired to `#modal-complete-job`.
  * Inline badge duplication in `_queue_tabs.html` bloated the template over 400 lines without a reusable component.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/_ticket_type_badge.html` (Created canonical, DRY job type badge partial)
  * `dispatch/templates/dispatch/pipeline/2_assignment.html` & `_assign_modals.html` (Added badge, concern/plan display, and `.btn-open-complete` action button, modularized modals)
  * `dispatch/templates/dispatch/pipeline/4_qa.html` & `5_approval.html` (Added badge and concern/plan display)
  * `dispatch/templates/dispatch/_queue_tabs.html` & `_tab_ticket_table.html` (Unified to use `_ticket_type_badge.html`)
* **1-Step Fix**:
  * Create `_ticket_type_badge.html` and include it alongside `ticket.ticket_number` in all pipeline and queue templates.
  * Add the green `Complete` button (`.btn-open-complete`) to Ongoing rows in `2_assignment.html` to invoke the `#modal-complete-job` technical completion popup.
  * Render `ticket.concern` or `ticket.plan_package` under the client name in Ongoing/Pending tables and assignment modals so dispatchers immediately understand job requirements.

### ERR-054: Redundant Page Redirection on Dispatch Button Bouncing Users into Stage 2 Pipeline
* **Symptoms**:
  * Staff clicking the blue "Dispatch" button on pending ticket rows in the Central Dispatch HQ Console (`/dispatch/monitoring/`, `/dispatch/internet-install/`, `/dispatch/cignal-install/`, `/dispatch/client-concerns/`) were redirected to a completely separate page (`/dispatch/pipeline/2-assignment/?q=...`).
  * The destination page presented an identical pending queue table with duplicate tabs, confusing staff who were just trying to assign field units to a ticket.
* **Root Causes**:
  * In `dispatch/templates/dispatch/_queue_tabs.html`, the Dispatch button was coded as a hyperlink `<a href="{% url 'dispatch_assignment' %}?q=...">` rather than an in-place modal trigger.
  * An in-place assignment modal (`#modal-assign-ticket`) and AJAX submission endpoint (`/dispatch/api/tickets/<id>/assign/`) already existed in `_modals.html` and `_scripts.html` but were bypassed by this link.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/_queue_tabs.html` (Converted `<a>` redirect into `<button class="btn-open-assign">` modal trigger with ticket type and concern data attributes)
  * `dispatch/templates/dispatch/_modals.html` (Enhanced `#modal-assign-ticket` header card to display ticket type and concern)
  * `dispatch/templates/dispatch/_scripts.html` (Wired `.btn-open-assign` to populate ticket type and concern in modal)
* **1-Step Fix**:
  * Replace the `<a href="{% url 'dispatch_assignment' %}">` redirect with `<button class="btn-open-assign">` so clicking "Dispatch" opens the crew assignment modal directly inside the console without page hopping.

---

## 📝 How to Add a New Error Entry

1. Assign a new `ERR-XXX` identifier.
2. Fill in: **Symptoms**, **Root Causes**, **Exact Target Files**, and **1-Step Fix**.
3. Keep entries short, actionable, and sniper-focused.






