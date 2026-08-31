# Installer & Config Guide

2 batch scripts to simplify deployment on Windows:

- `install.bat` — First-time setup (run once)
- `change-port.bat` — Change IP address or port

---

## install.bat

Run as Administrator on the target machine. Does everything automatically.

### Flow

```
┌─ Start ─────────────────────────────────────────────────┐
│                                                         │
│  1. Check Admin Rights                                  │
│     └─ Must be "Run as Administrator"                   │
│                                                         │
│  2. Check Prerequisites                                 │
│     ├─ Node.js 20+ (from PATH)                          │
│     ├─ npm (bundled with Node.js)                       │
│     ├─ Git (warn only if missing)                       │
│     └─ PostgreSQL CLI tools (from PATH)                 │
│         (psql, pg_dump, pg_restore)                     │
│         └─ FAIL with [ERROR] if any critical is missing │
│                                                         │
│  3. Database Setup                                      │
│     ├─ Prompt: PostgreSQL admin password                 │
│     ├─ Verify admin credentials (psql SELECT 1)         │
│     ├─ Check if user 'dispatch' exists (pg_roles)       │
│     ├─ Check if database 'dispatch_db' exists            │
│     │                                                    │
│     ├─ If BOTH exist:                                    │
│     │   ├─ Prompt: dispatch user password                │
│     │   └─ Verify password (psql -U dispatch)            │
│     │                                                    │
│     └─ If EITHER missing:                                │
│         ├─ Prompt: dispatch user password (default:      │
│         │   dispatch123)                                  │
│         ├─ CREATE USER dispatch WITH PASSWORD             │
│         ├─ CREATE DATABASE dispatch_db OWNER dispatch     │
│         └─ GRANT ALL on schema, tables, sequences        │
│                                                         │
│  4. Configuration                                       │
│     ├─ Detect IP from ipconfig                          │
│     ├─ Prompt: Server IP (default: detected IP)         │
│     ├─ Prompt: Web dashboard port (default: 5502)       │
│     │   └─ Validates: digits only, 1-5 chars, 1-65535  │
│     ├─ Generate random JWT secret                       │
│     ├─ Prompt: Backup folder path                       │
│     │   (default: .\backups)                            │
│     ├─ Write root .env                                  │
│     └─ Write backend\.env                               │
│         (DATABASE_URL, PORT, CORS, PG tool paths)       │
│                                                         │
│  5. Install Dependencies                                │
│     ├─ npm install --audit=false (root)                  │
│     ├─ npm install --prefix backend --audit=false        │
│     ├─ npm install --prefix frontend --audit=false       │
│     └─ FAIL with [ERROR] if any install fails           │
│                                                         │
│  6. Prisma Generate                                     │
│     ├─ cd backend && npx prisma generate && cd ..       │
│     └─ FAIL with [ERROR] if generation fails            │
│                                                         │
│  7. Build                                               │
│     ├─ npm run build (backend TS + frontend)            │
│     └─ FAIL with [ERROR] if build fails                 │
│                                                         │
│  8. Database Migrations & Seeds                         │
│     ├─ cd backend && npx prisma migrate deploy          │
│     │   && cd ..                                        │
│     ├─ node seedConfigOptions.js                        │
│     ├─ node seedSuperAdmin.js                           │
│     └─ FAIL with [ERROR] if migration fails             │
│                                                         │
│  9. PM2 Setup                                           │
│     ├─ mkdir logs                                       │
│     ├─ npm install -g pm2                               │
│     ├─ pm2 start ecosystem.config.js                    │
│     ├─ pm2 save                                         │
│     ├─ npm install -g pm2-windows-startup               │
│     │   └─ [WARN] if install fails (continues)          │
│     └─ pm2-startup install                              │
│         └─ [WARN] if fails (app still runs, just no     │
│             auto-start on reboot)                       │
│                                                         │
│  Done ── App running at http://ip:{port} (default 5502) │
└─────────────────────────────────────────────────────────┘
```

### What the user needs to provide

| Prompt | When | Example |
|---|---|---|
| PostgreSQL admin password | Always | `postgres` |
| Dispatch user password | If user+db exist: verify. If missing: set new | `dispatch123` |
| Server IP | Only if auto-detect fails (169.254.x.x) | `192.168.1.14` |
| Web dashboard port | Always (default: 5502) | `5502` |
| Backup folder path | Always (default: .\backups) | `D:\Backups` |

### Files created

| File | Purpose |
|---|---|
| `backend\.env` | Backend configuration |
| `backups\` | Default backup directory |

---

## change-port.bat

Run when you need to change the server IP or port. Shows current values, prompts for new ones, and updates all config files.

### Flow

```
┌─ Start ─────────────────────────────────────────────────┐
│                                                         │
│  1. Detect current values                               │
│     ├─ Read SERVER_IP from .env                         │
│     └─ Read PORT from backend\.env                      │
│                                                         │
│  2. Ask what to change                                  │
│     ├─ [1] IP address only                              │
│     ├─ [2] Port number only                             │
│     └─ [3] Both IP and Port                             │
│                                                         │
│  3. Ask for new value(s)                                │
│     ├─ IP: validates format (xxx.xxx.xxx.xxx)           │
│     └─ Port: validates digits only, 1-65535             │
│                                                         │
│  4. Update .env files                                  │
│     ├─ Update SERVER_IP in root .env (if IP changed)    │
│     ├─ Update PORT in backend\.env (if port changed)    │
│     └─ Update CORS_ORIGINS in backend\.env              │
│                                                         │
│  5. Summary                                             │
│     └─ Show old → new values                            │
│                                                         │
│  6. Restart PM2 (optional)                              │
│     ├─ Prompt: Restart now? (Y/n)                       │
│     └─ pm2 restart dispatch-backend                     │
│                                                         │
│  Done ── Config updated, PM2 restarted                  │
└─────────────────────────────────────────────────────────┘
```

### When to run

| Scenario | Run |
|---|---|
| PC IP address changed | `change-port.bat` |
| Want to use different port | `change-port.bat` |
| Moving to different network | `change-port.bat` |

### What the user needs to provide

| Prompt | When | Example |
|---|---|---|
| What to change | Always | `1`, `2`, or `3` |
| New IP address | If IP selected | `192.168.1.14` |
| New port number | If port selected | `5502` |
| Restart PM2? | Always (default: Y) | `Y` or `n` |

---

## Requirements

### install.bat

| Check | Why | Auto-fail |
|---|---|---|
| Administrator rights | Create DB, install services | Yes |
| Node.js 20+ (in PATH) | Run the app | Yes |
| npm (bundled with Node.js) | Install dependencies | Yes |
| PostgreSQL 16+ CLI (in PATH) | Create DB, backups | Yes |
