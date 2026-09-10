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

5. **The Orchestrator Pattern & 400-Line Circuit Breaker**:
   - Template files, scripts, and Python view files must not exceed 400 lines.
   - **Just-In-Time Operation Cleanup**: If any file touched exceeds 400 lines, do NOT add more code to it. Split it into focused partials under 250 lines (`{% include %}` or sub-modules) with `diff: 0` tag parity before completing the task. Never scan the whole repo to split files; only clean files naturally touched by ongoing tasks.

6. **Automatic Production Deployment**:
   - Once verified locally:
     1. Stage and commit with conventional message (`feat(...)`, `fix(...)`).
     2. `git push origin main`
     3. `ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"`
     4. If Python/templates changed: `ssh root@143.198.207.144 "docker restart gametech-billing-system_web_1"`
     5. If static CSS/JS changed: `ssh root@143.198.207.144 "docker exec gametech-billing-system_web_1 python manage.py collectstatic --noinput"`

7. **3-Step Escalation & No-Repeat Failures**:
   - Step 1: `grep_search` for the exact symbol → Step 2: Read 50–80 line slice → Step 3: **STOP** and ask user for browser console error or exact URL.
   - **FORBIDDEN**: Continuing past 3 steps by opening additional files or running broad scans.
   - Max 2 attempts per approach. If same fix fails twice, pivot to a different strategy or escalate to user.

8. **Template Include-Chain Verification**:
   - When creating or editing a template partial (e.g. `_modal_ticket.html`), **ALWAYS verify** it is actually `{% include %}`'d in a parent template using `grep_search`.
   - If it's not included anywhere → add the `{% include %}` tag. Otherwise the partial is dead code.
