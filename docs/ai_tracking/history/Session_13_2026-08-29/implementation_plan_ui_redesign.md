# Full System UI Redesign Plan
## Goal: Apply premium gradient/glassmorphism design to ALL HTML templates

### Design Language
- **Page Hero**: `page-hero` class — dark blue gradient banner with icon, title, subtitle
- **Section Headers**: `section-header section-header-[color]` — gradient colored card headers
- **Filter Panels**: `filter-glass` — frosted glass filter areas
- **Status Pills**: `pill pill-active/expired/suspended/inactive/pending`
- **Table**: `table-premium` — styled thead, hover rows, pill badges
- **Cards**: `dashboard-card` with `section-header` inside
- **Buttons**: `btn-premium btn-p-[primary/success/danger/warning/ghost]`
- **Avatar**: `av av-sm/md av-[color]`
- **Empty State**: `empty-state` with `es-icon`
- **Fonts**: Inter (already in base)

### ✅ ALREADY DONE
- `base.html` — notifications dropdown, online staff panel, changelog redesigned
- `logs.html` — ✅
- `payment_logs.html` — ✅
- `notifications.html` — ✅
- `theme.css` — v2 with all global utilities ✅

### 🔄 PRIORITY ORDER (now executing)
1. `dashboard.html` — Main home page, highest traffic
2. `customer_list.html` — Core ops page
3. `view_customer.html` — Customer detail
4. `pay_customer.html` — Payment flow
5. `add_customer.html` — Add customer form
6. `edit_customer.html` — Edit form
7. `add_on_payments.html` — Payments hub
8. `subscription_plans.html` — Plans list
9. `plan_list.html` / `add_plan.html` / `edit_plan.html`
10. `staff_and_admins.html` / `add_staff.html` / `edit_staff.html`
11. `settings.html` / `settings_list.html` / `settings_form.html`
12. `improvement_requests.html`
13. `mikrotik_active_users.html`
14. `auto_suspend.html`
15. `geomap.html`
16. `payment_addon_logs.html`
17. `rebates_logs.html`
18. `user_cignal_logs.html`
19. `cignal_play_list.html` / `cignalplay_form.html`
20. `sms_messaging.html`
21. `agents.html` / `add_agent.html` / `edit_agent.html` / `view_agent.html`
22. `mac_history.html`
23. `change_password.html`
24. `profile.html`
25. `statement_of_account.html`
26. `customer_rebate.html` / `customer_rollback.html`
27. `edit_payment_log.html`
28. `service_plans.html`
29. `payment_success.html`

### SKIP (by request / special design)
- `live_monitoring.html` — special design, DO NOT TOUCH
- `login.html` — already has custom design
- `payment_portal.html` — customer-facing portal
