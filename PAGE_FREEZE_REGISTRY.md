# PAGE_FREEZE_REGISTRY.md — Frozen Pages (NEVER EDIT)

> **PURPOSE**: Single source of truth for all pages that are permanently frozen.  
> **Rule**: If a page is listed here, DO NOT edit, restyle, refactor, or touch it as a side-effect of any task.  
> **Verify before committing**: `git diff --stat -- <frozen-paths>` must be EMPTY.

---

## Frozen Pages

| Page | Protected Paths | Reason |
|---|---|---|
| **Login** | `billing/templates/billing/login.html`, `billing/views/auth.py` (login view only) | Hand-authored design baseline |
| **Live Monitoring** | `billing/templates/billing/live_monitoring/` (entire directory), `billing/views/live_monitoring.py`, `billing/views/api/network.py` (monitoring endpoints only) | Hand-authored design baseline |
| **Dashboard** | `billing/templates/billing/dashboard/`, `billing/templates/billing/dashboard.html` | Visual baseline owned by another contributor |

---

## Allowed Exceptions

- Reading frozen pages to extract design values (colors, fonts, radii) for use on OTHER pages
- Fixing a confirmed production 500 error pinpointed by docker logs to an exact line (backend logic only — never templates/CSS)

---

## Verify Before Committing

```bash
# Must be EMPTY for any UI task
git diff --stat -- billing/templates/billing/login.html billing/templates/billing/live_monitoring/ billing/templates/billing/dashboard/ billing/templates/billing/dashboard.html
```
