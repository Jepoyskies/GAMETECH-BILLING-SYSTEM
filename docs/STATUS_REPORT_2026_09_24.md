# Gametech Unli Fiber — Comprehensive System Status Report
**Date:** September 24, 2026  
**Branch:** `feature/dispatch-operation` (HEAD commit: `b4503d1`)  
**Target Droplet:** `143.198.207.144` (DigitalOcean / Ubuntu / Docker Compose V2)  
**Safety Protocol Active:** `ROUTER_MODE=read_only` (Physical MikroTik writes strictly blocked)  

---

## 1. Item Status Table

| Item / Subsystem | Status | How Verified | Commit(s) | What is Left | Risks / Notes |
|---|---|---|---|---|---|
| **Phase 0: Safety Net & Hardware Protection** | **DONE** | [VERIFIED] Code in `network_manager/services/base.py` & `sync_services.py`; 10 unit tests in `billing.tests.test_router_dry_run` + 3 tests in `network_manager.tests.test_router_modes` pass. `ROUTER_MODE=read_only` active in running container environment. | `6862590`, `4520af1` | None. | Zero live socket writes reach hardware while `read_only` is active. |
| **Phase 1: Security Hardening & Logins** | **DONE** | [VERIFIED] `Customer.portal_password_hash` active; droplet query confirmed **0** plaintext passwords exist. Brute-force lockout (5 attempts -> 15 min lock) & IP rate limit (15/min) active in `billing/middleware.py`. 11 unit tests in `billing.tests.test_phase1_security` + 5 in `customer_portal.tests.test_portal_security` pass. | `6067b0d`, `8141209` | Semaphore key rotation on droplet `.env`. | Password policy enforced on staff, tech, and portal logins. |
| **Phase 2: Foundation (Models, Migrations & Permissions)** | **DONE** | [VERIFIED] Migrations `billing.0055`, `dispatch.0011` applied. 16 named permissions registered. `JobTicket` model with `can_transition_to` state machine. 9 unit tests in `billing.tests.test_phase2_foundation` pass. | `7d227c8`, `51a37c0` | None. | Permissions correctly partitioned across 5 roles. |
| **Phase 3: Checklist, Prospects & Agent Portal** | **DONE** | [VERIFIED] Mandatory 6-item onboarding checklist in `billing/views/customers/crud.py`; model guard on `Customer.save`; mobile agent portal in `billing/templates/billing/agent_portal/`. 18 unit tests in `billing.tests.test_phase3_onboarding` pass. | `9d54e4c`, `c4ff682` | None. | Manual override requires `billing.add_existing_subscriber` permission. |
| **Phase 3.1: Strict Onboarding & Guard Audit** | **DONE** | [VERIFIED] Model bypass flags (`is_test_data`, `_checklist_verified`) audited. Method choices restricted strictly to `in_person` and `phone`. Proven rollback tested against temporary database. | `209fcb8` | None. | Proven 56-table parity verified on scratch database. |
| **Phase 3.2: Router Modes & Guard Loopholes** | **DONE** | [VERIFIED] Tri-state `ROUTER_MODE` gateway in `MikrotikBase._get_api()`. Blocked writes log to `SystemLog`. Customer status preserved when router write is blocked (`sync_status='Blocked'`). 7 tests in `billing.tests.test_phase3_2_guards` pass. | `4520af1` | None. | Background cron tasks safely blocked from altering router state. |
| **Phase 3.3: Hardening & Bug Fixes** | **DONE** | [VERIFIED] Semaphore key default removed from `settings.py`; `GametechPasswordPolicyValidator` added to `AUTH_PASSWORD_VALIDATORS`; legacy plaintext fallback removed from `check_portal_password`; concurrency-safe ticket generator (`test_ticket_concurrency.py` 10 threads pass); proven rollback on scratch database (57 tables, 1,163 rows). | `445cb94`, `d7da57a` | Input real rotated key into droplet `.env`. | Complete isolation of secrets and clean rollback proof. |
| **Customer View "More Actions" Dropdown** | **PARTIAL / BROKEN** | [VERIFIED] Inspected `billing/templates/billing/view_customer/_profile_header.html`. All 10 items exist in template (SOA, Update Health, Send SMS, Send Email, Rebate, Rollback, Kick Session, Force Suspend, Force Reactivate, Delete). However, 3 operational defects confirmed: (1) Rollback intercepted by unwanted `confirmRollback()` Swal popup; (2) Dropdown lacks `max-height`/scroll and clips bottom items on viewports < 900px; (3) Delete button role check restricted to `role == 'Admin'`. | `53ac42a`, `12e5192` | Apply surgical 15-line CSS/template repair to `_profile_header.html`. | Technicians and staff on laptops cannot reach lower action items without CSS scroll fix. |
| **Regression Audit of Redesigned Pages** | **DONE** | [VERIFIED] Audited all 9 pages against pre-redesign commits in `docs/FEATURE_INVENTORY.md`. Found 6 non-KEPT items (Delete customer moved to row dropdown, Cignal Play column merged, Add Customer email made optional, Agent list mobile cards consolidated, Dispatch pipeline replaced by Queue, Customer View More Actions clipping). | `b4503d1` | User approval of non-KEPT items. | Code behavior is stable; inventory cataloged. |
| **Phase 4A: Unified Dispatch Queue & Mobile Tech View** | **DONE** | [VERIFIED] Unified queue in `dispatch/views_queue.py` & `queue.html`; mobile tech view in `dispatch/views_tech.py` & `tech_mobile.html`; Arrived (starts timer, optional GPS) and Done (stops timer, report); 3-call-attempt rule before returning to dispatch; timer correction with reason. 7 tests in `dispatch.tests.test_dispatch_operations` pass. | `2b93eec`, `040fa78` | None. | Draft Stage 1/2/3 pages retired with backward-compatible URL redirects. |
| **Phase 4B: Dispatch QA, Admin Approval & Lifecycle** | **DONE** | [VERIFIED] QA cockpit in `4_qa.html` with mandatory `client_called_by_qa` checkbox; Revisit (resets timer) vs Correct Report (keeps timer); Admin approval cockpit in `5_approval.html`; 2-bounce alert (`repeated_bounce_alert=True`); clean repairs bypass admin approval; unreachable close (`closed_not_installed`) and reopen flow; Customer View 6-step lifecycle tracker; Request Service modal enters queue. 7 tests in `dispatch.tests.test_phase4b_operations` pass. | `4ec657b`, `b4503d1` | None. | Complete field-to-activation operations verified. |
| **Phase 5: Billing Integration, 60-Day Lock & Incentives** | **PARTIAL / NOT BUILT** | [VERIFIED] Model fields exist in `billing/models.py` (`Customer.first_payment_date`, `Customer.agent_lock_until`, `IncentiveSetting`, `AgentQualificationEvent`, `AgentPayoutBatch` in migration `0055`). However, automatic first-payment date hook in `pay_customer_view`, server-side 60-day staggered lock enforcement, automated Welcome SMS on first payment, and the incentive calculation engine / payout workflows are **NOT STARTED**. | `7d227c8` | Implement first-payment hook, 60-day lock check in payment views, welcome SMS trigger, and qualification/payout engine. | Agents cannot yet automatically qualify or cash out referral commissions. |
| **Phase 6: UI Unification in Dark & Light** | **PARTIAL** | [VERIFIED] Dispatch Queue, Customers Directory, Subscriptions, Cignal Dashboard, Customer View fully support dual themes with standard CSS tokens (`design_system.css`). Secondary admin pages (Network Devices, NAP Boxes, System Settings, Message Templates) still run legacy markup. | `53ac42a`, `040fa78` | Refactor remaining secondary admin templates into design-system partials. | Minor visual inconsistency between core dispatch/customer views and network/system settings. |
| **Documents & Migration Track** | **NOT STARTED** | [VERIFIED] `docs/SYSTEM_STORY_AND_MAP.md` does not exist (`False`). Legacy billing import commands (`import_legacy`, `docs/CUTOVER_RUNBOOK.md`) do not exist (`False`). Cron `auto_reconcile_routers.py` exists, but M1/M2/M3 cutover pipeline is unbuilt. | N/A | Write System Story, Cutover Runbook, and build M1-M3 legacy import scripts. | High operational risk if attempting cutover without proven reconciliation runbook. |

---

## 2. Specification Check (docs/SPEC.md Decisions 1–18)

| Decision # | Summary | Status | Evidence & Verification |
|---|---|---|---|
| **1** | Mandatory Onboarding Checklist (server-side, 6 items, declines recorded, atomic submit) | **BUILT** | [VERIFIED] `billing/views/customers/crud.py:add_customer` validates all 6 checkboxes; `Customer.save()` model guard rejects invalid creates; `ChecklistConfirmation` stores immutable snapshot. Declines record without creating customer. 18 tests in `test_phase3_onboarding` pass. |
| **2** | Walk-in Add Customer after checklist; disconnected until installed | **BUILT** | [VERIFIED] `installation_status='pending'`, `status='disconnected'`; excluded from billing cutoff and active dashboard counters in `billing/views/dashboard.py` and `list.py`. |
| **3** | Agents create only PROSPECTS; staff get bell notification, run checklist, create customer with agent linked | **BUILT** | [VERIFIED] `billing/views/agents.py:submit_prospect` creates `Prospect(status='under_review')` and `Notification` to staff. `add_customer` pre-fills prospect data and sets `customer.original_agent`. |
| **4** | Agent portal: minimal mobile layout, no staff access, no contact details in table, duplicate detection, first submission credit | **BUILT** | [VERIFIED] `billing/templates/billing/agent_portal/` mobile layout; phone and address excluded from referral table; `check_customer_or_prospect_duplicate()` in `billing/validators.py` preserves first agent credit. |
| **5** | First payment activates customer; first payment date = install date; starts 60-day lock; QA/admin never gate activation | **PARTIAL** | [VERIFIED] Models have `first_payment_date` and `agent_lock_until`. Payment renewal activates customer. However, automatically stamping `first_payment_date = install_date` upon first payment is Phase 5 work, not yet built. |
| **6** | Staggered lock: 3-day/15-day/custom options disabled for agent referrals for 60 days from first payment date | **PARTIAL / NOT BUILT** | [VERIFIED] Field `agent_lock_until` exists on `Customer`. Server-side validation blocking short renewals in `billing/views/payments/transactions.py` is not yet implemented. |
| **7** | Incentive engine: PHP 500 per qualified 2nd month payment; cash out PHP 2,500 per 5 qualified; permanent history | **PARTIAL / NOT BUILT** | [VERIFIED] Models `IncentiveSetting`, `AgentQualificationEvent`, `AgentPayoutBatch` exist in `billing/models.py`. The calculation listener on payment and the cashout request views are not yet implemented. |
| **8** | Agent changes require permission and logged reason; original agent preserved | **BUILT** | [VERIFIED] `billing/views/customers/crud.py:edit_customer` enforces `billing.change_customer_agent`, requires reason, logs to `CustomerAgentHistory`. `customer.original_agent` is never mutated. |
| **9** | 5 Roles: Agent, Staff, Dispatch, Technician, Admin; permission-based | **BUILT** | [VERIFIED] `setup_dispatch_permissions` management command created 16 permissions mapped across Django Auth groups. Multi-role assignment supported. |
| **10** | Same-person rule: do not block; flag jobs where one person handled 2+ stages and display to admins | **BUILT** | [VERIFIED] `JobTicket.same_person_flag` and `same_person_stages` computed during QA review; displayed with warning badge in `pipeline/5_approval.html` and `admin_summary.html`. |
| **11** | Bounce-backs need reason and type (revisit vs correct report); admin summary; alert after 2 bounces | **BUILT** | [VERIFIED] `TicketBounceHistory` captures reasons and types; `repeated_bounce_alert=True` triggered on 2nd bounce with in-app notification; `dispatch/templates/dispatch/admin_summary.html` aggregates patterns. |
| **12** | Client unreachable: technician logs call attempts (3-attempt rule), returns to dispatch; close flow (`Closed - Not Installed`); reopen flow | **BUILT** | [VERIFIED] `CallAttemptLog` tracks attempts; return to dispatch unlocks after 3 attempts; `api_close_unreachable` requires `client_agent_informed` tick; `api_reopen_onboarding` resets customer and redirects to checklist. |
| **13** | Technician mobile-first view: see only assigned jobs; Arrived (timer + GPS), Done (stops timer, report); timer correction with reason | **BUILT** | [VERIFIED] `dispatch/views_tech.py:technician_mobile_ui` filters `technicians=tech`; self-assignment blocked; `api_ticket_arrived` & `api_ticket_done` record timestamps and GPS; `api_correct_timer` audits adjustments. |
| **14** | Assignment: team-based picker, off-duty marking | **BUILT** | [VERIFIED] `_queue_assign_modal.html` assigns individuals or entire team; `api_toggle_technician_duty` toggles `technician.is_available`; off-duty techs excluded from assignable list. |
| **15** | Notifications (bell): prospect submitted, tech Done, bounce-backs, repeated bounce alert, unreachable return | **BUILT** | [VERIFIED] Reuses `billing.models.Notification`. Triggered across all 5 events with direct links to tickets or prospects. |
| **16** | Real Site Visit ticket type (assign -> done) | **BUILT** | [VERIFIED] `SITE_VISIT` in `TICKET_TYPE_CHOICES`; flows directly from `IN_PROGRESS` -> `COMPLETED`, skipping QA; selectable in Request Service modal. |
| **17** | One central ticket-number generator | **BUILT** | [VERIFIED] `dispatch/utils.py:generate_ticket_number()` generates sequential `GT-YYYYMMDD-XXXX`. Concurrency verified across 10 simultaneous threads with 0 collisions. |
| **18** | Welcome SMS on first payment with portal credentials, single display, masked in SmsLog | **PARTIAL / NOT BUILT** | [VERIFIED] Password generation and masking in `SmsLog` exist for manual reset. Automatic trigger on first payment renewal in `pay_customer_view` is Phase 5 work, not yet built. |

---

## 3. No-Regression Check (Comparison with docs/FEATURE_INVENTORY.md)

Every page in the repository was audited against its pre-redesign baseline. All findings are cataloged below:

| Page | Control / Feature | Baseline State | Current State | Audit Classification |
|---|---|---|---|---|
| **Customers Directory** (`/customers/`) | Delete Customer | Direct button on row | Moved into 3-dots row dropdown menu | **MOVED** (Clean UI consolidation) |
| **Customers Directory** (`/customers/`) | All Filters & Columns | 9 columns, 5 filters | 10 columns, 5 filters, bulk actions | **KEPT / EXPANDED** |
| **Customer Subscriptions** (`/subscriptions/`) | All Actions, Filters & Bulk Tools | 5 columns, 7 KPI filters, bulk SMS/email | 100% identical controls and endpoints | **KEPT** (Zero loss) |
| **Cignal Play** (`/cignal-play/`) | "Adjusted By" Column | Separate table column | Merged into "Date Applied" cell | **MOVED / MERGED** (Responsive improvement) |
| **Cignal Play** (`/cignal-play/`) | Delete Subscription | Direct button on row | Moved into 3-dots row dropdown menu | **MOVED** |
| **Dispatch Dashboard** (`/dispatch/`) | Pipeline Stage 1/2/3 Buttons | 3 separate stage buttons | Replaced by unified Dispatch Queue (`dispatch_queue`) | **REMOVED / REPLACED** (Required by SPEC Phase 4A) |
| **Dispatch Master Log** (`/dispatch/monitoring/`) | Table Columns | 7 legacy columns | Expanded to 17 standard ISP columns | **EXPANDED** (Zero loss) |
| **Dispatch Management** (`/dispatch/management/`) | 4 Management Subtabs | Monolithic single template | Sliced into 4 modular partials | **MOVED** (Zero loss) |
| **Add Customer** (`/customers/add/`) | Email Address Input | Required field | Optional field | **BEHAVIOR CHANGED** (Intentional for rural subscribers) |
| **Renew / Pay Bill** (`/pay/`) | Payment Engine & Controls | All inputs & calculations | 100% identical to baseline (0 diff) | **KEPT** |
| **Message Templates** (`/settings/templates/`) | Template Editor & Smart Tags | All inputs & previews | 100% identical to baseline (0 diff) | **KEPT** |
| **Agent Pages** (`/agents/`) | Mobile Cards Layout | Separate card markup | Unified into responsive DataTables | **REMOVED / CONSOLIDATED** |
| **Customer View** (`/customers/view/<id>/`) | More Actions: Rollback | Direct link `<a href="...">` | Button with SweetAlert confirmation | **BEHAVIOR CHANGED / BROKEN** (Redundant popup before form) |
| **Customer View** (`/customers/view/<id>/`) | More Actions: Bottom Actions | Unrestricted height | No max-height/scroll on dropdown | **CLIPPED BY CSS** (Clipped on < 900px viewports) |
| **Customer View** (`/customers/view/<id>/`) | More Actions: Delete Customer | Admin permission check | Hardcoded `request.user.role == 'Admin'` | **HIDDEN BY CONDITION** (Hidden for superusers without Admin role) |

---

## 4. Server State & Production Health

- **Target Host:** DigitalOcean Droplet `143.198.207.144` (Ubuntu 22.04 LTS).
- **Active Git Branch:** `feature/dispatch-operation`.
- **Active Droplet Commit:** `b4503d1` (`docs(dispatch): document Phase 4B QA, approval, bounce tracking, and lifecycle updates`). Working tree clean. Matches local repository and `origin/feature/dispatch-operation`.
- **Main Branch Status:** `origin/main` is at commit `a352602` (`feat(checkout): detached drawer...`). **Main is completely untouched** by any work in this feature branch.
- **Docker Containers Health:** All 5 containers are running and healthy:
  - `gametech-billing-system-web-1`: Up 1+ hour (`0.0.0.0:8000->8000/tcp`).
  - `gametech-billing-system-celery-1`: Up 3+ hours.
  - `gametech-billing-system-celery-beat-1`: Up 3+ hours.
  - `gametech-billing-system-db-1`: Up 3+ hours (`postgres:15-alpine`, port 5432).
  - `gametech-billing-system-redis-1`: Up 3+ hours (`redis:7-alpine`, port 6379).
- **Hardware Protection (`ROUTER_MODE`):**
  - Confirmed actively set to `ROUTER_MODE=read_only` across `web`, `celery`, and `celery-beat` containers.
  - Zero live modifying packets leave the host for physical MikroTik routers. Blocked writes log to `SystemLog`.
- **Database Migrations:**
  - Latest migration applied on droplet: `billing.0058_phase3_2_guards_and_source`, `dispatch.0013_jobticket_is_flagged_and_more`, `network_manager.0008_alter_mikrotikdevice_id_alter_napbox_id`.
  - Zero unapplied migrations exist between the repository and production database.
- **Database Backups Ledger (`/root/backups`):**
  - `gametech_phase0_backup_20260924.sql` (231 KB)
  - `gametech_phase1_backup_20260924.sql` (233 KB)
  - `gametech_phase2_backup_20260924.sql` (233 KB)
  - `gametech_phase3_backup_20260924.sql` (272 KB)
  - `gametech_phase3_1_backup_20260924.sql` (305 KB)
  - `gametech_phase3_2_backup_20260924.sql` (277 KB)
  - `gametech_backup_phase3_3.sql` (311 KB)
  - `gametech_backup_pre_phase4a.sql` (311 KB)
  - `gametech_backup_pre_phase4b.sql` (313 KB)

---

## 5. Automated Test Suite Execution & Coverage

All tests were executed directly inside the production container on the droplet across 3 small batches. **100% of tests passed with zero failures and zero errors:**

| Batch | Test Modules | Test Count | Result | Execution Time |
|---|---|---|---|---|
| **Batch 1** | `billing.tests.test_baseline`, `billing.tests.test_router_dry_run`, `network_manager.tests.test_router_modes` | 16 | **OK** (0 failures, 0 errors) | 6.490s |
| **Batch 2** | `billing.tests.test_phase1_security`, `billing.tests.test_phase2_foundation`, `billing.tests.test_phase3_onboarding`, `billing.tests.test_phase3_2_guards` | 45 | **OK** (0 failures, 0 errors) | 135.690s |
| **Batch 3** | `customer_portal.tests.test_portal_security`, `dispatch.tests.test_dispatch_operations`, `dispatch.tests.test_ticket_concurrency`, `dispatch.tests.test_phase4b_operations` | 21 | **OK** (0 failures, 0 errors) | 66.699s |
| **TOTAL** | **Full System Active Test Suite** | **82** | **OK (100% PASSING)** | **208.88s** |

### Untested Modules & Test Gaps
1. `customer_portal`: Has 5 tests for portal authentication and lockout security, but **zero unit tests** for customer billing invoices, payment submission, profile editing, or support ticket views.
2. `network_manager`: Has 3 tests verifying router mode write-interception, but **zero unit tests** for device discovery, 2-way sync staging, Winbox live traffic graphs, or NAP box management.
3. `billing` (secondary views): Has 58 tests covering security, onboarding, router safety, and foundation, but **zero unit tests** for Cignal Play subscriptions CRUD, SMS message template editing, or employee payroll calculations.
4. `dispatch` (admin management): Has 16 operational tests, but **zero tests** for creating teams, setting monthly quotas, or editing dropdown choices in `management.html`.

---

## 6. Security & Hardening Audit

| Security Control | Status | Evidence & Verification |
|---|---|---|
| **Plaintext portal passwords gone** | **YES** | [VERIFIED] Queried production PostgreSQL database: `Customer.objects.filter(portal_password__isnull=False).exclude(portal_password='').count() == 0`. Model method `check_portal_password` has zero fallback to plaintext and strictly verifies PBKDF2/SHA256 hashes. |
| **Login lockout & IP rate limiting active** | **YES** | [VERIFIED] `billing.middleware.LoginRateLimitMiddleware` actively throttles `/login/`, `/portal/login/`, and `/admin/` to 15 POST requests/min per IP. Account & IP brute-force lockout actively triggers 15-minute lock after 5 consecutive failures via Redis cache. Verified by `test_login_lockout_after_failed_attempts`. |
| **Password policy on all logins** | **YES** | [VERIFIED] `GametechPasswordPolicyValidator` active in `gametech_core/settings.py:AUTH_PASSWORD_VALIDATORS`. Enforces 10+ characters, upper, lower, digit, special character, and weak-password blacklist. Called on staff creation, tech creation, agent portal, and customer portal. Verified by unit tests. |
| **No literal API keys left in repo** | **YES** | [VERIFIED] `SEMAPHORE_API_KEY` default hardcoding removed from `gametech_core/settings.py` (reads `env("SEMAPHORE_API_KEY", default="")`). Search across all code, tests, and scripts found zero hardcoded third-party API keys. Droplet `.env` configured with placeholder for rotated key. |
| **HTTPS status** | **PREPARED / HTTP** | [VERIFIED] Code is fully environment-driven for HTTPS (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`). `docs/HTTPS_SETUP.md` is complete with Nginx and Certbot instructions. The droplet currently responds on HTTP `http://143.198.207.144` pending domain DNS pointing and SSL issuance. |
| **Temp password never in logs or SmsLog** | **YES** | [VERIFIED] `billing/views/customers/auth_actions.py:reset_customer_portal_password` masks temporary passwords as `Temp Password: [REDACTED]` in `SmsLog`. `SystemLog` audit entries never contain cleartext passwords. Displayed strictly once to staff in a session banner that clears immediately upon render. |

---

## 7. Open List (Unfinished Work, Risks & Pending Decisions)

1. **Customer View "More Actions" Dropdown Surgical Fix:**
   - *Problem:* (a) Rollback item has a redundant `confirmRollback()` Swal confirmation popup before navigating to the transaction selection screen; (b) Dropdown menu lacks `max-height: 480px; overflow-y: auto;` causing the bottom items (Kick Session, Force Suspend, Force Reactivate, Delete) to clip off screen on laptop viewports (< 900px height); (c) Delete customer checks `request.user.role == 'Admin'` rather than `request.user.is_superuser or request.user.has_perm('billing.delete_customer')`.
   - *Awaiting Decision:* Apply the 15-line template fix to `billing/templates/billing/view_customer/_profile_header.html`.
2. **Phase 5 Billing Integration & First Payment Date:**
   - *Problem:* `Customer.first_payment_date` and `Customer.agent_lock_until` exist in the database, but `billing/views/payments/transactions.py:pay_customer_view` does not yet stamp `first_payment_date = install_date` upon recording the first payment.
   - *Risk:* Without this timestamp, the 60-day staggered lock cannot compute its expiration window.
3. **Phase 5 Staggered Lock Server-Side Enforcement:**
   - *Problem:* Server-side validation blocking 3-day and 15-day renewals for agent-referred customers during the 60-day window has not been written in the payment transaction views.
4. **Phase 5 Welcome SMS Automated Dispatch:**
   - *Problem:* Automatic dispatch of the welcome SMS with portal credentials upon first payment has not been wired into `pay_customer_view`.
5. **Phase 5 Agent Incentive Calculation Engine & Payouts:**
   - *Problem:* Models `IncentiveSetting`, `AgentQualificationEvent`, and `AgentPayoutBatch` exist, but the automated signal/listener that detects a customer's 2nd month payment and logs a PHP 500 qualification has not been built. The admin payout batching screen (PHP 2,500 per 5 qualified) is unbuilt.
6. **Phase 6 UI Dark & Light Unification (Secondary Admin Pages):**
   - *Problem:* Core customer and dispatch pages are unified, but secondary pages (`/devices/`, `/nap-boxes/`, `/settings/`, `/settings/templates/`) still run legacy CSS.
7. **Migration Track (M1, M2, M3) & Documentation:**
   - *Problem:* `docs/SYSTEM_STORY_AND_MAP.md` is unwritten. `docs/CUTOVER_RUNBOOK.md` is unwritten. Management commands for the legacy database import (`import_legacy`) and router reconciliation (`reconcile_routers`) do not exist.
8. **Semaphore SMS Key Rotation on Droplet:**
   - *Problem:* The droplet `/root/GAMETECH-BILLING-SYSTEM/.env` has `SEMAPHORE_API_KEY=` as an empty placeholder. SMS dispatch currently fails gracefully (logs warning and skips). The real rotated key must be pasted into `.env`.
9. **Proposed Changes from Regression Audit Awaiting User Approval:**
   - *Customer Directory:* Keep `Delete Customer` in the row dropdown menu (instead of separate row button).
   - *Cignal Play:* Keep `Adjusted By` column merged into `Date Applied` cell.
   - *Add Customer:* Keep `Email Address` field optional.
   - *Agent List:* Keep responsive table layout instead of separate mobile cards.

---

## 8. Recommended Next Steps

1. **Step 1: Apply Customer View "More Actions" Surgical Fix**  
   Apply the verified 15-line diff to `_profile_header.html` (restore direct rollback link, add `max-height: 480px; overflow-y: auto;` to `.dropdown-menu`, fix delete role check).
2. **Step 2: Implement Phase 5 First Payment & 60-Day Lock Hook**  
   In `billing/views/payments/transactions.py:pay_customer_view`, stamp `first_payment_date` and `agent_lock_until = payment_date + 60 days` when first payment is received; enforce staggered lock server-side.
3. **Step 3: Implement Phase 5 Automated Welcome SMS on First Payment**  
   Wire the welcome SMS trigger into `pay_customer_view` on first payment with randomly generated temporary portal credentials (masked in `SmsLog`).
4. **Step 4: Implement Phase 5 Incentive Calculation Engine & Admin Cashout Cockpit**  
   Build the payment listener that qualifies agent referrals upon 2nd month payment completion (PHP 500) and the admin payout batch management screen (multiples of PHP 2,500).
5. **Step 5: Author Migration Track & Cutover Runbook (Stages M1–M3)**  
   Write `docs/SYSTEM_STORY_AND_MAP.md`, `docs/CUTOVER_RUNBOOK.md`, and build the `import_legacy` and router reconciliation tools.

---

## 9. Manual Visual Verification Checklist (For User)

Please open the following URLs in your browser to inspect visual layout, responsiveness, and dark/light themes:

| Page / Feature | URL | What to Test | Themes / Devices |
|---|---|---|---|
| **Unified Dispatch Queue** | `http://143.198.207.144/dispatch/queue/` | Test tab switching (Unassigned, In Progress, QA), open Assignment modal, toggle technician duty status | Desktop & Mobile; Dark & Light |
| **Mobile Technician View** | `http://143.198.207.144/dispatch/tech/` | Inspect job cards, test Arrived button (timer starts), Done button (stops timer & report form), call attempt logger | Mobile View (DevTools Ctrl+Shift+M or phone); Dark & Light |
| **Dispatch QA Cockpit** | `http://143.198.207.144/dispatch/qa/` | Inspect timer display, verify "Client was called" requirement, test Revisit vs Correct Report bounce modals | Desktop; Dark & Light |
| **Admin Final Approval** | `http://143.198.207.144/dispatch/approval/` | Inspect ticket details, approve customer activation, test Bounce to Dispatch modal | Desktop; Dark & Light |
| **Admin Summary Analytics** | `http://143.198.207.144/dispatch/admin-summary/` | Inspect bounce patterns table, same-person flags, separate unreachable returns table | Desktop; Dark & Light |
| **Customer View ("More Actions")** | `http://143.198.207.144/customers/view/1/` | Open "More Actions" dropdown, verify all 10 items, verify scrolling on laptop screen (<900px height) | Desktop & Laptop; Dark & Light |
| **Add Customer Checklist** | `http://143.198.207.144/customers/add/` | Verify 6-item onboarding policy checklist, test walk-in decline modal, test checklist bypass guard | Desktop & Mobile; Dark & Light |
| **Mobile Agent Portal** | `http://143.198.207.144/agent-portal/dashboard/` | Verify absence of admin sidebar, test prospect submission form, verify referral table hides customer contact info | Mobile; Dark & Light |
| **Customers Directory** | `http://143.198.207.144/customers/` | Test search, status filter, router filter, bulk edit plan modal, CSV export | Desktop & Mobile; Dark & Light |
| **Customer Subscriptions** | `http://143.198.207.144/subscriptions/` | Test 7 KPI cards, connection filter, bulk SMS modal, row Pay shortcut | Desktop; Dark & Light |
| **Cignal Play Dashboard** | `http://143.198.207.144/cignal-play/` | Test KPI metric cards, active/overdue/all tabs, reload modal, edit modal | Desktop; Dark & Light |

---
*Status report compiled and verified from running code, droplet containers, test runners, and database ledgers.*
