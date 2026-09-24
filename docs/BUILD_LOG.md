# Gametech Unli Fiber — Engineering Build Log & Decision Ledger

**Branch:** `feature/dispatch-operation`  
**Target Droplet:** `143.198.207.144` (DigitalOcean / Ubuntu / Docker Compose)  
**Postgres Database:** `gametech_db`  
**Redis Cache:** Redis 7 (Docker container `gametech-billing-system-redis-1`)

---

## Database Backups Ledger

| Phase | Timestamp | Backup Path | File Size | Description | Rollback Command |
|---|---|---|---|---|---|
| **Phase 0** | 2026-09-24 03:45 UTC | `/root/backups/gametech_phase0_backup_20260924.sql` | 231 KB | Pre-migration baseline backup before Dispatch Operation build | `cat /root/backups/gametech_phase0_backup_20260924.sql \| docker exec -i 28514b2a5c9a psql -U gametech_user gametech_db` |
| **Phase 1** | 2026-09-24 04:35 UTC | `/root/backups/gametech_phase1_backup_20260924.sql` | 233 KB | Pre-migration backup before Customer password hashing migration 0054 | `cat /root/backups/gametech_phase1_backup_20260924.sql \| docker exec -i 28514b2a5c9a psql -U gametech_user gametech_db` |
| **Phase 2** | 2026-09-24 05:16 UTC | `/root/backups/gametech_phase2_backup_20260924.sql` | 233 KB | Pre-migration backup before Phase 2 Dispatch Foundation migrations 0055 & 0011 | `cat /root/backups/gametech_phase2_backup_20260924.sql \| docker exec -i 28514b2a5c9a psql -U gametech_user gametech_db` |

---

## Phase 0: Safety Net & Hardware Protection

### 1. Architectural Decisions
- **`ROUTER_DRY_RUN` Global Guard:**
  - Added environment setting `ROUTER_DRY_RUN = env.bool("ROUTER_DRY_RUN", default=("test" in sys.argv or any("pytest" in str(arg) for arg in sys.argv)))`.
  - When active, all RouterOS API connections (`network_manager.services.MikrotikAPI` and `network_manager.sync_services.MikrotikAPI`) are intercepted at the connection pool level.
  - A dedicated mock engine (`network_manager/services/dry_run.py`) provides an in-memory store simulating `/ppp/secret`, `/ppp/active`, `/ppp/profile`, `/system/resource`, and `/interface/ethernet`.
  - Guarantees 0 network packets leave the server destined for physical MikroTik routers during tests, staging, or dev workflows.
- **Automated Test Suite Structure:**
  - Established formal Django test runner suite under `billing/tests/`:
    - `test_router_dry_run.py`: Verifies dry run interception, mock user queries, comment updates, and kick actions.
    - `test_baseline.py`: Verifies database model integrity, authentication enforcement, and major dashboard rendering.
- **Safe Test Data Seeding & Cleanup:**
  - Added `python manage.py seed_dispatch_test_data` with `--cleanup` flag.
  - Test records are clearly tagged with `[TEST-DATA]` and `test_dispatch_` prefixes, allowing 1-step idempotent teardown without affecting real billing entities.

### 2. Forensic Audit: Parts of the Application Touching Routers
The codebase interacts with live MikroTik routers across the following functional areas:
1. **Billing & Payment Renewal (`billing/views/payments/transactions.py`):**
   - Enables PPPoE user (`api.enable_pppoe_user`)
   - Updates speed profile (`api.set_user_pppoe_profile`)
   - Disconnects active session to force profile renegotiation (`api.kick_active_user`)
2. **Customer Lifecycle Actions (`billing/views/customers/actions.py` & `list.py`):**
   - Auto-cutoff / suspend: disables PPPoE secret and kicks active session
   - Manual kick / disconnect session from profile view
   - Update PPPoE credentials and profile limits
3. **Background Tasks & Daemons (`billing/tasks.py`):**
   - `auto_suspend_task`: queries expired subscribers and disables RouterOS secrets
   - `auto_sync_failed_task`: retries failed router API sync operations
   - `auto_reconcile_routers_task`: validates database secrets vs router state
   - `fetch_live_monitoring_data_task`: polls router CPU, uptime, and interface traffic
4. **NOC & Live Monitoring APIs (`billing/views/api/network.py` & `dashboard.py`):**
   - Router uplink ping status dots (`/api/router-uplink-status/`)
   - Active PPPoE sessions list (`/api/active-pppoe-users/`)
   - SFP optical power level monitor (`api.get_optical_readings()`)
5. **Network Manager Sync Engine (`network_manager/views/sync.py` & `devices.py`):**
   - 2-way sync staging area (imports secrets/profiles from router into Django)
   - Winbox dashboard live resource monitor (`network_manager/views/winbox.py`)

---

## Phase 1: Security Hardening & Logins

### 1. Architectural Decisions
- **Customer Portal Password Hashing:**
  - Implemented `portal_password_hash` (`CharField(max_length=255)`) on `Customer` model via migration `0054_customer_portal_password_hash.py`.
  - Data migration hashes all existing plaintext passwords using Django's PBKDF2/SHA256 hasher and clears the legacy `portal_password` column.
  - Model helpers `set_portal_password(raw)` and `check_portal_password(raw)` enforce that cleartext passwords are never persisted.
- **Global Password Policy (`billing/validators.py`):**
  - Minimum 10 characters, at least 1 letter, 1 number, 1 special character (`!@#$%^&*()-_=+[]{}|;:,.<>?`).
  - Blacklist for common weak passwords.
  - Passwords cannot contain username, subscriber full name, or phone number.
  - Temporary passwords generated via `generate_temp_password(10)` with unambiguous characters (no `0/O`, `1/l/I`), forced first-login change, and 7-day expiration.
  - PPPoE modem passwords left stored as-is behind the existing eye toggle (to avoid disconnecting physical modems).
- **Authentication Hardening & Brute-Force Lockout (`billing/security.py`):**
  - Removed customer full-name login across all endpoints.
  - Removed login with PPPoE password. Subscribers authenticate strictly with PPPoE username or registered mobile + portal password.
  - 5 consecutive failed attempts locks account and IP for 15 minutes (900 seconds) via Redis/Django cache.
  - Throttled IP rate limiting via `LoginRateLimitMiddleware` (max 15 POST requests per minute on `/login/`, `/portal/login/`, and `/admin/login/`).
  - Failed attempts logged to `SystemLog`.
- **Customer Profile View ("Reset and resend"):**
  - Removed cleartext portal password display and copy button from `_info_cards.html`.
  - Replaced with secure "Reset and resend" button (`reset_customer_portal_password`). Generates a 10-char temporary password, hashes it, sets `must_change_password=True`, sends SMS via existing wrapper (masked in `SmsLog`), and displays the plaintext temporary password ONCE to staff on customer profile view.
- **Agent Temporary Credentials Protection:**
  - Agent temporary passwords removed from flash messages (`messages.success`) and system logs.
  - Rendered once in a dismissible confirmation banner on `view_agent.html` and cleared from session immediately upon viewing.
- **Semaphore SMS Configuration:**
  - Hardcoded API key extracted to `settings.SEMAPHORE_API_KEY` with environment variable override (`env("SEMAPHORE_API_KEY", default="...")`).
  - Added `settings.SEMAPHORE_SENDER_NAME`.
  - `send_semaphore_sms` refactored to read from settings and execute without blocking payments or workflows.
- **HTTPS & Domain Preparation:**
  - Made `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, and `SECURE_HSTS_SECONDS` environment-driven.
  - Created `docs/HTTPS_SETUP.md` with complete registrar, Certbot, Nginx reverse proxy, and Django production directives.

---

## Phase 2: Foundation (Models, Migrations & Permissions)

### 1. Architectural Decisions
- **Prospect & Onboarding Lifecycle:**
  - Added `Prospect` model in `billing/models.py` with full duplicate detection fields, agent linkages, review timestamps, decline reasons, and test flags.
  - Added `ChecklistConfirmation` model recording all 6 policy commitments (free install, plan rate, no lock-in, 60-day staggered lock, same-day repair, 24h+ outage rebates) along with policy snapshots and verification methods (`in_person`, `phone`, `chat`).
- **Permanent Agent Attribution & History:**
  - Added permanent `Customer.original_agent` (ForeignKey to `Agent`) preserving the originating sales agent forever.
  - Added `CustomerAgentHistory` tracking historical agent reassignments with mandatory staff reasons and actor audit trails.
- **Agent Referral Incentive & Payout Engine:**
  - Added `IncentiveSetting` (singleton) providing configurable incentive parameters (PHP 500.00/qualified customer, 5 customer payout batch size, 60-day staggered lock).
  - Added `AgentQualificationEvent` logging permanent qualification events upon 2nd month payment completion or cumulative payment thresholds, with payment rollback revocation support.
  - Added `AgentPayoutBatch` supporting batch creation in multiples of 5, reference numbers, and admin payment confirmation.
- **JobTicket Operational & QA Additions:**
  - Added `SITE_VISIT` ticket type to `TICKET_TYPE_CHOICES` and `APPROVED` status to `STATUS_CHOICES`.
  - Added field operational timers: `arrived_at`, `finished_at`, `technician_report`.
  - Added QA review fields: `qa_by`, `client_called_by_qa`, and `client_agent_informed` before closing.
  - Added same-person workflow detection: `same_person_flag` and `same_person_stages`.
  - Added `TicketBounceHistory` recording bounce reasons, stage transitions, bounce types (`revisit` vs `correct_report`), and actor logging.
  - Added `CallAttemptLog` tracking the 3-attempt unreachable contact workflow (`unanswered`, `rejected`, `busy`, `client_declined`, `other`).
- **Central Ticket Number Generator (`dispatch/utils.py`):**
  - Created `generate_ticket_number()` delivering sequential `GT-YYYYMMDD-XXXX` ticket numbers shared across staff and portal requests, leaving legacy ticket numbers untouched.
- **Customer Status Exclusions Audit:**
  - Added `closed_not_installed` status choice to `Customer.STATUS_CHOICES` and `Customer.INSTALLATION_STATUS_CHOICES`.
  - Audited and updated `billing/views/customers/list.py`, `billing/views/dashboard.py`, and `billing/management/commands/auto_suspend.py`.
  - Pending install and `closed_not_installed` customers are strictly excluded from billing overdue queries, router cutoff loops, and active dashboard KPI counters.
- **Named Permissions & RBAC Matrix (`setup_dispatch_permissions`):**
  - Registered 14 named permissions covering prospects, checklist execution, customer conversion, technician assignment, field job actions, timer corrections, dispatch QA, admin approval, bounce summaries, agent changes, and payout confirmation.
  - Seeded permission matrices across the 5 personas (`Agent`, `Technician`, `Dispatch`, `Staff`, `Admin`).
- **Small Ergonomic Fixes:**
  - Added `normalize_ph_phone(phone)` in `billing/validators.py` standardizing Philippine mobile numbers to `09XXXXXXXXX`.
  - Updated Leaflet map center defaults in `add_customer.html` and `edit_customer.html` to Cagayan de Oro (`8.4542, 124.6319`, zoom 13).
  - Unified customer ticket history technician attribution fallback to `Unassigned` across all templates and views.

---

---

## Phase 3: Onboarding Policy Checklist, Prospects Inbox & Mobile Agent Portal (COMPLETED & VERIFIED)
- **Pre-Migration Safety Backup:**
  - Droplet snapshot: `/root/backups/gametech_phase3_backup_20260924.sql` (272 KB).
- **Mandatory Pre-Installation Policy Checklist:**
  - Enforced server-side in `billing/views/customers/crud.py` for all new-install registrations (`installation_status='pending'`).
  - Requires all 6 policy checkboxes ticked: free standard install, agreed plan rate, no 24-month lock-in, 60-day staggered lock, same-day repair, 24h+ outage rebates.
  - Captures confirmed_by, verification method (`in_person`, `phone`, `chat`), and an immutable JSON policy snapshot.
  - Direct POSTs bypassing the checklist are strictly rejected with an explicit validation error.
- **Manual Override Exception ("Installed / Existing Subscriber"):**
  - Allows bypassing the checklist and install ticket creation ONLY when `installation_status='installed'`.
  - Requires `billing.create_customer` permission and explicitly logs an audit trail in `SystemLog` (`MANUAL_OVERRIDE_ADD`).
- **Atomic Creation & Idempotent Unassigned Dispatch Ticket:**
  - One atomic transaction creates `Customer` (`Pending Install`), records `ChecklistConfirmation`, converts `Prospect` if present, and triggers install job order creation.
  - Reused existing `auto_create_dispatch_ticket_on_pending_install` signal in `dispatch/signals.py`.
  - Job ticket is created as UNASSIGNED (`status='PENDING'`, `team=None`, `assigned_to=None`) in the Dispatch Queue; technicians cannot view it until Dispatch assigns it in Phase 4.
  - Idempotency guarantees exactly ONE install ticket per subscriber even if customer profile is re-saved.
- **Declines Handling:**
  - `ChecklistConfirmation` supports null prospect/customer with `applicant_name` and `applicant_phone` to record walk-in declines without creating phantom subscriber accounts.
  - Agent referral declines update `Prospect.status='declined'` with the recorded decline reason and display in real time on the agent's dashboard.
- **Mobile-First Agent Portal (No Admin Sidebar):**
  - Minimal mobile responsive layout (`base_agent.html`) with Gametech branding, no admin sidebars.
  - Referral intake form (`submit_prospect.html`) with Philippine mobile number normalization (`normalize_ph_phone`).
  - Referrals tracker (`dashboard.html`) showing real-time status badges, payment progress indicators, and Phase 5 incentive/payout placeholders.
  - Prospect editing (`edit_prospect.html`) allowing agents to update details until staff opens/reviews the lead.
  - Duplicate detection on submit and staff review against both existing customers and prospects.
  - Staff bell notification (`Notification` model) generated whenever an agent submits a new referral lead.
  - Restyled agent profile (`view_agent.html`) with "Add Customer to this Agent" CTA button.
- **Automated Test Suite:**
  - `billing.tests.test_phase3_onboarding`: 9 comprehensive automated tests (100% passing).
  - Full billing test suite: 36 tests (100% passing).

---

## Verification & Rollback Procedures

### One-Line Emergency Rollback Commands
- **Rollback Phase 3 (Return to Phase 2 baseline):**
  ```bash
  git checkout feature/dispatch-operation~3; cat /root/backups/gametech_phase3_backup_20260924.sql | ssh root@143.198.207.144 "docker exec -i 28514b2a5c9a psql -U gametech_user gametech_db"; ssh root@143.198.207.144 "docker restart gametech-billing-system-web-1"
  ```
- **Rollback Phase 2 (Return to Phase 1 baseline):**
  ```bash
  git checkout feature/dispatch-operation~4; cat /root/backups/gametech_phase2_backup_20260924.sql | ssh root@143.198.207.144 "docker exec -i 28514b2a5c9a psql -U gametech_user gametech_db"; ssh root@143.198.207.144 "docker restart gametech-billing-system-web-1"
  ```
- **Rollback Phase 1 (Return to Phase 0 baseline):**
  ```bash
  git checkout feature/dispatch-operation~5; cat /root/backups/gametech_phase1_backup_20260924.sql | ssh root@143.198.207.144 "docker exec -i 28514b2a5c9a psql -U gametech_user gametech_db"; ssh root@143.198.207.144 "docker restart gametech-billing-system-web-1"
  ```
- **Rollback Entire Feature (Return to main):**
  ```bash
  git checkout main; git pull origin main; cat /root/backups/gametech_phase0_backup_20260924.sql | ssh root@143.198.207.144 "docker exec -i 28514b2a5c9a psql -U gametech_user gametech_db"; ssh root@143.198.207.144 "docker restart gametech-billing-system-web-1"
  ```



