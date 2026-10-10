# DISPATCH MODULE — HANDOFF BRIEF FOR A DEDICATED SESSION

You are taking ownership of the **Dispatch** module of the Gametech Unli Fiber billing
system (Cagayan de Oro ISP). Another session owns Sync Manager / billing and is working
in parallel. **Stay inside `dispatch/`, plus the small number of `billing/` changes
listed explicitly below.** Do not touch Sync Manager, routers, billing logic, or the
dashboard/login baselines.

---

## 0. READ THESE FIRST (non-negotiable project rules)

Repo root: `C:\Users\gametech\Documents\GAMETECH-BILLING-SYSTEM`

Read, in this order, before writing any code:

1. `AGENTS.md` — the full rulebook. Especially:
   - **Rule 0/1** — Logic Freeze + Scope Lock.
   - **The Zero-Scan Law** — never crawl the repo. Use `gametech_filing_index.md` to
     find things. Grep for a symbol, then read a 50–80 line slice. Never open a
     1,000-line file end-to-end.
   - **Rule 24 (400-line circuit breaker)** — if you touch a file over 400 lines, you
     must split it into partials/modules under 250 lines as part of that work.
     `dispatch/views.py` is already split; `dispatch/models.py` is 638 lines.
   - **Rule 38 (full-stack atomic batching)** — batch Model+migration+views in one
     stage, templates in the next, deploy in a third. Don't do 1-file micro-edits.
   - **Rule 26 (PowerShell)** — chain commands with `;` NEVER `&&`.
   - **Rule 33** — for multi-line local Python, pipe via stdin: `@' ... '@ | python -`.
2. `gametech_filing_index.md` — URL → View → Template → Models map.
3. `gametech_error_runbook.md` — read ERR-125 onward before debugging anything.
   Add a new `ERR-XXX` entry for anything novel you solve.
4. `gametech_architecture_map.txt` — **grep it, never read it** (2,174 lines).

---

## 1. THE ONE RULE THAT CAN END THE COMPANY

> **NEVER write to a MikroTik router. Not once. Not "just to test".**

The routers at `172.30.120.1/.2/.3` are shared with the **legacy billing system that is
still running the business** and the office Mini PC. A stray write can cut off a paying
subscriber, de-provision a live account, collide with the old system, or undo a
technician's field work.

Current state: `ROUTER_MODE=read_only`, write tokens unarmed, **0 pairs / 0 pushes ever**.

**Dispatch must stay on the near side of that border.** Dispatch records what happened
in the field. It does not provision, suspend, or modify router state. If you believe a
dispatch feature needs a router write, **stop and report it — do not implement it.**

---

## 2. WHAT SIR ASKED FOR (verbatim intent, three features)

### A. Job-order credit: who opened it vs. who closed it

> "If a CSR staff opened a job order but never got to close it, then another staff was
> the one that closes it, then they get **1 point each**. If one staff opened and closed
> a job, that staff gets **2 points**. The job order must show which staff opened and
> which staff closed it — who handled it first, then who handled it last."

### B. Technician replacement / handover, with a reason

> "Some technicians don't finish the task within the day. There should be a replacement
> — this tech started it, got replaced by this tech that finished it — and there should
> be a **reason why they changed technicians**. There are instances where the first
> technician only knew how to do the first part and not the last, that's why they get
> replaced."

### C. MAC address + serial number captured at technician submission

> "For the last submission of the technician, like after they installed and need to
> submit the form, they should input the **MAC address and serial number** of the home
> modem of that customer. The system should automatically put it in the customer's
> profile — that this customer **owned** this home modem. So that when it's time to
> replace, we can change it, and we could literally track the entire operation."

### D. General
> "We also need a lot of improvements for this to finally finish the dispatch area part."

---

## 3. EXACT CURRENT STATE (verified — do not re-derive, do not guess model names)

`dispatch/models.py` (638 lines) contains:
`Team`, `Technician`, `ConfigOption`, `DispatchRecord`, `MonitoringRecord`, `JobDetail`,
`AuditLog`, `JobTicket`, `JobTicketHistory`, `TicketBounceHistory`, `CallAttemptLog`.

### `JobTicket` — the fields that already exist (use these, don't re-add)

| Need | Existing field | Status |
|---|---|---|
| **Who opened it** | `created_by` → `User`, `related_name="dispatched_tickets"` | ✅ EXISTS |
| **Who closed it** | `admin_approved_by` → `User`, `related_name="admin_approved_tickets"` | ✅ EXISTS |
| When approved | `admin_approved_at` | ✅ EXISTS |
| QA reviewer | `qa_by` → `User` | ✅ EXISTS |
| **Modem serial number** | `ont_modem_sn` (CharField 100) | ✅ EXISTS on the ticket |
| **MAC address** | — | ❌ **MISSING on JobTicket** |
| Assigned technicians | `technicians` = **M2M to `Technician`** | ⚠️ **NO ORDER, NO HISTORY** |

Status machine (`STATUS_CHOICES`): `PENDING → ASSIGNED → IN_PROGRESS → COMPLETED
(awaiting QA) → QA_PASSED → APPROVED`, plus `CANCELLED`.
`can_transition_to()` (line ~442) validates transitions; `COMPLETED` can go back to
`ASSIGNED` / `IN_PROGRESS`.

Timing fields already present: `time_start`, `time_accomplish`, `duration`,
`done_at`, `done_duration`, `arrived_at`, `arrival_latitude/longitude`, `finished_at`,
`qa_completed_at`, `timer_corrected_at/by/reason`.

### The real gap for feature B
`JobTicket.technicians` is a plain `ManyToManyField`. It **cannot** record who was
first, who replaced whom, or why. That is the whole of feature B.

### `JobTicketHistory` — a generic status-change log
`job_ticket`, `actor`→User, `from_status`, `to_status`, `note`, `timestamp`.
Useful, but it is a flat status log — it has no notion of *technician handover* or a
*replacement reason*.

### Equipment tracking already partially exists in `billing/models.py`

- `Customer.mac_address` (line 608) — the modem MAC currently on the profile.
- **`CustomerMacHistory`** (line 1220, `db_table="customer_mac_history"`) —
  `customer` FK (`related_name="mac_history"`), `mac_address`, `detected_at`,
  `Meta.ordering = ["-detected_at"]`.

So the *MAC* replacement history table exists but is **MAC-only** — no serial, no
reason, no link to the job ticket that caused the change. Feature C is about wiring the
dispatch approval form into this, and extending it to carry serial + reason + ticket.

### The leaderboard already renders — with zeros

`dispatch/templates/dispatch/dash_partials/_dash_leaderboards.html` renders
"Field Productivity & Close Rate Leaderboard" (technician) and
"Customer Service Representative (CSR) Performance". Columns include
`ASSIGNED`, `DISP. HANDLED`, `DISP. CLOSED`, `DISPATCH RATE`, `CONCERNS HANDLED`,
`CONCERNS CLOSED`, `% OF TARGET`, `AVG / DAY`.

Everything shows **0** because there is no ticket history yet and the point logic does
not exist. That screenshot is the acceptance target, not a mockup.

Dispatch views are already split: `dispatch/views.py`, `views_approval.py`,
`views_management.py`, `views_queue.py`, `views_tech.py`. Follow that pattern.

---

## 4. WHAT TO BUILD

Design freely, but these constraints come from the business, not from taste:

### A. Credit / points
- Points are **per completed job order**, awarded on closure (`APPROVED`).
- `created_by == admin_approved_by` → **2 points** to that person.
- Different people → **1 point each**.
- Decide and **document** how a ticket that never gets approved scores (suggestion:
  0, and say why). Do not silently award points for cancelled work.
- The **job order page must visibly show both**: who opened, who closed.
- The leaderboard must actually count these. Real columns, real numbers, ranking that
  reorders when a ticket is closed.
- Points must be **derived, not hand-stored**, wherever possible — a ticket already
  records its opener and closer. If you cache the score, it must be recomputed on
  closure and on any correction, or the leaderboard will lie.

### B. Technician handover
- Replace the flat M2M with an **ordered assignment history**: who was assigned, in
  what order, who replaced whom, when, and **why** (mandatory reason on replacement).
- Suggested shape: a `TicketTechnicianAssignment` model —
  `job_ticket` FK, `technician` FK, `sequence`, `assigned_at`, `started_at`,
  `finished_at`, `replaced_by` (self-FK or FK), `replacement_reason`,
  `is_current`. Order by `sequence`.
- Backfill existing tickets so no history is lost (there is at least one real ticket:
  `GT-20261010-0001`).
- The **replacement reason should be a controlled choice, not free text alone** —
  Sir's example is "first tech only knew how to do the first part". Suggest a
  `ConfigOption`-backed list (the project already uses `ConfigOption` for this) with a
  required free-text note when the reason is "Other".
- Show the handover chain on the ticket: *Merk (start) → Vince (finish, reason: skill
  mismatch)*.

### C. MAC + serial at technician submission
- Technician's final submission form (the one that completes the job) must require
  **MAC address** and **serial number** of the customer's home modem.
- On submit, write to `CustomerMacHistory` **and** update `Customer.mac_address`.
- Extend the history so a modem can be **replaced over time**: add serial, a reason,
  and the originating `JobTicket` FK. Today the model can only record a MAC — it cannot
  answer "which modem did they have before, and why did it change?"
- Validate/normalise MAC input (accept `AA:BB:CC:DD:EE:FF`, `aa-bb-cc-dd-ee-ff`,
  bare `aabbccddeeff`; store one canonical form). Reject obvious junk.
- Warn on **duplicate MAC across two different customers** — that is a real field
  failure (same modem provisioned twice) and is exactly the kind of thing this feature
  exists to catch.

### D. Improvements
Use judgement. Prioritise anything that blocks a non-technical staff member from
finishing a job order without asking for help.

---

## 5. HOW TO WORK SAFELY

**Develop locally first.** The user's machine has Docker Desktop running
(`C:\Users\gametech\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe` — note the
**per-user** path, not `Program Files`) and a local stack:

```powershell
docker ps                                    # gametech-db / redis / web
docker compose up -d --no-build web          # source is volume-mounted at /app
```

- Code is volume-mounted (`- .:/app`), so template/Python edits are live on restart.
- Local `.env` is pinned `ROUTER_MODE=read_only` with **empty** write tokens, and the
  local DB has **no router devices** — a local container cannot reach the routers even
  by accident. Keep it that way. Do not put real router IPs or credentials in any local
  file.
- `.env` is git-ignored. Never commit secrets.

**Test suite — where it runs.** Do **NOT** run tests inside the production
`gametech-web` container; the droplet is 1 vCPU / 1.9 GB and building a test DB there
has taken the site down before (ERR-082). The harness `/root/gtrun.sh` on the droplet
runs the suite in an **unmanaged throwaway container** against real PostgreSQL.

```bash
ssh root@143.198.207.144 "docker rm -f gt-test; /root/gtrun.sh"
# then poll /root/gt-testout/gt.txt for:  Ran N tests ... OK
```

Two traps that have bitten this project:
- **ERR-130** — without `DATABASE_URL` inherited from the live container the suite
  silently falls back to SQLite and the results are meaningless (counts differ:
  271 vs 200 vs 283). Verify you're on PostgreSQL.
- A stale `gt-test` container holding `test_gametech_db` causes
  *"database is being accessed by other users"* and a red `__EXIT=1` even when every
  test passed. If you see that, `docker rm -f gt-test` and drop the DB before rerunning.

Current baseline: **297 tests, all passing.** Don't regress it.

**Verify in the real system, not just in code.** Walk the whole path in the browser on
your local stack: CSR creates a job order → dispatch assigns → technician arrives →
submits with MAC/serial → QA → admin approves → check the leaderboard moved. Also test
the handover path with two technicians.

Real local accounts (passwords match the username pattern):
Admin `Jep` / `Jill` / `Admin` = `1234` · CSR `Vince` = `csr-12345678` ·
Technician `Merk` = `tech-12345678` · Agent `Martin` = `agent-12345678`.

---

## 6. DEFINITION OF DONE

- [ ] Job order page shows **who opened** and **who closed**.
- [ ] Points follow the 2 / 1+1 rule, are **derived** from ticket data, and the
      leaderboard numbers actually change when a ticket is approved.
- [ ] Technician handover is recorded **with a mandatory reason**, ordered, and
      visible on the ticket.
- [ ] Technician submission **requires MAC + serial**, writes to the customer profile
      and the equipment history, and flags duplicate MACs across customers.
- [ ] A modem replacement is traceable: previous modem, new modem, why, which ticket.
- [ ] Migrations applied and reversible; existing tickets backfilled, not orphaned.
- [ ] Full suite green (297+), no router write path added.
- [ ] New `ERR-XXX` runbook entry for anything novel.
- [ ] Committed on `main` with a conventional message, pushed, production pulled and
      `docker restart gametech-web` (NOT `docker compose up` — see ERR-132, something
      external runs `--build` every ~40 min and tears production down).

---

## 7. REPORT BACK

Tell the user, in plain language:
1. What you built and where it lives (files).
2. What the numbers now mean, with a real worked example from the test data.
3. Anything you found broken or dangerous that you did **not** fix, and why.
4. Anything you think Sir should decide (especially: do cancelled or bounced tickets
   earn points? who counts as "opened" a ticket auto-created by the system?).

Do not claim a feature works because the code compiles. Open the page and use it.