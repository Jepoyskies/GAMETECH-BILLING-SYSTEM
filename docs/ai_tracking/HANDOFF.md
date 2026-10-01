# ACTIVE HANDOFF — read this first

> **Latest session: 14 (2026-09-30).**
> Full detail: [`history/Session_14_2026-09-30/HANDOFF_2026-09-30.md`](history/Session_14_2026-09-30/HANDOFF_2026-09-30.md)

This file is a pointer only. When a session ends, move the previous handoff into
`history/Session_NN_<date>/` and replace this with a fresh one.

---

## Recently completed

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

## Standing warnings

- Do **not** run `manage.py test` inside the production `gametech-web`
  container — it destabilised the droplet once (ERR-082). Use `check`,
  `migrate --check`, and the read-only RequestFactory pattern (Rule 29b).
- `billing/templates/billing/dashboard/` and `billing/templates/billing/live_monitoring/`
  are frozen — see `PAGE_FREEZE_REGISTRY.md`.
- Purple still remains in the shared base template (`gt-cl-purple` changelog
  cards, dashboard chart palette) and in
  `dispatch/templates/dispatch/pipeline/tech_mobile.html`.
- `Agent.objects.count() == 0` — the Agent Portal has never been tested against
  real data.
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
