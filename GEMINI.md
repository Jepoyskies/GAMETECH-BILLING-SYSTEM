# GEMINI.md — Gametech Smart Triage Router & Protocol Reference

This workspace strictly adheres to the protocols defined in:
- **`AGENTS.md`**: Master sniper debugging protocol, token conservation laws, and architectural guidelines.
- **`gametech_filing_index.md`**: Master file locator matrix and standardized coding recipes.
- **`gametech_error_runbook.md`**: Incident and symptom triage matrix (check FIRST for any bug).
- **`gametech_architecture_map.txt`**: Model relationships, URL routes, background tasks, and Mikrotik contracts (**grep only, never read fully — 83KB**).

---

## 🔀 Triage Router (What to Check FIRST Based on Request Type)

| Request Type | Check FIRST | Then |
|---|---|---|
| **500 / Server Error** | `ssh root@143.198.207.144 "docker logs --since 2m gametech-billing-system_web_1 2>&1 \| tail -40"` | Traceback → file:line → 50-line read |
| **UI broken / wrong layout** | `gametech_error_runbook.md` symptom index | Template partial → CSS selector |
| **"Where is this page?" / URL paste** | `gametech_filing_index.md` URL column | Never grep urls.py or scan dirs |
| **Data not showing / cache empty** | Redis keys: `ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli KEYS 'pattern*'"` | Then view logic |
| **API returns wrong/empty data** | `curl` the endpoint directly to see raw JSON shape | Compare with frontend JS `fetch()` handler |
| **Add a new feature** | `gametech_filing_index.md` Recipes section | Follow the recipe step-by-step |
| **Model/field/FK question** | `grep_search gametech_architecture_map.txt` for the model name | Never open `billing/models.py` |
| **Mikrotik / router issue** | `gametech_error_runbook.md` ERR-004 | `network_manager/services/` |
| **Payment / balance mismatch** | `gametech_error_runbook.md` ERR-005 | `billing/signals.py` → `payments.py` |
| **Static CSS/JS not updating in prod** | Was `collectstatic` run? Check browser cache (Ctrl+Shift+R) | Then check file path in template `{% static %}` tag |
| **New page / feature request** | `gametech_filing_index.md` Recipes section | Follow orchestrator pattern for templates |
| **Permission / 403 error** | Check `@login_required` and `user.is_staff` in the view | Then check URL routing order in `urls.py` |
| **Zombie Data (Logged out but showing, deleted but visible, stale count)** | Check Redis: `ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli GET 'key_name'"` — use AGENTS.md Rule #23 Registry to find key name | Inspect the Logout/Delete/Disable view to see why it failed to `cache.delete()` or remove from dict |

---

## ⚡ Core Directives for All AI Sessions:
1. **Always `git pull origin main` First**: Never work on stale branches.
2. **Zero-Scan Debugging**: Never run broad directory searches or open unrelated files.
3. **Check the Error Runbook First**: Cross-reference symptoms with `gametech_error_runbook.md`.
4. **Targeted Reads (50–80 Lines Max)**: Use `grep_search` and slice parameters.
5. **Surgical In-Place Edits**: Only modify lines needing changes.
6. **Automatic Deployment Sync**: Commit, push to `origin main`, pull on the production droplet (`143.198.207.144`), and restart container if necessary.
7. **Runbook Enrichment**: Document newly solved errors into `gametech_error_runbook.md`.
8. **No Repeat Failures**: Max 2 attempts per approach. If same fix fails twice, escalate to user.
9. **Batch Deploys**: For multi-file tasks, make ALL edits → single commit → single push → single restart.
10. **Verify API Contracts**: Before rewriting backend logic, `curl` the API to see actual response shape.
11. **No Git Archeology**: Never run `git log`, `git reflog`, `git diff`, or `git blame` to understand features. See AGENTS.md Rule #22.
12. **Cache Sync on State Changes**: Verify Redis invalidation when editing Login/Logout/Delete views. See AGENTS.md Rule #21.
13. **400-Line Circuit Breaker**: When touching a file > 400 lines, split into < 250 line partials before completing the task. See AGENTS.md Rule #24.

---

## 🚨 Quick-Reference Commands (Copy-Paste Ready)

```bash
# Check production logs — time-bounded (PREFERRED for recent 500s)
ssh root@143.198.207.144 "docker logs --since 2m gametech-billing-system_web_1 2>&1 | tail -40"

# Check production logs — tail-based (when timing is unknown)
ssh root@143.198.207.144 "docker logs --tail 50 gametech-billing-system_web_1 2>&1 | tail -30"

# Deploy to production
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"

# Restart after Python/template changes
ssh root@143.198.207.144 "docker restart gametech-billing-system_web_1"

# Collectstatic after CSS/JS changes (MANDATORY)
ssh root@143.198.207.144 "docker exec gametech-billing-system_web_1 python manage.py collectstatic --noinput"

# Check Redis cache keys
ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli KEYS '*pattern*'"

# Inspect a specific Redis cache value
ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli GET 'active_portal_customers'"

# Check div balance in a template
python -c "content = open('path/to/template.html', 'r', encoding='utf-8').read(); import re; o = len(re.findall(r'<div\b', content)); c = len(re.findall(r'</div>', content)); print(f'opens: {o}, closes: {c}, diff: {o-c}')"

# Verify API response shape (replace URL as needed)
ssh root@143.198.207.144 "curl -s http://localhost:8000/api/endpoint/ | python3 -m json.tool | head -20"
```

---

## 🔗 Dynamic UI → API Data Source Map

> **Rule**: When a user reports a broken widget, stale counter, or "data not showing" in a specific UI element, look up the element here FIRST. Jump directly to the API endpoint — **NEVER** read the HTML template or JS file to find the `fetch()` URL.

| UI Element (Location) | JS Fetch Function | API Endpoint | Backend Handler |
|---|---|---|---|
| Online Staff Dropdown (`_topbar.html`) | `fetchOnlineStaff()` in `_scripts.html` | `/api/online-staff/` | `billing/views/auth.py → online_staff_api` |
| Live Monitoring Hero Stats (`_hero.html`) | `fetchLiveMonitoringData()` | `/api/live-monitoring/` | `billing/views/api/dashboard.py → live_monitoring_api` |
| Customer Portal Active Sessions (topbar badge) | `fetchOnlineStaff()` (combined) | `/api/online-staff/` | `billing/views/auth.py → online_staff_api` (portal_customers section) |
| Dashboard Stats Cards | Page load (server-rendered) | N/A (context variable) | `billing/views/dashboard.py → dashboard_view` |
| Router Uplink Status Dots | `fetchUplinkStatus()` | `/api/router-uplink-status/` | `billing/views/api/network.py` |
