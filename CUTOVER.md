# CUTOVER RUNBOOK — Old PHP System → Gametech Billing

One command. That is the whole procedure.

---

## The command

```bash
# 1. put the new .sql on the server
scp "gametech (2).sql" root@143.198.207.144:/root/new.sql

# 2. import it
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && \
  docker cp /root/new.sql gametech-web:/tmp/new.sql && \
  docker exec gametech-web python manage.py import_legacy_customers /tmp/new.sql"
```

It prints a **CUTOVER SUMMARY** at the end. That summary is the whole checklist.

---

## What it is safe to do

| Action | Result |
|---|---|
| Run it twice | No duplicates. Matches on `pppoe_username`, updates in place. |
| Run it on a file you already imported | Expiry dates and details refresh. Nothing is lost. |
| Customer changed their portal password | **Not** reset. Existing hash is kept. |
| Original install date | Preserved, not overwritten. |
| Kill it halfway | Safe. Re-run and it picks up where it left off. |

---

## What the summary flags

```
! N customers have no plan        -> billing price may be wrong
! N customers have NO expiry date -> see /customers/?filter=no_expiry
! N router(s) with no customers   -> delete at /devices/devices/
```

These are the **only** things needing a human decision. Everything else is done.

---

## The two rules

**1. Never flip `ROUTER_MODE` to `live` until the expiry dates are current.**

```
grep ROUTER_MODE docker-compose.yml .env     # must read: read_only
```

While `read_only`, the system reads the routers but **cannot disconnect anyone**.
That is what makes it safe to look at everything before going live.

**2. Import BEFORE connecting the real routers.**

If the routers are connected first, their 2,000+ live secrets look like unknown
"orphans" — and the Sync Manager has a **Delete** button on that list.

---

## After the import, in order

1. `docker restart gametech-web`
2. Open `/customers/?filter=no_expiry` — decide those accounts
3. Delete any router listed as having no customers
4. Move the mini PC, connect the real routers
5. Register them at `/devices/devices/`
6. **Sync Plans from MikroTik** — the router's profile names win
7. `docker exec gametech-web python manage.py auto_reconcile_routers --dry-run`
   — read the plan, do NOT run it blind
8. Sync Manager — matches by PPPoE username, fix in the system only
9. Flip `ROUTER_MODE: read_only` → `live` in `docker-compose.yml` AND `.env`
10. `docker compose up -d`

---

## If something looks wrong

```bash
# what's the last import report?
cat /app/billing/data/last_import_report.json   # inside the container

# back it out
docker exec gametech-db pg_dump -U gametech_user -d gametech_db > /root/backups/before.sql
```

Backups are in `/root/backups/`.
