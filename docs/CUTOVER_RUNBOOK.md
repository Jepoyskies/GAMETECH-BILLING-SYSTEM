# CUTOVER RUNBOOK — disconnecting the legacy system

**Read this before cutover day, not during it.**

This is the procedure for the day Gametech Unli Fiber stops using the old PHP
system and the new system becomes the sole authority on billing.

Nothing in this runbook arms the router locks. That step is deliberately
absent, and deliberately yours.

---

## What changes on cutover day

Before cutover there are **two** authorities on whether a customer is paid:
the legacy system, and this one. That duplication is the reason every safety
rule in this project exists — our copy of an expiry can be stale, and acting
on a stale date disconnects a subscriber somebody deliberately kept.

After cutover there is **one** authority: us. The safety rules do not expire,
but their *reason* changes:

| rule | why it existed before | why it exists after |
|---|---|---|
| Nothing writes to a router unattended | the legacy system might disagree | a bulk action on wrong data is still a mass outage |
| Pairing before any write | our data might be stale | pairing is now the only human check that remains |
| Two independent locks | a stray config edit could open a router | unchanged — it protects against our own mistakes |

The word that changes is **stale**. Before cutover the risk was *theirs*. After
cutover the risk is *ours*, and the only defence left is the human review
that Sync Manager already enforces.

---

## BEFORE THE DAY

### 1. Get a fresh export and dry-run it

Sir Rom's export is the input. Never import it live first.

```bash
python manage.py import_legacy_customers <his_export.sql> --dry-run
```

It writes nothing and prints what *would* happen. Confirm it reports a
plausible customer count. **If it says "Parsed 0 rows", stop** — that is a
format mismatch and you have a MySQL/phpMyAdmin dump problem, not a
business one.

### 2. Import for real

```bash
python manage.py import_legacy_customers <his_export.sql>
```

Every account returns to the pairing queue. This is intended: a pairing made
against the previous export verified data you no longer hold.

### 3. Work the verification queue

Staff and Sir Rom go through Sync Manager account by account. For each one,
confirm against the legacy system **while it is still available**:

- does the name match?
- does the PPPoE username match?
- **is the expiry date correct?**

That last one is the one that matters. Before cutover it is a cross-check
against a live system. After cutover there is nothing to cross-check against.

### 4. Check readiness

```bash
python manage.py cutover_readiness
```

Report only — connects to no router, changes nothing. **0 blockers** is the
bar. Warnings are expected and are listed there for tracking.

---

## ON THE DAY

### 5. Confirm the legacy system is quiet

Verify the old system has stopped writing to the routers before you take
over. Two systems actively managing the same subscribers is exactly the
conflict this project was built to avoid, and it is the one thing this
runbook cannot undo for you.

### 6. Cut over billing

Point staff at the new system. Nothing technical changes — the site is
already the live one.

### 7. Verify from a staff account

Log in as a real role (not superuser) and check:

- the Customers Directory loads and counters look sane
- Sync Manager opens for each of the three routers
- a payment recorded against a test account appears correctly

### 8. Confirm reads, not writes

```bash
python manage.py auto_suspend --dry-run
```

Expect the armable count to be **0** unless you have paired accounts that
are also past due. This confirms the pairing gate still holds.

---

## STILL ARMED OFF — ON PURPOSE

After cutover, **nothing auto-suspends**. An expired customer keeps their
internet until a human acts.

That is a deliberate trade, and it is worth being explicit about it:

- being slow to suspend costs **revenue**
- being wrong about a suspension costs **customers**

For a short period after cutover, take the revenue risk.

### The staged ramp

Do not arm both locks on day one. When you are ready:

1. Arm for a **small, verified batch** — accounts you personally confirmed.
2. `auto_suspend --dry-run` and read the armable count.
3. Run for real on that batch only.
4. Watch what happened before going further.
5. Ramp up as confidence grows.

`auto_suspend` refuses to run above 50 armable accounts. That valve is
there because a bulk import can leave hundreds of accounts flagged active
with a long-past expiry, and disconnecting a third of the customer base at
3am is an outage, not a collections action.

---

## IF SOMETHING GOES WRONG

**A customer was suspended who should not have been.** Re-enable them in
Sync Manager, then find the pairing that authorised it. `SystemLog` records
who paired what and when, and the `SYNC_PAIR_APPROVED` audit row says
exactly which router read was verified.

**Too many suspended at once.** Immediately:

```bash
# Put the locks back. This is the fastest safe action.
ROUTER_MODE=read_only
# and unset ROUTER_WRITE_TOKEN
docker restart gametech-web
```

Then use Sync Manager to re-enable, or `auto_suspend` in reverse for known
accounts.

**The readiness report shows a blocker.** Do not arm anything. Blockers mean
either the router mode is already live, the tokens are armed, or an account
has been pushed. Resolve that first.

---

## THE ONE THING NO PROCEDURE CAN FIX

Our expiry dates are a **snapshot**. If Sir Rom extended an account over
there after the export, our copy is wrong, and once the legacy system is
gone nothing will contradict us.

**This is why step 3 exists and why it must happen while the legacy system is
still available.** Verification performed after cutover has nothing to check
against.

If your data is going to be wrong on the day, it will be wrong because
somebody extended a subscriber's expiry in a system we can no longer see.
The pairing queue is the last place that can be caught.

---

## COMMANDS

```bash
python manage.py cutover_readiness              # is it safe, report only
python manage.py auto_suspend --dry-run         # who would be disconnected
python manage.py import_legacy_customers f.sql --dry-run   # parse check
python manage.py import_legacy_customers f.sql              # real import
```
