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
| **Phase 3.3** | 2026-09-24 09:30 UTC | `/root/backups/gametech_backup_phase3_3.sql` | 311 KB | Pre-migration backup before Phase 3.3 fixes and security validation | `cat /root/backups/gametech_backup_phase3_3.sql \| docker exec -i gametech-billing-system-db-1 psql -U gametech_user -d gametech_db` |
| **Phase 4A** | 2026-09-24 11:20 UTC | `/root/backups/gametech_backup_pre_phase4a.sql` | 311 KB | Pre-migration backup before Phase 4A Dispatch Queue & Mobile Tech migration 0012 | `cat /root/backups/gametech_backup_pre_phase4a.sql \| docker exec -i gametech-billing-system-db-1 psql -U gametech_user -d gametech_db` |
| **Phase 4B** | 2026-09-24 12:40 UTC | `/root/backups/gametech_backup_pre_phase4b.sql` | 313 KB | Pre-migration backup before Phase 4B Dispatch QA & Approval migration 0013 | `cat /root/backups/gametech_backup_pre_phase4b.sql \| docker exec -i gametech-billing-system-db-1 psql -U gametech_user -d gametech_db` |

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

---

## Phase 3.1: Strict Onboarding Refinement & Security Hardening (COMPLETED & VERIFIED)

### 1. Pre-Fix Safety Backup & Proven Rollback
- **Droplet Snapshot:** `/root/backups/gametech_phase3_1_backup_20260924.sql` (305 KB) created with `pg_dump --clean --if-exists`.
- **Restoration Proof:**
  - Created temporary database `scratch_test_db` on PostgreSQL container `28514b2a5c9a_gametech-billing-system-db-1`.
  - Restored `/root/backups/gametech_phase3_1_backup_20260924.sql` into `scratch_test_db`.
  - Audited all tables and row counts: 56 tables, 1,132 rows in `gametech_db` exactly matched 56 tables, 1,132 rows in `scratch_test_db` (0 mismatches).
  - Dropped `scratch_test_db`.
- **Verified Working Rollback Command:**
  ```bash
  ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git checkout 209fcb8 && docker exec -i 28514b2a5c9a_gametech-billing-system-db-1 psql -U gametech_user -d gametech_db < /root/backups/gametech_phase3_1_backup_20260924.sql && docker restart gametech-billing-system-web-1"
  ```

### 2. Exact Policy Wording & Versioned Admin Policy Setting
- **Model:** `ChecklistPolicySetting` (`billing/models.py`, migration `0057_phase3_1_updates.py`).
- **Policy Items:**
  1. Free installation
  2. Their plan: `{plan_name} (₱{price}/month)` (dynamically formatted from chosen plan)
  3. No lock-in period
  4. Staggered payments (3-day, 15-day payments):
     - For agent referrals: `Not available for 60 days from your first payment`
     - For walk-ins: `Available`
  5. Repair within the day
  6. Rebates within 24 hours
- **Removed Speculative Caveats:** Removed "24-month", "drop cable & ONU", "weather & fiber availability", and "outage".
- **Confirmation Methods:** Restricted strictly to `in_person` and `phone` only (`chat` completely eliminated).
- **Snapshot Storage:** `ChecklistConfirmation.policy_snapshot` stores the immutable version and rendered text presented to the subscriber.

### 3. Customer Creation Paths & Model Guard Audit
A comprehensive audit of every customer creation path across the repository was conducted:

| # | File & Line | Method / Context | Installation Status | Checklist Enforcement Mechanism |
|---|---|---|---|---|
| 1 | `billing/views/customers/crud.py:283` | `add_customer()` (Standard New Install) | `pending` | Server-side validation requiring all 6 checkboxes + model guard `customer._checklist_verified = True` |
| 2 | `billing/views/customers/crud.py:187` | `add_customer()` (Manual Override) | `installed` | Requires dedicated permission `billing.add_existing_subscriber`; logs `MANUAL_OVERRIDE_ADD` in `SystemLog` |
| 3 | `billing/admin.py:60` | `CustomerAdmin.save_model()` (Django Admin) | `installed` or `pending` | If `installed`: enforces `billing.add_existing_subscriber` + `MANUAL_OVERRIDE_ADMIN` log. If `pending`: enforced by model guard. |
| 4 | `network_manager/views/devices.py:382` | `sync_device_to_database()` | `installed` | Router import; existing active subscriber imported with `installation_status='installed'` |
| 5 | `network_manager/views/sync.py:145` | `apply_device_sync_staging()` | `installed` | Router bulk import; existing active subscriber imported with `installation_status='installed'` |
| 6 | `billing/management/commands/recover_from_mikrotik.py:75` | Router recovery script | `installed` | Disaster recovery of live subscribers from RouterOS; sets `installation_status='installed'` |
| 7 | `billing/management/commands/seed_dispatch_test_data.py:80` | Test data seeder | `pending` | Bypassed via model guard test flag `is_test_data=True` |

- **Shared Model-Level Guard (`Customer.save()` in `billing/models.py`):**
  Intercepts every customer creation and save. If `installation_status == 'pending'` or `status == 'pending'`, and not `is_test_data=True` and not `_checklist_verified=True`, it validates that an agreed `ChecklistConfirmation` exists. If not found, raises `django.core.exceptions.ValidationError`.

### 4. Dedicated Override Permission
- Dedicated permission `billing.add_existing_subscriber` created on `Customer.Meta.permissions`.
- Seeded into `Admin` role by default in `setup_dispatch_permissions`.
- Tested that staff with only normal `add_customer` permission are rejected with HTTP 403.

### 5. Agent Portal Privacy Enforcement
- In `billing/templates/billing/agent_portal/dashboard.html`, referral table displays strictly:
  1. Applicant / Customer Full Name
  2. Application Status Badge (`Submitted`, `Under Review`, `Checklist Completed`, `Installed`, `Declined`)
  3. Payment Progress Indicator
  4. Due Date
- **Strictly Removed:** Contact phone number, installation address, and customer contact details before and after conversion.

### 6. Duplicate Detection & Agent Reassignment Guard
- Centralized in `billing/validators.py`: `check_customer_or_prospect_duplicate()`.
- Detects matches on **phone** OR **normalized name + address** (case, space, and punctuation-insensitive) against both active customers and open prospects.
- **Credit Preservation:** First submitting agent retains full attribution credit. Second submission flags `duplicate_flag=True` and links `duplicate_of` to the first record.
- **Reassignment Guard:** In `billing/views/customers/crud.py` (`edit_customer`), changing a customer's assigned sales agent requires `billing.change_customer_agent` permission, a mandatory logged reason, and records permanent history in `CustomerAgentHistory`.

### 7. Prospect Single-Conversion & Decline Rules
- `prospect_id` conversion in `add_customer()` uses `select_for_update()` row locking. If already `converted`, second submission is rejected.
- Declined prospects cannot convert unless explicitly reopened by staff with `manage_prospects` permission via `prospect_reopen()` view with a logged reason in `SystemLog`.

### 8. Staff On Agent's Behalf
- "Add Customer to this Agent" CTA on `view_agent.html` triggers `staff_add_customer_for_agent()` view (`billing/views/agents.py`), creating a `Prospect(source='staff_on_behalf', status='under_review')` and redirecting to the checklist and customer creation flow.

### 9. Production State Audit (Report Only)
- `ROUTER_DRY_RUN`: Currently evaluates to `False` in running container (only defaults to `True` during tests).
- Active Git Commit: `209fcb8` on branch `feature/dispatch-operation`.
- Database Migrations: All migrations through `0056` applied (`[X]`). Migration `0057` staged.
- Router Live Behavior: If a MikroTik router device and PPPoE username are specified when creating a customer in the UI, `sync_customer_to_mikrotik` executes a live socket command.
- **Recommendation:** Keep `ROUTER_DRY_RUN=True` for test execution. On production, only execute router sync when physical routers are intended to be provisioned.

### 10. Developer Placeholders Removed
- Removed `[Phase 5 Placeholder: Live commission wallet]` and incentive placeholders from `billing/templates/billing/agent_portal/dashboard.html` and `billing/templates/billing/view_agent.html`.

---

## Phase 3.2: Router Safety Engine, Guard Loopholes & Rollback Verification

### 1. Router Safety Architecture (`ROUTER_MODE`)
- **Tri-State Modes:** `ROUTER_MODE = 'dry_run' | 'read_only' | 'live'`.
- **Enforcement Layer:** Single gateway inside `MikrotikBase._get_api()` (`network_manager/services/base.py`) and `SyncMikrotikAPI._get_api_connection()` (`network_manager/sync_services.py`).
- **Read-Only Interception:** `ReadOnlyApiWrapper` wraps RouterOS API client resources with `ReadOnlyResourceWrapper`. Allows safe read operations (`.get()`, `monitor-traffic`, `ping`, `print`). Intercepts and blocks all write operations (`.add()`, `.set()`, `.remove()`, custom modifying `.call()`).
- **Blocked Write Auditing:** Every blocked write logs warning to Python logger and records an entry in `SystemLog` (`table_name="MikrotikRouter"`, `action="BLOCKED_WRITE"`, `target_name="ROUTER_MODE=read_only"`).
- **Environment Persistence:** `ROUTER_MODE=read_only` configured in `docker-compose.yml` for `web`, `celery`, and `celery-beat` services; active in running container environment (`os.environ["ROUTER_MODE"] == "read_only"`) and persists across container restarts. Defaults to `dry_run` during automated tests.
- **Celery / Background Tasks & Views Audit:**
  - `auto_suspend_task` (hourly cron): queries expired subscribers and attempts cut-off; in `read_only`, all secret disable/disconnect commands are blocked.
  - `auto_reconcile_routers_task` (every 30 min): reconciles secrets; pushes/updates are blocked.
  - `fetch_live_monitoring_data_task` (every 10s): only executes traffic/resource reads (permitted in `read_only`).
  - `auto_sync_failed_task` (every 5 min): retries failed syncs; writes blocked.
  - **No Dual-System Collision:** The legacy WAMP billing system and Django system do not conflict or double-cut routers; all socket write attempts from Django are intercepted and rejected at the wrapper level.

### 2. Guard Loophole Closures
- **Model Bypasses Removed:** `is_test_data` and `_checklist_verified` flags completely removed as bypass mechanisms from `Customer.save()`.
- **Scoped Test Context Manager:** `test_seeding_bypass_checklist` (`billing/security.py`) enables test runners and seeder commands to bypass the checklist guard. Strictly fails with `PermissionError` when `settings.DEBUG=False` in production.
- **Audited Admin Bypass:** `permission_gated_customer_bypass` (`billing/security.py`) requires `billing.bypass_customer_checklist` permission or superuser; logs actor, reason, and timestamp to `SystemLog`.
- **Creation-Only Guard:** Enforced `Customer.save()` checklist check ONLY on record creation or when transitioning into `pending` installation status. Existing pending customers can be edited, updated by payments, and updated by dispatch signals without validation errors.
- **Router Sync & Recovery Protection:**
  - Added dedicated permission `billing.import_router_subscribers` to `Customer.Meta.permissions`.
  - Added `source` CharField (default `manual`) to `Customer` model (migration `0058_phase3_2_guards_and_source.py`).
  - Router imports (`sync_device_users`, `apply_device_sync_staging`, `recover_from_mikrotik`) tag imported subscribers with `source='router_sync'`, set `installation_status='installed'`, enforce permission check, prevent duplicate accounts by matching on `pppoe_username`, and write summary `SystemLog` entries with created/skipped counts.

### 3. Corrected Rollback Standard & Scratch Database Proof
- **Container Names from `docker compose ps`:**
  - `gametech-billing-system-web-1`
  - `gametech-billing-system-celery-1`
  - `gametech-billing-system-celery-beat-1`
  - `gametech-billing-system-db-1`
- **Verified Rollback Command to Phase 3.1 (commit `209fcb8`):**
  ```bash
  ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git checkout 209fcb8 && docker stop gametech-billing-system-web-1 gametech-billing-system-celery-1 gametech-billing-system-celery-beat-1 && docker exec -i gametech-billing-system-db-1 psql -U gametech_user -d gametech_db < /root/backups/gametech_phase3_1_backup_20260924.sql && docker start gametech-billing-system-web-1 gametech-billing-system-celery-1 gametech-billing-system-celery-beat-1"
  ```
- **Verified Rollback Command to Phase 3.2 (commit `4520af1`):**
  ```bash
  ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git checkout 4520af1 && docker stop gametech-billing-system-web-1 gametech-billing-system-celery-1 gametech-billing-system-celery-beat-1 && docker exec -i gametech-billing-system-db-1 psql -U gametech_user -d gametech_db < /root/backups/gametech_phase3_2_backup_20260924.sql && docker start gametech-billing-system-web-1 gametech-billing-system-celery-1 gametech-billing-system-celery-beat-1"
  ```
- **Restoration Proof:**
  - Created temporary database `scratch_restore_verify_db` on `gametech-billing-system-db-1`.
  - Restored `/root/backups/gametech_phase3_1_backup_20260924.sql` into `scratch_restore_verify_db`.
  - Audited table count: exactly 56 tables restored with 0 errors.
  - Successfully dropped `scratch_restore_verify_db`.
  - Created pre-cutover Phase 3.2 database backup `/root/backups/gametech_phase3_2_backup_20260924.sql` (277KB).

### 4. Test Suite Execution & Coverage Verification
All tests passing across small batches:
- `billing.tests.test_phase3_onboarding`: 18 tests (Pass)
- `billing.tests.test_phase3_2_guards`: 7 tests (Pass)
- `billing.tests` (`test_baseline`, `test_phase1_security`, `test_phase2_foundation`, `test_router_dry_run`): 27 tests (Pass)
- `network_manager.tests.test_router_modes`: 3 tests (Pass)
- **Total Suite:** 55 tests passing across all active modules.

---

## Phase 3.3: Security Hardening, Ticket Concurrency, Router Safety & Rollback Proof

### 1. Semaphore API Key Secret Sanitization & Audit
- **Default Hardcoding Removed:** In `gametech_core/settings.py`, `SEMAPHORE_API_KEY = env("SEMAPHORE_API_KEY", default="")`.
- **Graceful Failure & Logging:** In `billing/views/__init__.py` (`send_semaphore_sms`) and `billing/tasks.py`, if `SEMAPHORE_API_KEY` is empty, SMS sending gracefully returns `(None, False)` and logs warning: `"Semaphore SMS not configured: SEMAPHORE_API_KEY is empty"`.
- **Docker & Environment:** Updated `docker-compose.yml` to pass `SEMAPHORE_API_KEY=${SEMAPHORE_API_KEY:-}` to `web`, `celery`, and `celery-beat`. Added `.env.example`.
- **Droplet Environment:** Created `/root/GAMETECH-BILLING-SYSTEM/.env` on droplet with `SEMAPHORE_API_KEY=` placeholder for the rotated key.
- **Literal Secret Audit:** Full repository search performed. Literal tokens/keys found in settings, tasks, and scripts cataloged by filename and variable name without printing secret values.

### 2. Global Password Policy for All Logins & AUTH_PASSWORD_VALIDATORS
- **AUTH_PASSWORD_VALIDATORS Audit:** Confirmed definitively that prior to Phase 3.3, `AUTH_PASSWORD_VALIDATORS` only contained generic Django defaults (min_length=8, no special characters, no letter+digit+special char enforcement).
- **GametechPasswordPolicyValidator:** Implemented `GametechPasswordPolicyValidator` in `billing/validators.py` and configured in `AUTH_PASSWORD_VALIDATORS`:
  - 10+ characters minimum length
  - At least one letter, one number, and one special character (`!@#$%^&*()-_=+[]{}|;:,.<>?`)
  - Common weak password blacklist rejection
  - Disallow matching or containing username, phone number, first/last name
- **Staff, Technician & Admin Enforcement:** Called `validate_password_policy` in `billing/views/staff.py` (`add_staff` and `edit_staff`), `billing/views/auth.py` (`add_agent`).
- **Tests Added:** Automated test cases for staff, technician, admin, and `AUTH_PASSWORD_VALIDATORS` added to `billing/tests/test_phase1_security.py`.

### 3. Plaintext Password Fallback Removal
- **Production Audit:** Queried `Customer.objects.filter(portal_password__isnull=False).exclude(portal_password="").count()` on droplet PostgreSQL. Exact count: **0** plaintext passwords exist.
- **Fallback Removed:** In `billing/models.py:Customer.check_portal_password`, removed the `if self.portal_password:` plaintext check. Unhashed records strictly return `False` until hashed on save.
- **Test Updated:** `test_legacy_plaintext_migration_and_fallback` in `billing/tests/test_phase1_security.py` updated to verify that unmigrated records return `False` until auto-hashed on save.

### 4. Concurrency-Safe Ticket Number Generation
- **Retry Mechanism:** In `dispatch/utils.py:generate_ticket_number`, wrapped sequence generation in atomic transaction with bounded retries (`max_attempts=5`) catching `IntegrityError`.
- **Model Save Protection:** In `dispatch/models.py:JobTicket.save`, wrapped creation in savepoint retry loop catching `IntegrityError`, regenerating `ticket_number` on collision.
- **Concurrency Test:** Added `dispatch/tests/test_ticket_concurrency.py` with multi-threaded `TransactionTestCase` spawning 10 simultaneous threads. All 10 tickets successfully created with zero duplicate numbers and zero `IntegrityError` exceptions.

### 5. Blocked Router Writes State Sync Audit & Fixes
- **Audit of 4 Places:**
  1. `auto_suspend` (`billing/management/commands/auto_suspend.py`): Previously, `mt.suspend_pppoe_user` returned `True` in read_only mode, causing DB to mark `customer.status = "suspended"`. Fixed: checks `mt.is_read_only`; leaves `customer.status` unchanged and marks `customer.sync_status = "Blocked"`.
  2. `auto_reconcile` (`billing/management/commands/auto_reconcile_routers.py`): Previously failed push/update left status unchanged. Fixed: on blocked read-only response, marks `customer.sync_status = "Blocked"`.
  3. `auto_sync_failed` (`billing/management/commands/auto_sync_failed.py` & `billing/signals.py`): Previously `post_save` signal marked `sync_status = "Synced"`. Fixed: `billing/signals.py` checks `api.is_read_only`; skips router writes and sets `sync_status = "Blocked"`.
  4. `payment/renewal` (`billing/views/payments/transactions.py`): Previously set `customer.status = "active"` even when router enable write was blocked. Fixed: if customer was suspended and `api.is_read_only`, customer remains `status = "suspended"` and `sync_status = "Blocked"`, preserving payments while not marking router-dependent state changes as done.
- **Model Choice:** Added `Blocked` to `Customer.SYNC_CHOICES`.
- **Tests Added:** Added comprehensive tests in `billing/tests/test_router_dry_run.py` verifying status preservation in `read_only` and preserving existing behavior in `dry_run`.

### 6. Rollback Command & Scratch Database Verification
- **Current Droplet Backup:** Created clean pg_dump: `/root/backups/gametech_backup_phase3_3.sql` (311KB).
- **Restoration Proof:**
  - Created temporary database `gametech_scratch` on `gametech-billing-system-db-1`.
  - Restored `/root/backups/gametech_backup_phase3_3.sql` into `gametech_scratch`.
  - Audited table count: exactly **57 tables** in `gametech_db` vs **57 tables** in `gametech_scratch` (100% match).
  - Audited total row count: exactly **1,163 rows** in `gametech_db` vs **1,163 rows** in `gametech_scratch` (100% match).
  - Dropped `gametech_scratch`.
- **Exact Rollback Command (Returning to pre-Phase 3.3 commit `445cb94`):**
  ```bash
  ssh root@143.198.207.144 "docker stop gametech-billing-system-web-1 gametech-billing-system-celery-1 gametech-billing-system-celery-beat-1 && cd /root/GAMETECH-BILLING-SYSTEM && git checkout 445cb94 && docker exec -i gametech-billing-system-db-1 psql -U gametech_user -d gametech_db < /root/backups/gametech_backup_phase3_3.sql && docker start gametech-billing-system-web-1 gametech-billing-system-celery-1 gametech-billing-system-celery-beat-1"
  ```

### 7. Customer Portal Security Tests & Active Protection Confirmation
- **Portal Security Test Suite (`customer_portal/tests/test_portal_security.py`):**
  1. `test_login_by_phone`: Authenticates successfully with 11-digit local mobile numbers (`0917...`) and international formats (`+63...`), establishing portal session and redirecting to portal dashboard.
  2. `test_login_lockout_after_failed_attempts`: 5 consecutive failed login attempts trigger an immediate 15-minute account and IP lockout; subsequent attempts return `"Too many failed login attempts"` and reject authentication.
  3. `test_forced_password_change_with_policy`: Directs `must_change_password=True` accounts to `/portal/force-change-password/`, validates `GametechPasswordPolicyValidator` (rejects short, common, or username-containing passwords), and updates credentials upon providing compliant password.
  4. `test_temporary_password_expiry`: Accounts with temporary passwords older than 7 days (`is_temp_password_expired() == True`) are rejected upon login attempt with an expiry notice.
  5. `test_reset_and_resend_never_logs_plaintext`: Staff reset action dispatches SMS with `[REDACTED]` masked body into `SmsLog`, logs audit event in `SystemLog` with no plaintext credentials, and never exposes plaintext password in application logs.
- **Active Protection Confirmation in Running Application:**
  - **IP Rate Limiting:**
    - Active Middleware: `billing.middleware.LoginRateLimitMiddleware` (configured in `gametech_core/settings.py:MIDDLEWARE`).
    - Monitored Paths: `RATE_LIMITED_PATHS = ("/login/", "/portal/login/", "/admin/login/", "/admin/")`.
    - Thresholds: **15 requests per 60 seconds** per client IP. Returns HTTP 429 with `Retry-After` header.
  - **Account / IP Brute-Force Lockout:**
    - Active Engine: `billing.security.is_account_or_ip_locked` and `billing.security.record_login_failure`.
    - Integrated Endpoints: `billing.views.auth.login_view` (`/login/`), `customer_portal.views.auth.portal_login` (`/portal/login/`).
    - Thresholds: **5 consecutive failed attempts** triggers **900 seconds (15 minutes)** lockout across account and IP. Automatically creates `SystemLog` entry with `action="ACCOUNT_LOCKED"`.

### Final Phase 3.3 Small-Batch Test Run Verification
- Batch 1 (`billing.tests.test_phase1_security`): 11 tests (Pass)
- Batch 2 (`billing.tests.test_router_dry_run`): 10 tests (Pass)
- Batch 3 (`dispatch.tests.test_ticket_concurrency`): 2 tests (Pass)
- Batch 4 (`customer_portal.tests.test_portal_security`): 5 tests (Pass)
- Batch 5 (`billing.tests.test_phase3_onboarding`): 18 tests (Pass)
- Batch 6 (`billing.tests.test_phase3_2_guards`): 7 tests (Pass)
- Batch 7 (`billing.tests.test_baseline`): 3 tests (Pass)
- Batch 8 (`billing.tests.test_phase2_foundation`): 9 tests (Pass)
- Batch 9 (`network_manager.tests.test_router_modes`): 3 tests (Pass)
- **Total Phase 3.3 Verified Test Suite:** **68 tests, 0 failures, 0 errors** across all active modules.

---

## Phase 4A: Dispatch Operations & Mobile Technician Workflows

### 1. Architectural Decisions & Scope
- **Pre-Migration Safety Backup:**
  - Dumped PostgreSQL database prior to running migration `0012`: `/root/backups/gametech_backup_pre_phase4a.sql` (311 KB).
  - Droplet migration `dispatch.0012_jobticket_arrival_coords_timer_correction` successfully applied.
- **Retirement of Draft Stage 1/2/3 Pages:**
  - Audited codebase and removed unlinked legacy draft files:
    - `dispatch/templates/dispatch/pipeline/1_verification.html`
    - `dispatch/templates/dispatch/pipeline/2_assignment.html`
    - `dispatch/templates/dispatch/pipeline/3_tech_mobile.html`
  - Added URL alias redirects for `dispatch_verification` and `dispatch_assignment` directing to `dispatch_queue`.
  - Updated sidebar navigation (`billing/templates/billing/base/_sidebar.html`), QA (`4_qa.html`), and approval (`5_approval.html`) templates to point to `dispatch_queue` and `technician_mobile_ui`.
- **Unified Dispatch Queue Architecture (`dispatch/views_queue.py` & `queue.html`):**
  - Tickets arrive initially with status `UNASSIGNED` (or `PENDING` mapped into unassigned view).
  - Sub-views/tabs: All, Unassigned, Assigned, In Progress, Review/QA, Completed, Returned/Cancelled.
  - Metrics cards: Unassigned count, Dispatched count, In-Progress count, On-Duty technician count.
  - Implemented modular partials: `_queue_assign_modal.html`, `_queue_timer_modal.html`, `_technician_duty_bar.html`, and `_queue_ticket_row.html`.
- **Team-Based Assignment Picker & Off-Duty Technician Toggle:**
  - Assignment modal supports assigning to individual technicians or entire teams in one atomic action.
  - Off-duty technician toggle (`api_toggle_technician_duty` on `/dispatch/api/technicians/<tech_id>/toggle-duty/`): updates `technician.is_available`.
  - Off-duty technicians are strictly excluded from assignment picker dropdowns.
- **Technician Mobile-First Job View (`dispatch/views_tech.py` & `tech_mobile.html`):**
  - Technicians see **ONLY** jobs assigned to them (`technicians=tech`, status in `ASSIGNED`, `IN_PROGRESS`).
  - Technicians cannot see unassigned jobs and cannot self-assign jobs (enforced at both UI and API level with HTTP 403 Forbidden).
  - **Arrived Action (`api_ticket_arrived`):**
    - Transitions ticket `ASSIGNED` -> `IN_PROGRESS`.
    - Starts the timer: records `arrived_at = timezone.now()` and `time_start`.
    - Captures optional GPS coordinates (`arrival_latitude`, `arrival_longitude`) if provided by the device browser.
  - **Done Action (`api_ticket_done`):**
    - Stops the timer: records `finished_at = timezone.now()`, `time_accomplish`, and calculates duration in minutes.
    - Saves technician completion report (`technician_report`).
    - Standard installs/repairs transition to `PENDING_REVIEW` for QA dispatcher sign-off.
    - `SITE_VISIT` tickets flow directly from `ASSIGNED` -> `IN_PROGRESS` -> `COMPLETED`, skipping QA.
    - Dispatches in-app notification to staff: `Technician Completed Job: <ticket_number>`.
  - **Contact Attempt Logging & 3-Attempt Rule (`api_log_call_attempt` & `api_return_to_dispatch`):**
    - Technicians log contact attempts with outcome (`unanswered`, `busy`, `out_of_coverage`, `client_declined`, `wrong_number`).
    - Attempt entries persisted to `CallAttemptLog`.
    - Return to Dispatch button unlocks strictly after 3 logged attempts or client refusal.
    - Returning to Dispatch transitions ticket to `CANCELLED`, records cancellation reason, sets customer `installation_status='closed_not_installed'`, records audit history, and dispatches notification to staff.
- **Dispatcher Timer Correction (`api_correct_timer`):**
  - Dispatchers / staff can manually correct forgotten arrival or completion timestamps via modal.
  - Requires a mandatory explanation (`reason`), recorded in `timer_correction_reason`, `timer_corrected_at`, and `timer_corrected_by`.
  - Recalculates job duration in minutes.
- **Audit Logging & State Transition Guard:**
  - `JobTicket.can_transition_to(target_status)` validates state machine constraints.
  - Every transition creates a `JobTicketHistory` entry and logs to `SystemLog`/`AuditLog`.

### 2. Automated Test Suite (`dispatch/tests/test_dispatch_operations.py`)
- Created comprehensive test suite under `dispatch/tests/`:
  1. `test_allowed_and_forbidden_state_transitions`: Validates forward flow (`UNASSIGNED` -> `ASSIGNED` -> `IN_PROGRESS` -> `PENDING_REVIEW`) and rejects invalid leaps (`UNASSIGNED` -> `COMPLETED`).
  2. `test_technicians_cannot_see_or_accept_unassigned_jobs`: Validates technician sees only assigned jobs, receives HTTP 403 when attempting to assign unassigned tickets.
  3. `test_off_duty_technicians_not_offered`: Verifies off-duty technicians are filtered out of the assignment modal list.
  4. `test_arrived_starts_timer_and_records_optional_gps`: Verifies arrival timestamp initiation and optional latitude/longitude storage.
  5. `test_done_stops_timer_and_saves_report`: Verifies completion timestamp, duration calculation, and report storage.
  6. `test_timer_correction_with_logged_reason`: Verifies dispatcher timer adjustment requires a non-empty reason and updates audit metadata.
  7. `test_3_contact_attempt_rule_and_return_to_dispatch`: Verifies that return to dispatch is blocked before 3 attempts, unlocked after 3 attempts or client refusal, sets customer to `closed_not_installed`, and dispatches notification to staff.
- **All 7 tests passed (0 failures, 0 errors).**
- **Existing Regression Batches (Phase 1 Security, Portal Security, Router Dry Run, Concurrency) all passed (0 failures, 0 errors).**

---

## Phase 4B: Dispatch QA, Admin Final Approval, Bounce-Back History, & Customer Lifecycle Integration

### 1. Architectural Decisions & Implementation Details
- **Pre-Migration Safety Backup:**
  - Dumped PostgreSQL database prior to running migration `0013`: `/root/backups/gametech_backup_pre_phase4b.sql` (313 KB).
  - Droplet migration `dispatch.0013_jobticket_is_flagged_and_more` successfully applied.
- **Dispatch QA Screen (`dispatch/views_approval.py` & `pipeline/4_qa.html`):**
  - Allows Dispatch/QA staff to review technician time logs (arrival, accomplishment, duration), job dates, and customer/technician reported problems.
  - **Client Verification Guard:** Passing QA strictly requires confirming that the client was called (`client_called_by_qa` checkbox). If unchecked, submission is rejected with HTTP 400.
  - **QA Pass Flow:**
    - Standard installs transition to `QA_PASSED` for final Admin sign-off.
    - Repairs evaluate the **Repair Bypass Rule**: if clean (`bounce_count < 2`, not `repeated_bounce_alert`, not `is_flagged`, not `same_person_flag`), repairs bypass Admin approval and transition immediately to `APPROVED`.
    - If a repair has bounced 2+ times or is flagged, it forwards to `QA_PASSED` requiring Admin sign-off.
  - **QA Bounce Flow (`api_qa_review`):**
    - Technicians receive bounced jobs with a mandatory explanation (`reason`).
    - Two bounce types supported:
      1. `correct_report`: Report correction needed without physical revisit. Ticket returns to `IN_PROGRESS` while keeping the original job timer.
      2. `revisit`: Physical site revisit required (e.g., optical loss issue, high attenuation). Ticket returns to `ASSIGNED` and timer is reset for a fresh site visit timer.
    - Every bounce creates an immutable `TicketBounceHistory` audit record with timestamps, bounced by, and reason.
- **Admin Approval Screen (`dispatch/views_approval.py` & `pipeline/5_approval.html`):**
  - Restricted strictly to staff/superusers with administrative permissions.
  - **Approve Action (`api_admin_approve`):**
    - Transitions ticket to `APPROVED`, records `admin_approved_by` and `admin_approved_at`.
    - Activates customer subscription (`status='active'`, `installation_status='installed'`).
    - Logs event to `SystemLog`.
  - **Bounce to Dispatch Action (`api_admin_approve`):**
    - Requires mandatory reason.
    - Transitions ticket from `QA_PASSED` back to `COMPLETED` (returns to QA review queue).
    - Increments `bounce_count`, logs `TicketBounceHistory` with `bounce_type='admin_to_dispatch'`.
- **Alert After 2 Bounces on the Same Job:**
  - Whenever `ticket.bounce_count >= 2`, system automatically sets `ticket.repeated_bounce_alert = True`.
  - Dispatches immediate staff notification (`🚨 Repeated Bounce Alert: Job Ticket <ticket_number> has bounced <N> times`).
  - Highlights ticket with persistent alert badge across Queue, QA, and Approval dashboards.
- **Admin Summary Analytics Page (`dispatch/views_approval.py` & `admin_summary.html`):**
  - Aggregates operational bounce patterns:
    - Bounces grouped by user (technician / dispatcher), stage (QA vs Admin), and reason.
    - Same-person audit flags (`same_person_flag = True` when the technician and QA reviewer share the same identity or credentials).
    - Unreachable client returns shown strictly separately in an isolated table from quality/technical bounces.
- **Unreachable Client Close & Reopen Lifecycle (`api_close_unreachable` & `api_reopen_onboarding`):**
  - Close flow handles unreachable subscribers with standardized reasons (`no_contact`, `change_of_mind`, `undecided`, `other`).
  - Mandatory confirmation that both client and agent were informed (`client_agent_informed` tick).
  - Sets customer lifecycle state to `Closed - Not Installed` (`installation_status='closed_not_installed'`).
  - Reopen flow (`api_reopen_onboarding`): Resets customer to `pending_installation` and returns redirect URL directly to onboarding checklist to issue a new job order.
- **Customer View Six-Step Lifecycle Tracker Integration (`billing/views/customers/crud.py` & `_lifecycle_tracker.html`):**
  - Updated tracker to dynamically reflect real job ticket statuses:
    1. Application -> 2. Document Verification -> 3. Schedule Dispatch -> 4. Field Installation / In Progress -> 5. QA Review & Testing -> 6. Activated / Live.
  - Displays dynamic badges for `In-Progress`, `QA Review`, `Repeated Bounce Alert`, `Audit Flag`, and `Closed - Not Installed`.
- **Request Service Modal Unification (`_modal_customer_repair.html` & `dispatch/views.py`):**
  - Updated Request Service modal on Customer View with choices for `INSTALLATION`, `REPAIR`, and `SITE_VISIT`.
  - Submissions enter the unified dispatch queue directly with `status='PENDING'` and source tab routing.

### 2. Automated Test Suite (`dispatch/tests/test_phase4b_operations.py`)
- Created comprehensive test suite under `dispatch/tests/test_phase4b_operations.py`:
  1. `test_qa_screen_pass_requires_client_called_confirmation`: Validates that passing QA strictly requires confirming the client was called; rejects uncalled submissions with HTTP 400.
  2. `test_qa_bounce_to_technician_requires_reason_and_type`: Validates required bounce reason and correct handling of `revisit` (resets timer, status `ASSIGNED`) vs `correct_report` (preserves timer, status `IN_PROGRESS`).
  3. `test_alert_after_2_bounces_on_same_job`: Validates that bouncing a job ticket twice sets `repeated_bounce_alert = True`.
  4. `test_repairs_skip_admin_approval_unless_bounced_twice_or_flagged`: Validates that clean repairs transition directly from QA to `APPROVED`, while repairs with 2+ bounces or `is_flagged=True` transition to `QA_PASSED` requiring Admin approval.
  5. `test_admin_approval_screen_and_bounce_to_dispatch`: Validates Admin approval activates customer, and Admin bounce to dispatch requires a reason and creates audit history.
  6. `test_close_unreachable_flow_and_reopen_onboarding`: Validates that closing an unreachable subscriber requires the `client_agent_informed` tick, sets customer to `Closed - Not Installed`, and reopening resets to `pending_installation` with checklist redirect.
  7. `test_request_service_modal_site_visit_enters_queue`: Validates that creating a `SITE_VISIT` via Request Service modal enters the unified queue as `PENDING` under `CLIENT_CONCERNS`.
- **All 7 Phase 4B tests passed (0 failures, 0 errors in 24.1s).**
- **All Regression Test Batches passed (0 failures, 0 errors):**
  - `dispatch.tests.test_dispatch_operations` & `dispatch.tests.test_ticket_concurrency`: 9 tests passed.
  - `billing.tests.test_phase1_security` & `customer_portal.tests.test_portal_security`: 16 tests passed.
  - `billing.tests.test_router_dry_run`: 10 tests passed (`ROUTER_MODE=read_only` confirmed active and blocking writes).




