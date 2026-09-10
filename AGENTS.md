# AGENTS.md — Global AI Assistant Instructions for Gametech Unli Fiber

## Operating Mode: Aider-Style Sniper Workflow

All AI assistants (Antigravity / Gemini) working in this repository MUST follow the surgical, token-conserving guidelines below to prevent credit depletion and maximize speed across all team members:

1. **Targeted Scoping**: Focus ONLY on the specific file(s) mentioned in the user's request.
2. **Never Read Full Monolithic Files**: Use `grep_search` to find exact symbols or line numbers. Never dump or view full 500+ line files without slice constraints (`StartLine`/`EndLine`).
3. **Use the Architecture Map**: Use `gametech_architecture_map.txt` (~2,000 lines / ~8.5k tokens) for data models, routes, tasks, and system contracts instead of scanning hundreds of repository files.
4. **Surgical Edits**: Use targeted replacements (`replace_file_content`) to swap only the lines being changed — never rewrite whole files.
5. **No Clutter**: Do not create loose test scripts in the root directory. Use `archived_scripts/` or clean up temporary files immediately.
