# ACTIVE HANDOFF — read this first

> **Latest session: 14 (2026-09-30).**
> Full detail: [`history/Session_14_2026-09-30/HANDOFF_2026-09-30.md`](history/Session_14_2026-09-30/HANDOFF_2026-09-30.md)

This file is a pointer only. When a session ends, move the previous handoff into
`history/Session_NN_<date>/` and replace this with a fresh one.

---

## Open Task (start here)

### Role Editor UI — expose the action-level permissions ⬅️

The backend already supports view/create/edit/delete permissions via
`action_required` and `StaffRole.has_action_perm()`. The Edit Roles screen
(`billing/templates/billing/manage_roles.html`) does not yet render those
toggles, so the capability is invisible.

**Files:** `manage_roles.html` · `billing/views/staff.py` (`manage_roles` +
`ROLE_MODULE_SPECS`) · `billing/models.py` (`has_action_perm`)

**Do not remove** the `_actions` preservation guard added in `manage_roles` —
without it every role edit wipes the action permissions.

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
