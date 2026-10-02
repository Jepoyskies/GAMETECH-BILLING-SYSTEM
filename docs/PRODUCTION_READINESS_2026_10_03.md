# Overnight Production Readiness Report — 2026-10-03

**Verdict: NOT 100% ready. Roughly 90–92%.** The code is in better shape than
the "95%" estimate suggested, but two live configuration items block real
production use. Neither is a code bug; both need your decision.

---

## 1. Test suite: was 12 broken, now 148 passing

| Stage | Result |
|---|---|
| Before this session | 112 tests, **12 failing** |
| After | **148 tests, 0 failing** |

Root cause of all 12: dispatch test fixtures created users with `is_staff=True`
but **no role**. Every dispatch view is wrapped in
`@role_required([...])`, which resolves the role from a `SystemAdmin` row. A
role-less user was treated as unauthorised and **redirected to the dashboard
(302)** — so tests asserting 200/403/400 all failed. The code was correct; the
fixtures were stale.

### One real security hole found and fixed

`dispatch/views_queue.py::api_assign_ticket` checked `is_staff` **first**, which
short-circuited the whole permission expression. A field technician with
`is_staff=True` could **self-assign a job**, violating SPEC decision 14
("technicians never self-pick"). Now a user who is a `Technician` is refused
before any role or permission is considered. You approved this fix.

---

## 2. Your re-import question — ANSWERED

`billing/tests/test_import_idempotency.py` (10 tests) proves:

- Re-import **updates in place and never duplicates**
- Changed fields (phone, address, status) are updated
- Missing PPPoE password now **keeps the working one and warns you**
  (previously it nulled the password, silently disconnecting subscribers)
- Portal password hashes survive (no customer lockouts)
- `installed_at` survives (billing clock and agent 60-day lock stay correct)
- A human review decision outranks the export
- `--dry-run` writes nothing

**You can safely re-import your updated export file.**

---

## 3. Live production data (read-only probe, 2026-10-03)

```
customers              2041     plans         34
payments                  1     devices        4
tickets                   1     prospects      1
agents                    1

status: active 2001 | pull out 39 | inactive 1 | suspended 0 | expired 0
installation_status: installed 2041  (0 pending)
null expiry: 16        no PPPoE password: 0
sync_status: Unverified 1290 | Blocked 751
```

`manage.py check` → clean. `migrate --check` → no pending migrations.

### ⚠️ BLOCKER 1 — `ROUTER_MODE=read_only` is still set in production

Your compose file comment says: *"Flip to 'live' only after router credentials
are confirmed correct."*

Confirmed set on the droplet. **Consequence:** nothing can ever reach a
Mikrotik router. Provisioning a new subscriber, suspending a lapsed one, and
reconnecting all silently no-op. The 751 `Blocked` rows are exactly those
accounts whose sync was refused.

**This is the single biggest gap between "built" and "live".** I have not
changed it — flipping it makes the system write to real routers.

### ⚠️ BLOCKER 2 — 805 subscribers are past due but still `active`

```
active_with_past_expiry  805
active_future_expiry    1186
active_null_expiry        10
```

These 805 have an expiry date in the past but status `active`, so they are
**still being served and still billing as current**. Note this is *not* an
`auto_suspend` failure — `auto-suspend-hourly` was deliberately removed from
Celery Beat (`settings.py:243-250`, "nothing may write to a router
unattended"), so auto-suspension is now a manual command by design.

But it also means nobody has run it, and 805 accounts are past due. Decide
whether that's correct before going live.

---

## 4. Findings I did NOT act on (need your call)

1. **`django` is unpinned in `requirements.txt`.** Local image and production
   both run 5.2.17, but your docs say 6.1. A future deploy could silently
   upgrade Django. Pinning it is a one-line change.

2. **Only 1 payment, 1 ticket, 1 prospect, 1 agent in production.** All four
   core workflows are effectively untested by real usage. The 2,041 customers
   are all `installation_status='installed'` with **0 pending** — consistent
   with a pure legacy import, meaning the new onboarding → dispatch → payment
   path has never run against real data.

3. **1,290 accounts are `Unverified`.** Honest default (never checked against a
   router), but it means most of your base is unconfirmed.

4. **10 active customers have a NULL expiry** and 16 overall. They need a
   decision before they can be collected or renewed.

---

## 5. What is genuinely well covered

| Workflow | Coverage |
|---|---|
| Customer creation + checklist | strong (12 tests) |
| Dispatch operations | strong (7 tests) |
| Phase 4B QA / bounce-backs / site visits | strong (7 tests) |
| Agents & incentives | strong (12 tests) |
| Portal security, lockout, password policy | strong (11 tests) |
| Legacy import / re-import | strong (10 tests, new) |
| Payments → receipt → balance | strong (24 tests, new) |
| Lifecycle / state domains | strong (12 tests, new) |

---

## 6. Not verified by this session

- **Live MikroTik calls.** Every test runs with `ROUTER_MODE=dry_run`, so the
  socket layer is stubbed. Real router behaviour is unproven.
- **Celery worker execution.** Beat is firing correctly, but no worker task
  that mutates money or routers was exercised.
- **SMS delivery** (Semaphore).
- **The customer portal UI** as a subscriber would see it.

---

## 7. How to run the suite yourself

```powershell
docker compose -p gametech-test -f docker-compose.test.yml up -d db redis
docker compose -p gametech-test -f docker-compose.test.yml run --rm web python manage.py test billing dispatch network_manager customer_portal
```

Isolated project `gametech-test`: its own Postgres 15, own Redis, no shared
volumes or ports with production, `ROUTER_MODE=dry_run`.

---

## 8. Recommended order to reach 100%

1. Confirm router credentials, then set `ROUTER_MODE=live` in the droplet's
   `.env`.
2. Decide what to do with the 805 past-due-but-active accounts.
3. Resolve the 10 NULL-expiry actives and 16 NULL expiries.
4. Pin Django in `requirements.txt`.
5. Run one real subscriber end-to-end: onboarding → install → payment →
   verify on router.