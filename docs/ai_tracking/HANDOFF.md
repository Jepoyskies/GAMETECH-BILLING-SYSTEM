# ACTIVE HANDOFF — read this first

> **Latest session: 15 (2026-10-03).**

This file is a pointer only. When a session ends, move the previous handoff into
`history/Session_NN_<date>/` and replace this with a fresh one.

---

## Recently completed

### Persona portals brought onto the theme + demo credentials reset ✅

**Credentials** were reset so a walkthrough could be done. These are throwaway
demo passwords shared over chat — rotate them if the system goes live:

| Username | Password | Lands on |
|---|---|---|
| `Jep` / `Jill` / `Admin` | `1234` | `/` |
| `Vince` | `csr-12345678` | `/` |
| `Martin` | `agent-12345678` | `/agent-dashboard/` |
| `Merk` | `tech-12345678` | `/dispatch/tech-dashboard/` |

`Cardo` (Viewer) and `test_technician` were left untouched. Passwords live only
as PBKDF2 hashes, so they can only ever be **reset**, never read back.

**CSR + Viewer no longer reach the admin panel.** `can_access_administration`
flipped to `False` for both, plus the `administration.admin_panel` subtab. Done
as **data** in `StaffRole`, not hardcoded, so the Role Editor can grant it back.
Verified: Vince and Cardo get `302 /` from `/admin-panel/` and `/staff/roles/`;
Jep still gets `200`.

**Portal UI.** Agent + Technician portals now pass WCAG AA in **both** light and
dark mode, zero measured failures. Fixes in `static/css/gt/portal.css` (now
cache-busted to `?v=4.6` in both portal base templates — **bump this string
whenever portal.css changes** or browsers keep serving the old file):
- new `--persona-accent-text` token (gold-on-gold was 1.00:1)
- `.pt-kpi-*` modifiers retargeted `.pt-kpi-value` -> `.kpi-value` (the class
  templates actually use) and scoped under `.portal` to outrank `.kpi-value`
- `body.portal a` narrowed to `a:not(.btn)` — it was repainting Bootstrap buttons
- `text-warning/info/success/danger` remapped in the `.portal` legacy bridge
- `tech_dashboard.html` lost six hardcoded inline hex colours (incl. a `#a78bfa`
  purple) in favour of `pt-kpi-*` classes

Full write-up: **ERR-098**. Near-miss that produced a duplicate install ticket:
**ERR-097**.

---

## Standing warnings

- **The stack recreates itself on its own.** Several times this session all five
  containers were destroyed and recreated ~10s apart with no deploy of mine in
  flight — nginx returns 502 until `docker compose up -d`. Not yet root-caused.
  If a container vanishes mid-command, wait ~20s and re-check `docker ps`.
- **Do not create a `JobTicket` from a billing view.** `dispatch/signals.py`
  already auto-creates the `INSTALLATION` ticket off `Customer` post_save, with a
  de-duplication guard. A raw create in `add_customer` shipped for one commit
  and double-dispatched every install. See ERR-097.
- **Do not trust `getComputedStyle` after a manual theme toggle.** Reading in the
  same evaluate call that adds `dark-mode` returns stale values and invents
  contrast failures. Use `localStorage.setItem("theme", ...)` + a real
  navigation, then read on a later turn.
- **Do NOT exercise `manage_roles` POST against a real `StaffRole` row.** The
  view has no dry-run and writes immediately. The `CSR` role was overwritten once
  and had to be restored from a SQL backup. Create a throwaway `ZZ_TMP_*` role.
- Do **not** run `manage.py test` inside the production `gametech-web` container
  (ERR-082). Use `check`, `migrate --check`, and the read-only `Client`/`RequestFactory` pattern.
- `billing/templates/billing/dashboard/` and `billing/templates/billing/live_monitoring/`
  and `billing/templates/billing/login.html` are frozen — see `PAGE_FREEZE_REGISTRY.md`.

---

## Open issues (not fixed, worth a decision)

1. **The permission matrix is still barely enforced.** `_role_allows()` in
   `billing/decorators.py` documents a step-3 fallback to the `StaffRole` matrix
   but the code does not implement it — it compares role NAMES only, plus a
   special case where `"Admin" in allowed_roles` unlocks via the administration
   module. All ~59 dispatch guards are flat
   `@role_required(["Admin","Editor","Staff","CSR","Dispatch"])`, so subtab
   changes in the Role Editor still won't gate most screens. `module_required()`
   exists and works but is used **zero** times outside its docstring. Converting
   dispatch guards to `@module_required("dispatch", "<subtab>")` is the fix; it
   was left alone deliberately to avoid a 59-site refactor inside a UI task.
2. **`Agent` role has `can_access_billing=False`.** Confirm agents genuinely
   must not see billing before go-live.
3. **Dispatch has almost no live data** — 1 open ticket, 1 real agent, 2
   technicians (one test), 3 teams. `manage.py seed_dispatch_test_data` exists if
   a populated demo is wanted.

---

## Historical (session 14 and earlier)

### Role Editor UI — action-level permission toggles ✅ DONE (`d902c28`)

`manage_roles.html` now renders per-module **View / Create / Edit / Delete**
toggles alongside the module + subtab checkboxes, with All/None shortcuts and
denied tiles painted red. Saved into `subtab_permissions["_actions"]`.

**Storage shape is keyed by MODULE, not subtab:**

```json
{"_actions": {"dispatch": {"view": true, "create": false,
                           "edit": false, "delete": false}}}
```

The older comment in `models.py` and this file showed a subtab key
(`{"agents": {...}}`) — that key is **never read** by `has_action_perm()`.
Corrected in `billing/models.py:184-203`. Subtab granularity is already
handled separately by `has_subtab_perm()`.

`manage_roles` only rewrites `_actions` when the POST actually carried
`act_<module>_<verb>` fields; otherwise the prior block is preserved verbatim.

### ⚠️ Next: the permission matrix is barely enforced

`module_required` is used **zero** times outside its own docstring. All 59
dispatch guards are `@role_required(["Admin","Editor","Staff","CSR","Dispatch"])`
— a flat name list, so they ignore the matrix. Only 6 `action_required` sites
exist (5 on `dispatch/agents`, 1 on `administration/admin_panel`). The Role
Editor now writes real data, but subtab-level changes still won't gate most
screens until views are converted to `module_required`.

---

## Recently completed (do not redo)

- **Dispatch Queue page** rebuilt to match `/customers/` using the shared
  design system. Zero purple in the page markup. `1cdd08e`
- **Permission overhaul** — `role_required` now consults the StaffRole matrix
  (it previously only matched role names, so the Edit Roles UI changed the
  sidebar but never enforced access). ~50 dispatch views gated, Agent and
  Technician roles hardened. `58a86d3`

---

## Recently completed (do not redo)

### Persona landing router + own portals for Agents & Technicians ✅
`resolve_landing_url()` in `billing/views/auth.py` is the single authority for
where a user lands after login. Role is tested **before** `is_staff` (Martin and
Merk are both `is_staff=True`). New mobile-first Technician Field Portal at
`dispatch/templates/dispatch/pipeline/{portal_base_tech,tech_dashboard}.html`.
The Agent Portal shell already existed — a dead duplicate
`billing/agent_dashboard.html` was deleted (ERR-088).

### Two safety fixes ✅
- `seed --clear` now refuses to run on a non-DEBUG database (ERR-090). It would
  otherwise delete every customer, payment, agent, router and persona role.
  `seed.py` was also the whole file duplicated; dead copy removed.
- Agent cash-out requests had **no audit trail** (ERR-091). Both silently-broken
  `SystemLog` sites now use `log_sensitive_operation()`.

### New commands
| Command | Purpose |
|---|---|
| `link_persona_profiles` | Create missing Agent/Technician profiles. Dry run by default, `--apply`, `--unlink`. |
| `audit_systemlog_calls` | AST-scan for `SystemLog.create()` calls that silently die. `--strict`, `--show-dynamic`, `--path`. |

---

## Standing warnings

- Do **not** run `manage.py test` inside the production `gametech-web`
  container — it destabilised the droplet once (ERR-082). Use `check`,
  `migrate --check`, and the read-only RequestFactory pattern (Rule 29b).
- `billing/templates/billing/dashboard/` and `billing/templates/billing/live_monitoring/`
  are frozen — see `PAGE_FREEZE_REGISTRY.md`.
- Purple still remains in the shared base template (`gt-cl-purple` changelog
  cards, dashboard chart palette) and in
  `dispatch/templates/dispatch/pipeline/tech_mobile.html`.
- ~~`Agent.objects.count() == 0`~~ **RESOLVED 2026-10-01.** Agent + Technician
  profiles now exist and are linked (Martin -> Agent id 19, Merk -> Technician
  id 10, team unassigned). Both portals verified rendering 200. See ERR-089 and
  `python manage.py link_persona_profiles`.
- **Do NOT exercise `manage_roles` POST against a real `StaffRole` row.** The
  view has no dry-run and writes immediately. During the Session 15 test pass
  the `CSR` role was overwritten (all modules off, all subtabs false) and had
  to be restored by hand from `/root/backups/pre_plaintext_drop_20260930_2105.sql`.
  Create a throwaway `ZZ_TMP_*` role instead, as done in that session.
- **`docker restart gametech-web` restarts only web.** The whole stack
  (`db`, `redis`, `celery`, `celery-beat`) was observed recreating itself
  several times in one session — containers destroyed then created, ~10s apart,
  no OOM, memory fine. If a container vanishes mid-command, wait ~20s and
  re-check `docker ps` rather than assuming the deploy failed.
