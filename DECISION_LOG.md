# DECISION_LOG.md — Architectural Decisions

> **PURPOSE**: Running log of architectural decisions so future sessions don't re-litigate settled questions.  
> **Rule**: Before proposing an architectural change, check this log. If a decision is already recorded, follow it unless the user explicitly overrides it.

---

## Decision Format

```
### [DATE] — [TITLE]
**Decision**: What was decided
**Rationale**: Why
**Consequences**: What this means for future work
```

---

## 2026-10-04 — Live Monitoring Right-Side Modernization
**Decision**: The right-side panels of Live Monitoring (`_info_cards.html`, `_live_traffic_card.html`, and right-column CSS in `_styles.html`) are unfrozen and modernized to align with Gametech's theme tokens. The left-side hero card (`_hero.html`) remains strictly frozen and untouched.
**Rationale**: Owner explicitly requested to keep the left side exactly as it is while modernizing the right-side cards (alerts, telemetry, add-ons, and live traffic table) to match the system theme.
**Consequences**: Future work may edit right-side panels for UI improvements, but must preserve all JS telemetry/polling hooks and never touch `_hero.html`.

---

## 2026-09-30 — Agents Separated from Dispatch System
**Decision**: Agents and Agent Payouts moved from Dispatch System sidebar into their own top-level "Agents" menu item.
**Rationale**: Agents are a distinct operational domain (sales, commissions, referrals) and deserve their own navigation section for faster access.
**Consequences**: Dispatch System no longer auto-expands on agent pages. Agents section uses `dispatch_agents` permission gate.

---

## 2026-09-30 — DB Backup Uses pg_dump for PostgreSQL
**Decision**: `backup_database_view` now uses `pg_dump` subprocess for PostgreSQL instead of trying to read a SQLite file.
**Rationale**: Production runs PostgreSQL 15, not SQLite. The old code always failed with "Database file not found" and redirected to settings.
**Consequences**: Backup button now produces a real `.sql` file. SQLite path still supported for local dev.

---

## 2026-09-30 — Agents Card Moved to Settings
**Decision**: Agents card moved from Admin Panel (owner-only) to Settings > My Account section.
**Rationale**: Staff need access to manage agents without needing owner-level Admin Panel access.
**Consequences**: Agents accessible from both Settings page and sidebar. Admin Panel no longer has Agents card.

---

## 2026-09-24 — Dispatch Operation Architecture
**Decision**: Dispatch uses team-based assignment (technicians never self-pick), QA approval flow, and bounce-back system with reasons.
**Rationale**: Business requires accountability and quality control on every install/repair.
**Consequences**: All dispatch views must preserve the assignment → arrival → completion → QA → approval pipeline.

---

## 2026-09-24 — Router Dry Run Guard
**Decision**: `ROUTER_DRY_RUN` environment setting intercepts all RouterOS API connections during tests.
**Rationale**: Prevent accidental changes to physical MikroTik routers during development/testing.
**Consequences**: Tests and staging must use `ROUTER_DRY_RUN=True`. Production must have it `False`.

---

## 2026-09-24 — Incentive Engine
**Decision**: PHP 500 per referred customer whose SECOND month is paid. Cash out PHP 2,500 per 5 qualified.
**Rationale**: Aligns agent incentives with actual revenue collection, not just signups.
**Consequences**: Incentive calculations must check payment history, not just customer creation.

---

## 2026-09-24 — 60-Day Staggered Payment Lock
**Decision**: Agent-referred customers cannot use staggered payments for 60 days from first payment.
**Rationale**: Reduce risk of non-payment on new agent-referred accounts.
**Consequences**: Staggered payment options must be disabled server-side during the lock period.

---

## 2026-09-24 — Same-Person Rule (Flag, Don't Block)
**Decision**: One person handling 2+ stages of a job is flagged for admin review, not blocked.
**Rationale**: Small team may need flexibility; visibility is sufficient.
**Consequences**: Every stage records the actor. Admin dashboard shows same-person flags.

---

## 2026-09-24 — Client Unreachable Flow
**Decision**: After 3 call attempts (or refusal), job returns to Dispatch. Customer becomes "Closed - Not Installed".
**Rationale**: Prevent technicians from being stuck on unreachable clients indefinitely.
**Consequences**: Unreachable returns tracked separately from quality bounces. Customer can reopen with new job order.

---

## 2026-09-24 — Welcome SMS on First Payment
**Decision**: First payment triggers welcome SMS with portal credentials via existing SMS wrapper.
**Rationale**: Customers need portal access info immediately after paying.
**Consequences**: SMS uses message templates with `{portal_username}`, `{temp_password}`, `{portal_address}` tags. Password shown once on payment-success screen.

---

## 2026-10-01 - Persona Landing Router (Agents & Technicians Get Their Own Home)

**Decision**: `billing.views.auth.resolve_landing_url(user)` is the single
authority for where a logged-in user lands. It is used by every post-login
redirect in `unified_login_view` (both the "already authenticated" GET branch
and the successful-authenticate POST branch). One function, no per-view special
cases.

| Persona | Lands on | Shell |
|---|---|---|
| Staff / Admin / CSR / Dispatch | `dashboard` (main system) | `billing/base.html` |
| Agent | `agent_dashboard` | `billing/agent_portal/base_agent.html` |
| Technician | `technician_dashboard` | `dispatch/pipeline/portal_base_tech.html` |
| Customer | `customer_portal:portal_dashboard` | customer portal |

**Rationale**: Agents and technicians were landing in the main billing system
because the login view had no branch for them. Their *pages* were already
correctly permission-gated, but their *home* was not. A persona shell is a home,
not a permission bypass.

**Consequences**:
- The role matrix is UNCHANGED. `role_required` / `action_required` still
  govern which modules each role may open. Editing roles in the admin Role
  Editor still works exactly as before.
- An Agent given the `agents` module does NOT get raw Edit/Delete Agent. On
  their own page their only creation action is **Submit New Referral**
  (`agent_add_prospect`), which is the dispatch-flow equivalent of "add their own
  customer". Editing agent records stays Admin/Staff only.
- A Technician sees a job order only once staff has confirmed the dispatch
  ticket AND selected the team + the specific person. The `technicians=<me>` M2M
  filter is the single isolation gate, shared by `technician_dashboard` and
  `technician_mobile_view` so the two can never disagree. Technicians cannot
  see, claim, or self-assign unassigned work.
- Staff/Admin can preview any technician's board with `?tech_id=<id>`.
- Mobile-first was chosen for the Technician shell: thumb tab bar, large
  tap targets, overdue-first triage ordering.

**Not done (deliberately)**: Dispatcher and CSR personas were left on the main
system. They are cross-cutting internal roles, not field personas. If they ever
need their own landing page, add a branch to `resolve_landing_url` — do not
special-case it inside a view.

**Files**: `billing/views/auth.py`, `dispatch/views_tech.py`, `dispatch/urls.py`,
`dispatch/templates/dispatch/pipeline/portal_base_tech.html`,
`dispatch/templates/dispatch/pipeline/tech_dashboard.html`
**See also**: ERR-081 (concurrent deploy sessions bounce the stack),
ERR-088 (dead duplicate Agent Portal template).
