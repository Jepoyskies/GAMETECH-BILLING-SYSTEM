# SESSION_STARTUP.md — AI Session Orientation Checklist

> **PURPOSE**: Give any AI assistant immediate orientation in under 30 seconds. Read this file FIRST before any task.

> **RESUMING WORK?** Read `SESSION_HANDOFF.md` first — it records the open
> problems, decisions needed, and hard rules from the previous session.

---

## 30-Second Orientation (READ THIS FIRST)

1. **Project**: Gametech Unli Fiber — ISP billing, subscriber management, dispatch, MikroTik network ops
2. **Stack**: Django 6.1, PostgreSQL 15, Redis 7, Celery, Bootstrap 5, jQuery
3. **Production**: `ssh root@143.198.207.144` — container `gametech-web`
4. **Master Rules**: `AGENTS.md` (39 rules — sniper debugging, token conservation)
5. **File Locator**: `gametech_filing_index.md` (never grep urls.py or scan dirs)
6. **Error Triage**: `gametech_error_runbook.md` (check FIRST for any bug)
7. **Architecture**: `gametech_architecture_map.txt` (grep only, never read fully)
8. **Business Spec**: `docs/SPEC.md` (dispatch flow, agent rules, billing logic)
9. **Frozen Pages**: `PAGE_FREEZE_REGISTRY.md` (never edit these)
10. **Decision Log**: `DECISION_LOG.md` (architectural decisions — don't re-litigate)
11. **Unfinished Work**: `docs/ai_tracking/HANDOFF.md` (read FIRST if it exists — what the last session left open)

---

## Quick Command Reference

```bash
# Deploy to production
git add -A; git commit -m "fix(...)"; git push origin main
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"
ssh root@143.198.207.144 "docker restart gametech-web"

# Check logs for 500 errors
ssh root@143.198.207.144 "docker logs --since 2m gametech-web 2>&1 | tail -40"

# Python syntax check (local, zero deps)
python -m py_compile path/to/file.py

# Static files deploy
ssh root@143.198.207.144 "docker exec gametech-web python manage.py collectstatic --noinput"

# Redis check
ssh root@143.198.207.144 "docker exec gametech-redis redis-cli KEYS 'pattern*'"
```

---

## File Priority Order (Read Only What You Need)

| Task | Read This | NEVER Do |
|---|---|---|
| Any bug | `gametech_error_runbook.md` | Guess by reading code |
| URL → file lookup | `gametech_filing_index.md` | Grep urls.py |
| Model fields/FK | grep `gametech_architecture_map.txt` | Open models.py |
| New feature | `gametech_filing_index.md` Recipes | Start from scratch |
| Business logic | `docs/SPEC.md` | Guess the rules |
| Frozen pages | `PAGE_FREEZE_REGISTRY.md` | Edit frozen files |
| Picking up unfinished work | `docs/ai_tracking/HANDOFF.md` | Re-do what the last session already shipped |
