# Cutover Runbook — Router Connection & Pairing Approval

**For:** the morning the mini PC is connected to the production MikroTik routers.
**Rule for the whole session:** the Sync Manager is a border control. Nothing
goes live because the system noticed it. Nothing goes live because you read a
number. Everything goes live because **you clicked it**.

---

## Before you start

1. Take a backup — Settings → DB Backup (or `manage.py backup_db`)
2. Confirm the old billing system is **read-only or stopped**. If it is still
   running suspension jobs it can disable a secret you just approved, and you
   will think the new system is broken.
3. Set expiry dates on the **16 customers flagged "no expiry"** in
   Settings → Import Data → View. They are live on the routers right now and
   will never cut off on their own.

---

## The five cards

| Card | Means | Action |
|---|---|---|
| **Needs Review** | On router, PPPoE matches, but profile/comment differs | Already has internet. Check bandwidth, then Approve or Auto-Fix |
| **Active Users** | On router, PPPoE matches, profile matches | Already has internet. **Approve** to record your sign-off |
| **Mikrotik Router Users** | On router, no customer in our system | Orphans. Review, delete if stale |
| **Suspicious** | Flagged oddities | Investigate individually |
| **Missing on Router** | In our system, not on the router | **Push** — but read the warning first |

---

## Order of work

### 1. Read first. Click nothing.

Open **Network Ops → Mikrotik Devices → Sync Manager** on each router and
write down the five counts. Send them before approving anything.

**The single most likely outcome:** Active Users ≈ 1,997 / 41 / 2. Those
subscribers were live in the old system, their secrets are still on the
routers, and your job is only to approve what you have reviewed.

### 2. Approve the matches

On **Active Users**: tick the rows you have checked, then
**Approve Selected**.

- Reads the router to confirm each secret exists
- **Never writes to the router** — approval cannot change a subscriber
- `sync_status` moves `Unverified → Synced`
- Your name, the secret, its enabled flag and its profile are written to
  System Logs under `SYNC_PAIR_APPROVED`

### 3. Push the missing ones

On **Missing on Router**:

- **Paid + has expiry** → Push. Creates the secret using the PPPoE username
  already in our system. Never invents a new one.
- **Unpaid or no expiry** → refused. Needs your **Admin password**, and it is
  logged with both your name and the Admin's.

> **Read this before pushing a Missing customer.** If a customer is absent
> from the router, pushing uses *our* PPPoE username. If their home modem was
> configured with a different one, they will not connect and a technician will
> have to visit. A customer missing because they are genuinely new is safe. A
> customer missing because the router lost them, or the old system renamed
> them, is **not** — check with them first.

### 4. Orphans

On **Mikrotik Router Users**, review each one. Watch for names with trailing
spaces (e.g. `Jillian `) — those are real subscribers who cannot
authenticate, and a technician visit is the likely fix. Delete only what you
are confident is stale.

---

## What is deliberately blocked

| Attempt | Result |
|---|---|
| CSR or Technician pushes an unpaid account | Refused |
| Bulk-push selected to include unpaid | Those rows held back, rest proceed |
| Override with wrong password | Refused |
| Override by a non-Admin | Refused |
| Override with blank Admin name | Refused |
| Push while `ROUTER_MODE=read_only` | Refused, marked `Blocked` |
| Delete a secret belonging to a known customer | Refused unless confirmed |

Every override is in **System Logs** with the operator, the approving Admin, the
reasons, and the exact credentials written.

---

## After you approve

- Customers → filter **"Not pushed to router"** shows anything left
- Every approval is auditable: System Logs, filter action `SYNC_PAIR_APPROVED`
  and `SYNC_ADMIN_OVERRIDE`

---

## If something looks wrong

Send me the five counts per router before acting. The two questions I cannot
answer for you without seeing the routers are:

1. Do the routers actually contain these PPPoE secrets?
2. Do they have a matching bandwidth profile for every plan in use?

Everything else has been verified against the live database and against
MikroTik A.