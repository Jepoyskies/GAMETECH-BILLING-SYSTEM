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
