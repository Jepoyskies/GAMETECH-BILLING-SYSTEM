# Gametech Unli Fiber — Engineering Build Log & Decision Ledger

**Branch:** `feature/dispatch-operation`  
**Target Droplet:** `143.198.207.144` (DigitalOcean / Ubuntu / Docker Compose)  
**Postgres Database:** `gametech_db`  
**Redis Cache:** Redis 7 (Docker container `gametech-billing-system-redis-1`)

---

## Database Backups Ledger

| Phase | Timestamp | Backup Path | File Size | Description | Rollback Command |
|---|---|---|---|---|---|
| **Phase 0** | 2026-09-24 03:45 UTC | `/root/backups/gametech_phase0_backup_20260924.sql` | 231 KB | Pre-migration baseline backup before Dispatch Operation build | `cat /root/backups/gametech_phase0_backup_20260924.sql \| docker exec -i gametech-billing-system-db-1 psql -U gametech_user gametech_db` |

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

## Verification & Rollback Procedures

### One-Line Emergency Rollback Command
If any deployment needs to be completely undone:
```bash
git checkout main; git pull origin main; cat /root/backups/gametech_phase0_backup_20260924.sql | ssh root@143.198.207.144 "docker exec -i gametech-billing-system-db-1 psql -U gametech_user gametech_db"; ssh root@143.198.207.144 "docker restart gametech-billing-system-web-1"
```
