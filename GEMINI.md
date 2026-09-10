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
| **500 / Server Error** | `ssh root@143.198.207.144 "docker logs --tail 50 gametech-billing-system_web_1 2>&1 \| tail -30"` | Traceback → file:line → 50-line read |
| **UI broken / wrong layout** | `gametech_error_runbook.md` symptom index | Template partial → CSS selector |
| **"Where is this page?" / URL paste** | `gametech_filing_index.md` URL column | Never grep urls.py or scan dirs |
| **Data not showing / cache empty** | Redis keys: `ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli KEYS 'pattern*'"` | Then view logic |
| **Add a new feature** | `gametech_filing_index.md` Recipes section | Follow the recipe step-by-step |
| **Model/field/FK question** | `grep_search gametech_architecture_map.txt` for the model name | Never open `billing/models.py` |
| **Mikrotik / router issue** | `gametech_error_runbook.md` ERR-004 | `network_manager/services/` |
| **Payment / balance mismatch** | `gametech_error_runbook.md` ERR-005 | `billing/signals.py` → `payments.py` |

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

---

## 🚨 Quick-Reference Commands (Copy-Paste Ready)

```bash
# Check production logs (ALWAYS first for 500s)
ssh root@143.198.207.144 "docker logs --tail 50 gametech-billing-system_web_1 2>&1 | tail -30"

# Deploy to production
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"

# Restart after Python/template changes
ssh root@143.198.207.144 "docker restart gametech-billing-system_web_1"

# Check Redis cache keys
ssh root@143.198.207.144 "docker exec gametech-billing-system_redis_1 redis-cli KEYS '*pattern*'"

# Check div balance in a template
python -c "content = open('path/to/template.html', 'r', encoding='utf-8').read(); import re; o = len(re.findall(r'<div\b', content)); c = len(re.findall(r'</div>', content)); print(f'opens: {o}, closes: {c}, diff: {o-c}')"
```
