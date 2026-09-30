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
| **ERR-057** | Dispatch Queue Tab Count Mismatch, Missing Tab 4 Records, and Inactive QA Approval Queue | `dispatch/views.py`, `pipeline_views.py`, `_queue_tabs.html`, `4_qa.html` | Queue / Pipeline |
| **ERR-058** | Dispatch Trash Can Delete Buttons Inactive and 403 Forbidden for Non-Staff CSR Accounts | `dispatch/_modal_scripts.html`, `dispatch/views.py`, `dispatch/urls.py` | Queue / API |
| **ERR-059** | Disconnected Operations Pipeline: Missing Repair Intake, Missing Tech Confirmation Guard, and Duplicate Dispatch Job Tickets | `dispatch/views.py`, `pipeline_views.py`, `_modal_scripts.html`, `view_customer.html` | Operations / Dispatch |
| **ERR-060** | Unconsumed Internal Flash Messages Leaking to Public Login Screen Styled as Alarming Red Error Banners | `billing/templates/billing/base.html`, `login.html`, `billing/views/auth.py`, `customer_portal/views/auth.py` | Auth / Messages |
| **ERR-063** | Customer Portal Modal Backdrop Freeze on Plan Selection & Close | `_modals.html`, `plan_card.html`, `portal_dashboard.html`, `_scripts.html` | Frontend (Modals) |
| **ERR-071** | `Conflicting migrations detected; multiple leaf nodes` OR `references nonexistent migration 00XX` | `billing/migrations/`, `dispatch/migrations/` | DB / Migrations |
| **ERR-072** | New sidebar subtab link never renders for any role, including Admin | `billing/models.py` (`subtab_specs`), `billing/views/staff.py` (`ROLE_MODULE_SPECS`) | Auth / Navigation |
| **ERR-073** | Feature page is built and renders but nothing in the UI can open it; dead partials left behind | `base/_sidebar.html`, `settings.html`, `admin_panel.html` | Navigation (Dead Ends) |
| **ERR-074** | Table rows shifted one column vs header; empty-state `colspan` wrong | `payment_logs.html` (any table with a gated `<th>`) | Frontend (Table) |
| **ERR-075** | All containers gone, every page returns `000`, `No such container` | `/root/GAMETECH-BILLING-SYSTEM`, `docker-compose.yml` | Deployment / Outage |
| **ERR-076** | Bare `NameError: name 'XForm' is not defined` on a few pages only; rest of app healthy | view module's import block, e.g. `billing/views/settings.py` | Python / Views |
| **ERR-080** | DB Backup button redirects to Settings instead of downloading a file | `billing/views/settings.py` (`backup_database_view`) | Backend / Backup |
| **ERR-065** | Blinding White Cards on Dispatch Dashboard in Dark Mode & Table Contrast Degradation | `dispatch/dashboard.html`, `_monitoring_page_styles.html`, `_gt_design_system.html` | Frontend (Theme/CSS) |
| **ERR-066** | Broken Light Theme, Overlapping Badges, Solid Blue Router Pill, and Unsynced Runtime Charts | `_gt_design_system.html`, `customer_list/_table.html`, `_scripts.html`, `tokens_and_base.css` | Frontend (Theme/CSS) |
| **ERR-077** | DB Backup button redirects to Settings instead of downloading a file | `billing/views/settings.py` (`backup_database_view`) | Backend / Backup |

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

### ERR-055: Annoying Browser Confirmation Popups on Undispatch and Dispatch Operations
* **Symptoms**:
  * Staff clicking "Undispatch" on assigned/ongoing tickets received an annoying native browser confirmation prompt: `143.198.207.144 says: Undispatch ticket TKT-... and return to Pending assignment queue? [OK] [Cancel]`.
  * Actions like logging failed calls ("No Answer") or sending welcome SMS triggered native browser `confirm(...)` modals, creating repetitive friction during high-volume operations.
* **Root Causes**:
  * `dispatch/templates/dispatch/pipeline/2_assignment.html` had `data-confirm="..."` on the undispatch form, which invoked `window.gametechConfirm`. When SweetAlert2 was unavailable or fallback triggered, it defaulted to native `window.confirm(...)`.
  * `dispatch/templates/dispatch/_scripts.html` wrapped undispatch and contact attempts in `gametechConfirm` and `confirm(...)`.
  * `dispatch_monitoring.html`, `internet_install.html`, `client_concerns.html`, `cignal_install.html`, and `3_tech_mobile.html` had inline `if (!confirm(...)) return;` checks.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/pipeline/2_assignment.html` (Removed `data-confirm` on undispatch form)
  * `dispatch/templates/dispatch/_scripts.html` (Converted undispatch, contact attempt, and welcome SMS to instant execution with button spinners)
  * `dispatch/templates/dispatch/dispatch_monitoring.html`, `internet_install.html`, `client_concerns.html`, `cignal_install.html` (Removed `if (!confirm(...))` from undispatch clicks)
  * `dispatch/templates/dispatch/pipeline/3_tech_mobile.html` (Removed `if (!confirm(...))` on No Answer)
* **1-Step Fix**:
  * Remove `data-confirm` and native `confirm(...)` barriers from routine reversible actions like undispatching, enabling instant 1-click execution with dynamic loading spinners.

### ERR-056: Redundant Walk-in Intake Modal in Stage 1 Verification Instead of Canonical Customer Form
* **Symptoms**:
  * Staff clicking "Intake Walk-in" on Stage 1 Verification (`/dispatch/pipeline/1-verification/`) were presented with a separate in-page modal (`#intakeWalkinModal`) that duplicated applicant registration fields.
  * Submitting the modal failed for non-agent staff because the form action posted to `agent_add_prospect`, expecting an `agent_profile`.
  * Non-technical users expected walk-in applicants to be processed through the unified CRM Customer Registration system (`/customers/add/`) rather than maintaining fragmented, competing applicant intake modals.
* **Root Causes**:
  * `1_verification.html` embedded an inline modal `#intakeWalkinModal` posting to `agent_add_prospect` instead of linking to the canonical `add_customer` view (`/customers/add/`).
  * `add_customer` did not respect a `next` query/post parameter to return staff back to Stage 1 Verification after registration.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/pipeline/1_verification.html` (Replaced modal trigger with direct link `<a href="{% url 'add_customer' %}?next={% url 'dispatch_verification' %}">` and removed redundant 70-line modal)
  * `billing/views/customers/crud.py` (Added `next` redirect handler in `add_customer`)
  * `billing/templates/billing/add_customer.html` (Added hidden `next` input and dynamic Cancel link)
### ERR-057: Dispatch Queue Tab Count Mismatch, Missing Tab 4 Records, and Inactive QA Approval Queue
* **Symptoms**:
  * Tab "Completed (1)" badge displays 1, but tab body shows "No Completed Records Yet".
  * Tab "All Records (4)" badge displays 4, but table displays "Showing 1–1 of 1 records".
  * Stage 3 QA Review (`/dispatch/pipeline/4-qa/`) displays "No tickets awaiting QA review" even when jobs are completed.
* **Root Causes**:
  * `dispatch_monitoring_view` added `records.count()` blindly to `completed_count` and omitted `completed_records` from template context.
  * `_queue_tabs.html` Tab 4 (`#tab-all`) only iterated `{% for record in records %}`, omitting `{% for t in job_tickets %}`.
  * `dispatch_qa` in `pipeline_views.py` filtered `JobTicket.objects.filter(status='COMPLETED', customer__status='pending')`, permanently hiding tickets for active subscribers, and `4_qa.html` checked non-existent `completed_at` instead of `done_at`.
* **Exact Target Files**:
  * `dispatch/views.py` (Fixed disjoint record partitioning and passed `completed_records` to context)
  * `dispatch/pipeline_views.py` (Removed `customer__status='pending'` filter, supported both `COMPLETED` and `QA_PASSED` tickets, unified QA & Super Admin final sign-off)
  * `dispatch/templates/dispatch/pipeline/4_qa.html` (Fixed `ticket.done_at`, status pills, action buttons, and modal loop)
  * `dispatch/templates/dispatch/_queue_tabs.html` & `dispatch/templates/dispatch/tabs/` (Modularized into `<100` line sub-partials and included both `job_tickets` and `records` in Tab 4)
* **1-Step Fix**:
  * Partition records disjointly, loop both `job_tickets` and `records` in Tab 4, and remove `customer__status='pending'` from `dispatch_qa`.

### ERR-058: Dispatch Trash Can Delete Buttons Inactive and 403 Forbidden for Non-Staff CSR Accounts
* **Symptoms**:
  * Red square trash can icon buttons (`.btn-delete-ticket` and `.btn-delete-record`) do nothing when clicked in Pending Queue or Master Records.
  * In other views, clicking delete returns a 403 Forbidden or "Unauthorized" error message.
* **Root Causes**:
  * `_scripts.html` was historically not included in dedicated queue pages (`client_concerns.html`, `internet_install.html`, `cignal_install.html`, `dispatch_monitoring.html`), leaving `.btn-delete-ticket` buttons without a registered click handler.
  * `api_delete_ticket` enforced `is_staff=True` or `is_superuser=True`, but standard dispatcher and CSR Django accounts (`CSRAna`, `TechMike`, `MeiMei`) have `is_staff=False`.
  * Direct monitoring records (`MonitoringRecord`) lacked a corresponding delete API endpoint.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/_modal_scripts.html` (Added universal delegated click handlers on `document` for both `.btn-delete-ticket` and `.btn-delete-record` with SweetAlert2 confirmation, loading spinner, and animated row removal)
  * `dispatch/views.py` (Replaced staff requirement with standard `@login_required`, added `api_delete_record` endpoint)
  * `dispatch/urls.py` (Registered `path('api/records/<int:record_id>/delete/', views.api_delete_record)`)
  * `billing/templates/billing/base/_scripts.html` (Added `showCancelButton: true` to `window.gametechConfirm` defaultOpts)
* **1-Step Fix**:
  * Include delegated event listeners in `_modal_scripts.html` (loaded universally via `_modals.html`), expose `api_delete_record`, and authorize authenticated operators via `@login_required`.

### ERR-059: Disconnected Operations Pipeline: Missing Repair Intake, Missing Tech Confirmation Guard, and Duplicate Dispatch Job Tickets
* **Symptoms**:
  * Repair, relocation, or reconnection tickets filed via API land in `INTERNET_INSTALL` queue instead of `CLIENT_CONCERNS`.
  * Dispatchers can click "Complete Job" without warning even when technicians on site haven't submitted reports or optical signal levels.
  * Approving customer in `/dispatch/pipeline/1-verification/` duplicates existing `JobTicket` records.
  * Customer profile lacks visibility into the 6-stage operational pipeline (`Agent -> Customer -> Dispatch -> Tech -> Dispatch QA -> Admin`).
* **Root Causes**:
  * `api_create_ticket` in `dispatch/views.py` defaulted `source_tab='INTERNET_INSTALL'` for all tickets unless explicitly passed.
  * `#modal-complete-job` modal had no verification checking `ticket.time_accomplish` or technician confirmation flag before submission.
  * `dispatch_verification` blindly called `JobTicket.objects.create()` on verification approval without checking `customer.job_tickets.filter(status__in=['PENDING', 'ASSIGNED'])`.
  * Lack of a dedicated repair intake modal accessible directly from Customer Detail and Customer List views.
* **Exact Target Files**:
  * `dispatch/views.py` (Auto-routed `source_tab` based on `ticket_type`, added `tech_confirmed` to `api_ticket_detail`)
  * `dispatch/pipeline_views.py` (Added ticket re-use/de-duplication logic in `dispatch_verification`, allowed staff preview in `technician_mobile_ui`)
  * `dispatch/templates/dispatch/_modal_scripts.html` (Integrated SweetAlert2 technician report completion confirmation guard)
  * `billing/templates/billing/view_customer/_lifecycle_tracker.html` & `_modal_customer_repair.html` (Created visual 6-stage lifecycle stepper and repair ticket modal)
* **1-Step Fix**:
  * Auto-map `source_tab` to `CLIENT_CONCERNS` for non-install types, query existing open tickets in verification, and intercept `#modal-complete-job` trigger with `tech_confirmed` prompt.

### ERR-060: Unconsumed Internal Flash Messages Leaking to Public Login Screen Styled as Alarming Red Error Banners
* **Symptoms**:
  * Logging out or navigating to `/login/` presents multiple red warning boxes displaying internal operational success notices (e.g. *"Job details saved and marked as Done."*).
* **Root Causes**:
  * `billing/base.html` lacked a `{% if messages %}` block inside `<main class="content-wrapper">`. Operational messages produced during views (like job completion) were never rendered and consumed on dispatch/monitoring pages, remaining trapped in session/cookie storage.
  * `login.html` hardcoded `<div class="login-error">{{ message }}</div>` for all messages regardless of tag (`success` vs `error`), rendering success messages in alarming pink/red boxes.
  * `custom_logout_view` and `portal_logout` did not purge internal session messages on logout, causing unconsumed messages to bleed onto the public login page.
* **Exact Target Files**:
  * `billing/templates/billing/base.html` (Added universal message rendering, picked up automatically by `_scripts.html` toast converted)
  * `billing/templates/billing/login.html` (Added `.login-success` CSS and conditional tag classes)
  * `billing/views/auth.py` & `customer_portal/views/auth.py` (Purged message storage upon logout)
  * `dispatch/templates/dispatch/complete_job.html` (Added button submit loading protection to prevent multiple clicks)
* **1-Step Fix**:
  * Add universal messages to `base.html`, flush message storage in `custom_logout_view` with `storage.used = True; storage._queued_messages = []`, and style `.login-success` in `login.html`.

### ERR-061: OpenStreetMap 403 Forbidden Access Block on Dispatch Map & Operational Closed Counter Discrepancy
* **Symptoms**:
  * The Field Operations Map in `/dispatch/dashboard/` fails to render tiles, showing grey/blank grid boxes with `403 Access blocked` errors in the browser console from `tile.openstreetmap.org`.
  * Overview KPI statistics cards show a counter mismatch (e.g. `Total Closed: 1` on overview card vs `2` in Completed queue tab).
* **Root Causes**:
  * OpenStreetMap foundation volunteer servers enforce strict User-Agent headers and rate-limits that block generic browser web apps, as recognized in runbook pattern `ERR-023`.
  * `get_operational_overview_stats()` in `dispatch/analytics.py` only queried `JobTicket` objects and ignored `MonitoringRecord` entries, whereas `dashboard_view` and `dispatch_monitoring_view` aggregate both schemas.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/_scripts.html` (Switched tile layer from `tile.openstreetmap.org` to Google Maps tiles `https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}` with dark styling)
  * `dispatch/analytics.py` (Updated `get_operational_overview_stats()` to query both `JobTicket` and `MonitoringRecord` for total closed jobs)
* **1-Step Fix**:
### ERR-062: Hero Banner CSS Pseudo-Element Click Interception & Staff Modal Disconnect
* **Symptoms**:
  * On `/staff/`, clicking the "Add Staff" button in the hero banner fails to respond or is hard to click in certain screen regions.
  * Adding staff redirected away or threw permission denied for non-superuser administrators; standalone page form wiped out input on validation errors.
  * Custom staff roles defined in Manage Roles were missing from the Add Staff role dropdown.
* **Root Causes**:
  * `.page-hero::before` decorative pseudo-element was positioned at `top: -60px; right: -60px; width: 220px; height: 220px;` without `pointer-events: none;`, physically overlaying and intercepting pointer clicks on the hero action buttons.
  * `@role_required(["Admin"])` did not check `can_access_administration` or `admin_panel` subtab permissions from `user.role_perms`.
  * Lack of an inline modal popup (`#addStaffModal`) consistent with `/agents/` and `/staff/roles/` forced users onto a detached `/staff/add/` page with hardcoded static `<select>` options.
* **Exact Target Files**:
  * `static/css/theme/layout_and_darkmode.css` (Added `pointer-events: none;` to `.page-hero::before` and `.page-hero::after`)
  * `billing/decorators.py` (Added `can_access_administration` subtab permission and AJAX JSON 401/403 support to `role_required`)
  * `billing/views/staff.py` (Added AJAX JSON support, case-insensitive uniqueness checks, and passed `available_roles` to `staff_list`)
  * `billing/templates/billing/partials/_modal_add_staff.html` (Created modern glassmorphic Add Staff modal partial)
  * `billing/templates/billing/staff_and_admins.html` & `dispatch/templates/dispatch/_management_accounts.html` (Wired up `data-bs-target="#addStaffModal"`)
### ERR-063: Customer Portal Modal Backdrop Freeze on Plan Selection & Close
* **Symptoms**:
  * On `/portal/dashboard/`, clicking "Select Plan" or the "X" close button inside the Choose Service Plan modal (`#planModal`) leaves the dashboard covered in an unclickable dark grey screen (`.modal-backdrop` stuck with `modal-open` and `overflow: hidden` on `<body>`).
* **Root Causes**:
  * Combining `data-bs-target="#mockPaymentModal" data-bs-toggle="modal"` with `data-bs-dismiss="modal"` on the exact same button creates a race condition in Bootstrap 5's modal transition listener (`hidden.bs.modal` vs `shown.bs.modal`), destroying or orphaning the backdrop.
  * Duplicate loading of Bootstrap JS bundles (`bootstrap@5.3.0` in `portal_dashboard.html` and `bootstrap@5.3.2` in `_scripts.html`) bound duplicate click data-api handlers on `document`, causing multi-modal triggers to fire twice simultaneously.
  * Extraneous closing `</div>` tag at the end of `#planModal` in `_modals.html` (opens: 60, closes: 61).
* **Exact Target Files**:
  * `customer_portal/templates/customer_portal/portal_dashboard/_modals.html` (Removed `data-bs-dismiss="modal"` from `#plan-select-btn` and `custom-close-btn`; removed extra `</div>`)
  * `customer_portal/templates/customer_portal/partials/plan_card.html` (Removed `data-bs-dismiss="modal"` from `.select-plan-btn`)
  * `customer_portal/templates/customer_portal/portal_dashboard.html` (Consolidated to single `bootstrap@5.3.2` bundle in head/scripts)
  * `customer_portal/templates/customer_portal/portal_dashboard/_scripts.html` (Removed duplicate script import, used `getOrCreateInstance`, and added global `hidden.bs.modal` backdrop cleanup guard)
* **1-Step Fix**:
  * Remove `data-bs-dismiss="modal"` from multi-modal toggle buttons, remove duplicate Bootstrap JS bundle, and add failsafe `hidden.bs.modal` cleanup guard for orphaned backdrops.

---

### ERR-064: Dispatch Log Row Click & Missing 9-Section Comprehensive Dispatch Modal
* **Symptoms**:
  * Clicking a row in the Dispatch Log (`/dispatch/dashboard/`, `/dispatch/monitoring/`, `/dispatch/dispatches/`) did not open the comprehensive 9-section Job Info, Subscriber Info, Location, Issue, Scheduling, Work Timeline, Service Details, Sign Off, and Technician modal present in the live system (`http://192.168.200.29:5502/dispatches`).
* **Root Causes**:
  * Table rows lacked click event handlers bound to a master detail modal; `api_ticket_detail` only returned a subset of fields without `all_teams` or technician lists; no `POST` update handler existed to persist field updates.
* **Exact Target Files**:
  * `dispatch/views.py` (`api_ticket_detail` GET & POST handlers supporting `JobTicket` and `MonitoringRecord`)
  * `dispatch/urls.py` (added `/dispatch/dispatches/` alias)
  * `dispatch/templates/dispatch/_modal_dispatch_detail.html`
  * `dispatch/templates/dispatch/_modal_dispatch_detail_script.html`
  * `dispatch/templates/dispatch/styles/_modal_dispatch_detail_styles.html`
  * `dispatch/templates/dispatch/_ticket_list.html`
  * `dispatch/templates/dispatch/tabs/_tab_all.html`, `_tab_pending.html`, `_tab_ongoing.html`, `_tab_completed.html`
* **1-Step Fix**:
  * Implement `_modal_dispatch_detail.html` (<250 lines) with all 9 sections and dynamic Team technician checkboxes with "Select all".
  * Wire row click handlers with `openDispatchDetailModal(id)` across all tables and `stopPropagation` on row action buttons.
  * Upgrade `api_ticket_detail` to serialize comprehensive data and accept `POST` updates with SweetAlert confirmation.

### ERR-065: Blinding White Cards on Dispatch Dashboard in Dark Mode & Table Contrast Degradation
* **Symptoms**:
  * Switching to dark mode leaves cards in `/dispatch/dashboard/` bright white (`#fff`) with black text against the dark theme background.
  * Customer Directory and Cignal Play tables suffer contrast degradation, unreadable dark text, or washed out rows in dark mode.
* **Root Causes**:
  * `dispatch/dashboard.html` hardcoded `#fff` card and layout backgrounds without `html.dark-mode` / `.dark-mode` selectors.
  * `_monitoring_page_styles.html` omitted `{% include "dispatch/styles/_theme.html" %}`, depriving monitoring pages of CSS tokens.
  * `_gt_design_system.html` table cells lacked explicit `--bs-table-color` overrides, allowing Bootstrap 5's default black text to conflict with dark mode.
* **Exact Target Files**:
  * `dispatch/templates/dispatch/dashboard.html`
  * `dispatch/templates/dispatch/styles/_monitoring_page_styles.html`
  * `dispatch/templates/dispatch/styles/_theme.html`
  * `billing/templates/billing/partials/_gt_design_system.html`
  * `billing/templates/billing/customer_list/_styles.html`
* **1-Step Fix**:
  * Add scoped `html.dark-mode` overrides for `.dash-kpi-card`, `.overview-layout`, `.overview-mini-card`, `.monitoring-card-box`, `.leaderboard-card`, and SVG tracks.
  * Include `_theme.html` inside `_monitoring_page_styles.html`.
  * Set `--bs-table-color` explicitly to `#334155` (light) and `#cbd5e1` (dark) with `#1e293b` solid dark card surfaces in `_gt_design_system.html`.

---

### ERR-066: Broken Light Theme on Customer Directory, Overlapping Badges, Solid Blue Router Pill, and Unsynced Runtime Charts
* **Symptoms**:
  * In light mode on `/customers/`, the router column is rendered as an unreadable solid blue pill with invisible text.
  * The "Active" and "Connected" badges overlap horizontally; due date appears with yellow text on white.
  * Inputs and dropdowns lack visible borders in light mode; filter pill active state is solid fill conflicting with the primary CTA.
  * Charts across Dashboard and Dispatch fail to update colors dynamically on theme toggle without reloading.
* **Root Causes**:
  * Router pill used `bg-primary bg-opacity-15 text-primary` which collapsed to solid `#0d6efd` in Bootstrap 5 without opacity CSS variables.
  * Status badges used inline flex without vertical spacing, causing horizontal collision with connection status dots.
  * Incomplete token sets in `:root` and `.dark-mode`; Chart.js instances lacked a reactive listener for `themeChanged`.
* **Exact Target Files**:
  * `billing/templates/billing/partials/_gt_design_system.html`
  * `static/css/theme/tokens_and_base.css`
  * `billing/templates/billing/customer_list/_hero.html`
  * `billing/templates/billing/customer_list/_table.html`
  * `billing/templates/billing/customer_list/_scripts.html`
  * `billing/templates/billing/base/_scripts.html`
  * `dispatch/templates/dispatch/styles/_dashboard_styles.html`
* **1-Step Fix**:
  * Implement unified Stage 1 tokens at `:root` (light) and `.dark-mode` (dark) with WCAG AA >= 4.5:1 text contrast.
  * Change router column to plain text `--text-primary`; stack status badges vertically with `gap: 6px` and muted due date.
  * Normalize inputs and selects to 40px height with `--input-border` (`#C3CCDB` in light); style active filter pills with soft accent tint.
  * Add universal `Chart.instances` updater on `themeChanged` in `base/_scripts.html` to update grids, ticks, legends, and donut segment borders without reload.

---

### ERR-067: Customer View "More Actions" Dropdown Clipped at 40px Below Account Header
* **Symptoms**:
  * On `/customers/view/<id>/` (Customer Profile), clicking the "More Actions" dropdown button expands a truncated ~40px dark box displaying only the uppercase header `ACCOUNT`, cutting off all 10 actions (Statement of Account, Update Health, Send SMS, Send Email, Rebate, Rollback, Kick Session, Force Suspend, Force Reactivate, Delete).
  * The dropdown toggle chevron flips upwards (`^`) due to Popper boundary detection failure.
* **Root Causes**:
  * `.page-header` in `billing/templates/billing/partials/_gt_design_system.html` enforces `overflow: hidden;`, causing the parent `.customer-view-header` to hard-clip any element protruding beyond the card's bottom border.
  * Bootstrap 5 Popper.js treats `.page-header` as a clipping parent, detects insufficient clearance, and attempts to constrain or flip the menu into a dropup.
  * Sibling `.dashboard-card.animate-fade-in` in `_lifecycle_tracker.html` retains a CSS `transform: translateY(0)` stacking context via `animation-fill-mode: both`.
* **Exact Target Files**:
  * `billing/templates/billing/view_customer/_styles.html`
  * `billing/templates/billing/view_customer/_profile_header.html`
  * `billing/templates/billing/view_customer/_lifecycle_tracker.html`
* **1-Step Fix**:
  * Set `overflow: visible !important;` on `.page-header.customer-view-header` (and suppress `.page-header.customer-view-header::after { display: none !important; }` to eliminate horizontal scroll bleed).
  * Add `data-bs-display="static"` to both `#moreActionsDropdown` and `#requestServiceDropdown` buttons to disable Popper dynamic boundary clipping and enforce pure static CSS positioning.
  * Explicitly style `.page-header.customer-view-header .dropdown-menu` with `position: absolute !important; top: 100% !important; right: 0 !important; left: auto !important; margin-top: 8px !important; z-index: 1060 !important; max-height: calc(100vh - 180px) !important; overflow-y: auto !important;`.
  * Add `style="position: relative; z-index: 1;"` to the `_lifecycle_tracker.html` outer row to ensure stacking priority remains subordinate to `.customer-view-header` (`z-index: 1050`).

---

### ERR-068: Inverted Terminology & Discrepancies Across Customer Status (Router vs Connection & Missing Dispatch Status)
* **Symptoms**:
  * Customer profile (`/customers/view/<id>/`) and directory (`/customers/`) showed conflicting, confusing descriptions (e.g. `Offline (Router API Down)` or `Secret Not Found on Router` when account is Active/Paid).
  * `dispatch_status` always evaluated to `None` or was missing even when the customer had an active ticket (`TICK-...`).
  * "Router" and "Connection" statuses were defined backwards compared to physical network architecture (Repeater -> MikroTik -> Switch -> Home Router).
* **Root Causes**:
  * In `billing/models.py`, `JobTicket.objects.filter(status__in=['pending', ...])` searched lowercase statuses, while `JobTicket.STATUS_CHOICES` stores uppercase (`PENDING`, `ASSIGNED`, `IN_PROGRESS`, `QA_PASSED`).
  * Legacy code labeled the customer's PPPoE session as "Connection" and the ISP WAN uplink as "Router", inverting the actual topology.
* **Exact Target Files**:
  * `billing/models.py` (`dispatch_status`, `payment_status`, `router_status`, `connection_status`)
  * `billing/views/api/network.py` (`api_customer_mikrotik_status`)
  * `billing/templates/billing/view_customer/_profile_header.html`
  * `billing/templates/billing/view_customer/_info_cards.html`
  * `billing/templates/billing/view_customer/_scripts.html`
  * `billing/templates/billing/customer_list/_customer_status.html`
  * `billing/templates/billing/customer_list/_scripts.html`
* **1-Step Fix**:
  * Standardize the 4-status matrix across all views:
    1. **For Dispatch**: `No` or active ticket type (`Repair`, `Installation`, etc.) querying uppercase `JobTicket` statuses.
    2. **Payment**: `Paid` (active & valid expiration) vs `Unpaid`.
    3. **Router**: Customer home modem (`Online` = active PPPoE session on MT, `Offline` = disconnected).
    4. **Connection**: ISP WAN internet uplink (`Online` = MikroTik receiving internet from repeater, `Offline` = repeater/uplink down).

---

## 📝 How to Add a New Error Entry


1. Assign a new `ERR-XXX` identifier.
2. Fill in: **Symptoms**, **Root Causes**, **Exact Target Files**, and **1-Step Fix**.
3. Keep entries short, actionable, and sniper-focused.

---

### ERR-067: Frontend Memory Bloat, Slow Pages & Aggressive Polling
* **Symptoms**:
  * Browser snoozes/discards the site tab with a "using too much memory" warning.
  * Some pages load very slowly, others very fast (inconsistent).
* **Root Causes**:
  1. A `MutationObserver` observing `document.body` with `subtree: true` that was **never disconnected**, re-running `querySelectorAll` on every DOM mutation forever.
  2. Aggressive polling: `fetchOnlineStaff` every 5s and `fetchNotifications` every 30s on **every** page; `updateConnectionStatuses` every 30s on the customer list; `fetchStatus` every 5s on customer profiles.
  3. No `document.hidden` guard on the base/customer-list polling, so background tabs kept polling.
  4. N+1 queries on high-traffic views (portal dashboard, customer profile, payment logs) missing `select_related`.
  5. `api_offline_users` and `api_network_alerts` hitting every MikroTik router and the DB on **every** request with no caching.
  6. No index on `Customer.expires_at` despite being the most frequently filtered field in the system.
* **Exact Target Files**:
  * `billing/templates/billing/base/_scripts.html` (MutationObserver + polling intervals)
  * `billing/templates/billing/customer_list/_scripts.html`, `billing/templates/billing/view_customer/_scripts.html` (polling)
  * `billing/templates/billing/base.html` (render-blocking SweetAlert2, missing preconnect, Bootstrap version mismatch)
  * `customer_portal/views/dashboard.py`, `billing/views/customers/crud.py`, `billing/views/customers/actions.py`, `billing/views/payments/logs.py`, `billing/views/services.py` (N+1)
  * `billing/views/api/network.py` (`api_offline_users`, `api_network_alerts` caching)
  * `billing/views/analytics.py` (uncached aggregations)
  * `billing/models.py` (`Customer.expires_at` db_index)
* **1-Step Fix**:
  1. `setTimeout(() => observer.disconnect(), 15000)` after `observer.observe(...)`.
  2. Relax intervals (5s→15s, 30s→60s) and add `if (document.hidden) return;` to every polling function.
  3. Add `select_related("plan", "barangay", "mikrotik_device")` to portal/profile/SOA queries and `select_related("customer")` to payment logs.
  4. Cache `api_offline_users_payload` and `api_network_alerts_payload` for 30s; skip circuit-broken routers via `router_unreachable_<id>`.
  5. Cache the analytics context for 300s under `analytics_dashboard_<date>`.
  6. Add `db_index=True` to `Customer.expires_at` (migration `0060_customer_expires_at_index`).
  7. Move SweetAlert2 to end-of-body with `defer`, add CDN `preconnect` hints, unify Bootstrap to 5.3.3.
  8. Standardize jQuery 3.7.1 + DataTables 1.13.7 across all templates (previously 3 versions each, causing duplicate downloads).

---

### ERR-068: Untracked Migration Files on Server Break `manage.py migrate`
* **Symptoms**:
  * `CommandError: Conflicting migrations detected; multiple leaf nodes in the migration graph`.
  * `manage.py check` reports bogus `admin.E127/E108/E116` errors for `MessageTemplate` / `CustomerAgentHistory` (fields `is_active`, `updated_at`, `changed_at` "do not exist") even though `billing/admin.py` is correct in the repo.
* **Root Causes**:
  1. `makemigrations` run directly on the droplet generated migration files that were **never committed to git** (e.g. `0059_remove_customer_adjusted_by_referral_and_more.py`, `0061_merge_*.py`). Repo and database drift apart.
  2. Running `makemigrations` on the server a second time (a different `--name`) produced a **duplicate** `0060` index migration alongside the one committed to the repo, creating two leaf nodes.
  3. With migration files missing/stale in the droplet working tree, Django resolved models from an outdated state, producing phantom admin errors.
* **Exact Target Files**:
  * `billing/migrations/` (all files)
  * Droplet working tree `/root/GAMETECH-BILLING-SYSTEM`
* **1-Step Fix**:
  1. `scp` the untracked migration files from the droplet into the local repo, verify with `python -m py_compile`, then `git add billing/migrations/ && git commit && git push origin main`.
  2. On the droplet: `git checkout -- billing/migrations/` to restore tracked files, then `git pull origin main`.
  3. **NEVER run `makemigrations` on the droplet** — always generate migrations locally and commit them. Generate with an explicit `--name`, and confirm the file lands in git before deploying.
  4. Verify with `manage.py check` (expect "no issues") and `manage.py migrate billing` (expect "No migrations to apply").
  5. If a duplicate `0060` exists, do not delete DB rows from `django_migrations`; instead add an empty merge migration depending on both leaves.

---

### ERR-069: Container Name Flapping After `docker compose up -d`
* **Symptoms**:
  * `docker exec gametech-billing-system_web_1 ...` intermittently returns `No such container` or `cannot exec in a stopped container`, then later works again.
  * `docker ps -a` shows containers with hash prefixes (e.g. `9d8bdc08521b_gametech-billing-system-celery-1`) alongside clean-named ones.
* **Root Causes**:
  1. An external verification process on the droplet runs `python manage.py check` / `showmigrations` inside the web container, and concurrent `docker compose up -d` invocations recreate containers mid-command.
  2. The droplet checkout sits on branch `feature/dispatch-operation` rather than `main`, so `git pull origin main` fast-forwards a non-default branch and the two can visibly diverge.
  3. Two postgres volumes exist (`gametech-billing_postgres_data` = the `external: true` one actually in use, and the orphaned `gametech-billing-system_postgres_data`). Compose warns about the label mismatch every run.
* **Exact Target Files**:
  * `/root/GAMETECH-BILLING-SYSTEM/docker-compose.yml`
  * Droplet git checkout (branch state)
* **1-Step Fix**:
  1. **Resolve the container name immediately before use**: `docker ps --format '{{.Names}}' | grep web` — never assume the name is stable across turns.
  2. For routine deploys prefer `docker restart <name>` (Rule 32v2); use `docker compose up -d` only when a port actually dropped (502 from nginx).
  3. Confirm the live volume before any `compose up`: `docker inspect <db-container> --format '{{range .Mounts}}{{.Name}}{{end}}'` must report `gametech-billing_postgres_data`. **Never** delete or prune the orphaned volume.
  4. Verify health after any recreate: `curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/login/` must return `200`.
  5. Consider switching the droplet checkout to `main` so deploys and repo state stay aligned.







### ERR-070: Dashboard Cards Washed-Out Purple / Dark-Mode Styles Not Applying

**Symptom**: Dashboard KPI cards render as a flat washed-out lavender/purple instead of the correct dark-navy glass-morphism style. Occurs when the system-wide gt/ design-system CSS is loaded on the Dashboard page.

**Root Cause (two compounding bugs introduced by UI unification commits):**
1. ase.html added a *second* dark-mode script on ody (document.body.classList.add) that conflicted with the dashboard's html.dark-mode CSS selectors, leaving dark mode partially active but mismatched.
2. gt/tokens.css and gt/data.css were placed *outside* the dashboard exclusion guard ({% if url_name != 'dashboard' %}), so they loaded on the dashboard and overrode its custom design-token variables with the gt/ palette.

**Fix**: In illing/templates/billing/base.html:
- Remove the duplicate ody.dark-mode script block; keep only the html.dark-mode script in <head>.
- Move ALL gt/ CSS links (	okens.css, data.css, components.css, surfaces.css, legacy.css) inside the single {% if url_name != 'dashboard' %} guard.

**Files**: illing/templates/billing/base.html  
**Commit**: ix(dashboard): isolate dashboard from gt/ CSS entirely and remove duplicate body.dark-mode script`n


---

### ERR-071: Migration Graph Broken by Locally-Generated but Uncommitted Migration Files

**Symptom** (two distinct variants, both seen on the droplet):
1. `CommandError: Conflicting migrations detected; multiple leaf nodes in the migration graph: (0059_..., 0060_...) in billing`
2. `Migration 0015_alter_monitoringrecord_dispatch in app 'dispatch' references nonexistent migration 0014_merge_...`

**Root Cause**: Django generated a branch merge locally (e.g. `0059` and `0060` both descended from `0058`), and the auto-created merge migration was applied to the production DB -- but the `.py` files were **never committed or pushed**. The DB's `django_migrations` table recorded the merge as applied while the file did not exist in git, so the droplet had a different graph than the repo.
- Variant 1 (two leaf nodes): the merge file was missing entirely, so both branches still looked like leaves.
- Variant 2 (missing dependency): a later migration `0015` *did* get committed and depends on the lost `0014`, so a **fresh clone of `main` was broken for everyone**.

**Exact Target Files**:
- `billing/migrations/`, `dispatch/migrations/`
- `django_migrations` table (read-only check)

**Diagnosis (1 step, no code reading)**:
```
docker exec gametech-web python manage.py showmigrations billing dispatch 2>&1 | tail -10
```

**1-Step Fix**:
1. Recover the lost file from the droplet (`cat dispatch/migrations/00XX_merge_*.py`) or regenerate it.
2. **Commit the migration file to `main`.** Do *not* run `git reset --hard` first -- that is what destroys the file in the first place.
3. Re-verify: `docker exec gametech-web python manage.py makemigrations --check --dry-run` must print `No changes detected`.

**Prevention**: After any `makemigrations`, commit the generated file **in the same commit** as the model change. Never leave a migration untracked.

---

### ERR-072: New Sidebar Subtab Silently Hidden (SubtabMap Returns False for Unregistered Names)

**Symptom**: A link added to `billing/templates/billing/base/_sidebar.html`, guarded by
`{% if request.user.role_perms.subtabs.dispatch_<newtab> %}`, never renders -- for **any** role, including Admin. No error, no traceback.

**Root Cause**: `StaffRole.subtabs` is a `dict` subclass whose `__getattr__` returns `self.get(item, False)`. It is only populated with the names listed in `subtab_specs`:
```python
"dispatch": ["dispatch_dashboard", "dispatch_operation", ...]
```
Any name absent from that list resolves to `False`, so the guard is always false. Same for `{{ admin.role_perms.subtabs.<name> }}` in any template.

**Exact Target Files**:
- `billing/models.py` -> `StaffRole.subtabs` property -> `subtab_specs`
- `billing/views/staff.py` -> `ROLE_MODULE_SPECS` (drives the Roles admin UI)

**1-Step Fix**: Register the new subtab in **BOTH** sources of truth; they are independent and easy to forget:
```python
# billing/models.py
"dispatch": [..., "cignal_install", ..., "geo_map"]

# billing/views/staff.py
("cignal_install", "Cignal Install", "fa-tv"),
("geo_map", "Field Map", "fa-map-marked-alt"),
```
Then verify it resolves for a **non-Admin** role too:
```python
r = StaffRole.objects.exclude(name__iexact="admin").filter(can_access_dispatch=True).first()
print(r.subtabs.dispatch_cignal_install)   # must be True, not False
```

**Note**: `has_subtab_perm()` returns `True` for any subtab when the role has no key for that module in `subtab_permissions`, so per-role gating is inert until an admin configures it in the Roles UI. That is *not* a substitute for registering the name.

---

### ERR-073: Unreachable Pages / Dead Template Partials (Navigation Drift)

**Symptom**: A feature is fully built and renders correctly, but nothing in the UI can open it. Users report "I clicked around and can't find it". Separately, partials accumulate that nothing includes.

**Real instances found**:
| Dead page | Why unreachable | Fix |
| :--- | :--- | :--- |
| `/dispatch/map/` | its only reference was a dead `_nav_tabs.html` partial | sidebar link added |
| `/dispatch/cignal-install/` | never added to the sidebar | sidebar link added |
| `/dispatch/receipt/<id>/` | finished printable Official Receipt, no entry point | row button in Payment Logs |
| `/dispatch/admin-summary/` | pipeline stepper never linked forward | stepper completed on all stages |
| `dispatch/_nav_tabs.html` | 179 lines, included by nothing, duplicated the sidebar | deleted |

**Root Cause**: Pages get added to `urls.py` and built, but the navigation layer is not updated in the same change. Deleting a partial can also silently orphan every page that only it linked to.

**Exact Target Files**:
- `billing/templates/billing/base/_sidebar.html` (primary nav)
- `billing/templates/billing/settings.html`, `billing/templates/billing/admin_panel.html` (quick-link hubs)
- app partial folders

**Audit approach** -- reverse every named URL, then subtract legitimate non-page routes:
- *Endpoints, not pages*: webhooks (`xendit_webhook`), gateway returns (`payment_success`), forced redirects (`force_change_password`), POST-only actions (`verify_customer`, `approve_cignal_request`).
- *Dynamic reverse*: names passed to a template as a **string** in context (e.g. `"create_url": "create_account_type"` then `{% url create_url %}`) look unreferenced but are fine.
- *Aliases*: several names can map to the same view (`dispatch_staff`/`dispatch_management`, `technician_my_jobs`/`technician_mobile_ui`).
- *Namespaced*: `{% url 'customer_portal:portal_checkout' %}` will not match a search for the bare name.

**Prevention (Rule 13)**: Before deleting any partial, grep the whole repo for its filename and re-audit any page it was the sole linker for. After adding a page to `urls.py`, wire it into the sidebar or a hub page in the same change.

---

### ERR-074: Table Columns Misaligned When the Header Cell Is Permission-Gated

**Symptom**: Every data row renders shifted one column left of its header, or the empty-state row spans the wrong width.

**Root Cause**: the `<th>` was gated but the `<td>` was not (or vice versa):
```html
<!-- BROKEN: header disappears for non-Admin, but the row cell always renders -->
{% if request.user.role == 'Admin' %}<th>Actions</th>{% endif %}
...
<td>...</td>
```

**Exact Target Files**: `billing/templates/billing/payment_logs.html` (and any table using `colspan`)

**1-Step Fix**: Make the column exist for everyone and gate only the privileged *buttons* inside it:
```html
<th>Actions</th>
...
<td>
  <a href="...">Receipt</a>          <!-- available to all roles -->
  {% if request.user.role == 'Admin' %}
    <a href="...">Edit</a>           <!-- Admin only -->
  {% endif %}
</td>
```

**Verify parity (do not eyeball it)** -- header count must equal row-cell count must equal the empty-state `colspan`:
```python
th   = len(re.findall(r'<th[\s>]', head))
td   = len(re.findall(r'<td[\s>]', row))
span = re.findall(r'colspan="(\d+)"', table)
assert th == td == int(span[0])
```
Beware: a naive `<th[^>]*>` regex also matches `<thead>`, inflating the count by one. Use `<th[\s>]`.

---

### ERR-075: Whole Stack Destroyed by Concurrent Deploy Sessions (Site Fully Down)

**Symptom**: `docker ps` shows one or zero containers; every page returns HTTP `000`. `docker exec gametech-web ...` returns `No such container`. `could not translate host name "db"` because the db container is gone. Observed repeatedly during a multi-session audit.

**Root Cause**: Several AI/terminal sessions running deploys against the same droplet at the same time. The destructive commands seen in `ps`:
```
git reset --hard origin/main ; docker-compose build ; docker-compose down ; docker-compose up -d
```
Three aggravating factors:
1. Legacy `docker-compose` (v1) used alongside `docker compose` (v2) -- different default project names, so each invocation recreates the other's containers and forces hash-prefixed names.
2. `git reset --hard origin/main` deletes uncommitted migration files (see ERR-071).
3. A test container named `gt_testrunner` squatted the `com.docker.compose.service=web` label, so `docker compose up -d web` failed with a name conflict while the real web container stayed down.

**Data safety**: business data lives in the external volume `gametech-billing_postgres_data` and survives container deletion. Verify before acting:
```
docker volume ls | grep postgres_data
```
A second, stale volume `gametech-billing-system_postgres_data` also exists. **Never prune it blindly** -- confirm which one the db container mounts first:
```
docker inspect <db-container> --format '{{range .Mounts}}{{.Name}} -> {{.Destination}}{{end}}'
```

**1-Step Recovery**:
```bash
cd /root/GAMETECH-BILLING-SYSTEM
# remove all project containers; volumes are untouched
for r in 1 2 3; do
  L=$(docker ps -a --format '{{.Names}}' | grep -E "gametech|gt_" | tr '\n' ' ')
  [ -z "$L" ] && break
  for c in $L; do docker rm -f "$c"; done
  sleep 6
done
docker compose up -d
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/login/   # must be 200
```

**Prevention**: Only one session may deploy at a time. Always use Compose **V2** (`docker compose`, with a space). Never `git reset --hard` on the droplet -- use `git pull --ff-only origin main`. Resolve container names dynamically at use time rather than assuming them:
```bash
WEB=$(docker ps --filter "label=com.docker.compose.service=web" --format '{{.Names}}' | head -1)
```


---

### ERR-076: Views Use a Name They Never Imported (NameError -> 500 on those pages only)

**Symptom**: A handful of pages return HTTP 500 while the rest of the app is healthy, and the traceback is a bare `NameError: name 'XForm' is not defined` with no line context that points at the import block.

**Real instance**: `billing/views/settings.py` imported only `AddonPlanForm`:
```python
from billing.forms import AddonPlanForm          # WRONG
```
but used `AccountTypeForm` (4 call sites) and `BarangayForm` (3 call sites). So every Account Type and Barangay create/edit page 500'd:
```
/settings/account-types/add/     500
/settings/account-types/edit/1/   500
/settings/barangays/add/         500
/settings/barangays/edit/1/      500
```

**Root Cause**: A form class was used in a view module without ever being added to that module's import list. Nothing at import time detects this -- the module loads fine and the app boots. It only explodes when that specific view renders.

**Exact Target Files**:
- `billing/views/settings.py` (this case)
- `billing/admin.py` had the sibling variant: `list_display` / `date_hierarchy` referenced model fields that do not exist (`MessageTemplateAdmin` -> `is_active`, `updated_at`; `CustomerAgentHistoryAdmin` -> `date_hierarchy="changed_at"` when the field is `created_at`). Django admin raises `FieldError` on those pages only.

**1-Step Fix**: `python -m py_compile` will NOT catch this (the name is only resolved at call time). Use an authenticated render sweep instead -- see below.

**Detection (this is the reusable part)**: a route-resolution check (`curl` -> 302) is **not** enough, because an auth wall hides 500s on protected pages. Walk every resolvable route through Django's test `Client` as a staff user:
```python
from django.test import Client
from django.contrib.auth import get_user_model
c = Client(); c.force_login(User.objects.filter(is_staff=True).first())
r = c.get(url)          # real routing + real middleware
assert r.status_code != 500
```
Gotchas when writing this sweep:
- Use `test.Client`, **not** `RequestFactory`. `RequestFactory` skips middleware, so any view calling `messages.success()` raises `MessageFailure: You cannot add messages without installing django.contrib.messages.middleware.MessageMiddleware` -- a false positive. It also does not pass URL kwargs to the view, producing 30 bogus `TypeError: view() missing 1 required positional argument`.
- Seed arg converters with real ids (`Customer.objects.values_list("id", flat=True).first()`), and skip routes whose converter has no seed -- those surface as 404, not 500.
- Expect benign non-500s: 302 (auth wall), 404 (seeded id absent), 405 (POST-only endpoint hit with GET).

### ERR-077: Multi-Line `{# #}` Template Comment Renders as Raw Text on the Page

**Symptom**: A line of raw text appears at the very top of the rendered page (above the sidebar/chrome), ending with a visible `#}` delimiter. In this case: *"…Live Monitoring is permanently frozen - it must never receive the Login rebrand. Restores its pre-rebrand token values. #}"* on `/live-monitoring/`.

**Root Cause**: Django's `{# #}` comment syntax is **single-line only**. The lexer regex (`tag_re` in `django/template/base.py`) does not match across newlines, so a comment opened on one line and closed on the next is never tokenized as a comment -- the entire text, including the closing `#}`, is rendered verbatim. No error is raised; the page returns 200.

**Exact Target Files**:
- `billing/templates/billing/base.html` (this case: the AGENTS.md Rule 39 note inside the `{% if url_name == 'live_monitoring' %}` block)

**1-Step Fix**: Use the `{% comment %} … {% endcomment %}` template tag for any comment spanning multiple lines:
```django
{% comment %}AGENTS.md Rule 39: Live Monitoring is permanently frozen - it must never
   receive the Login rebrand. Restores its pre-rebrand token values.{% endcomment %}
```

**Detection**: grep every `{#` in `billing/templates/` and confirm the closing `#}` is on the **same line**. Any multi-line occurrence is a live text leak. All other `{# #}` comments in this repo are single-line and safe.

---

### ERR-078: Server Error (500) on Cignal Dashboard (`TemplateSyntaxError: 'block' tag with name 'content' appears more than once`)

**Symptom**: Navigating to `/cignal-dashboard/` results in a `Server Error (500)`. The traceback shows `django.template.exceptions.TemplateSyntaxError: 'block' tag with name 'content' appears more than once`.

**Root Cause**: During a design system migration, the old `{% block content %}` section (using legacy `cignal-hero` classes) was not removed before adding the new `{% block content %}` section (using `gt-` design system classes). Django's template parser forbids duplicate block names at the same level.

**Exact Target Files**:
- `billing/templates/billing/cignal_dashboard.html`

**1-Step Fix**: Remove the old duplicate `{% block content %}...{% endblock %}` section. Keep only the new section that uses the current `gt-` design system classes.

**Detection**: Run `grep -n "block content" billing/templates/billing/cignal_dashboard.html` — if more than one match exists, the duplicate must be removed.

---

### ERR-079: Both MikroTik Routers Unreachable — LIVE MT STATUS Shows "Error" on All Customers

**Symptom**: The billing system shows `⚠️ Error` on LIVE MT STATUS for all customers. Production logs show:
```
Timeout/Error connecting to Mikrotik API on 192.168.88.2: timed out
Timeout/Error connecting to Mikrotik API on 192.168.88.1: timed out
Failed to get active PPPoE users from Mikrotik A: Router unreachable (cached)
Failed to get active PPPoE users from Mikrotik B: Router unreachable (cached)
```

**Root Cause Pattern**: The cloud server (DigitalOcean) loses API access to both MikroTik routers because the **office Tailscale subnet router bridge PC** lost its internet connection. The bridge PC connects to the internet via a **WiFi repeater**, and the repeater's LAN port (or the switch port it was plugged into) became faulty/intermittent — causing the Tailscale tunnel to drop.

**Key Diagnostic Clue**: "Was online for X weeks, then started dropping intermittently. Comes back online for a few minutes after restart, then drops again." This pattern = physical LAN port failure on the repeater or switch, NOT a software/Tailscale issue.

**Exact Target**: Office bridge Mini PC → WiFi repeater → LAN cable → switch/router port

**1-Step Fix**: 
1. Move the repeater's LAN cable to a **different port** on the switch/router
2. Tailscale reconnects automatically within 30–60 seconds
3. Router API access restores; LIVE MT STATUS errors clear on next page refresh

**Verification**:
```bash
ssh root@143.198.207.144 "docker logs --since 2m gametech-web 2>&1 | grep -i 'timeout\|timed out' | tail -10"
# Should return empty if routers are back online
```

**Long-term Prevention**:
- Run a direct LAN cable from the Mini PC to the switch — eliminate the repeater as a dependency
- Mark the faulty port with tape so it is never reused
- If repeater WiFi must be used, set Mini PC network adapter power management to OFF (Device Manager → adapter Properties → Power Management → uncheck "Allow computer to turn off this device to save power")

**Date Logged**: 2026-09-30

---

### ERR-080: DB Backup Button Redirects to Settings Instead of Downloading a File

**Symptom**: Clicking "DB Backup" on the Settings or Admin Panel page redirects back to the Settings page with no file downloaded.

**Root Cause**: The `backup_database_view` in `billing/views/settings.py` tried to read `settings.DATABASES["default"]["NAME"]` as a file path and serve it via `FileResponse`. On production (PostgreSQL), `NAME` is just a database name string (e.g. `gametech_db`), not a file path. `os.path.exists()` always returned `False`, so the view always hit the `messages.error` + `redirect("settings")` fallback.

**Exact Target Files**:
- `billing/views/settings.py` (`backup_database_view`)

**1-Step Fix**: Branch on `settings.DATABASES["default"]["ENGINE"]`:
- For SQLite: serve the file directly (existing behavior)
- For PostgreSQL: use `subprocess.run(["pg_dump", ...])` with `PGPASSWORD` env var, write to a temp file, serve via `FileResponse`, then delete the temp file

**Date Logged**: 2026-09-30

---

## ERR-042: Add Staff Modal Shows Generic "Please check input" Instead Of The Real Reason

**Symptom**: Submitting the "Add Staff Member" modal on `/staff/` always shows
`Error creating staff member. Please check input.` regardless of the actual cause.
The user cannot tell what is wrong with the form.

**Root Cause (TWO separate bugs, both must be fixed)**:

1. **Silent fallback swallowed every real message.** In
   `billing/templates/billing/partials/_modal_add_staff.html` the fetch handler did
   `await response.json().catch(() => ({}))`. When the server returned a **non-JSON**
   body (nginx 502 HTML page, Django 500 traceback page, or a 403 CSRF HTML page),
   `data` became `{}`, so `data.message` was `undefined` and the hardcoded fallback
   string was displayed. The real HTTP status was never surfaced.

2. **The form POSTed during a container restart.** nginx logged
   `"POST /staff/add/" 502` with `connect() failed (111): Connection refused` /
   `upstream prematurely closed connection`. The web container was down/restarting,
   so nginx had no upstream to talk to. Because of bug #1, the 502 looked like a
   form validation problem instead of a server outage.

**Confirmed Real Validation Rule (for this exact payload)**:
username `Vince` + password `Vince_12345` is **rejected** by
`billing/validators.py::validate_password_policy`:
> `Password must not contain or match your username, full name, or phone number.`

Reason: the policy rejects any password where the identifier appears as a substring
(`if len(val) >= 3 and val in pw_lower`). So `vince` inside `vince_12345` fails.
This is intended behaviour, not a bug.

**1-Step Fix**:
- `billing/views/staff.py` (`add_staff`): every `JsonResponse` error now includes a
  `"field"` key (`password`, `username`, `email`, or the specific missing field) so the
  frontend knows exactly which input to highlight. Empty-form responses report the
  first missing field instead of a generic "fill in all required fields."
- `billing/templates/billing/partials/_modal_add_staff.html`: replaced
  `response.json().catch(() => ({}))` with `await response.text()` + `JSON.parse` in a
  try/catch, then built an explicit message per HTTP status (401 / 403 / 502 / 504 /
  5xx / other). Added `markFieldError()` which adds `.gt-field-invalid` to the offending
  input, injects an inline red hint under it, focuses it, and clears on resubmit.

**Verification** (run the following Python block through the container shell):
```python
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
u = get_user_model().objects.filter(is_superuser=True).first()
c = Client(); c.force_login(u)
r = c.post("/staff/add/", {"username":"Vince","full_name":"Vince Macarandan",
    "email":"vince@gmail.com","role":"Agent","status":"Active","password":"Vince_12345"},
    HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_REFERER="http://testserver/staff/")
print(r.status_code, r.content.decode())
# Expect: 400 {"status": "error", ..., "field": "password"}
```

**Companion Gotcha - `docker restart` can leave a zombie container**:
If `gametech-web` disappears from `docker ps` but `docker exec` reports
`No such container`, the container is stuck in `created` state and a plain
`docker restart` will fail. Also, a new empty `gametech-billing_postgres_data`
volume gets created alongside the live one. Heal with:
```bash
ssh root@143.198.207.144 "docker rm gametech-web; cd /root/GAMETECH-BILLING-SYSTEM && docker compose up -d"
```
Always confirm the pre-existing DB volume is reused (check `docker inspect gametech-db`
mounts) so live subscriber data is never orphaned behind a fresh empty volume.

**Lesson**: Never `catch` a JSON parse failure into an empty object when the response
status matters. Read text, parse defensively, and always branch on the HTTP status so
infrastructure failures (502/504) are never misreported as user input errors.

**Date Logged**: 2026-09-30


---

### ERR-081: Containers Repeatedly Return to `Created` State — Concurrent Compose Sessions (Root Cause Confirmed)

**Symptom**: `gametech-web`, `gametech-celery` and `gametech-celery-beat` keep
reverting to `Created` while `gametech-db` / `gametech-redis` restart on their
own. `docker exec` fails with `No such container`. The site goes down
intermittently. `docker ps -a` may briefly show *no* containers at all.

**Root Cause (confirmed 2026-09-30)**: NOT a Docker daemon crash and NOT an OOM.
Verified: `snap.docker.dockerd` had 6 days of continuous uptime on the same PID,
`dmesg` showed zero OOM kills, and free memory was healthy. The cause is a
**second session running `docker compose up -d` concurrently**, which recreates
each other's containers mid-flight (this is the ERR-069 mechanism). On this date
an extra superuser named `screenshot_verify` (created 12:33, logged in 12:36)
was deploying alongside the primary session and triggering exactly this.

**Critical detail**: `restart: unless-stopped` does **not** rescue a container
that has never been started. A container left in `Created` will stay dark
forever, so the usual self-heal safety net silently does nothing.

**Fix**:
```bash
ssh root@143.198.207.144 "/root/GAMETECH-BILLING-SYSTEM/scripts/safe_compose.sh up -d"
```
`scripts/safe_compose.sh` wraps `docker compose` in an `flock` so two sessions
queue instead of fighting. Prefer plain `docker restart gametech-web` for routine
deploys (AGENTS.md Rule 32v2) — that path never triggers the flapping.

**Prevention**: One deploy at a time. Treat any account/session performing
verification screenshots as a *deploy-capable* session.

**Date Logged**: 2026-09-30

---

### ERR-082: Do Not Run the Django Test Suite Inside the `gametech-web` Container

**Symptom**: `docker exec gametech-web python manage.py test billing` prints
`EEEE...`, appears to kill the web container, and the container later reverts to
`Created` (see ERR-081). Running the suite is enough to destabilise production.

**Root Cause**: The suite builds a full test database (all 60+ migrations) inside
a 1 vCPU / 1.9 GB container that is simultaneously serving production traffic
alongside Postgres, Redis, Celery and Celery Beat. It is far too small to host
test workloads, and the container churn compounds ERR-081.

**Fix / Prevention**: Run tests on a local dev machine or a dedicated throwaway
container, never in the production `web` container. Reserve
`docker exec gametech-web python manage.py check` (cheap) for production
verification.

**Bonus finding**: the failing `E`s were **not** a code regression. They were
`column "portal_password_plaintext" of relation "billing_customer" does not
exist` — see ERR-083.

**Date Logged**: 2026-09-30

---

### ERR-083: `portal_password_plaintext` Was Applied to Production Without a Migration

**Symptom**: Every billing test erroring with
`ProgrammingError: column "portal_password_plaintext" of relation
"billing_customer" does not exist`, while production works perfectly.

**Root Cause**: `Customer.portal_password_plaintext` existed in `models.py` and
had been added to the production database by hand, but **no migration was ever
committed** for it. Production has the column; any database built from
migrations (CI, a new developer machine, a test run without `--keepdb`) did not.
`makemigrations --check --dry-run` correctly reported the drift.

**Fix**: Migration `billing/migrations/0063_customer_portal_password_plaintext.py`
now captures the field. Because production already had the column, it was
recorded there with a fake apply so the schema is untouched:
```bash
docker exec gametech-web python manage.py migrate billing 0063 --fake
```
Fresh databases now get the column for real.

**Lesson**: Never patch production schema by hand. If a column exists in prod
but `makemigrations --check` is clean, you have drift — a future rebuild will
break. Run `makemigrations --check --dry-run` before every deploy.

**Date Logged**: 2026-09-30
