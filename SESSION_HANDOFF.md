# SESSION HANDOFF — 2026-09-30 → 2026-10-01

> **Read this first on a new machine.** Written at the end of a working session so a
> different device can pick up cold. Production is `ssh root@143.198.207.144`,
> container `gametech-web`, repo `/root/GAMETECH-BILLING-SYSTEM`.
> See also `SESSION_STARTUP.md` (orientation) and `gametech_error_runbook.md` (ERR-081/082/083).

---

## 1. HEADLINE — the password feature was REMOVED after we built it

We spent this session building "let Admins see staff passwords" (a plaintext
mirror, mirroring the existing customer-portal pattern). It worked and was
verified. It has since been **deleted on security grounds** in commit:

```
b756059 security(billing): drop plaintext staff and portal password mirrors; hash-only storage
```

That commit:
- removed `SystemAdmin.password_plaintext` and `Customer.portal_password_plaintext` from `models.py`
- added `billing/migrations/0064_drop_plaintext_password_columns.py` and **applied it to production**
- stripped the eye/copy UI from `edit_staff.html`, `staff_and_admins.html`, and
  `view_customer/_info_cards.html`
- `SystemAdmin` now has only `password_hash`

**Consequence: the stored passwords are gone permanently.** The four accounts
below still *work* with these passwords (the hashes are intact) — they just
cannot be displayed anywhere any more:

| Account | Role | Password (still valid, no longer visible) |
|---|---|---|
| Vince | CSR | `csr-12345678` |
| Merk | Technician | `tech-12345678` |
| Martin | Agent | `angent-12345678` |
| Cardo | Viewer | `viewer-12345678` |

**DECISION NEEDED:** keep hash-only (accept that a forgotten password must be
reset, not looked up), or reinstate visibility. If reinstating, re-apply the same
approach as `2260ec4` + `723f0a9` + `fbee1c7`, then reset the four accounts
because the mirror data no longer exists. Note this also affects the **customer
portal** — staff can no longer read a subscriber's portal password.

---

## 2. Verified state at handoff

- Production head: `3cc047e`; no pending migrations; `manage.py check` clean; `login` returns 200.
- All five containers healthy: `gametech-web` (healthy), `gametech-db` (healthy),
  `gametech-redis` (healthy), `gametech-celery`, `gametech-celery-beat`.
- **Exactly 7 staff accounts** — your 3 admins and 4 staff. Nothing else.
  - Admins: `Admin`, `Jep`, `Jill` (all `is_superuser`) — **do not touch these**
  - `Vince` (CSR), `Merk` (Technician), `Martin` (Agent), `Cardo` (Viewer)
- Swap: 2 GB active and persistent. Disk ~26–29% used.

### Junk that is still in the database
Non-staff `auth_user` rows from earlier testing — harmless, cannot reach the app,
but they are test residue: `Jill@gmail.com` (Sep 24), `test_agent` (Sep 28),
`test_technician` (Sep 28). Remove if you want a clean slate.

---

## 3. Infrastructure hardening (done, keep it)

- **2 GB swap** added at `/swapfile`, persisted in `/etc/fstab`, `vm.swappiness=10`.
  The box is 1 vCPU / 1.9 GB and previously had **zero** swap with dockerd peaking
  at 1.1 GB.
- **Container log rotation** capped at `10m x 3` in `docker-compose.yml`
  (one log had reached 34 MB unbounded).
- **Web healthcheck** added to `gametech-web` in `docker-compose.yml` (db/redis
  already had one). See §5 — this may need to be removed.
- **~8 GB disk reclaimed** via `docker builder prune -f`. Disk went 35% → 26%.
- **`scripts/safe_compose.sh`** — wraps `docker compose` in `flock` so two
  sessions queue instead of recreating each other's containers.
- **Stale 66 MB volume deleted:** `gametech-billing-system_postgres_data`
  (a frozen PG cluster from Sep 8, referenced by nothing). The **live** volume is
  `gametech-billing_postgres_data` — never delete or rename it.
- Fresh verified backup: `/root/backups/gametech_live_20260930.dump` (57 tables).

---

## 4. Migration drift that was fixed

`Customer.portal_password_plaintext` existed in production but had **no
migration** — any fresh database (CI, new machine, test run without `--keepdb`)
would have been missing the column and portal password saves would 500.
Captured as `0063`, fake-applied on prod. Later removed again by `b756059`.

**Always run before deploying:**
```bash
docker exec gametech-web python manage.py migrate --check
```

---

## 5. OPEN PROBLEM — container flapping (root cause partly known)

`gametech-web` / `gametech-celery` / `gametech-celery-beat` repeatedly fall into
`Created` state and the site goes down. **`restart: unless-stopped` does not
rescue a container that has never started**, so the usual safety net does nothing.

Two confirmed contributing factors:

1. **Concurrent `docker compose` sessions.** Each recreates the other's
   containers mid-flight. Use `scripts/safe_compose.sh`, and prefer plain
   `docker restart gametech-web` for routine deploys.
2. **Snap Docker healthcheck bug** — daemon log shows:
   ```
   healthcheck failed fatally: Unavailable: connection error:
   "transport: Error while dialing: only one connection allowed"
   ```
   Snap-confined Docker allows only one concurrent healthcheck session. With three
   healthchecks (db, redis, **and the web one added this session**) dockerd fails
   them and containers get recreated. **Test removing the web healthcheck first** —
   it is one block in `docker-compose.yml`.

Ruled out: daemon crash (`snap.docker.dockerd` had 6+ days continuous uptime on
the same PID), OOM (no kernel OOM kills, swap healthy), snap auto-refresh (no snap
changes), cron/watchdog (none installed).

---

## 6. Hard rules for whoever works next

1. **Never run the test suite in `gametech-web`.** It destabilises production.
   `AGENTS.md` was corrected — use `manage.py check` / `migrate --check` or the
   RequestFactory pattern (Rule 29b) instead.
2. **Never touch the 3 admins** (`Admin`, `Jep`, `Jill`) unless explicitly asked.
3. **Never delete or rename** the volume `gametech-billing_postgres_data`.
4. **One deploy at a time.** Two AI sessions on this box fought all day and
   knocked the site over repeatedly.
5. **Test against a test database, never production.** A sibling session created
   `probe_*`, `screenshot_verify` and `agentregress` superuser accounts in the
   live database while testing a role matrix. `screenshot_verify` was a real
   superuser with an unknown password and had to be deleted three times. If it
   reappears, it means something is still testing against prod.
6. Frozen pages — never edit: `billing/templates/billing/dashboard/`,
   `billing/templates/billing/login.html`, `billing/templates/billing/live_monitoring/`.

---

## 7. Suggested order of work for the next session

1. Decide §1 (hash-only vs. reinstate password visibility).
2. Confirm no other session is active; `git status` clean; containers stable.
3. Chase §5 — remove the web healthcheck, observe whether flapping stops.
4. Automated **offsite** backups (all current backups are on one disk, and that
   disk lost its database twice today). Highest remaining value.
5. Give the test suite a real home (CI or a local dev box).
6. Optional: clear the three junk users in §2.

---

## 8. Cheat sheet

```bash
# deploy
git add -A; git commit -m "fix(...)"; git push origin main
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull --ff-only origin main"
ssh root@143.198.207.144 "docker restart gametech-web"

# health
ssh root@143.198.207.144 "docker ps --format '{{.Names}}|{{.Status}}'"
ssh root@143.198.207.144 "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/login/"
ssh root@143.198.207.144 "docker exec gametech-web python manage.py check"

# emergency: containers stuck in Created
ssh root@143.198.207.144 "/root/GAMETECH-BILLING-SYSTEM/scripts/safe_compose.sh up -d"

# backup
ssh root@143.198.207.144 "docker exec gametech-db pg_dump -U gametech_user -d gametech_db -Fc > /root/backups/backup_$(date +%Y%m%d).dump"

# run python on the droplet (PowerShell-safe: pipe via stdin, never inline -c)
@'
print("hello")
'@ | ssh root@143.198.207.144 "docker exec -i gametech-web python manage.py shell"
```
