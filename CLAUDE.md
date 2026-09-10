# CLAUDE.md — Gametech Billing System Protocol

All Claude Code and Anthropic Claude assistants operating in this repository **MUST** strictly follow the master protocols defined in:
- **`AGENTS.md`**: Master sniper debugging protocol, token conservation laws, and architectural guidelines.
- **`gametech_filing_index.md`**: Master file locator matrix and standardized coding recipes (URL → View → Template map).
- **`gametech_error_runbook.md`**: Incident and symptom triage matrix (check FIRST for any bug).

---

## ⚡ Core Rules for Claude

1. **The Freshness Law (`git pull origin main` First)**:
   - Before editing or diagnosing code on ANY task, run `git pull origin main`. Multiple team members work across devices.

2. **The Ponytail Mandate (Write Less, Delete More)**:
   - Before writing or editing code, stop at the first rung that holds:
     1. *YAGNI*: Reject unneeded abstractions, wrappers, and boilerplate.
     2. *Reuse*: Check for existing helpers/patterns in the codebase before writing new logic.
     3. *Stdlib/Native First*: Use Python, Django, or browser built-ins before custom helpers or libraries.
     4. *Shortest Working Diff*: One line before ten. Deletion over addition. Fix root cause once at source.

3. **Zero-Scan Debugging (Save Credits)**:
   - **FORBIDDEN**: Broad directory scans, file searches, or reading 100+ line files without slice constraints.
   - Read **ONLY** the localized slice (50–80 lines max) using grep.
   - For 500 errors, inspect production logs first:
     ```bash
     ssh root@143.198.207.144 "docker logs --since 2m gametech-billing-system_web_1 2>&1 | tail -40"
     ```

4. **URL-To-File Fast Map**:
   - When a user provides a URL, look up the target files in `gametech_filing_index.md`. Never grep `urls.py` or scan template directories.

5. **The Orchestrator Pattern**:
   - Template files and Python view files must not exceed 400 lines. Break large UI pages into modular partials (`_hero.html`, `_scripts.html`, `_styles.html`).

6. **Automatic Production Deployment**:
   - Once verified locally:
     1. Stage and commit with conventional message (`feat(...)`, `fix(...)`).
     2. `git push origin main`
     3. `ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"`
     4. If Python/templates changed: `ssh root@143.198.207.144 "docker restart gametech-billing-system_web_1"`
     5. If static CSS/JS changed: `ssh root@143.198.207.144 "docker exec gametech-billing-system_web_1 python manage.py collectstatic --noinput"`
