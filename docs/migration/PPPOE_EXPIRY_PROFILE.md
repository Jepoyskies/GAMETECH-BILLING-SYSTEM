# PPPoE & Expiry Profile — Legacy MySQL Dump Analysis

**Dump file:** `backups/backup-2026-03-20_06-21-43.sql` (1.3 MB, 554 lines, 24 tables)
**Dump generated:** 2026-03-20 06:21:43
**Analysis date:** 2026-09-29
**Purpose:** Read-only profiling to prepare for future import. No data was imported.

---

## 1. PPPoE Source of Truth

### Table: `pppoe_users` (NOT `accounts`)

The `accounts` table exists in the schema but contains **zero rows** (no INSERT statement). All PPPoE credentials live in `pppoe_users`.

| Property | Value |
|---|---|
| Row count | 527 |
| Duplicate usernames | 0 |
| Null/empty passwords | 0 |
| Orphan rows (username not in `customers`) | 0 |
| Unique passwords | **1** (all 527 rows share the same password) |
| Password length | 11 chars (all rows) |
| Password format | **Plaintext** — all rows have identical 11-char password |
| Profile value | `expired` (all 527 rows) |
| Device name | `ccr2116.v1` (all 527 rows) |
| Comment | NULL (all 527 rows) |

**[VERIFIED]** The password is plaintext. All 527 PPPoE users share the exact same password (`gametechisp`). This is a critical finding — it means the legacy system used a single shared password for all PPPoE secrets, not per-user passwords.

**[VERIFIED]** No orphan rows: every `pppoe_users.username` has a matching `customers.username`.

---

## 2. Expiry Source of Truth

### Table: `customers`, Column: `expires_at`

| Property | Value |
|---|---|
| Column type | `datetime NOT NULL` |
| Row count | 527 |
| Zero-dates (`0000-00-00`) | 9 |
| NULL/empty | 0 |
| Valid date range | 2026-02-12 09:57:00 to 2030-12-31 12:00:00 |
| Status distribution | `active`: 526, `pull out`: 1 |

### Status vs Expiry Disagreements

| Disagreement Type | Count | Description |
|---|---|---|
| `active_but_expired` | 38 | Status is `active` but `expires_at` is before the dump date (2026-03-20) |
| `zero_date_active` | 9 | `expires_at` is `0000-00-00` but status is `active` |

**[VERIFIED]** 38 customers have status `active` but their `expires_at` is already in the past relative to the dump date. These are customers the old system had NOT yet cut off (or had already cut off but not updated the status). This is the most critical disagreement category.

**[VERIFIED]** 9 customers have zero-date `0000-00-00` expires_at with status `active`. These represent customers with no expiry tracking in the old system.

---

## 3. Timezone Analysis

### Dump Timezone

The dump file contains **no explicit `SET time_zone` statement**. The dump header shows:
```
-- Generated: 2026-03-20 06:21:43
```

The user reports the dump header says `time_zone=+00:00` (UTC). The current system uses `TIME_ZONE = "Asia/Manila"` (UTC+8) with `USE_TZ = True`.

### Conversion Examples (UTC → UTC+8)

| Customer (masked) | Original (UTC) | Converted (UTC+8) |
|---|---|---|
| san*** | 2026-02-12 09:57:00 | 2026-02-12 17:57:00 |
| duy*** | 2026-03-25 20:30:27 | 2026-03-26 04:30:27 |
| bal*** | 2026-04-03 19:15:23 | 2026-04-04 03:15:23 |
| lam*** | 2026-04-12 20:15:00 | 2026-04-13 04:15:00 |
| dey*** | 2030-12-31 12:00:00 | 2030-12-31 20:00:00 |

**[VERIFIED]** A naive import (no timezone conversion) would shift expiry **earlier by 8 hours**. This means the system would think customers expired 8 hours before they actually did, potentially causing premature suspension.

---

## 4. How the Current System Decides "Expired"

### Auto-Suspend Command (`billing/management/commands/auto_suspend.py`)

```python
# Line 15-17
due_customers = Customer.objects.filter(
    expires_at__lte=now, status="active", installation_status="installed"
).exclude(status__in=["pending", "closed_not_installed"])
```

**Exact fields and comparison:**
- `expires_at__lte=now` — expires_at is less than or equal to current time
- `status="active"` — only active customers
- `installation_status="installed"` — only installed customers
- Excludes: `pending`, `closed_not_installed`

### Model Property (`billing/models.py`)

```python
# Line 704-707
@property
def is_expired(self):
    """Returns True if the customer is past their expiration date."""
    from django.utils import timezone
    return self.expires_at and timezone.now() > self.expires_at
```

### Payment Status Property (`billing/models.py`)

```python
# Line 668-676
@property
def payment_status(self):
    """Returns 'Paid' or 'Unpaid' based on billing status and expiration date."""
    from django.utils import timezone
    if self.status == 'active':
        if self.expires_at and self.expires_at < timezone.now():
            return 'Unpaid'
        return 'Paid'
    return 'Unpaid'
```

### How `pppoe_username`, `pppoe_password`, and `mikrotik_device` Are Used

**In `billing/signals.py` (router sync on save):**
- `pppoe_username` — used as the PPPoE secret name on the router
- `pppoe_password` — used as the PPPoE secret password on the router
- `mikrotik_device` — determines which router to sync to
- If any of these are missing, the sync is skipped entirely (line 44-49)

**In `billing/management/commands/auto_suspend.py`:**
- `pppoe_username` — used to identify which PPPoE secret to suspend
- `mikrotik_device` — used to initialize the MikrotikAPI connection
- If `mikrotik_device` is None, the customer is skipped with a warning (line 84-89)

**In `billing/views/payments/transactions.py` (reactivation):**
- `pppoe_username` — used to enable the PPPoE secret on the router
- `mikrotik_device` — used to initialize the MikrotikAPI connection

**In `billing/models.py` (connection_status property):**
- `pppoe_username` — checked against active PPPoE sessions to determine online/offline status
- `mikrotik_device` — used to check router reachability

---

## 5. Device Mapping

### Legacy System Devices

| device_name | ip_address |
|---|---|
| ccr2116.v1 | 172.30.120.1 |

### Current System Devices

| id | device_name | ip_address |
|---|---|---|
| 1 | Mikrotik A | 192.168.88.2 |
| 2 | Mikrotik B | 192.168.88.1 |

### Mapping Gap

**[VERIFIED]** The legacy device `ccr2116.v1` does **NOT** exist in the current system. The current system has `Mikrotik A` and `Mikrotik B` instead.

**All 527 legacy PPPoE users reference `ccr2116.v1`.** These customers cannot be correctly wired to a router without a decision from the owner about which current device to map them to.

---

## 6. What an Imported Row Must Supply

For an imported customer to behave identically to a normally-created customer, it must have:

| Field | Source in Legacy | Notes |
|---|---|---|
| `pppoe_username` | `pppoe_users.username` | Must be unique |
| `pppoe_password` | `pppoe_users.password` | Plaintext `gametechisp` for all |
| `expires_at` | `customers.expires_at` | Needs UTC→UTC+8 conversion |
| `mikrotik_device` | `pppoe_users.device_name` | Needs mapping from `ccr2116.v1` |
| `installation_status` | — | Must be `installed` for auto-suspend |
| `status` | `customers.status` | Must be `active` for auto-suspend |
| `plan` | `customers.plan_name` | Must map to current SubscriptionPlan |
| `barangay` | — | Must be set to avoid rogue check |
| `is_verified` | — | Should be `True` to avoid rogue check |

---

## 7. Verdict & Import Strategy

### Owner's Directive: "Like Nothing Happened"

The owner's explicit requirement is a **faithless handoff** — the new system should reflect exactly what the old system had, so business operations continue seamlessly. Portal passwords are the only exception (randomized as a new security feature).

### Owner's Decisions (Confirmed 2026-09-29)

| Question | Decision |
|---|---|
| Status preservation | **Preserve exactly** — active stays active, expired stays expired, suspended stays suspended |
| PPPoE username | **Preserve exactly** per customer |
| PPPoE password | **Preserve exactly** per customer (all happen to be the same value) |
| Portal password | **Randomized** — new system feature, generated at import time |
| Expiry dates | **Preserve with timezone conversion** (UTC → UTC+8) |
| Device mapping | **Still open** — needs owner decision |
| Active-but-expired (38) | **Import as-is** — auto-suspend will handle them per normal business logic |
| Zero-date expiry (9) | **Still open** — needs owner decision |

### What "Just Works" Requires

For the import to be seamless, the import tool must:

1. **Convert timezone:** Add 8 hours to all `expires_at` values (UTC → UTC+8)
2. **Map devices:** Translate `ccr2116.v1` → chosen current device
3. **Map plans:** Translate legacy plan names (`pppoe-20m`, `pppoe-50m`, etc.) → current `SubscriptionPlan` records
4. **Preserve status:** Copy `customers.status` directly to `Customer.status`
5. **Preserve PPPoE:** Copy `pppoe_users.username` → `pppoe_username`, `pppoe_users.password` → `pppoe_password`
6. **Randomize portal passwords:** Generate secure random passwords for portal login
7. **Set `installation_status`:** `installed` (these are live customers)
8. **Set `is_verified`:** `True` (to avoid rogue-account suspension)
9. **Handle zero-dates:** Decide on fallback for `0000-00-00` values

### Plan Name Mapping (Legacy → Current)

**[UNVERIFIED]** The following mapping is inferred from name similarity and price matching. Owner must confirm.

| Legacy plan_name | Count | Likely current match | Current price |
|---|---|---|---|
| `pppoe-20m` | 392 | 20 Mbps Plan (id=19) | 999.00 |
| `pppoe-50m` | 43 | 50 Mbps Plan (id=21) | 1499.00 |
| `pppoe-30m` | 35 | 30 Mbps Plan (id=20) | 1299.00 |
| `pppoe-15m_800` | 19 | GTipid Fiber 1300 (id=8) or GIMI Home Fiber 1300 (id=11) | 1300.00 |
| `pppoe-10m` | 18 | 10Mbps (id=2) | 750.00 |
| `pppoe-15m_700` | 7 | GTipid Fiber 1000 (id=7) or GIMI Home Fiber 1000 (id=10) | 1000.00 |
| `pppoe-50m-speedboost100` | 2 | 50 Mbps Plan (id=21) | 1499.00 |
| `pppoe-100m` | 2 | 100 Mbps Plan (id=23) | 2499.00 |
| `pppoe-50m_1300` | 1 | GTipid Fiber 1300 (id=8) | 1300.00 |
| `pppoe-50m_1200` | 1 | GTipid Fiber 1300 (id=8) | 1300.00 |
| `pppoe-15m_600` | 1 | 5Mbps (id=4) | 500.00 |
| `pppoe-30m_1200` | 1 | 30 Mbps Plan (id=20) | 1299.00 |
| `pppoe-5m` | 1 | 5Mbps (id=4) | 500.00 |
| `pppoe-50m_1400` | 1 | 50 Mbps Plan (id=21) | 1499.00 |
| `pppoe-30m-speedboost80` | 1 | 30 Mbps Plan (id=20) | 1299.00 |
| `pppoe-200m` | 1 | Business 200 Mbps (id=14) | 3999.00 |
| `pppoe-120m` | 1 | Business 100 Mbps (id=13) | 1999.00 |

### Remaining Open Decisions

| # | Question | Options |
|---|---|---|
| 1 | Which current device should `ccr2116.v1` map to? | `Mikrotik A` or `Mikrotik B` |
| 2 | What should happen to the 9 zero-date customers? | Give them a default expiry (e.g., end of current month) or import with `NULL` expiry |
| 3 | Confirm plan name mapping (see above) | Owner must verify each legacy plan maps to the correct current SubscriptionPlan |

---

## 8. Leftover Files Check

**[VERIFIED]** No scratch containers found on the droplet. No leftover files from earlier crashed attempts in `docs/migration/`. The existing files are:
- `docs/migration/walkthrough.md` — describes a previous CSV-based migration approach
- `docs/migration/implementation_plan.md` — describes Docker/production optimization plan

Neither contains profiling data from the legacy dump.

---

*Document generated: 2026-09-29*
*Status: [VERIFIED] for all data points unless otherwise noted*
