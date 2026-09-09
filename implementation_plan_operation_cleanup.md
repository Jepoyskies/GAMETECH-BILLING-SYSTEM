# Codebase Reorganization — Implementation Plan

> **Goal**: Split oversized files into smaller, well-named modules so that any AI tool (or human) can find, read, and fix a specific feature in seconds — without burning through your quota scanning 2,000+ lines of irrelevant code.

---

## Full Audit Summary

I scanned **191 source files** across your entire project. Here's the damage:

| Severity | Criteria | Count | Worst Offenders |
|----------|----------|------:|-----------------|
| CRITICAL | **1,000+ lines** | **6 files** | dashboard.html (2,774), theme.css (2,376), portal_dashboard.html (1,519), live_monitoring.html (1,395), base.html (1,103), view_customer.html (1,031) |
| HIGH | **500-999 lines** | **14 files** | customers.py (863), payments.py (808), customer_list.html (783), changelog.html (765), network_manager/views.py (753), sync_manager.html (693), styles.css (679), network_manager/services.py (674), api.py (645), seed.py (632), login.html (544), models.py (520), fbt_plc_calculator.html (515), pay_customer.html (495) |
| MEDIUM | **300-499 lines** | **16 files** | sms_messaging.html, services.py, settings.py, etc. |
| FINE | **Under 300 lines** | **155 files** | Already well-sized |

### Why This Is Eating Your Credits

Your theory is **100% correct**. Here's exactly what happens:

1. You report a bug like *"the live monitoring button is broken"*
2. I have to `view_file` on `live_monitoring.html` — **1,395 lines**. That's already 800 lines per view, so **2 reads minimum** just to find the section
3. Then I read the CSS embedded inside it (**382 lines of style**), the JS (**639 lines of script**), and **11 modals** — all unrelated to your button
4. Each read burns tokens. A 2,774-line dashboard.html costs **~5x more** than reading a focused 200-line file

**After this reorganization**: I'd read `live_monitoring/traffic_controls.html` (maybe 80 lines) and fix it instantly.

---

## User Review Required

> [!IMPORTANT]
> **This is a BIG refactor** — it touches almost every major file in the system. Nothing will break (we're using Django `{% include %}` and Python package patterns), but you should:
> 1. Review each phase and tell me if you want to skip any
> 2. Approve before I start — I'll do one phase per session to conserve credits
> 3. We should commit to Git before each phase so we can roll back if needed

> [!WARNING]
> **The changelog dropdown in base.html** (lines 390-510, ~120 lines of hardcoded HTML) — do you want me to move this into the database so it's managed from the admin panel? Or just extract it as a partial template? This is a design decision that affects the plan.

---

## Proposed Changes

The plan is split into **6 independent phases** you can execute across sessions. Each phase is self-contained — the system works perfectly after each one.

---

### Phase 1: Dashboard Template (Biggest Win — saves ~2,500 lines)

**File**: [dashboard.html](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/templates/billing/dashboard.html) — **2,774 lines**

This single file contains: 871 lines of CSS, 526 lines of JS, 7 modals, a hero banner, KPI cards, charts, tables, and widgets — all jammed together.

**Split into:**

```
billing/templates/billing/dashboard/
 _styles.html               (~870 lines) — All style blocks
 _hero_banner.html           (~60 lines)  — Welcome banner with mascot
 _kpi_cards.html             (~120 lines) — Revenue, Customers, Collection Rate
 _kpi_totals.html            (~80 lines)  — Today/Yesterday/Week/Month/Year cards
 _chart_sales.html           (~60 lines)  — Monthly sales bar chart container
 _chart_weekly.html          (~40 lines)  — Weekly sales chart
 _chart_pie.html             (~40 lines)  — Payment method pie chart
 _system_health.html         (~80 lines)  — Uptime + Downdetector widget
 _expiring_soon.html         (~60 lines)  — Expiring users alert widget
 _recent_logins.html         (~50 lines)  — Recent admin logins table
 _top_clients.html           (~50 lines)  — Top paying clients widget
 _popular_plans.html         (~40 lines)  — Popular plans widget
 _modal_recent_logins.html   (~100 lines) — Full recent logins modal
 _modal_top_clients.html     (~100 lines) — Top clients modal
 _modal_popular_plans.html   (~80 lines)  — Popular plans modal
 _modal_expiring.html        (~80 lines)  — Expiring soon modal
 _modal_revenue.html         (~80 lines)  — Revenue breakdown modal
 _modal_customers.html       (~80 lines)  — Customers modal
 _modal_collection.html      (~80 lines)  — Collection rate modal
 _scripts.html               (~530 lines) — All chart JS + modal loaders
```

The main `dashboard.html` becomes a clean ~50-line orchestrator:

```django
{% extends 'billing/base.html' %}
{% block extra_css %}{% include "billing/dashboard/_styles.html" %}{% endblock %}
{% block content %}
  {% include "billing/dashboard/_hero_banner.html" %}
  {% include "billing/dashboard/_kpi_cards.html" %}
  {% include "billing/dashboard/_kpi_totals.html" %}
  {% include "billing/dashboard/_chart_sales.html" %}
  ...
  {% include "billing/dashboard/_modal_recent_logins.html" %}
{% endblock %}
{% block extra_js %}{% include "billing/dashboard/_scripts.html" %}{% endblock %}
```

**Debugging benefit**: *"The KPI card shows wrong number"* -> I only read `_kpi_cards.html` (120 lines) instead of 2,774.

---

### Phase 2: Other Large HTML Templates

#### [SPLIT] [base.html](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/templates/billing/base.html) — **1,103 lines**

Contains: sidebar nav, topbar, notification bell, online staff dropdown, changelog dropdown (~120 lines of hardcoded entries), theme toggle, profile dropdown, and 489 lines of JS.

```
billing/templates/billing/base/
 _sidebar.html               (~120 lines) — Full sidebar navigation
 _topbar.html                (~200 lines) — Header bar with all dropdowns
 _notification_bell.html     (~50 lines)  — Notification dropdown
 _online_staff.html          (~40 lines)  — Currently logged in dropdown
 _changelog_dropdown.html    (~120 lines) — Changelog entries in topbar
 _profile_dropdown.html      (~50 lines)  — Profile + logout dropdown
 _theme_toggle.html          (~10 lines)  — Dark/light mode toggle
 _improvement_modal.html     (~90 lines)  — Improvement request modal + JS
 _scripts.html               (~490 lines) — Sidebar, notifications, online staff, idle timeout JS
```

The main `base.html` becomes a clean layout skeleton (~80 lines).

#### [SPLIT] [live_monitoring.html](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/templates/billing/live_monitoring.html) — **1,395 lines**

Contains: 382 lines CSS, 639 lines JS, 11 modals, hero section, 2x2 grid of panels, traffic card.

```
billing/templates/billing/live_monitoring/
 _styles.html                (~380 lines) — All CSS
 _hero.html                  (~60 lines)  — Left blue hero section
 _grid_panels.html           (~120 lines) — 2x2 grid (alerts, addons, offline, telemetry)
 _traffic_card.html          (~80 lines)  — Bottom live traffic card
 _modal_addon.html           (~60 lines)  — Apply addon modal
 _modal_customer_chart.html  (~50 lines)  — Customer live chart modal
 _modal_view_all.html        (~30 lines)  — View all modal
 _modal_search.html          (~40 lines)  — Search customer modal
 _scripts.html               (~640 lines) — All polling, chart, DataTables JS
```

#### [SPLIT] [view_customer.html](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/templates/billing/view_customer.html) — **1,031 lines**

Contains: 100 lines CSS, 275 lines JS, 7 modals, customer info cards, logs table.

```
billing/templates/billing/view_customer/
 _styles.html                (~100 lines)
 _info_cards.html            (~200 lines) — Basic, network, cignal info sections
 _live_monitoring.html       (~60 lines)  — Embedded live monitoring section
 _location_map.html          (~40 lines)  — Location map
 _logs_table.html            (~120 lines) — Customer activity logs table
 _modal_reactivate.html      (~40 lines)
 _modal_health.html          (~40 lines)
 _modal_expiration.html      (~40 lines)
 _modal_balance.html         (~40 lines)
 _modal_cignal.html          (~40 lines)
 _modal_sms.html             (~40 lines)
 _modal_email.html           (~40 lines)
 _scripts.html               (~280 lines)
```

#### [SPLIT] [customer_list.html](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/templates/billing/customer_list.html) — **783 lines**

```
billing/templates/billing/customer_list/
 _styles.html                (~105 lines)
 _hero_filters.html          (~80 lines)  — Page hero + filter pills
 _table.html                 (~150 lines) — Main DataTable
 _modal_bulk_sms.html        (~60 lines)
 _modal_bulk_email.html      (~60 lines)
 _modal_bulk_transfer.html   (~60 lines)
 _scripts.html               (~325 lines) — DataTables init, bulk actions JS
```

#### [SPLIT] [portal_dashboard.html](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/customer_portal/templates/customer_portal/portal_dashboard.html) — **1,519 lines**

```
customer_portal/templates/customer_portal/portal_dashboard/
 _styles.html                (~600 lines)
 _navbar.html                (~50 lines)
 _hero.html                  (~60 lines)
 _alerts.html                (~40 lines)
 _subscription_card.html     (~100 lines)
 _billing_history.html       (~80 lines)
 _quick_actions.html         (~60 lines)
 _modal_payment.html         (~80 lines)
 _modal_addon.html           (~80 lines)
 _modal_plan.html            (~80 lines)
 _scripts.html               (~300 lines)
```

#### [KEEP] [changelog.html](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/templates/billing/changelog.html) — **765 lines**
This is basically just static content (release notes). It's long but there's nothing to debug — leave it as-is.

---

### Phase 3: Python Views and Backend

The `billing/views/` package is **already split** (great job on that!), but some files have grown too large. Here's what to refactor:

#### [SPLIT] [customers.py](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/views/customers.py) — **863 lines, 19 functions**

Split by domain:

```
billing/views/
 customers.py      (KEEP — trim to ~400 lines)
   -> customer_list, add_customer, edit_customer, view_customer,
      delete_customer, verify_customer, unverify_customer

 customer_actions.py  (NEW — ~250 lines)
   -> customer_force_suspend, customer_kick_session,
      customer_force_reactivate, edit_customer_expiration,
      edit_customer_balance

 customer_tools.py    (NEW — ~200 lines)
   -> bulk_sms_view, bulk_email_view, sms_view, mac_history_view,
      auto_suspend_view, statement_of_account_view, bulk_transfer_router
```

#### [SPLIT] [payments.py](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/views/payments.py) — **808 lines, 11 functions**

```
billing/views/
 payments.py       (KEEP — trim to ~400 lines)
   -> payment_portal_view, pay_customer_view, payment_success_view,
      create_payment_view

 payment_logs.py   (NEW — ~250 lines)
   -> payment_logs_view, edit_payment_log_view, revert_transfer_payment,
      payment_addon_logs_view

 payment_financial.py (NEW — ~160 lines)
   -> customer_rebate_view, customer_rollback_view, rebates_logs_view
```

#### [SPLIT] [api.py](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/billing/views/api.py) — **645 lines, 17 functions**

This is a grab-bag of unrelated APIs. Split by feature:

```
billing/views/
 api.py            (KEEP — trim to ~150 lines, general utility APIs)
   -> api_notifications, api_mark_notification_read,
      api_mark_all_notifications_read, notifications_list_view

 api_monitoring.py (NEW — ~200 lines)
   -> api_live_monitoring_data, api_offline_users, api_router_uplink,
      api_network_alerts, api_active_pppoe_usernames

 api_dashboard.py  (NEW — ~150 lines)
   -> api_top_clients, api_popular_plans, api_downdetector_data,
      api_customer_mikrotik_status

 api_services.py   (NEW — ~150 lines)
   -> mikrotik_active_users_data_api, subscription_plans_data_api,
      live_addon_requests_api, resolve_addon_request_api
```

#### [SPLIT] [network_manager/views.py](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/network_manager/views.py) — **753 lines, 23 functions**

Convert to a views package (same pattern as billing):

```
network_manager/views/
 __init__.py        (import hub)

 devices.py         (~200 lines)
   -> device_list, add_device, edit_device, delete_device,
      test_device_connection, sync_device_users, device_hardware_api

 nap.py             (~100 lines)
   -> nap_list_view, add_nap_view, edit_nap_view, delete_nap_view

 sync.py            (~150 lines)
   -> sync_manager, sync_push_user, sync_autofix_user,
      sync_delete_user, sync_bulk_action, setup_router_profiles

 winbox.py          (~200 lines)
   -> winbox_routers, winbox_dashboard, winbox_secret_action,
      winbox_profile_action, winbox_kick_action

 calculator.py      (~50 lines)
   -> fbt_plc_calculator_view
```

#### [SPLIT] [network_manager/services.py](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/network_manager/services.py) — **674 lines, 1 giant class**

The `MikrotikAPI` class is one massive class with all router operations. Split into method groups:

```
network_manager/services/
 __init__.py        (re-exports MikrotikAPI)
 base.py            (~100 lines) — MikrotikAPI.__init__, connect, disconnect
 users.py           (~200 lines) — add_user, edit_user, delete_user, get_users
 profiles.py        (~100 lines) — get_profiles, add_profile, edit_profile
 monitoring.py      (~150 lines) — get_traffic, get_resources, health checks
 sync.py            (~120 lines) — sync_all, reconcile, bulk operations
```

---

### Phase 4: CSS Organization

#### [SPLIT] [theme.css](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/static/css/theme.css) — **2,376 lines**

This is the second-largest file in the project. Split by responsibility:

```
static/css/
 theme.css          (KEEP — trim to ~200 lines, just CSS variables + base)
 theme-dark.css     (~500 lines) — All dark mode overrides
 theme-sidebar.css  (~200 lines) — Sidebar and navigation styles
 theme-cards.css    (~200 lines) — Card, glass-card, KPI card styles
 theme-tables.css   (~200 lines) — Table, DataTable overrides
 theme-dropdowns.css (~150 lines) — Dropdown, notification, staff panel
 theme-modals.css   (~150 lines) — Modal styling
 theme-animations.css (~100 lines) — All animations and transitions
 theme-forms.css    (~100 lines) — Form inputs, buttons, badges
 theme-gamer.css    (~200 lines) — Gamer theme toggle, scanlines, CRT effects
```

Then update `base.html` to load them:

```html
<link rel="stylesheet" href="{% static 'css/theme.css' %}">
<link rel="stylesheet" href="{% static 'css/theme-dark.css' %}">
<link rel="stylesheet" href="{% static 'css/theme-sidebar.css' %}">
...
```

#### [KEEP] [styles.css](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/static/css/styles.css) — **679 lines**
This is borderline. It's mostly action button and table utility styles. Can be left as-is for now.

---

### Phase 5: Customer Portal

#### [MODIFY] [customer_portal/views.py](file:///c:/Users/alber/OneDrive/Documents/Vscode/GAMETECH-BILLING-SYSTEM/customer_portal/views.py) — **401 lines**
This is borderline but manageable. If it grows past 500, convert to a views package. **Skip for now.**

---

### Phase 6: Cleanup and Documentation

After all splits are done:

1. **Delete duplicate CSS**: `static/assets/css/styles.css` (679 lines) appears to be a duplicate of `static/css/styles.css` — verify and remove
2. **Clean up `billing/views/__init__.py`**: Update imports to include the new split modules
3. **Update `billing/urls.py`**: No changes needed — the `__init__.py` re-exports handle routing
4. **Create a `README` inside `billing/templates/billing/`** explaining the folder structure for future reference

---

## Execution Priority and Time Estimates

| Priority | Phase | Impact | Est. Time |
|----------|-------|--------|-----------|
| 1st | **Phase 1** — Dashboard HTML | Eliminates the #1 worst file (2,774 -> ~50 lines) | ~1 session |
| 2nd | **Phase 2** — Other HTML templates | Fixes 5 more monster files | ~2 sessions |
| 3rd | **Phase 3** — Python views | Makes backend debugging 3x faster | ~1 session |
| 4th | **Phase 4** — CSS | Fixes the #2 worst file (2,376 lines) | ~1 session |
| 5th | **Phase 6** — Cleanup | Polish and documentation | ~30 min |

> Phase 5 (Customer Portal views.py) can be skipped — it's only 401 lines and manageable.

---

## Open Questions

1. **Changelog dropdown in base.html**: Should I move the changelog entries to the database (managed via admin panel) or just extract as a partial template? Moving to database = more work but cleaner long-term.

2. **CSS split granularity**: Do you want me to split `theme.css` into 10 files as proposed, or would fewer larger files (e.g., just `theme-base.css`, `theme-dark.css`, `theme-components.css`) be better?

3. **Phase order**: I recommend starting with Phase 1 (dashboard.html) since it's the single biggest win. Do you agree, or do you want to prioritize differently?

4. **Git strategy**: Should I commit after each phase, or do you want to review all changes before committing?

---

## Verification Plan

### After Each Phase
- Run `python manage.py check` to verify no Django errors
- Run the audit script again to confirm line counts dropped
- Visually verify the affected pages still render correctly

### Final Verification
- Full page load test on: Dashboard, Customer List, View Customer, Live Monitoring, Portal Dashboard
- Confirm dark mode still works across all pages
- Confirm all modals still open/close correctly
- Re-run the audit script — target: **0 files over 800 lines**
