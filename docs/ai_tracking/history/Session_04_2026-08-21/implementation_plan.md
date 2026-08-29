# System Logic & Functional Audit Plan

Per your instructions, I have conducted a deep-dive audit of the backend code governing payments, synchronizations, expirations, and logging to ensure the system is completely foolproof.

## User Review Required

> [!IMPORTANT]
> I found a critical race condition in the auto-suspend logic and a missing global audit logger. Please review my proposed fixes below and approve them so we can make this system bulletproof.

## Open Questions

None. The issues discovered are purely backend logic bugs that need immediate fixing.

## Proposed Changes

### 1. Fix Critical Race Condition in Auto-Suspend
When the `auto_suspend.py` script runs at midnight, it communicates with the Mikrotik router to suspend expired accounts. If an account's MAC address is unknown, the system tries to dynamically learn it from the active session. 
**The Bug:** When it saves this new MAC address to the database, it accidentally triggers the "Re-sync to Mikrotik" background signal *before* the customer is actually marked as suspended. This causes the router to instantly re-enable the customer, fighting against the suspension script!
**The Fix:** 
#### [MODIFY] `network_manager/services.py`
- I will modify the database save method inside `suspend_pppoe_user` to use `.update(mac_address=...)` which safely bypasses the re-sync signal and prevents this race condition.

### 2. Global Audit Logging (The "Labtest" Fix)
You mentioned that changing a customer's name (like "labtest") or number didn't show up in the logs. Currently, the system only logs major events like Suspensions or Payments, but ignores manual profile edits.
**The Fix:**
#### [MODIFY] `billing/signals.py`
- I will implement a powerful `post_save` listener that automatically compares the old customer data against the new customer data every time a save happens. 
- If *anything* changes (Name, Phone, Plan, Status, Router, Expiration), it will automatically generate a highly detailed `SystemLog` entry (e.g., `"Changed Phone from 09123 to 09999", "Changed Plan from 10Mbps to 50Mbps"`). 
- This guarantees 100% accountability for the staff.

### 3. Cleanup Redundant Payment API Calls
**The Fix:**
#### [MODIFY] `customer_portal/views.py`
- The mock payment portal is currently double-sending upgrade commands to the Mikrotik router (once manually, and once via the automated signal). I will clean this up so it only sends the exact required commands, reducing router CPU load and speeding up payments.

## Verification Plan

### Automated/Manual Verification
- I will manually simulate a customer profile edit and verify that a detailed audit log appears in the database.
- I will verify the code syntax for the MAC address update fix to ensure it no longer triggers infinite loops.
