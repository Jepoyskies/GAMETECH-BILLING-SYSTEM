# 🚀 Goal Description

Currently, the billing system relies on Django signals and manual button clicks in the "Sync Manager" to keep Mikrotik routers updated. While I have hardened the individual API calls (fixing the silent crashes and newline bugs), the architecture itself is still vulnerable to "drifting" (e.g., someone manually edits a user via Winbox, a temporary network outage drops a signal, etc.). 

To stop the tiring process of "coming back to fix and figure it out," I propose building a **Full Auto-Reconciliation System**. This will act as an automated background guard dog that constantly compares the Django database with every Mikrotik router and automatically fixes any discrepancies.

## ⚠️ User Review Required

Please review the proposed rules for the Auto-Reconciler below. Are you okay with Django being the **absolute Source of Truth**? This means if someone manually changes a profile or password on the router via Winbox, the auto-reconciler will overwrite it back to match what is in the Django dashboard.

## ❓ Open Questions

1. **Orphans (Mikrotik -> Django):** If the auto-reconciler finds a user on the router that *doesn't exist* in Django, what should it do? 
   - *Option A:* Automatically import them into Django.
   - *Option B:* Delete them from the router.
   - *Option C:* Do nothing, just leave them as "Unknown" in the Sync Manager for you to handle manually.
   *(I recommend Option C to prevent accidental deletions or messy imports).*

2. **Schedule:** How often do you want this background reconciliation to run? (e.g., every 30 minutes, every hour, once a day?)

## 🛠️ Proposed Changes

### Core Sync Logic Hardening
I will create a unified, bulletproof sync utility that shares the same sanitization logic (stripping newlines from addresses, handling API quirks) so that the background task, the signals, and the UI buttons all share the same safe code.

#### [MODIFY] `network_manager/sync_services.py`
- Add strict newline scrubbing to comments.
- Share logic with `billing/signals.py`.

### The Auto-Reconciler Task
#### [NEW] `billing/management/commands/auto_reconcile_routers.py`
Create a management command that performs a full 2-way diff:
1. Connects to each router.
2. Downloads all PPPoE secrets.
3. Compares with Django Customers assigned to that router.
4. **Pushes** missing Django customers to the router.
5. **Updates** customers on the router whose profiles/passwords don't match Django.

#### [MODIFY] `gametech_core/settings.py`
- Register `auto_reconcile_routers` in Celery Beat to run automatically at your preferred interval (e.g., every 30 mins).

## ✅ Verification Plan

### Automated Tests
- Trigger the command via `python manage.py auto_reconcile_routers` in the terminal.
- Verify the terminal logs show it detecting and fixing missing/mismatched profiles on Mikrotik A.

### Manual Verification
- We will intentionally change a password in Winbox on `lab_test`, run the auto-reconciler, and verify it automatically changes it back to match the Django dashboard.
