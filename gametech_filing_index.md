# 🗺️ Gametech Filing & Architecture Directory (The Master Code Locator)

> **Purpose**: Eliminates exploratory file searches (`list_dir`, broad greps) and prevents AI context bloat.  
> **Rule for All AI Assistants**: **CHECK THIS DIRECTORY FIRST** to pinpoint the exact files, folders, and recipes needed for any task.

---

## ⚡ 1. The Instant File Locator Matrix

| Functional Domain | Views / Handlers | URL Routes | Templates & Partials | Models / Services |
| :--- | :--- | :--- | :--- | :--- |
| **NOC Live Monitoring** | `billing/views/network.py` | `billing/urls.py` (`/live-monitoring/`) | `billing/templates/billing/live_monitoring.html`<br>Components: `live_monitoring/_hero.html`, `_info_cards.html`, `_live_traffic_card.html`, `_modal_*.html`, `_scripts.html` (orchestrator), `_scripts_modals.html`, `_scripts_polling.html`, `_scripts_telemetry.html`, `_scripts_traffic_table.html`, `_styles.html` | `billing/models.py` (`MikrotikDevice`, `Barangay`)<br>`network_manager/services/base.py` |
| **Customer Telemetry API** | `billing/views/api/network.py` (`api_customer_mikrotik_status`) | `billing/urls.py` (`/customers/api/status/<id>/`, alias: `/api/customer/<id>/mikrotik-status/`) | Rendered by `live_monitoring/_modal_search_customer.html` | `network_manager/services/users.py`<br>`network_manager/services/secrets.py` |
| **Customer Management** | `billing/views/customers/`<br>`billing/views/api/customers.py` | `billing/urls.py` (`/customers/`) | `billing/templates/billing/customer_list.html`<br>`billing/templates/billing/view_customer.html`<br>Partials: `view_customer/_hero.html`, `_modals.html`, `_scripts.html` | `billing/models.py` (`Customer`, `CustomerMACHistory`, `Barangay`) |
| **Payments & Invoicing** | `billing/views/payments/`<br>`billing/views/xendit.py` | `billing/urls.py` (`/payments/`, `/xendit/`) | `billing/templates/billing/payment_*.html` | `billing/models.py` (`Payment`, `Rebate`)<br>`billing/signals.py` (Auto-reconnect) |
| **Subscription Plans** | `billing/views/services.py` | `billing/urls.py` (`/plans/`) | `billing/templates/billing/partials/subscription_plans_table.html` | `billing/models.py` (`SubscriptionPlan`, `AddOnRequest`) |
| **Hardware / Mikrotik Bridge** | `network_manager/services/` (`base.py`, `users.py`, `secrets.py`, `profiles.py`, `system.py`) | `network_manager/urls.py` | Admin or rendered via NOC components | `network_manager/models.py`<br>`network_manager/sync_services.py` |
| **Background Cron Tasks** | `billing/tasks.py` | Triggered by Celery Beat | Monitored in Live Monitoring NOC | Celery Beat in `gametech_core/settings.py` |
| **Field Dispatch / Tickets** | `dispatch/views.py` | `dispatch/urls.py` (`/dispatch/`, `/dispatch/dashboard/`, `/dispatch/monitoring/`, `/dispatch/internet-install/`, `/dispatch/cignal-install/`, `/dispatch/client-concerns/`, `/dispatch/complete-job/<id>/`, `/dispatch/audit-log/`, `/dispatch/management/`) | `dispatch/templates/dispatch/dashboard.html`, `dispatch_monitoring.html`, `internet_install.html`, `cignal_install.html`, `client_concerns.html`, `complete_job.html`, `audit_log.html`, `management.html`, `_add_record_modal.html` | `dispatch/models.py` (`Team`, `Technician`, `ConfigOption`, `DispatchRecord`, `MonitoringRecord`, `JobDetail`, `AuditLog`)<br>`dispatch/forms.py` (`DispatchRecordForm`, `MonitoringRecordForm`, `JobDetailForm`) |
| **Customer Self-Service Portal** | `customer_portal/views.py` | `customer_portal/urls.py` (`/portal/`) | `customer_portal/templates/` | `customer_portal/models.py` |
| **Top Navigation & Active Sessions** | `billing/views/auth.py` (`online_staff_api`)<br>`billing/middleware.py` | `billing/urls.py` (`/api/online-staff/`) | `billing/templates/billing/base/_topbar.html`<br>`billing/templates/billing/base/_scripts.html` | `User`, `Customer`, Redis Cache (`seen_user_*`, `seen_customer_*`, `active_portal_customers`) |
| **Network Devices & Sync Manager** | `network_manager/views/devices.py`<br>`network_manager/views/sync.py` | `network_manager/urls.py` (`/devices/`, `/devices/devices/<id>/sync/`, `/devices/devices/<id>/setup-profiles/`) | `network_manager/templates/network_manager/device_list.html`<br>`network_manager/templates/network_manager/sync_manager.html`<br>Partials: `sync_manager/_hero.html`, `_card_active_users.html`, `_card_router_users.html`, `_card_suspicious.html`, `_card_missing.html`, `_modal_alert.html`, `_styles.html`, `_scripts.html` | `network_manager/models.py`<br>`network_manager/sync_services.py` |
| **System Audit Logs** | `billing/views/system_logs.py` | `billing/urls.py` (`/logs/`) | `billing/templates/billing/logs.html`<br>Partials: `logs.html` | `billing/models.py` (`SystemLog`)<br>`billing/tasks.py` (`auto_cleanup_system_logs_task`) |
| **Design System / Dark Mode** | N/A | Global Static | `static/css/theme/tokens_and_base.css`<br>`static/css/theme/components.css`<br>`static/css/theme/layout_and_darkmode.css` | N/A |

---

## 🏗️ 2. Architectural Conventions (The Golden Rules)

### A. The Orchestrator Pattern (Strict Template Separation)
* **Parent templates must be lightweight (< 200 lines)**:
  - `billing/templates/billing/live_monitoring.html`
  - `billing/templates/billing/dashboard.html`
  - `billing/templates/billing/view_customer.html`
* **All features live in component partials**:
  - Located in a subfolder named after the page (e.g. `billing/templates/billing/live_monitoring/`).
  - Filename **must start with an underscore** (e.g. `_hero.html`, `_modal_view_all.html`, `_scripts.html`, `_styles.html`).
* **Never write inline script logic inside modal or card partials**:
  - Keep JS logic cleanly separated inside `_scripts.html`.
  - Keep page-specific CSS overrides inside `_styles.html`.

### B. Modular Views Pattern
* View files **must not exceed 400 lines**.
* When adding a new view domain, place it inside `billing/views/` (e.g. `billing/views/api/`, `billing/views/customers/`, `billing/views/payments/`).
* Always expose clean imports in `billing/views/__init__.py`.

---

## 🛠️ 3. Standardized Coding Recipes (How to Modify Code Safely)

### Recipe 1: Adding or Modifying a Modal
1. **Create/Edit the partial**:
   - File: `billing/templates/billing/<page>/_modal_<feature>.html`.
   - Use design tokens: `<div class="modal-content gt-modal-content border-0 shadow-lg rounded-4 overflow-hidden">`.
2. **Verify Tag Balance (MANDATORY)**:
   - Run:
     ```powershell
     python -c "content = open('billing/templates/billing/<page>/_modal_<feature>.html', 'r', encoding='utf-8').read(); import re; o = len(re.findall(r'<div\b', content)); c = len(re.findall(r'</div>', content)); print(f'opens: {o}, closes: {c}, diff: {o-c}')"
     ```
   - Must output: `diff: 0`.
3. **Include in Parent Orchestrator**:
   - Add `{% include "billing/<page>/_modal_<feature>.html" %}` at the bottom of the parent template (e.g. `live_monitoring.html`), **outside all cards/grid containers**.
4. **Wire Scripts**:
   - Add event listeners and fetch handlers in `_scripts.html`.

---

### Recipe 2: Adding or Fixing an API Endpoint
1. **Define Route**:
   - Edit `billing/urls.py`. Use clean RESTful paths:
     ```python
     path("api/v1/<resource>/<int:id>/", views.my_api_view, name="api_my_resource"),
     ```
2. **Implement View**:
   - File: `billing/views/api/<domain>.py`.
   - Always decorate with `@login_required` (unless public webhook).
   - Return standard `JsonResponse`:
     ```python
     @login_required
     def my_api_view(request, id):
         # logic
         return JsonResponse({"status": "success", "data": {...}})
     ```
3. **Call from Frontend**:
   - Use standard `fetch()` with `.then(r => r.json()).catch(err => console.error(err))` in `_scripts.html`.

---

### Recipe 3: Mikrotik RouterOS Operations
1. **Always use `MikrotikAPI` Service**:
   - Import: `from network_manager.services import MikrotikAPI`.
   - Initialize: `api = MikrotikAPI(router_device)`.
2. **Non-Blocking Telemetry**:
   - Live bandwidth/packet polling must be cached in Redis (`cache.get("live_monitoring_data")`) or executed in Celery tasks (`billing/tasks.py`) to prevent freezing Gunicorn sync workers.
3. **Safe Disconnect/Reconnect**:
   - Use `api.get_active_pppoe_users()` and `api.remove_active_user(username)`.
4. **Seamless Router Migrations (Zero-Drop)**:
   - When deleting a secret from an old router to migrate to a new one, always pass `kick_active=False` to `api.delete_pppoe_user()`. This leaves the active session alive until the physical hardware is swapped.

---

### Recipe 4: Financial & Customer Mutations (Signal Safety)
1. **Always wrap in `transaction.atomic()` with `select_for_update()`**:
   ```python
   from django.db import transaction

   with transaction.atomic():
       customer = Customer.objects.select_for_update().get(id=customer_id)
       customer.status = "active"
       customer.save() # MANDATORY: triggers billing/signals.py to sync physical Mikrotik router
   ```
2. **NEVER use `.update()` on QuerySets for customer status**:
   - `Customer.objects.filter(...).update(...)` **bypasses Django signals** and leaves physical routers out of sync!

---

### Recipe 5: Dark Mode & Theme Token Usage
1. **Design Tokens**:
   - Cards: `.gt-cl-card`, `.telemetry-result-card`
   - Modals: `.gt-modal-content`
   - Buttons: `.gt-btn`, `.btn-primary` with rounded pills
2. **CSS Overrides**:
   - Never hardcode light-only colors or inline hex styles like `style="background: white;"`.
   - Always provide dark mode selector:
     ```css
     .my-card { background: #ffffff; color: #1e293b; }
     .dark-mode .my-card, html.dark-mode .my-card { background: #1e293b !important; color: #f8fafc !important; }
     ```

---

## 🧰 4. Essential Sniper Commands Cheat Sheet

| Action | Sniper Command |
| :--- | :--- |
| **Pull latest changes** | `git pull origin main` |
| **Inspect server traceback** | `ssh root@143.198.207.144 "docker logs --tail 35 gametech-billing-system_web_1"` |
| **Restart Gunicorn container** | `ssh root@143.198.207.144 "docker restart gametech-billing-system_web_1"` |
| **Verify container status** | `ssh root@143.198.207.144 "docker compose ps"` |
| **Execute Python in container** | `@' <python_code> '@ \| ssh root@143.198.207.144 "docker exec -i gametech-billing-system_web_1 python"` |
| **Verify Div Balance** | `python -c "content = open('<file>', 'r', encoding='utf-8').read(); import re; o=len(re.findall(r'<div\b', content)); c=len(re.findall(r'</div>', content)); print(o-c)"` |
| **Check Redis keys** | `ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli KEYS '*pattern*'"` |

---

## ⚠️ 5. DANGER FILES (Never Read Fully — `grep_search` ONLY)

> **Rule**: These files are too large to ingest. Reading them fully burns thousands of tokens and bloats every subsequent AI turn. Use `grep_search` to find specific symbols within them.

| File | Size | Why Dangerous | What to Do Instead |
| :--- | :--- | :--- | :--- |
| `billing/models.py` | 2,000+ lines | Every model in one file | `grep_search` for model/field name, or check `gametech_architecture_map.txt` |
| `gametech_architecture_map.txt` | 83KB / 2,174 lines | Full schema + routes dump | `grep_search` for specific model, URL, or task name |
| `static/css/theme/layout_and_darkmode.css` | 500+ lines | Massive CSS file | `grep_search` for specific selector or class name |
| `billing/templates/billing/base/_topbar.html` | 300+ lines | Dense topbar with dropdowns | `grep_search` for the specific ID or section |
| `billing/views/` (any file > 300 lines) | Varies | Monolith risk | `grep_search` for function name, read 50-line slice |

---

## 🔗 6. Dynamic UI → API Data Source Map

> **Rule**: When a user reports a broken widget, stale counter, or "data not showing" in a specific UI element, look up the element here FIRST. Jump directly to the API endpoint — **NEVER** read the HTML template or JS file to trace the `fetch()` URL.

| UI Element (Location) | JS Fetch Function | API Endpoint | Backend Handler |
| :--- | :--- | :--- | :--- |
| Online Staff Dropdown (`base/_topbar.html`) | `fetchOnlineStaff()` in `base/_scripts.html` | `/api/online-staff/` | `billing/views/auth.py → online_staff_api` |
| Live Monitoring Hero Stats (`live_monitoring/_hero.html`) | `fetchLiveMonitoringData()` | `/api/live-monitoring/` | `billing/views/api/dashboard.py → live_monitoring_api` |
| Customer Portal Active Sessions (topbar badge) | `fetchOnlineStaff()` (combined response) | `/api/online-staff/` | `billing/views/auth.py → online_staff_api` (portal_customers section) |
| Dashboard Stats Cards | Page load (server-rendered) | N/A (context variable) | `billing/views/dashboard.py → dashboard_view` |
| Router Uplink Status Dots | `fetchUplinkStatus()` | `/api/router-uplink-status/` | `billing/views/api/network.py` |

---

## 🗃️ 7. Redis Cache Key Quick Reference

> **Rule**: For full cache key details (TTL, set-by, invalidation), see `AGENTS.md` Rule #23. This is a quick-lookup shortcut.

| Cache Key | What It Tracks |
| :--- | :--- |
| `active_portal_customers` | Dict of logged-in customer portal users |
| `seen_customer_{id}` | Last-activity timestamp for a portal customer |
| `seen_user_{id}` | Last-activity timestamp for a staff/admin user |
| `live_monitoring_data` | Cached Mikrotik live monitoring response |
| `dashboard_stats_{date}` | Cached dashboard statistics for a date |
