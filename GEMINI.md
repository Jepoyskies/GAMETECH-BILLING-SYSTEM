# GEMINI.md — Gametech Sniper Workflow & Protocol Reference

This workspace strictly adheres to the protocols defined in:
- **`AGENTS.md`**: Master sniper debugging protocol, token conservation laws, and architectural guidelines.
- **`gametech_filing_index.md`**: Master file locator matrix and standardized coding recipes.
- **`gametech_error_runbook.md`**: Incident and symptom triage matrix.
- **`gametech_architecture_map.txt`**: Model relationships, URL routes, background tasks, and Mikrotik contracts.

## ⚡ Core Directives for All AI Sessions:
1. **Always `git pull origin main` First**: Never work on stale branches.
2. **Zero-Scan Debugging**: Never run broad directory searches or open unrelated files.
3. **Check the Error Runbook First**: When debugging, cross-reference symptoms with `gametech_error_runbook.md`.
4. **Targeted Reads (50–80 Lines Max)**: Use `grep_search` and slice parameters.
5. **Surgical In-Place Edits**: Only modify lines needing changes.
6. **Automatic Deployment Sync**: Commit, push to `origin main`, pull on the production droplet (`143.198.207.144`), and restart container if necessary.
7. **Runbook Enrichment**: Document newly solved errors into `gametech_error_runbook.md`.
