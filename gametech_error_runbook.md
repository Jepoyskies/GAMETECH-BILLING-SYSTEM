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
| **ERR-086** | Peso sign renders as `â‚±` (mojibake) on tiles, tables, receipts | 6 template files (see detailed entry) | Frontend (Encoding) |

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

**See it on screen now**: The customer detail page (`/customers/view/<id>/`) shows this as
**Link Chain → 1. Mini PC = "We Are Blind"**, with `0/2 routers answered Ns ago`. Check that
before reading logs. Before 2026-10-01 this failure made *every* subscriber display as
**Fully Offline**, because an empty poll was read as "everyone is down" — a false accusation.
See `billing/diagnostics.py`.

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

---

### ERR-084: Revealed Passwords Showed `csr-12345678` / `ImportError` Took Down the Whole Site

**Symptom (A)**: On **Edit Staff Member** and **View Customer**, clicking the eye
icon revealed `csr-12345678` instead of `csr-12345678` (a hyphen turned into a
literal `\` `u` `0` `0` `2` `d`). The user could not change it back.

**Root Cause (A)**: `|escapejs` was used inside an **HTML attribute**
(`data-pw="{{ customer.pppoe_password|escapejs }}"`). `escapejs` is for *JS string
literals* and escapes the hyphen `-` as the six characters `\` `u` `0` `0` `2` `d`
(same for `=` and `'`). Inside an attribute
the browser decodes HTML but **not** the `\` `uXXXX` sequences, so the mangled text
was what got revealed and copied. The database was always correct.

**Fix (A)**: Drop `|escapejs` from `data-pw` attributes (Django autoescape
already handles the HTML context). Reading the value out of the DOM in JS
(`getAttribute`) means no JS escaping is needed at all.

**Symptom (B)**: Every page 500'd with
`ImportError: cannot import name 'action_required' from 'billing.decorators'`.

**Root Cause (B)**: Commit `58a86d3` added `@action_required` to the views **and**
the function to `billing/decorators.py`, but only the view half had been pushed.
Production ran views that imported a symbol the deployed decorators.py did not
have. All containers had also stopped, which hid the failure until restart.

**Fix (B)**: Pushed `58a86d3` and restarted the stack via `docker compose up -d`.

**Lesson**:
- Never use `|escapejs` in an HTML attribute. `data-*` attributes are read with
  `getAttribute()` and need no JS escaping; `escapejs` only belongs *inside* a
  real JS string literal (`onclick="fn('{{ x|escapejs }}')"`).
- Before restarting a downed droplet, run `git log origin/main..HEAD` locally.
  An unpushed commit holding half a refactor is the usual cause of
  "import name not found" on prod.
- Pages that display credentials must be `@never_cache`, otherwise the browser
  keeps showing a stale (possibly wrong) password after an override.

**Files**: `billing/templates/billing/view_customer/_info_cards.html`,
`billing/views/staff.py` (`edit_staff`)

**Date Logged**: 2026-09-30

---

### ERR-085: Plaintext Password Mirrors Removed (Security Hardening)

**Symptom**: Discovery finding, not a runtime error. `SystemAdmin.password_plaintext`
and `Customer.portal_password_plaintext` stored every staff login and every
subscriber portal login in clear text alongside the PBKDF2 hash. A database dump
or read-only SQL access yielded all of them.

**Root Cause**: Both columns existed only so staff could *read back* a password
instead of resetting it (added in migrations `0062`/`0063`). Both authentication
paths already used the hash, and `reset_customer_portal_password` already SMSeed
the temp password to the subscriber and held it in the session for a one-time
display. The mirrors were therefore redundant as well as a liability.

**Fix**: Migration `billing/migrations/0064_drop_plaintext_password_columns.py`
drops both columns. Removed the read-back UI (`Current Password` block on Edit
Staff, the password column on the staff list, the portal-password reveal on the
customer profile) and the dead `gtTogglePw`/`gtCopyPwFrom` helpers. Staff reset
via the existing Override Password field; subscribers use Forgot Password.

**Deliberately NOT changed**: `Customer.pppoe_password` and
`MikrotikDevice.api_password` stay plaintext. A MikroTik secret cannot be hashed
- the router must authenticate with the literal value - and the PPPoE secret is
the password the subscriber already shares with their own household.

**Backup**: `pg_dump` taken before the drop at
`/root/backups/pre_plaintext_drop_20260930_2105.sql`.

**Lesson**: Never add a plaintext mirror "so staff can see it". If a password
must be shown once, show it once at generation time (SMS/session), never persist
it. The reset flow is the only legitimate read path.

**Files**: `billing/models.py`, `billing/views/staff.py`,
`billing/management/commands/reset_all_portal_passwords.py`,
`billing/templates/billing/edit_staff.html`,
`billing/templates/billing/staff_and_admins.html`,
`billing/templates/billing/view_customer/_info_cards.html`

**Date Logged**: 2026-09-30

### ERR-086: Peso Sign Renders as `â‚±` (Double-Encoding Mojibake) on Tiles, Tables & Receipts
* **Symptoms**:
  * The peso sign `₱` displays as `â‚±` (three glyphs) on the Cignal dashboard revenue tile, addon plan prices, payout stats, plan list, edit-payment-log label, and agent stats.
  * Only SOME templates affected; models.py, services.py, portal statement and dispatch receipt render `₱` correctly.
* **Root Cause**:
  * Classic double-encoding mojibake baked into the template SOURCE. `₱` (U+20B1, UTF-8 bytes `E2 82 B1`) was decoded as Latin-1/Windows-1252 somewhere in the past → `â` `‚` `±` → saved as UTF-8. `base.html` correctly declares `<meta charset="UTF-8">`, so the file bytes themselves were wrong (not a charset-meta issue).
* **Exact Target Files** (21 occurrences across 6 templates):
  * `billing/templates/billing/cignal_dashboard.html` (revenue tile)
  * `billing/templates/billing/addon_plans_list.html` (3 sites)
  * `billing/templates/billing/agents/_stats.html`
  * `billing/templates/billing/edit_payment_log.html`
  * `billing/templates/billing/payouts/index.html` (13 sites)
  * `billing/templates/billing/plan_list.html` (2 sites)
* **1-Step Fix**:
  * Source-level replace of the mojibake sequence (U+00E2 U+201A U+00B1) with the correct `₱` (U+20B1) in those 6 files. No backend/charset changes needed. Verify with `grep` for the mojibake sequence repo-wide afterward.
* **Lesson**: When a currency/symbol shows as multiple weird glyphs, suspect double-encoding in the source file BEFORE touching charset headers or backend encoding. Check the actual bytes (e.g. Python `bytes` / `char` codepoints) rather than guessing from the rendered output.

**Files**: the 6 templates listed above
**Date Logged**: 2026-09-30

---

### ERR-087: "All Customers Offline" Was Unresolvable � No Way To Tell A Dead Mini PC From A Dead Office Uplink

**Symptom**: Every subscriber showed **Fully Offline**. The runbook had entries for
"router unreachable" and "Tailscale bridge drop", but neither the UI nor the logs could
answer the only question that matters: *is the Mini PC actually broken, or is it fine and
the LAN to the routers is broken?* Staff were guessing, and guessing wrong means either
wasted truck rolls or missed outages.

**Root Cause**: The cloud (Celery in `gametech-celery`) opens RouterOS sockets to
`192.168.88.x:8728` and that traffic rides **through the office Mini PC's Tailscale subnet
route** (`192.168.88.0/24`). So `0/N routers answered` is genuinely ambiguous � a powered-off
Mini PC and a powered-on Mini PC with a dead WiFi repeater produce *identical* evidence.
The old `router_status` compounded it by reporting `Offline` whenever the poll came back
empty, turning one bridge fault into a false accusation against every customer.

**Exact Target**: `billing/diagnostics.py`, `billing/views/api/bridge.py`,
`scripts/bridge_heartbeat.sh`, `billing/models.py` (`router_status` / `connection_status`)

**Why the Mini PC cannot self-report from inside a container**: Tailscale's LocalAPI resolves
peer credentials in the *host* PID namespace, so `GET /localapi/v0/status` over
`/var/run/tailscale/tailscaled.sock` returns **HTTP 403** to any container caller, even
`--user root`. Verified on the droplet. The heartbeat therefore runs on the **host**.

**1-Step Fix**: Two independent signals instead of one.
1. `scripts/bridge_heartbeat.sh` on the host reads real `tailscale status --json`, finds the
   peer advertising `192.168.88.0/24`, and POSTs it to `/billing/api/bridge/heartbeat/`
   (token-gated, fails closed with 503 if `BRIDGE_HEARTBEAT_TOKEN` is unset).
2. `billing/utils.py` keeps recording how many routers answered the last poll.

The pair is decisive:
| tunnel | routers | verdict |
|---|---|---|
| UP | 0 | `bridge_lan` � Mini PC is **fine**; the LAN to the routers is broken |
| DOWN | 0 | `bridge_down` � our side: Mini PC off, or office uplink/repeater dead |
| UP | some | judge that router normally |

`router_status` / `connection_status` now return `Unknown` (never `Offline`) while the bridge
is not `Online`, so the customer list stops accusing everyone.

**Install (droplet, root)**:
```bash
# 1. token into docker-compose.yml under web: and celery: environment:
#      BRIDGE_HEARTBEAT_TOKEN=<generated>
# 2. copy + enable
install -m 755 scripts/bridge_heartbeat.sh /root/bridge_heartbeat.sh
printf '%s' '<same token>' > /root/.bridge_token && chmod 600 /root/.bridge_token
crontab -e   #  * * * * * /root/bridge_heartbeat.sh >/dev/null 2>&1
# 3. restart so the env var lands
docker compose up -d
# verify
curl -s -X POST http://127.0.0.1:8000/billing/api/bridge/heartbeat/ \
  -H "X-Bridge-Token: <token>" -H 'Content-Type: application/json' \
  -d '{"online":true,"hostname":"DESKTOP-164V38N"}'
```

**Verification**: On any customer page, **Link Chain ? 1. Mini PC** must show a
`measured` badge (not `inferred`). `inferred` means the host cron is not installed yet and the
ladder is running on router-poll evidence alone.

**Lesson**: One signal cannot localise a fault when every downstream signal passes through
the thing that might be broken. When "A unreachable" could mean "A is dead" *or* "the only
path to A is dead", you need a second, independent observation of A itself before you can
tell staff where to drive.

**Files**: `billing/diagnostics.py`, `billing/views/api/bridge.py`, `scripts/bridge_heartbeat.sh`, `billing/models.py`
**Date Logged**: 2026-10-01
---

### ERR-088: Agent Portal Had a Dead Duplicate Template — Edits Were Going Into a File Nobody Renders

**Symptom**: An agent-facing page "looks" like it exists in two places. You open
`billing/templates/billing/agent_dashboard.html`, fix a bug, push, and nothing
changes in production. The bug is still there and you have no idea why.

**Root Cause**: `billing.views.agents.agent_dashboard` renders
**`billing/agent_portal/dashboard.html`**, not the top-level
`billing/agent_dashboard.html`. The top-level file is an orphan left from an
earlier iteration. It still contained a full Bootstrap/FontAwesome table, its own
header, and even referenced context variables (`qualified_count`, `target_count`)
that the view never sets — so it could not have rendered correctly even if wired.

**Fix**: Deleted `billing/templates/billing/agent_dashboard.html`. The live Agent
Portal is the `agent_portal/` folder: `base_agent.html` (own shell),
`dashboard.html`, `submit_prospect.html`, `edit_prospect.html`.

**Lesson**: Before editing any template, confirm the view's `render(request,
"...")` string points at it. Two templates for one view is a silent trap, and
Django will not warn you. Use `grep_search` for the filename across all
templates to check it is not orphaned before you trust it.

**Related**: The Agent Portal already had its own stripped-down shell
(`agent_portal/base_agent.html`) and its own dashboard. The missing half of the
persona split was the Technician, plus a landing router — see
`DECISION_LOG.md` "Persona Landing Router".

**Files**: `billing/views/agents.py`, `billing/templates/billing/agent_portal/`
**Date Logged**: 2026-10-01

---

### ERR-089: "Role = Agent" on the Staff & Admins Page Does NOT Create an Agent — Persona Users Were Bounced Back to the Main Dashboard

**Symptom**: An Agent or Technician logs in, is routed to their own portal,
and is immediately redirected back to the main billing dashboard with
"Your account is not linked to an Agent profile." The role badge on the Staff &
Admins page clearly says `Agent`.

**Root Cause — two parallel identity systems**:
1. `auth_user` (Django auth) — the real login, password, `is_staff`.
2. `SystemAdmin` (`username / full_name / email / role / status`) — the table
   the **Staff & Admins page actually lists** (`billing/views/staff.py:39`), and
   the source `user.role` resolves from.

`user.role` is **not a field on User** — verify with:
```python
"role" in [f.name for f in User._meta.get_fields()]   # -> False
```
It is injected at runtime, with a `SystemAdmin` lookup fallback in
`_role_allows()` (`billing/decorators.py:236-239`) and
`has_dispatch_permission()`.

The trap: the role LABEL is what `resolve_landing_url()` and `_role_allows()`
read, but it does **not** create the business profile that actually holds work:
- `Agent` (`User.agent_profile`) — prospects, commission ledger, payout batches
- `Technician` (`User.technician`) — the `JobTicket.technicians` M2M assignment

So `hasattr(user, "agent_profile")` is False, the view's
`except Agent.DoesNotExist` fires, and the user is bounced.

**Confirm with**:
```python
from billing.models import Agent
from dispatch.models import Technician
print(Agent.objects.count(), Agent.objects.filter(user__isnull=False).count())
print(Technician.objects.count(), Technician.objects.filter(user__isnull=False).count())
```

**Fix**: `python manage.py link_persona_profiles` (dry run by default,
`--apply` to write, `--unlink` to reverse). Idempotent; only touches users whose
`SystemAdmin.role` is exactly `Agent` or `Technician`; never guesses a phone and
never touches a password.

**Two related traps found in the same pass**:
- `is_staff` is the ONLY thing that grants `/admin/` (Django admin is routed at
  `gametech_core/urls.py:22`). Agent and Technician accounts created as staff
  could reach full Django admin. `link_persona_profiles` forces
  `is_staff = False`, matching `views/auth.py:191-192`. This breaks nothing:
  `_role_allows()` keys off `is_superuser` + `role`, never `is_staff`;
  `staff.py` lists `SystemAdmin` rows so they stay on the Staff & Admins page.
- `SystemLog` is `(table_name, record_id, action[max_length=50], changed_by)`.
  `views/auth.py:204` passes `user=` / `ip_address=` and a >50 char `action`
  inside a bare `try/except`, so **that audit entry silently never writes**.
  Put the human-readable text in `new_data`, keep `action` a verb like `CREATE`.

**Lesson**: In this codebase "role" is a label in a mirror table and a profile
is a real row. Never treat the Staff & Admins role badge as proof that an
Agent/Technician profile exists. A persona user is only real once the business
profile row is linked to the User.

**Files**: `billing/models.py` (`Agent`, `SystemAdmin`, `SystemLog`),
`billing/views/auth.py`, `billing/decorators.py`, `billing/views/staff.py`,
`billing/management/commands/link_persona_profiles.py`
**See also**: `DECISION_LOG.md` "Persona Landing Router"
**Date Logged**: 2026-10-01

---

### ERR-090: `manage.py seed --clear` Had No Production Guard — It Would Wipe Every Customer and Payment

**Symptom**: None yet. This is a **preventive** entry. A single mistyped
`python manage.py seed --clear` on the droplet destroys the business.

**Root Cause**: `seed.py` `--clear` ran, with no confirmation, no environment
check and no transaction:
```python
SystemLog.objects.all().delete()
SystemAdmin.objects.all().delete()      # every persona role
Payment.objects.all().delete()          # every receipt
Customer.objects.all().delete()         # 2,041 subscribers
MikrotikDevice.objects.all().delete()
Barangay / SubscriptionPlan / AccountType .delete()
Agent.objects.all().delete()            # Martin's agent profile
User.objects.filter(is_superuser=False).delete()   # Martin, Merk, all logins
```
None of those tables have a soft-delete, so there is **no undo**. And because
`SystemAdmin` holds every persona role, running it would also silently strip
`role=Agent` / `role=Technician` from Martin and Merk (who are no longer
`is_staff=True`, so they would **not** be re-synced by `staff_list`).

**Extra hazard found in the same file**: `seed.py` was the **entire file
duplicated** — two `class Command` definitions (807 lines). Python uses the
last one, so the first ~233 lines were a stale, truncated draft that was
completely dead code, and it was what made the real command hard to find and
edit.

**Fix**:
- Removed the dead duplicate: 807 -> 573 lines, one `Command` class.
- Added `_guard_clear()`, called as the FIRST statement of `handle()`. It
  returns immediately when `settings.DEBUG` is True (normal dev workflow) and
  otherwise **always** aborts, telling the operator to drop and recreate the
  database by hand. `--i-am-sure` deliberately does NOT unlock production: it
  exists only to make the abort message explicit.

**Verification** (guard called directly, never reaching the delete block):
```
DEBUG in production = False
  ack=False: correctly aborted -> Aborted. Database: gametech_db
  ack=True:  correctly aborted -> Aborted. Database: gametech_db
SystemLog rows before/after: 22153 / 22153
customers still present: 2041
```

**Lesson**: A destructive management command is a production incident waiting
to happen. Guard it at the top of `handle()`, before any side effect, and make
the guard testable in isolation. Never test it by running the real thing.

**Files**: `billing/management/commands/seed.py`
**Date Logged**: 2026-10-01

---

### ERR-091: Agent Cash-Out Requests Had NO Audit Trail (Silent `SystemLog` Failure)

**Symptom**: An agent requests a commission cash-out, the staff bell notification
fires and the success message shows — but nothing lands in the audit log, so
there is no record of who asked for what amount.

**Root Cause**: `billing/views/agents.py` did:
```python
try:
    SystemLog.objects.create(
        user=request.user.username,                                  # not a field
        action=f"Agent '{agent.name}' submitted cash-out request for PHP ...",  # >50 chars
        ip_address=request.META.get("REMOTE_ADDR", ""),              # not a field
    )
except Exception:
    pass
```
`SystemLog` has **no** `user` and **no** `ip_address` field, and `action` is
`CharField(max_length=50)`. So Django raised `TypeError` before touching the DB
and the bare `except` swallowed it. The entry was never written, not once. This
is a direct cash/ledger audit gap (AGENTS.md Rule 39).

**The same bug existed in `billing/views/auth.py`** (the "Configured Portal
Login for Agent" audit entry) — see ERR-089.

**How to find these without guessing**: `python manage.py audit_systemlog_calls`.
It AST-parses every `SystemLog.objects.create(...)` in the repo and reports
unknown field names, missing required fields, and `action` literals longer than
50. It executes nothing and touches no data. `--strict` for CI, `--show-dynamic`
to list the `action=` values built at runtime (8 remain, all needing a manual
length check).

**Current state**: both confirmed-broken sites are fixed. The auditor reports
`OK: no definite SystemLog defects. (8 dynamic action(s) pending manual review.)`
across 195 files in 14 apps.

**Fix pattern** — reuse the existing helper instead of hand-rolling kwargs:
```python
from billing.security import log_sensitive_operation
log_sensitive_operation("AGENT_CASHOUT_REQUEST", "Agent", agent.id,
                        request.user.username, "full sentence goes in details")
```
`action` stays a short verb; the human-readable text goes in `new_data`.

**Lesson**: A bare `except: pass` around an audit write converts a loud bug into
an invisible one. Audit writes should either succeed or be logged as an error
(`log_sensitive_operation` does `logger.error`) — never silently dropped. And
when auditing money movement, the audit write is the feature, not a side effect.

**Files**: `billing/views/agents.py`, `billing/views/auth.py`,
`billing/management/commands/audit_systemlog_calls.py`, `billing/security.py`
**Date Logged**: 2026-10-01

### ERR-092: "1,240 Paid but Offline" Was A False Alarm - A Router Outage Masqueraded As 1,240 Customer Outages

**Symptom**: The Customers Directory KPI strip showed **Paid/Offline = 1240** and
every visible row was badged "Paid, Offline". That reads as "almost your whole
customer base is down", and the correct staff reaction is to dispatch 1,240
technicians.

**It was false. Not one customer was actually offline.** All three production
routers were timing out at the time, so zero PPPoE sessions existed to observe.

**Root cause** — `billing/views/customers/list.py` compared `pppoe_username`
against the `active_pppoe_usernames_set` cache and treated *any* username not in
that set as "offline". When the routers are unreachable the set is **empty**, so
the empty set was read as "nobody is online" instead of "we could not look".

Two secondary defects compounded it:
- The seven KPI cards used independent `Q()` filters that **overlapped**, so
  they did not reconcile: 852 + 388 + 1240 + 402 + 389 + 16 = **2,047** against
  a total of **2,041**.
- `customer.connection_status` / `router_status` already had a blindness guard in
  `billing/models.py`, but the KPI counters bypassed the properties entirely and
  never got that guard.

**Fix**: new `billing/customer_state.py` is now the single source of truth.
`network_visibility()` returns `connected_usernames = None` when we cannot see
the network, and `hardware_state()` maps `None` to `"unknown"`, never
`"offline"`. One resolve pass produces both the counts and the rows, so a KPI
can never disagree with its own list. The page shows a banner while blind.

**Guard against recurrence**: `_assert_filters_cover_all_states()` raises at
import time if any `Lifecycle` lacks a `FILTERS` entry. That guard caught a real
regression during this work - `paid_unknown` had no filter, so 1,991 customers
vanished from the totals. It now fails loudly at startup instead of silently
misreporting.

**Verify**: KPI cards must sum to Total. Currently `SUM=2041 TOTAL=2041`.

**Files**: `billing/customer_state.py`, `billing/views/customers/list.py`,
`billing/templates/billing/customer_list/_hero.html`,
`billing/templates/billing/customer_list/_filters.html`,
`billing/templates/billing/customer_list/_customer_status.html`
**Date Logged**: 2026-10-02

### ERR-093: Routers Were Written To Unattended - Cron Suspended 751 Customers And Reconcile Pushed Secrets Every 30 Min

**Symptom**: After importing 2,038 customers from the legacy phpMyAdmin dump, two
scheduled jobs were one config flip away from a mass outage:

1. `auto-suspend` ran **hourly** and targeted every account with
   `expires_at <= now AND status='active'`. That matched **751** customers
   (739 on `patag`, 12 on `uptown`). Only `ROUTER_MODE=read_only` was stopping it.
2. `auto-reconcile-routers` ran **every 30 minutes** with no arguments and would
   create/overwrite PPPoE secrets on live routers unattended.
3. Separately, `billing/signals.py` pushed a customer to their router on **every
   `post_save`** - so the instant staff pressed Save, the secret was written to
   the live router. No confirmation, no diff, no undo.

**Why the 751 was the real danger**: the legacy export marked all 751 as
`status='active'` while their expiry was already past. The old PHP system had no
way to represent "expired on paper, still connected" - staff kept taking cash and
never cleaned up. Those are most likely **paying customers**. Suspending them is
a collections action, not a cron side effect.

**Note the trap**: `Payment` had 1 row and `outstanding_balance` was 0 for all
2,041 customers. That is *missing* data, not *zero* debt. And the importer
hardcoded `is_verified=True` and `sync_status="Synced"` (lines 293/298), so
unverified rows looked verified. Never read those flags as payment evidence.

**Fix**
- Removed `auto-suspend-hourly` and `auto-reconcile-routers-30min` from
  `CELERY_BEAT_SCHEDULE`. Nothing on the schedule may write to a router.
- `auto_suspend` now aborts above `BULK_SUSPEND_THRESHOLD = 50` and logs
  `AUTO_SUSPEND_ABORTED`, and refuses outright when `network_visibility()` is
  false. Verified: it reports
  `ABORTED: 751 ... No customers were suspended.`
- `auto_reconcile_routers` requires `--apply`. Bare invocation is a read-only
  report; the old unattended cron call became a no-op.
- `sync_customer_to_mikrotik` is now **opt-in**. Without
  `instance.push_to_router = True` it calls `_stage_pending()` and writes
  nothing. Verified with a spy: plain create = 0 router writes; explicit push = 1.
- `sync_status` gained `Unverified` and `Pending`, and the default is now
  `Unverified` (migration `0067`) which reset the 1,290 falsely-"Synced" rows.

**Deliberate staff actions are unaffected**: suspend, reconnect, router transfer
and payment-activate all call the router API directly rather than relying on
`save()`, so they still write immediately.

**Files**: `gametech_core/settings.py`, `billing/signals.py`,
`billing/models.py`, `billing/management/commands/auto_suspend.py`,
`billing/management/commands/auto_reconcile_routers.py`,
`billing/management/commands/auto_sync_failed.py`,
`billing/migrations/0067_customer_sync_status_unverified.py`
**Date Logged**: 2026-10-02

### ERR-094: The Router's `disabled` Flag Was Never Read - The Sync Manager Could Not Tell A Cut-Off Customer From A Live One

**Symptom**: The Sync Manager listed router secrets with profile, comment,
password and an "Active" indicator, but no enabled/disabled state. Every secret
looked equally healthy, so the one question that matters for collections - "is
this person actually cut off?" - had no answer on the page.

**Root cause**: `MikrotikAPI.get_all_pppoe_users()` in
`network_manager/sync_services.py` built its output dict from `name`, `password`,
`profile`, `comment`, `is_active`, `is_suspicious` and **never read
`s.get("disabled")`**, even though the MikroTik `/ppp/secret` resource returns it
as the string `"true"`/`"false"`.

`is_active` was also the wrong signal for this question: it reflects
`/ppp/active`, i.e. *who is dialled in right now*, which is empty at 3am. A
customer who is suspended and a customer who is quietly paying both show as
"not active".

**Proof from the live router** (`Mikrotik A`, 192.168.88.2) after the fix:

| name | enabled | disabled | active | profile |
|---|---|---|---|---|
| jane_pppoe | False | True | False | default |
| john_pppoe | False | True | False | default |
| Jillian | True | False | False | default |
| delacruz_juan | True | False | **True** | GTipid Fiber 1000 |

Before the fix all four rows were indistinguishable.

**Fix**
- `get_all_pppoe_users()` now normalises `disabled` to booleans and returns both
  `disabled` and `is_enabled`.
- Added a `No Profile or Password - cannot authenticate` suspicious reason.
  `Jillian` is enabled but has **neither** a profile nor a password, so it can
  never authenticate no matter what its comment claims.
- `sync_manager` now computes `router_disabled`, `connected_but_unpaid` and
  `state_mismatch`, splitting matched users into `synced` vs `needs_review`:
  - system says lapsed, router says enabled -> **Connected, Unpaid**. Collect.
    Do NOT suspend. This is the state the old PHP system could not represent.
  - system says fine, router says disabled -> a paying customer is cut off.
    Reconnect.

**Caveat on comments**: `delacruz_juan` carries the old system's comment format
(`paid Sep 23, 2026 exp Nov 19`) and is flagged `Missing/Invalid Comment`
because the heuristic expects `Name | Barangay`. That flag is a false positive
here - the comment is real data from the legacy router and is worth reading
before "fixing" it.

**Files**: `network_manager/sync_services.py`, `network_manager/views/sync.py`
**Date Logged**: 2026-10-02

### ERR-095: /customers/ Took 40 Seconds and 13 MB - A 2,041-Row N+1 Was OOM-Killing The Web Container

**Symptom**: Opening the Customers Directory took ~40 seconds and produced a
**13.2 MB** HTML document (~6,800 bytes per row). On a 1 vCPU / 2 GB droplet it
regularly pushed the web container into the OOM killer -- at 23:05 all five
containers were SIGKILLed together (`exit 137`) and the site went dark. Two
separate "the site is down" incidents traced back to this one page.

**Root causes, in order of cost**

1. **N+1 on `dispatch_status`.** `Customer.dispatch_status` falls through to
   `self.dispatches.filter(done_at__isnull=True).first()` and the status cell
   calls it per row. That is **2,041 database queries on every page load**,
   ~23s of the total. Fixed by resolving it in the view with two bulk queries
   and pinning `_dispatch_status_pinned` onto each row, so the model property
   and the template both read the batch value.
2. **No pagination.** All 2,041 rows were rendered into one document so the
   client-side DataTable could page them. The browser had to receive the entire
   customer base to search it.
3. **Duplicate per-row property calls.** The status cell called
   `customer.router_status` and `customer.connection_status`, and
   `connection_status` rebuilt a lowercased set of every active user for every
   row -- an O(n^2) string loop. ~6,000 redundant Redis round trips, ~7s.
4. **Router reachability read per customer** instead of per device, so a 4-device
   setup made ~2,000 redundant `cache.get` calls.

**Fix**

- Bulk-resolve dispatch, router and connection state once in the view; the
  template reads `resolved_*` values. **No per-row queries remain.**
- **Server-side search / filter / sort / pagination** (`PAGE_SIZE = 100`),
  searching across name, username, email, phone, plan, barangay and router.
- DataTables is kept ONLY as the checkbox/row-helper layer, because
  `customer_list/_scripts_bulk.html` depends on `table.$()` for bulk SMS, email
  and router transfer. Its own search/ordering/paging are disabled so there is
  one UI, not two.

**The trap to avoid**: an earlier attempt capped the queryset and shipped 25
rows, which made search *blind* -- "Juan Dela Cruz" was unfindable among 2,041
customers. Capping rows is only safe when search moves into the database with
it. Verified: walking pages 1..21 reaches **2,041 of 2,041** unique customers.

| | before | after |
|---|---|---|
| render time | 39.6s | **0.5s** |
| HTML size | 13.2 MB | **946 KB** |
| DB queries on the page | ~2,041 | **3** |

**Guard**: `scripts/maintenance/check_templates.py` compiles all 235 templates
and fails loudly. It exists because two template bugs here (`{%- ... %}` is not
valid Django, and `page_obj.previous_page_number` *raises* `EmptyPage` on page 1
instead of returning a falsy value) were each only discoverable as a live 500.

**Files**: `billing/views/customers/list.py`, `billing/models.py`,
`billing/templates/billing/customer_list/_table.html`,
`billing/templates/billing/customer_list/_scripts.html`,
`billing/templates/billing/customer_list/_hero.html`,
`billing/templates/billing/customer_list/_styles.html`,
`scripts/maintenance/check_templates.py`
**Date Logged**: 2026-10-02

### ERR-096: The Sync Manager Had Its OWN Connection Path With No Circuit Breaker - 15s Hang Per Dead Router

**Symptom**: Opening the Sync Manager for a powered-off router blocked for
~15 seconds on every visit, which reads as "the site is broken".

**Root cause**: `network_manager/sync_services.py` has a **second, independent**
connection path (`_get_api_connection`) alongside
`network_manager/services/base.py`. It had **none** of the protections:

- no circuit breaker -- it never checked `router_unreachable_{id}`, so every
  page load paid the full socket timeout again
- a 5s socket timeout instead of the 2s the other path uses
- a legacy-auth retry on **any** `RouterOsApiCommunicationError`, so a router
  that is simply unplugged was dialled twice

5s x 2 attempts plus library retries = ~15s of dead page.

**Fix**
- Both paths now share **one** breaker key. `sync_services` resolves the
  `MikrotikDevice` from the IP so `router_unreachable_<id>` matches; otherwise
  the two paths keep separate opinions and neither trips the other's breaker.
- Escalating backoff in `base.py`: 30s -> 2m -> 5m -> 15m, reset the moment the
  router answers, so recovery is still automatic. These are LAN devices -- one
  that is down stays down until someone fixes it physically.
- **Do not retry legacy auth when the router is unreachable.** Auth mode is
  irrelevant to a host that never answered. The retry now only fires when the
  router replied and rejected the credentials.
- The Sync Manager view checks the breaker *before* dialling and shows a
  **"Retry now"** button (`?force=1`) so a cached outage is never a dead end.

**Measured**: all four routers now load in **0.03-0.53s**. The 15s figure only
survives on a genuinely cold first hit, which the 10s background poller absorbs.

**Lesson**: two connection paths to the same hardware means two sets of bugs.
Any new router call must go through `network_manager/services`, not a local
helper.

**Files**: `network_manager/sync_services.py`, `network_manager/services/base.py`,
`network_manager/views/sync.py`,
`network_manager/templates/network_manager/sync_manager.html`
**Date Logged**: 2026-10-02

---

### ERR-097: `add_customer` Did NOT Need An Install Ticket - `dispatch/signals.py` Already Created It (Near-Miss Double-Dispatch)

**Symptom**: A new applicant created at `/customers/add/` showed
"installation order dispatched to the unassigned queue", but no `JobTicket`
existed for them. Read alone, that looks like a missing dispatch bridge.

**It was not missing.** `dispatch/signals.py` hooks `post_save` on `Customer` and
already creates the `INSTALLATION` ticket, with a de-duplication guard that looks
for an existing open `INSTALLATION` ticket first. A raw
`JobTicket.objects.create(...)` added inside `billing/views/customers/crud.py`
therefore produced **two** install tickets per applicant -- a technician
dispatched twice to one address, and the QA bounce-back counter double-counting.

**Why the near-miss was so easy to fall into**: the dispatch bridge is in the
`dispatch` app, not `billing`. Grepping only `billing/signals.py` for
`JobTicket.objects.create` returns nothing and reads as "no signal exists".

**Rule**: never create a `JobTicket` from a billing view. Go through the signal
or the dispatch views. Pinned by `billing/tests/test_single_install_ticket.py`.

**Lesson**: before concluding "this view creates nothing", check the OTHER app's
signals. Cross-app side effects are the normal case in this codebase.

**Files**: `dispatch/signals.py`, `billing/views/customers/crud.py`,
`billing/tests/test_single_install_ticket.py`
**Date Logged**: 2026-10-03

---

### ERR-098: Agent/Technician Portal Light Mode Was Unreadable - Accent Colours, Dead KPI Selectors, And A Rule That Repainted Buttons

Four separate defects made both persona portals fail WCAG AA in light mode while
looking fine in dark mode. Found by measuring computed contrast in the browser
(not by reading the CSS).

1. **Accent-on-soft-fill = invisible.** `.pt-portal-tag` and `.pt-badge-accent`
   painted `--persona-accent` (Gametech gold `#f8a815`) on `--persona-accent-soft`
   (16% gold): **1.00:1** -- literally unreadable. `--gt-gold-text` (`#8A5A05`)
   already existed for exactly this. Added a `--persona-accent-text` token
   (darkened in light, bright in dark) and routed every accent-as-text usage
   through it. Same bug hit `.pt-tab.active`, `.pt-kpi-accent .kpi-value` and
   `.btn-outline-primary`.
2. **The KPI colour modifiers were dead code.** They were written as
   `.pt-kpi-*  .pt-kpi-value`, but every template renders `class="kpi-value"` --
   `pt-kpi-value` appears nowhere. All six technician KPI numbers were falling
   back to plain body text. Renamed the child selector to `.kpi-value`.
3. **The light-mode modifiers still lost.** `.portal .kpi-value` is declared
   *later* in the file at equal specificity, so it won. Scoped the modifiers
   under `.portal` to outrank it.
4. **The theme repainted Bootstrap buttons.** `body.portal a { color: ... }`
   (0,1,2) outranks `.btn-outline-danger` (0,1,0), so the Logout button rendered
   indigo-on-navy at **1.87:1**. Narrowed to `a:not(.btn)`, and added a
   dark-mode override for `.btn-outline-danger` (Bootstrap's red is 3.73:1 on
   navy, under the 4.5 AA threshold for 14px text).

Also removed the last hardcoded hex from `tech_dashboard.html` (six inline
`style="color: #xxxxxx"`), which included a stray `#a78bfa` purple, and added
`text-warning`/`text-info`/`text-success`/`text-danger` remaps to the existing
`.portal` legacy bridge so every status pill in both portals themes at once.

**Lesson**: "it renders and the colours look right in the code" is not evidence.
Alpha compositing matters -- a 16%-opacity fill over white is near-white, so the
real background is never what `backgroundColor` reports. Measure the composited
pair.

**Gotcha that cost the most time**: toggling `dark-mode` by hand with
`classList.add()` and reading `getComputedStyle` in the *same* evaluate call
returns **stale values** and invents contrast failures that do not exist. Drive
the theme the way a user does -- `localStorage.setItem("theme","dark")` then a
real navigation -- and read on a later turn.

**Files**: `static/css/gt/portal.css`,
`billing/templates/billing/agent_portal/base_agent.html`,
`dispatch/templates/dispatch/pipeline/portal_base_tech.html`,
`dispatch/templates/dispatch/pipeline/tech_dashboard.html`
**Date Logged**: 2026-10-03

---

### ERR-099: No CSR Could Ever Create A Customer - `add_customer` Gate Used The Wrong Permission Codename

**Symptom**: `GET /customers/add/` returned **403 Forbidden** for every non-superuser.
The CSR was bounced from the single most important screen in the product. The
prospect page's "Run Checklist & Add Customer" button led straight to a dead end.

**Root cause**: two parallel permission systems that never met.
- The role matrix (`setup_dispatch_permissions.ROLE_PERMISSION_MATRIX`) grants the
  **custom** permission `billing.create_customer`
  ("Can convert prospect and create customer") to Staff + CSR.
- The view was decorated `@permission_required("billing.add_customer")` --
  Django's **auto-generated** add permission, which **no role group was ever
  granted**.

So `role_required(["Admin","Staff","CSR","Dispatch"])` passed, and the
`permission_required` underneath it killed the request one layer down. Only the
three superuser accounts worked, which is why this survived so long.

**Fix**: the view now gates on `billing.create_customer`.

**The class of bug**: the matrix could only grant the 14 *custom* permissions in
`DISPATCH_PERMISSIONS` (`perm_objs`), because `group.permissions.set([perm_objs[p]
for p in perms if p in perm_objs])` silently dropped anything else. Six views were
gated on auto permissions no role could hold:

| View | Gate | Was reachable by |
|---|---|---|
| `add_customer` | `billing.add_customer` | superusers only |
| `pay_customer_view` | `billing.add_payment` | superusers only |
| `customer_force_suspend` / `_reactivate` | `billing.change_customer` | superusers only |
| `customer_rebate_view` | `billing.add_rebate` | superusers only |
| `customer_rollback_view` | `billing.add_rollback` | **nobody, ever** |
| `delete_customer` | `billing.delete_customer` | superusers only |

That is: **taking a payment, suspending a customer and recording a rebate were
all impossible for counter staff.** Fixed by making the matrix resolve Django
auto permissions too (`AUTO_PERMISSION_CODENAMES`) and by granting the counter
set to Staff/CSR, with `delete_customer` kept admin-only.

**`billing.add_rollback` does not exist** in `auth_permission` at all -- the
`Rebate` model only has add/change/delete/view. That gate was permanently
unsatisfiable. Rollback rewrites the customer's expiry and balance, so it is now
gated on `change_customer`.

**Safety added**: the command now resolves every permission the matrix names and
**aborts** rather than writing a partial group, so a typo can never again
silently strip a role's access.

**Lesson**: when a view stacks `@role_required` and `@permission_required`, the
two must agree. Grep every `permission_required("...")` string and confirm each
one is actually granted to the roles the role-list implies.

**Files**: `billing/views/customers/crud.py`, `billing/views/payments/rebates.py`,
`billing/management/commands/setup_dispatch_permissions.py`
**Date Logged**: 2026-10-03

---

### ERR-100: Staff Were Logged Out After 5 Minutes Of Inactivity

**Symptom**: users were repeatedly returned to `/login/` mid-task. Reproduced
constantly while testing the CSR onboarding flow.

**Root cause**: `SESSION_COOKIE_AGE = 300  # 5 minutes` was hardcoded in
`settings.py`. With `SESSION_SAVE_EVERY_REQUEST = True` this is an *idle*
timeout, but 5 minutes is far too short for counter work -- filling the onboarding
checklist, keying a payment reference, or writing a long install address would
lose the form and bounce the user.

**Fix**: `SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=28800)`
(8 hours, one working day). Still sliding, still an idle timeout, now tunable
from `.env`.

**Lesson**: an idle timeout is a business decision, not a constant. Put it in env.

**Files**: `gametech_core/settings.py`
**Date Logged**: 2026-10-03

---

### ERR-101: Three Of Four Routers Are Unreachable From The Droplet

**Symptom**: reconciliation audit could only read **Mikrotik A**. The other three
tripped the circuit breaker:

```
ccr2116.v1 - patag        172.30.120.1  unreachable
ccr2116.v2 - uptown       172.30.120.2  unreachable
ccr2116.v3 - patag_carmen 172.30.120.3  unreachable
Mikrotik A                reachable, 4 PPPoE secrets
```

**Why**: `172.30.120.0/24` is RFC1918 private space. It is not routable from a
DigitalOcean public-IP droplet. Those three devices are only reachable from the
office LAN (or a VPN that is not connected). The circuit breaker is behaving
correctly -- this is a network topology fact, not a code fault.

**Consequence for reconciliation**: any audit must distinguish
*"router unreachable"* from *"zero customers"*. `get_active_pppoe_users()` in
`network_manager/services/users.py:9` swallows every exception and `return []`,
so a dead router is indistinguishable from an empty one. A reconciliation built on
it would confidently report the whole estate as offline.

**Fix direction**: have the audit check reachability first and refuse to bucket
when a router is down (see `archived_scripts/router_crm_reconciliation.py`).

**Files**: `network_manager/services/users.py`, `network_manager/models.py`
**Date Logged**: 2026-10-03

---

### ERR-102: A Bulk-Wipe Script Deleted Every User Including Staff

**What happened**: `archived_scripts/wipe_operational_data.py` keeps a set of
staff usernames and deletes the rest. The keep-set was written lowercase
(`{"jep", "martin", ...}`) but `auth_user.username` stores them capitalised
(`Jep`, `Martin`). `exclude(username__in=...)` matched nothing, so **all ten users
were deleted**, including every superuser, plus the Agent and Technician profiles.

**Recovery**: a verified `pg_dump` taken minutes earlier
(`/root/backups/PRE_WIPE_20261003_084711.dump`, 57 tables with data) restored the
database in full -- 2,041 customers and all staff. No permanent loss, entirely
because the backup existed and was verified *before* the destructive step.

**Fixes baked into the script**:
- keep-set uses exact stored casing, with a comment saying why
- a `preflight()` that raises `SystemExit` unless every staff account it intends
  to keep actually exists, and prints exactly which users are about to die
- a post-condition that raises if any staff went missing

**Lesson**: on a bulk delete, the dangerous part is not the DELETE, it is the
*filter*. Always assert the survivors first, and never trust a backup you have
not restored-tested. `auth_user.username` is case-sensitive -- there is no
`iexact` here.

**Files**: `archived_scripts/wipe_operational_data.py`
**Date Logged**: 2026-10-03

---

### ERR-103: `ROUTER_MODE=read_only` Silently Skips Provisioning

**Finding**: `.env` on the droplet sets `ROUTER_MODE=read_only`. Every router
write (`.add()`, `.set()`, `.remove()`) is intercepted by
`network_manager/services/read_only.py` and logged as a `BLOCKED_WRITE`
`SystemLog` row; only reads pass through.

**Consequence**: a customer created through the normal flow is **never** given a
PPPoE secret. Confirmed in the audit -- customer #2128 went through
Agent -> CSR -> assign -> technician COMPLETED and became `active`/`installed`,
but bucket **F (no secret on any router)** correctly reported it, and
`delacruz_juan_e2e` does not exist on Mikrotik A.

So the CRM and the routers are **intentionally** out of sync right now. This is
the safety interlock described in `docker-compose.yml`, not a bug -- but it means
the system is **not** ready to provision live subscribers until the mode is
deliberately changed after router credentials are confirmed.

**Lesson**: `read_only` is safe but must not be mistaken for "working". Before
go-live, confirm which mode is live and verify a real secret appears on the
router after creating a customer.

**Files**: `.env`, `network_manager/services/read_only.py`,
`network_manager/services/base.py`, `docker-compose.yml`
**Date Logged**: 2026-10-03

---

### ERR-104: Completing An Install Silently Activated The Subscriber - Activation Must Be Payment-Gated

**The rule the owner actually runs the business on**:
> after installation juan either pays to the technician or through online, or calls
> the CSR. The CSR clicks juan's profile, clicks renew/pay, pays the amount, then it
> gets active with the right due date.

**What the code did**: the technician's **Done** button set `status = 'active'`
on the customer by itself, with no `Payment` row and `expires_at = None`. End-to-end
test reproduced it: ticket `COMPLETED`, customer `active`/`installed`,
`installed_at` set, **`expires_at = None`, zero payments**. That is a subscriber
live on the network, marked Active in billing, owing nothing and due no date --
created by a technician clicking a button.

Meanwhile the payment path had the opposite gap: `pay_customer_view` set
`expires_at` correctly but only promoted `suspended -> active`. A never-paid
`pending` customer who paid stayed `pending` forever.

**Root cause**: activation had **seven** independent implementations spread across
completion paths, and "activate" was bundled into "the work is finished".

**Sites that self-activated** (all now guarded):
- `dispatch/signals.py` `sync_ticket_completion_to_customer` -- technician Done
- `dispatch/views.py` `complete_job_view` (legacy), DispatchRecord done, MonitoringRecord done
- `dispatch/views_approval.py` admin final approval
- `dispatch/pipeline_views.py` final_approve and approve (x2)

**Fix**: one shared rule on the model, so the rule lives in one place:

```python
@property
def awaiting_first_payment(self):
    """Physically installed, but never paid for."""
    if self.installation_status != "installed":
        return False
    if self.expires_at:
        return False
    return not self.payments.exists()
```

Every install-completion site now sets `installation_status = 'installed'` and
skips `status = 'active'` while `awaiting_first_payment` is True. Admin/QA
approval confirms the **work**, not the **payment**.

`pay_customer_view` now promotes `pending -> active` in the same transaction
that sets `expires_at` and `first_payment_date`, so **a due date and an Active
status can never disagree**.

**Verified** (`archived_scripts/e2e_payment_gated_activation_test.py`, 12/12):
- technician Done -> `installed` / still `pending` / `expires_at None` / 0 payments
- CSR pays -> `active` + `expires_at = <one month later>` + `first_payment_date`
- a customer who has already paid is still activatable (no regression)

**Lesson**: "the job is done" and "the customer is paying" are different facts.
Anything that conflates them will eventually hand out free service. When a state
has two independent causes, make ONE of them the only writer.

**Files**: `billing/models.py` (`Customer.awaiting_first_payment`),
`dispatch/signals.py`, `dispatch/views.py`, `dispatch/views_approval.py`,
`dispatch/pipeline_views.py`, `billing/views/payments/transactions.py`
**Date Logged**: 2026-10-03

---

### ERR-105: 41 Billing/Customer Views Were Gated By `@login_required` Alone

**Symptom**: a field Technician (Merk) could open `/customers/` and read the entire
subscriber list -- names, addresses, phones, balances. A static audit found the
same class of hole on **41 views** that touch customer, billing or money data.

Worst offenders reachable by any authenticated account:
- `cignal_export_csv_view` -- export every Cignal subscriber to CSV
- `create_xendit_invoice` -- **create real payment invoices**
- `purge_all_cancelled_cignal_subscriptions` / `purge_cignal_subscription` -- destructive
- `cancel_cignal_subscription`, `process_cignal_payment` -- money movement
- `payment_receipt_view`, the whole Cignal dashboard/applications/logs family

**Root cause**: `@login_required` answers "is this a known user", not "is this
user allowed to do this". These views simply never got a role gate. The sidebar
hid the links, but the URLs were open -- which is exactly what you must never rely
on for authorisation.

**Fix**: a new `billing_required` decorator in `billing/decorators.py` that
consults the same `StaffRole.can_access_billing` the sidebar uses, so the Role
Editor stays the single source of truth. Applied to 30 views across
`views_receipt.py`, `views/cignal_dashboard.py`, `views/services.py`,
`views/xendit.py`. `customer_list` got the check inside the view body so the Agent
redirect keeps priority.

Verified matrix (deny = 302/403):
- Technician: denied on all 10 billing pages
- Agent: denied on all 10
- CSR / Admin: allowed (CSR correctly still bounced from Admin-only pages)

**Lesson**: hiding a link is not a permission. Any URL reachable by an
authenticated user must be gated at the view.

**Files**: `billing/decorators.py` (`billing_required`),
`billing/views/customers/list.py`, `billing/views/cignal_dashboard.py`,
`billing/views/services.py`, `billing/views/xendit.py`, `billing/views_receipt.py`
**Date Logged**: 2026-10-04

---

### ERR-106: The Agent Commission Engine Was Dark - And Compose Silently Swallowed The Fix

**Symptom**: the Agent Portal advertises "Claimable Commission" and "Cashout at 5"
but every agent sits at PHP 0.00 forever. No agent has ever qualified.

**Root cause - two layers**:
1. `INCENTIVES_ENABLED = env.bool("INCENTIVES_ENABLED", default=False)` was never
   set in `.env`, so the whole engine (`billing/services/incentives.py`, the
   `post_save` trigger on Payment, qualification, payout batches) was a no-op.
2. Even after adding it to `.env`, it stayed off: **`docker-compose.yml` never
   passed it through.** `x-app-env` lists each variable explicitly, so anything
   not listed never reaches the container regardless of `.env`. Setting it in
   `.env` did literally nothing.

**The same trap applied to `ROUTER_MODE`**, which was hardcoded `ROUTER_MODE: read_only`
in compose -- so it could never be changed by editing `.env` either. Both are now
env-driven with the safe value as the default:

```yaml
ROUTER_MODE: ${ROUTER_MODE:-read_only}
INCENTIVES_ENABLED: ${INCENTIVES_ENABLED:-False}
SESSION_COOKIE_AGE: ${SESSION_COOKIE_AGE:-28800}
```

**Verified after enabling** (`INCENTIVES_ENABLED=True`): 5 agent-referred customers
paid 2 months each -> 5 qualification events, each backed by a real `Payment` row
-> `claimable_amount = 2500.00` and `is_cashout_eligible = True` -> Agent Portal
shows PHP 2,500.00 -> payout batch `BATCH-...-001` created with exactly 5 events
-> claimable resets to 0 -> CSR correctly refused `mark-paid` (no
`billing.mark_payout_paid`) -> Admin marked it paid, `paid_at` set, all 5 events
flipped to `paid_out`.

Note the qualification threshold is **2x the monthly price** (2nd month paid), and
cashout needs `batch_size` (5) qualifications. Both are intentional.

**Lesson**: a feature behind a flag that nobody set is a feature that does not
exist. And with Compose, an env var that is not listed in `environment:` does not
exist either -- `.env` alone is not enough.

**Files**: `docker-compose.yml`, `.env`, `billing/decorators.py`
**Date Logged**: 2026-10-04

---

### ERR-107: Force Suspend/Reactivate Gated BILLING On ROUTER Success

**Symptom**: with `ROUTER_MODE=read_only` (or any router timeout, or a customer
with no device assigned) staff **could not suspend or reactivate anybody**. The
collections workflow was dead and the failure looked like a normal redirect.

**Root cause**: a Rule 35 violation. `customer_force_suspend` only wrote
`status = "suspended"` *inside* `if success:` from the router call, and
`customer_force_reactivate` nested three levels of router success
(`enable` -> `profile` -> `kick`) in front of its DB update. Billing truth was made
dependent on hardware reaching back.

**Fix**: both now write the CRM status and the AuditLog **first, unconditionally**,
then attempt the router action as a separate best-effort step whose outcome is
reported distinctly (`messages.warning` tells staff the line may still be live and
to check the Sync Manager). Reactivating still requires superuser + password +
reason, and still never touches `expires_at`.

Verified: suspend works with no device and no router write; superuser reactivate
works the same way; CSR is still refused the reactivate override.

**Lesson**: hardware connectivity and billing lifecycle are independent domains.
Never let a router timeout decide whether a customer is suspended.

**Files**: `billing/views/customers/actions.py`
**Date Logged**: 2026-10-04

---

### ERR-108: Nothing Was Scheduled To Notice A Subscriber Had Gone Past Due

**The risk the owner named**: after cutover, "some customers will go past their
actually due dates and not get expired... connecting them right away makes the
company bankrupt."

**Confirmed as a real gap.** `auto_suspend` is deliberately unscheduled (the
project rule: nothing writes to a router unattended). But that rule removed the
*only* expiry enforcement, so a subscriber whose `expires_at` had passed simply
kept `status="active"` and stayed online **forever**. Verified: with
`expires_at` 5 days in the past, nothing had changed the status and no scheduled
task would have.

The safety net exists but is passive -- the customer list resolves such a row to
`connected_unpaid` ("Connected, Unpaid", `billing=lapsed`, `hardware=connected`,
`priority=0`), which is exactly right, but only if a human opens the list.

**Fix -- `billing/services/expiry_sweep.py` + `billing.tasks.expiry_sweep_task`,
scheduled 07:15 daily.** It does the *safe* half only:

- auto-renews from advance payment (`outstanding_balance <= -plan_price`) and
  writes the matching `Payment` row with `reference_no="AUTO-RENEW"`
- counts everyone past due, split by who is still online
- raises ONE `Notification` for staff linking to `/customers/`
- **never touches a router.** Suspending stays a deliberate human action through
  the "Connected, Unpaid" queue, which is what the lifecycle vocabulary intends.

`auto_suspend` remains unscheduled, so the safety rule is intact.

Verified 12/12: advance auto-renew granted a future expiry and logged a Payment;
the plain lapsed customer was left `active`; a Notification was raised; the router
was **byte-identical before and after**; the sweep is in the beat schedule and
`auto_suspend` is still not.

**Lesson**: "nothing automated touches the router" and "nothing notices a
non-payment" are different decisions. Removing the unsafe half should not have
removed the visibility half.

**Files**: `billing/services/expiry_sweep.py`, `billing/tasks.py`,
`gametech_core/settings.py`
**Date Logged**: 2026-10-04

---

### ERR-109: Plan Display Name Was Doing Double Duty As The MikroTik Profile

**Symptom**: customers on nicely-named plans (`GTipid Fiber 1000`, `5Mbps`,
`75 Mbps Plan`) would show as PERMANENT DRIFT in the Sync Manager, because the
comparison is exact string equality against the router's `/ppp/profile` name
(`pppoe-100m_1k`, `pppoe-15m_500`). Half the catalogue could never line up with
any router.

**Root cause**: `SubscriptionPlan` had no router-profile field. `name` was both
the customer-facing product label AND the technical router profile. Those are two
different namespaces and the legacy system already used the `pppoe-<speed>` form.

**Fix**:
- `SubscriptionPlan.router_profile` (blank = fall back to `name`, so nothing that
  already works changes) and `SubscriptionPlan.speed_mbps`.
- `SubscriptionPlan.effective_router_profile` is now the single place that answers
  "what should the router carry".
- `sync_helpers.desired_profile()` and the Sync Manager drift check both use it.

**Plan health** (`billing/services/plan_health.py`) now reports the two failure
modes the owner asked to see:
1. **duplicate price at different speeds** -- `5Mbps`, `pppoe-15m_500` and
   `10Mbps` are ALL PHP 500 at 5/15/10 Mbps. Found **7** such collisions.
2. **no router profile mapped** -- found **19** plans (now 18 after a mapping).

Backfilled all 34 plans' `speed_mbps` from their names and set `router_profile`
on the 15 that were already `pppoe-*`.

**Surfaced in three places**:
- a warning banner at the top of the Sync Manager, linking to Internet Plans
- `Plan Speed Mbps`, `Plan Router Profile` and `Plan Problem` columns in the
  customer CSV export (Juan's row reads
  `no router profile mapped; price shared with another speed`)
- green "catalogue is clean" banner once both counts reach zero

And it is **actionable**: `router_profile` + `speed_mbps` were added to the Add
and Edit plan forms, and the edit form shows what will actually be pushed.
Verified 10/10 end to end.

**Caution**: saving a plan triggers `sync_plans_on_save`, which pushes the
profile to every router. With `ROUTER_MODE=live` that is a real write. It failed
safely while the 3 routers were unreachable.

**Lesson**: a product name and a device identifier are different things. Sharing
one column guarantees a permanent mismatch.

**Files**: `billing/models.py`, `billing/services/plan_health.py`,
`network_manager/sync_helpers.py`, `network_manager/views/sync.py`,
`network_manager/templates/network_manager/sync_manager/_plan_health_banner.html`,
`billing/views/exports.py`, `billing/views/services.py`,
`billing/templates/billing/add_plan.html`, `billing/templates/billing/edit_plan.html`
**Date Logged**: 2026-10-04

---

### ERR-110: Import Expiry Fidelity Proven By A REAL Import (not a dry-run)

**Why this mattered**: every previous import test was a `--dry-run`. The owner's
stated worst fear was *"if the new system didnt read that sql file properly some
customers will go past their actually due dates and not get expired"*. Never
actually proven.

**The rehearsal** (2026-10-04, `/root/backups/PRE_REHEARSAL_20261004_064849.dump`
taken first, DB restored after):

- 528 customers, 799 payments, PHP 659,757.48 imported for real
- **518 of 518 expiry dates matched the source dump exactly. 0 mismatched.**
- 0 customers auto-provisioned to any router (`sync_status` all `Unverified`)
- 0 duplicate usernames
- 3 payments with no matching customer kept with a reason, not dropped

**The trap this exposed**: 507 of 528 imported customers came back PAST DUE, only
12 in the future. That is **not** a real backlog -- it is an artifact of the dump
being dated `2026-03-20` while today is `2026-10-04`. Every 30-day plan lapsed
during those 6.5 months. Do NOT use this number to judge tomorrow's import;
export fresh from the still-running legacy system and the figure will be real.

**The safety valve that mattered**: `expiry_sweep` auto-renews any past-due
customer whose advance credit covers a month. Measured across all 507:
**0 would be auto-renewed** (no imported customer has advance credit). Running it
for real produced `past_due=507 renewed=0`, payments `801 -> 801`, and exactly one
notification. No fabricated revenue, no router contact.

**9 customers imported with `expires_at=NULL`** (zero dates in the legacy DB).
They will never lapse on their own. The sweep counts them and raises
`9 installed customer(s) still have no expiry date`, but staff must set dates
manually or those 9 lines serve free indefinitely.

**Files**: `archived_scripts/rehearsal_import.sh`,
`archived_scripts/verify_real_import.py`, `archived_scripts/measure_pastdue_risk.py`
**Date Logged**: 2026-10-04

---

### ERR-111: Router `health_status` Is A Manual Label, Never Auto-Downgraded

**Symptom**: with 3 of 4 routers genuinely unreachable, every device still reads
`health_status='Excellent'`.

**Root cause**: `MikrotikDevice.health_status` is only ever written by
`billing/views/network.py` from a staff POST (and set to `Excellent` on
acknowledge). Nothing in the connection layer downgrades it on failure.

**Consequence at cutover**: the device-alert counters are
`MikrotikDevice.objects.exclude(health_status="Excellent")`, so they report **zero
device alerts while three routers are dead**. A staff member glancing at the
devices page would conclude everything is fine.

**Not a dead end**: `/devices/devices/<id>/test/` tests a single router, and the
Sync Manager shows a red banner when its API call fails. Reachability IS
discoverable, just not from the list page.

**Decision**: left as-is. Auto-probing four routers on every page load is exactly
the kind of load this 1-vCPU droplet should not take, and it would touch routers
unattended -- which breaks the project rule. Flagged for the owner instead. If a
live reachability column is wanted later, reuse the existing
`router_unreachable_{id}` circuit-breaker cache (45s TTL) rather than adding a
new poller.

**Files**: `network_manager/models.py`, `billing/views/network.py`,
`billing/views/api/network.py`
**Date Logged**: 2026-10-04

---

### ERR-112: Test Residue Survived The Operational Wipe

**Symptom**: after the data wipe, the alert bell still held **55 notifications**
and the audit log held **230 rows** -- all created by my own verification
harnesses. 44 were "Payment Received" alerts for customers that no longer
existed.

**Root cause**: the wipe targeted customers / payments / dispatch / prospects,
but `Notification` and `SystemLog` were never in scope, so they accumulated across
a dozen test runs.

**Consequence**: dead notifications pointing at deleted customers, and an audit
trail made entirely of test logins and test customer creations -- actively
misleading for a production cutover, where the audit log is supposed to be
evidence.

**Fix**: cleared both (`archived_scripts/clear_test_residue.py`), with a hard
guard that aborts if more than 5 customers are present. Payments were never
touched. Any notification or audit row created from now on is real activity.

**Lesson**: a data wipe is only complete if you enumerate the tables that
*reference* the deleted rows, not just the rows themselves.

**Files**: `archived_scripts/clear_test_residue.py`,
`archived_scripts/restore_after_rehearsal.sh`
**Date Logged**: 2026-10-04

### ERR-113: Customers Directory Toolbar Stacked Vertically / Status Clipped Into Actions

**Symptom**: on `/customers/` the search box, router and barangay selects stacked
vertically above the table; the router warning rendered as bare text inside the
KPI grid; every lifecycle filter appeared twice (KPI cards + an overflowing pill
row); the Status badge and dots spilled into the Actions column.

**Root cause**: (1) `<form id="customerSearchForm">` sat *inside* `<table>`
between `<colgroup>` and `<thead>` -- invalid HTML, the parser ejects it and its
flex layout is lost. (2) `.gt-alert` had no CSS anywhere in `static/css/gt`.
(3) `_filters.html` rendered the same `lifecycle_filters` loop as `_hero.html`.
(4) `table-layout: fixed` + percentage `<colgroup>` clipped the Status column,
and stopped DataTables Responsive from ever collapsing columns.

**Fix**: form moved above the table as a `.gt-table-toolbar`; auto table layout
with `data-priority` on optional columns; KPI cards in an auto-fill CSS grid
(zero buckets dimmed); `_filters.html` deleted; `.gt-alert` styled in the
page's `_styles.html`. Template/CSS only -- no view or logic change.

**Lesson**: never put a `<form>` (or any non-table element) directly inside
`<table>`; wrap the whole table instead or place the form before it.

**Files**: `customer_list.html`, `customer_list/_hero.html`, `_table.html`, `_styles.html`
**Date Logged**: 2026-10-04

---

### ERR-113: The Import Invented A Phantom Router And Stranded Every Customer

**Symptom**: after importing 2,041 subscribers, the Sync Manager showed the real
router `ccr2116.v1 - patag` with **zero** customers, and a mysterious second
device called `ccr2116.v1` holding all 2,041.

**Root cause**: `get_or_create_device()` matched on `device_name` only. The dump
calls the router `ccr2116.v1`; staff registered it as `ccr2116.v1 - patag`.
Different string, same physical router (both `172.30.120.1`), so `get_or_create`
happily created a **duplicate device row**. Every imported customer was parked on
the phantom.

Consequences at cutover: the real router looked empty, the phantom looked like it
had 2,041 accounts all drifting, and router bookkeeping was split across two
records for one box.

**Fix**: match on `ip_address` first and fall back to `get_or_create` by name
only when no device has that IP. The IP is the one value both sides agree on.

**Verified**: 527-row import, whose dump says `ccr2116.v1`, now puts all 527 on
`ccr2116.v1 - patag`. 4 devices (not 5), no phantom, 0 orphans. 5/5.

**This is the same bug class as ERR-109** (plan name doubling as the router
profile). A dump identifier and an internal label are not the same thing, and
matching them by string equality invents entities that do not exist.

**Lesson**: when importing from another system, match on the *address* the two
systems agree on -- an IP, an account number -- never on a human label.

**Files**: `billing/management/commands/import_legacy_customers.py`
**Date Logged**: 2026-10-04

---

### ERR-114: The Import Was Not Atomic -- A Partial Subscriber Base Was Possible

**Symptom**: an interrupted 2,041-row import left **287 customers** committed with
no import report and no way to tell how far it had got. Staff would have started
billing real people against a silently incomplete account list.

**Root cause**: `import_legacy_customers.handle()` had `try:` / `finally:` and no
`transaction.atomic()`. Every row committed on its own. The file's own comment
admits the process had already been OOM-killed once for the same reason.

**Fix**: an `all_or_nothing` decorator wraps `handle()` in a single transaction,
so the import either completes fully or changes nothing.

**Chaos-tested, not assumed**: baseline 1 customer -> start the import -> kill the
container mid-transaction -> after restart the count is still 1. No partial rows.
(The naive first attempt was inconclusive twice over: `pkill` does not exist in
the image and the baseline was polluted, so both were fixed before believing it.)

**Import at real 2,041 scale, measured on this 1 vCPU / 1.9 GB box**:
- completes clean, `EXIT=0`, 2,041 of 2,041 rows created
- **0 of 2,005 expiry dates mismatched** against the source file
- 0 duplicate usernames, 0 customers auto-provisioned to a router
- 2,041 of 2,041 received portal credentials
- peak container memory **362 MiB of 1.92 GiB (18.4%)** -- the OOM history is not
  reproducible at this size
- wall clock **~20 minutes** (527 rows takes ~4 minutes)

**Operational warning**: a 20-minute foreground command over SSH WILL be cut off
if the link drops, and that is exactly what produced the original 287-row mess.
Run the real import detached and poll it:

```bash
docker exec -d gametech-web sh -c \
  "python manage.py import_legacy_customers /tmp/legacy.sql > /tmp/import.log 2>&1; echo EXIT=\$? >> /tmp/import.log"
# then poll:  docker exec gametech-web grep EXIT= /tmp/import.log
```

Also note: `Customer.phone` is **not** unique, so subscribers sharing a household
phone import fine. Worth knowing, because the real export will contain them.

**Pre-import check**: the importer builds the plan catalogue from the dump's own
`service_plans` table. If tomorrow's export omits that table, subscribers land
with **no plan at all** -- no expiry can be computed and no billing can run.
Confirm `service_plans` is present before importing.

**Files**: `billing/management/commands/import_legacy_customers.py`,
`archived_scripts/build_scale_dump.py`, `archived_scripts/scale_import_full.sh`,
`archived_scripts/verify_scale_import.py`, `archived_scripts/chaos_import_test2.sh`
**Date Logged**: 2026-10-04

---

### ERR-115: "View" On An Agent Showed A Different Page From The Agent's Own Portal

**Symptom**: opening an agent from the Agents tab landed on a sparse "Agent
Details" page that Martin never sees, while `staff_agent_portal_detail` rendered a
*third* variant. Staff could not check what an agent actually sees, which was the
whole point of looking.

**Root cause**: `agent_dashboard` and `staff_agent_portal_detail` each carried a
byte-identical ~85-line copy of the portal context builder, and each rendered a
different template (`agent_portal/dashboard.html` vs
`staff/agent_portal_detail.html`). The copies drifted. Classic duplicated-logic
divergence.

**Fix**: one builder, `billing/services/agent_portal.agent_portal_context()`, and
one template. `staff_agent_portal_detail` now renders the agent's real dashboard
with `viewing_staff=True`. Deleted the duplicate template.

**Also**: removed the Agent Payouts nav item AND the matching page-header button.
There were two identical-looking doors onto commission figures already shown on
the Agent Portal dashboard. The route itself is untouched for direct links.

**Safety**: staff viewing is read-only. `agent_add_prospect` and
`agent_request_cashout` resolve the agent from `request.user.agent_profile`, so a
staff POST could not act as the agent -- but the UI no longer offers the buttons
at all, and a staff POST still 302s. Martin logging in himself gets the live
buttons.

**Files**: `billing/services/agent_portal.py`, `billing/views/agents.py`,
`billing/templates/billing/agent_portal/dashboard.html`,
`billing/templates/billing/agent_portal/base_agent.html`,
`billing/templates/billing/agent_portal/_my_customers.html`,
`billing/templates/billing/agents/_table.html`,
`billing/templates/billing/agents/_stats.html`,
`billing/templates/billing/base/_sidebar.html`
**Verified**: 34/34
**Date Logged**: 2026-10-04

---

### ERR-116: Multi-Line `{# #}` Comments Render As Literal Text

**Symptom**: raw template text appeared on the live pages --

    {# Staff opened someone else's portal to check on them. Say so, and give them a way back #}

shown to the user as visible body copy, mid-page.

**Root cause**: Django's `{# ... #}` is a **single-line** comment. Written across
several lines it does not match the comment token, so the template engine emits
the text verbatim. It fails silently -- `manage.py check` is clean and the page
still returns 200.

**Found in three places**, including one authored by a concurrent session
(`network_manager/sync_manager/_card_missing.html`, live on the Sync Manager
"Missing on Router" card).

**Fix**: use `{% comment %} ... {% endcomment %}` for anything that wraps. All
three converted; a repo-wide sweep now reports zero multi-line `{# #}` blocks.

**Lesson**: a template bug that renders rather than raises is invisible to every
automated check that only asserts on status codes. Assert on page *content*, and
grep for the pattern -- `{#[\s\S]*?#\}` containing a newline is the detector.

**Files**: `billing/templates/billing/agent_portal/base_agent.html`,
`billing/templates/billing/agent_portal/dashboard.html`,
`billing/templates/billing/base/_sidebar.html`,
`network_manager/templates/network_manager/sync_manager/_card_missing.html`
**Date Logged**: 2026-10-04

---

### ERR-117: Dispatch Customer Detail 500'd For Every Customer With Job History

**Symptom**: `/dispatch/customers/<id>/` raised
`AttributeError: 'JobTicket' object has no attribute 'completed_at'`.

Found by a whole-system sweep of all 470 named routes, not by a user report.
113 returned 200, and this was the only genuine crash in the project.

**Root cause**: `dispatch_customer_detail_view` built its turnaround-time column
from `ticket.completed_at`. `JobTicket` records completion as **`finished_at`**
(set when the technician clicks Done on site). There is no `completed_at` field.

The cruel part: the crash needed a customer who actually HAD a job ticket. Every
customer with an empty history sorted fine, so every smoke test passed and the
page looked healthy right up until dispatch had real work in it -- which is
precisely when staff need it.

**Fix**: `finished_at` in all three places (the turnaround calculation, the
`done_at` value passed to the template, and the null guard).

**Verification discipline**: my first guess was wrong. I assumed
`timezone.datetime.min` was the culprit and "fixed" it; that was not the bug
(`django.utils.timezone` does import `datetime`, so `timezone.datetime.min` is
valid -- there are 11 such usages across the codebase that are all fine). I
reverted that change and got the real traceback instead, which named the field in
one step. **The reverted diff was noise; the evidence was not.**

**Lesson**: a code path that only executes when there is real data is untested by
definition. Sweep the routes *with* data, not just against an empty database.

**Files**: `dispatch/views.py`
**Date Logged**: 2026-10-04

---

### ERR-118: Deleting A Plan Silently Deleted Its Router Profile From Every Router

**The worst bug found in this project.** It was armed and waiting for the day
the routers came back online.

**What happened**: while merging duplicate plan rows I saw the log:

    Failed to delete profile GTipid Fiber 1000: Could not connect to
    ccr2116.v1 - patag API.

`delete_plan_on_mikrotik` fires on `post_delete` of a `SubscriptionPlan` and
called `delete_plan_from_mikrotik(plan_name=instance.name)` on **every**
registered device, unconditionally.

**Why it was nearly catastrophic**: the duplicate rows I was deleting had the
SAME NAME as the surviving rows. So the moment the routers were reachable, that
merge would have deleted the profile `GTipid Fiber 1000` from all three routers
-- the profile carrying **1,396 live subscribers**. They would have kept
authenticating but lost their rate limits. Every duplicate-plan cleanup anyone
ever did in the admin carried this same trigger.

It survived only because the routers were powered off. That is not a safeguard,
that is luck.

**Fix**: the signal now refuses to touch a profile that anyone is still on. It
checks both customers pointing at any plan with that `router_profile`, and
sibling plans sharing it. If either is non-zero it logs loudly and returns.

**Verified 4/4 with the router API mocked**, so the proof does not depend on
router availability:
- deleting a plan whose profile has subscribers -> API never called
- deleting a genuinely unused plan -> profile still cleaned off all 4 devices

**Lesson**: a database delete should never have an unbounded external side
effect. And "the routers were off so it did not happen" is not a test result.

**Files**: `billing/signals.py`
**Date Logged**: 2026-10-04

---

### ERR-119: Duplicate Plan Rows, And The Import Created Them

**Symptom**: the catalogue listed `GTipid Fiber 1000` twice, `GTipid Fiber 1300`
twice, `GTipid Fiber 1500` twice -- same name, same price, same speed, different
row ids. 1,644 subscribers pointed at one of each pair arbitrarily.

**Cause**: plans are keyed on `name` but `name` has no unique constraint, and both
the importer and the plan editor created rows with `get_or_create`-style logic
that did not always match what was already there.

**Fix**: merged on exact `(name, price, speed_mbps)`, keeping the lowest id,
moving every customer onto the survivor, and carrying over a router profile if
only the dead row had one. Wrapped in `transaction.atomic`.

49 plans -> 46. 1,644 customers moved. 0 customers without a plan. 0 duplicates
remaining.

Plans whose names differ were never merged, even at the same price.

**Files**: `archived_scripts/merge_duplicate_plans.py`
**Date Logged**: 2026-10-04

---

### ERR-120: Plan Health Cried Wolf About Legitimate Price Tiers

**Symptom**: 8 "duplicate price collision" warnings. Six of them were not
problems at all:

    PHP 500  GTipid Fiber 500 (10 Mbps) / GTipid Fiber 500 (15 Mbps)
    PHP 1500 GTipid Fiber 1500 / GTipid Fiber 1500 (Speedboost)

Those are deliberate product tiers, and **the plan name states its own speed**.
A warning that fires on correct data trains staff to ignore the banner, which
would have hidden a genuine problem later.

**Fix**: the detector now distinguishes three cases.
- same price + same speed + same download speed -> a true duplicate (raised)
- same price + different speeds, but every name states its speed -> informational
  variant list, not a warning
- same price, different speeds, names that do NOT distinguish them -> raised,
  because the import genuinely cannot tell them apart

`plan_health()` gained a `variants` key; the Sync Manager banner reports it as a
neutral count instead of an alert.

**Files**: `billing/services/plan_health.py`,
`network_manager/templates/network_manager/sync_manager/_plan_health_banner.html`
**Date Logged**: 2026-10-04

---

### ERR-121: Four Real Duplicate Plans Remain, And Merging Them Is A Business Call

`plan_health` now reports exactly 4 ambiguous groups, and all 4 are **true
duplicates** by every measurable attribute -- same price, same upload, same
download. Only the NAME differs:

| plans | price | up/down | subscribers |
|---|---|---|---|
| `GTipid Fiber 1000` / `GTipid Fiber 1000 (Speedboost)` | 1000 | 20/20 | 1396 / 33 |
| `GTipid Fiber 1300` / `GTipid Fiber 1300 (Speedboost)` | 1300 | 30/30 | 103 / 4 |
| `GTipid Fiber 1500` / `GTipid Fiber 1500 (Speedboost)` | 1500 | 50/50 | 145 / 5 |
| `GIMI Home Fiber 1500` / `(New Plan)` / `(100 Mbps)` | 1500 | 100/100 | 0 / 39 / 0 |

**Deliberately NOT merged.** "Speedboost" is very likely a real commercial
promise -- a burst allowance, a priority, a better upload that simply was never
recorded in `speed_up`. Merging on the measurable fields would silently move 81
subscribers onto a different plan and erase the only evidence that the tier
exists. That is the owner's decision, not an automatic cleanup.

**To resolve**: either
- if Speedboost IS a distinct product, give it its real `speed_up` /
  `speed_down` and it stops being a duplicate, or
- if it is a leftover, merge it into the base plan in Internet Plans.

Until then the banner correctly reports 4. That is a true reading, not noise.

**Files**: `billing/services/plan_health.py`
**Date Logged**: 2026-10-04


### ERR-122: Same Error Shown Three Times On A Page (Flash + Inline Loop + Dedicated Card)
**Symptom**: Sync Manager on an unreachable router showed the same "Failed to connect to router" text 3x: a toast overlapping the topbar, an inline alert, and the page's own offline card.
**Cause**: The view called `messages.error(...)` AND passed `router_error` to the template; the template also had its own `{% for message in messages %}` loop on top of the toast already rendered by `billing/base.html`.
**Fix**: Do not flash an error the template already renders from context. Never add a per-page `messages` loop: `base.html` (line ~64) already toasts every message. Fixed in `network_manager/views/sync.py` + `sync_manager.html`.


### ERR-123: Developer Comment Visible On The Page (Multi-line `{# #}`)
**Symptom**: Raw text like `{# Cutover integrity strip. Separate from the lifecycle KPIs... #}` rendered above the Customers Directory integrity filters.
**Cause**: Django's `{# ... #}` comment syntax is SINGLE-LINE only. Spread over several lines it is not recognised and is output as plain text.
**Fix**: Use `{% comment %} ... {% endcomment %}` for any multi-line template comment. Fixed in `billing/templates/billing/customer_list/_hero.html`.


### ERR-124: Customer View Link Verdict Box Overlapping Live Monitoring & Map
**Symptom**: On `/customers/view/<id>/`, the link diagnosis box ("MikroTik is healthy ? the fault is between it and the customer's house") hung out of the middle column and superimposed directly on top of the Live Monitoring chart and Exact Location map. Additionally, "Last Logged Out" showed the raw Unix epoch `jan/01/1970 00:00:00`.
**Cause**:
1. `_link_verdict.html` was included inside Column 2 (`col-lg-4`) right after `.info-card`. Because `.info-card` had `height: 100%`, it consumed the full flex height of the column, causing the subsequent sibling (`#link-verdict`) to start at `top: 100%` and spill ~200px down over the next row (`_live_monitoring.html`).
2. MikroTik RouterOS returns `jan/01/1970 00:00:00` for PPP secrets that have never disconnected or logged out. The live polling handler did not filter out epoch `1970` timestamps.
**Fix**:
1. Moved `_link_verdict.html` out of Column 2 into its own full-width row (`col-12`) between `_info_cards.html` and `_live_monitoring.html`. Styled it with a clean badge, icon container, headline, recommendation, and checklist section.
2. Updated all 3 info card columns to `col-lg-4 d-flex` with `.info-card.flex-fill.w-100` (`display: flex; flex-direction: column; margin-bottom: 0`), ensuring all three cards match height without vertical overflow.
3. Filtered out `1970` epoch dates in `billing/views/api/network.py` and `_scripts.html` so newly provisioned accounts or sessions without previous disconnections show cleanly without epoch glitch text.


### ERR-125: Router Reachable Only On Its WAN Address, Not The Internal Subnet
**Symptom**: `MikrotikDevice` held `172.30.120.2` / `172.30.120.3` and every connection timed out, while a sibling router on `.1` at the identical API port and credentials worked fine. v1 could ping both of them with 0% loss, and their ARP entries were `complete=true` on `vlan1212`, so the boxes were alive and correctly addressed. Ping worked from a router but not from us; the API worked on the public address but not the internal one.
**Cause**: Not a router fault. Verified by reading each box over its public IP: the internal address was present and correct (`172.30.120.2/24` on `vlan1212`), the `api` service was enabled on the right port with an EMPTY `Address` field (so it listens on every interface), and `/ip/firewall/filter` had ZERO rules. Nothing on the router could block us. A TCP+ICMP sweep of `172.30.120.0/24` from the server showed only `.1` answering -- `.2`, `.3`, `.20` and `.30` were all invisible, including two other MikroTik devices the routers themselves could see. That rules out subnet routing: a real `/24` route carries you to every host on it. Only a single-host path to `.1` existed.
**Fix**: Two valid paths. (a) Record the WAN address in `MikrotikDevice.ip_address` -- works immediately, zero travel -- then have the ISP lock the API down in Winbox with an `input` chain rule allowing `dst-port=8701` from the server's fixed public IP and dropping the rest. (b) Keep `172.30.120.x` and have whoever is on-site fix routing so `.2`/`.3` are reachable from the PC advertising the Tailscale subnet route.
**Diagnose it with**: ask a reachable router to `ping` its neighbours (a read, changes nothing); read `/ip/service`, `/ip/address` and `/ip/firewall/filter` on the target over ANY reachable address; then sweep the management subnet from the server. If only one host answers, the fault is upstream of the routers.
**Files**: `network_manager/models.py` (data only, no code change)
**Date Logged**: 2026-10-06


### ERR-126: Live Poll Made One API Call Per Active Subscriber (~1,660 Calls, ~150s)
**Symptom**: The background live poll measured 178-221s per cycle instead of its intended ~10s. With a 300s cache TTL this starved the connectivity cache that the Customers page reads, so subscribers intermittently rendered "Unknown". Real load on v1: ~1,660 sequential RouterOS calls every cycle -- exactly the gratuitous router traffic we are trying to avoid.
**Cause**: `billing/utils.py` built a `<pppoe-username>` list from every active session and called `api.get_interfaces_traffic(interface_names)`, which loops `interfaces_api.call('monitor-traffic', ...)` once PER interface. With 1,660 live PPPoE sessions on v1 that is 1,660 round trips (~90ms each) = ~150s of the 197s total.
**Fix**: RouterOS 7 returns the same data on the plain `/interface` resource. A single `.get()` returned all 1,658 PPPoE interfaces WITH `rx-byte`/`tx-byte` in ~1.4s. Added `MikrotikSystemMixin.get_interface_counters()` returning `{name: {rx, tx}}`; the poll now differences consecutive samples over the real elapsed time to derive Mbps. Also cached the per-router `8.8.8.8` uplink ping to a 60s cadence instead of running it on every 10s cycle. Result: **197s -> ~5s (40x), ~1,660 calls -> ~4.**
**Gotcha**: librouteros CANNOT batch repeated API keys. `call('monitor-traffic', {'interface': [a, b]})` fails with `AttributeError: 'list' object has no attribute 'encode'`. Do not attempt to batch by list -- read the bulk resource instead.
**Files**: `network_manager/services/system.py`, `billing/utils.py`
**Date Logged**: 2026-10-06


### ERR-127: Slow Page That Is Not A Database Problem
**Symptom**: `/customers/` took 2.5s and shipped 921 KB. Every instinct says "slow queries", but `manage.py` profiling showed only **0.128s of 2.5s in the database (4%)**. Chasing indexes would have wasted days.
**Cause**: Template rendering. Each table row expands to ~190 lines of markup once `customer_list/_customer_status.html` is included, so 100 rows meant ~12,000 Django template node evaluations. Two separable costs:
1. **Row count** — the only real lever, since node evaluation scales linearly.
2. **Repeated inline styles** — 15 `style="..."` attributes per row (9 distinct values), i.e. 750-1,500 per page load. Moving them to `.gt-cl-*` classes in the page stylesheet cut them to zero.
A further ~31% of the row bytes was pure template indentation left behind by nested `{% if %}` blocks. Left alone on purpose: collapsing it with `{% spaceless %}` would remove the whitespace between adjacent `d-inline-block` elements and make the connectivity dot touch the customer name.
**Fix**: `PAGE_SIZE` 100 -> 50 (search/filter/sort still cover every customer through the existing SQL-backed DataTables path, so nothing becomes unfindable) and inline styles -> stylesheet. Result 2.5s -> ~1.1s, 921 KB -> 597 KB.
**Lesson**: profile before optimising. `connection.queries` tells you the truth in one run. Also check whether your "obvious" style is already dead -- `.text-title` is declared `!important`, so the inline `color:` on the router cell was already being overridden and contributed nothing.
**Files**: `billing/views/customers/list.py`, `billing/templates/billing/customer_list/{_table,_customer_status,_styles}.html`
**Date Logged**: 2026-10-06


### ERR-128: A URL Sweep That Includes /logout/ Invalidates Its Own Session
**Symptom**: A headless verification sweep reported `/customers/`, `/mac-history/` and the DataTables endpoint as FAILING -- 302 redirects, zero rows -- minutes after they had all been confirmed working at HTTP 200. Every post-sweep assertion was wrong.
**Cause**: The sweep enumerated every argument-free route and `GET`ed it. That list legitimately contains `/logout/`. Requesting it flushed the session, so every assertion after it ran unauthenticated and got bounced to the login page. The failures were an artefact of the test harness, not the application.
**Fix**: Either skip state-changing routes (`/logout/`, anything POST-only) when sweeping, or build a fresh `Client()` and `force_login()` per assertion. Verified after the fix: customer list HTTP 200 with 51 rows, 105 status badges, pagination `page 1/41`, DataTables payload 25 records.
**Lesson**: When a batch check suddenly fails on pages that were just fine, suspect the batch. Re-run the failing assertions individually with a fresh session before believing them.
**Date Logged**: 2026-10-06


### ERR-129: POST-Only Views Return None On GET, So A Stray GET Is A 500
**Symptom**: `network_manager.views.devices.test_device_connection` raised `ValueError: The view ... didn't return an HttpResponse object. It returned None instead.` on a GET. Same shape in ~23 views across `network_manager`, `dispatch` and `customer_portal`.
**Cause**: The view body is wrapped in `if request.method == 'POST':` with no trailing `return`, so any other method falls off the end and Django turns `None` into a 500. The button itself is fine -- it POSTs, and all three routers answer `{"status": "success"}`.
**Fix (NOT yet applied -- deliberately deferred)**: decorate these with `@require_POST`, or return an explicit `405`. Deferred on purpose: the other session was actively refactoring `network_manager/views/` at the time, and a 500 on a stray GET is cosmetic next to the risk of a mid-flight merge conflict. A stray GET only matters if a human types the URL or a crawler finds it; it cannot affect staff workflow.
**Diagnose it with**: POST to the endpoint, do not GET it. A `None` return on GET says nothing about whether the feature works.
**Files**: `network_manager/views/{devices,sync,winbox,naps}.py`, `dispatch/views.py`, `customer_portal/views/auth.py`
**Date Logged**: 2026-10-06
