# AGENTS.md — Global AI Assistant Protocol (Minified)

> **MANDATE**: You are a sniper. No exploratory scans. Strictly adhere to these rules to save tokens and prevent context bloat.
> **PROMPT TRANSLATION**: When a user gives a vague prompt (e.g., "counter broken"), do NOT ask for files. You MUST internally intercept, check `gametech_filing_index.md` (UI→API Map) to find the file, and jump directly there.

## ⚡ 1. CORE DIRECTIVES (Zero-Scan Law)
1. **Freshness Law**: `git pull origin main` FIRST.
2. **Zero-Scan**: NO `list_dir`, NO broad `grep`, NO reading >80 lines.
3. **Log-First Debugging**: For 500s: `ssh root@143.198.207.144 "docker logs --since 2m gametech-billing-system_web_1 2>&1 | tail -40"`. Read traceback BEFORE opening code.
4. **No Git Archeology**: DO NOT use `git log`, `reflog`, or `blame`. Rely on current file state.
5. **No Blind Guesses**: Max 2 attempts. Ask user if stuck.
6. **Deploy Sync**: Single commit/push → `ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"`. Restart python container or run `collectstatic` as needed.

## 🔀 2. TRIAGE ROUTER (Check FIRST)
| Request Type | Immediate AI Action |
|---|---|
| **500 Error** | Read Docker Logs (see command above) |
| **UI broken / Layout** | Check `gametech_error_runbook.md` |
| **"Where is this URL?"** | Check `gametech_filing_index.md` URL map |
| **Data not showing** | Check Redis cache (see Registry below) |
| **Zombie Data** | Check if logout/delete view forgot `cache.delete()` |
| **API returns wrong data** | `curl` endpoint first, compare with JS `fetch()` |
| **Model/field question** | `grep_search` in `gametech_architecture_map.txt` |

## 🗃️ 3. CACHE SYNC MANDATE & REGISTRY
**MANDATE**: Editing Login/Logout/Delete? YOU MUST explicitly delete Redis keys. Do not rely on Django session.
**REGISTRY**: Run `ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli GET 'key'"`
- `active_portal_customers`: Dict of logged-in portal users (600s TTL).
- `seen_customer_{id}`: Portal customer heartbeat (300s TTL).
- `seen_user_{id}`: Staff heartbeat (30 days TTL).
- `live_monitoring_data`: Mikrotik API payload (30s TTL).
- `dashboard_stats_{date}`: Daily stats (300s TTL).

## 🧼 4. ARCHITECTURE & HYGIENE
- **Orchestrators**: Templates < 400 lines. Use `{% include %}` for isolated partials.
- **Div Balance**: Verify `<div\b` == `</div>` when editing modals. No nested modals.
- **Transactions**: Financial edits require `transaction.atomic()` + `select_for_update()`.
- **JS Delegation**: For dynamic elements: `$(document).on('change', '#id', handler)`.
- **DANGER FILES**: `billing/models.py`, `gametech_architecture_map.txt`, `layout_and_darkmode.css` are MASSIVE. Use `grep_search` ONLY. Never open fully.
