# PM2 Setup Guide

> **Note:** This is the **manual installation guide**.
The installer (`install.bat`) handles everything here automatically. Only follow these steps if you're setting up manually.

Deploy with PM2 for 24/7 operation on low-resource machines (4 GB RAM mini PCs, etc.).

The backend serves both the API and the built frontend — only **one PM2 process** needed.

---

## 1. Prerequisites

- **Node.js 20 LTS** — [nodejs.org](https://nodejs.org/)
- **PostgreSQL 16.14** — [postgresql.org](https://www.postgresql.org/download/)
- **npm** (ships with Node.js)

### PostgreSQL Install Tips

During installation, only select:
- ✅ **PostgreSQL Server**
- ✅ **Command Line Tools**

Uncheck:
- ❌ pgAdmin 4
- ❌ Stack Builder

Remember your password, we will need it later.

---

## 2. Quick Install via install.bat

`install.bat` — it does everything automatically:

1. Right-click `install.bat` → **Run as Administrator**
2. Enter the PostgreSQL admin **password** when prompted
3. Enter your desired **port** for the dispatch website
4. Enter your desired path for **Backup files** dump. (External storage recomended)
3. Wait 5–10 minutes — done, copy the link procided to access the deployed dispatch.

The installer detects your IP, sets up the database, installs all dependencies, builds, migrates, seeds, and configures PM2 with auto-start on boot.

---

## 3. Manual Installation

### 3.1 Get the Project

copy via USB / SCP from another machine.

---

## 3. Install PM2

```bash
npm install -g pm2
```

---

## 4. Configure Environment

```bash
copy backend\.env.example backend\.env
```

Edit `backend\.env`:

```env
DATABASE_URL=postgresql://dispatch:your-password@localhost:5432/dispatch_db
PORT=5502
NODE_ENV=production
JWT_SECRET=your-long-random-secret
CORS_ORIGINS=http://192.168.x.x:5502   # replace with actual IP
```

Get your IP with `ipconfig`, look for `IPv4 Address`.

---

## 5. Install Dependencies & Build

```bash
# Install all dependencies
npm install

# Generate Prisma client
npx prisma generate --schema=backend/prisma/schema.prisma

# Build (compiles backend TS + builds frontend)
npm run build
```

---

## 6. First-Time Database Setup

```bash
# Run migrations (creates tables)
npx prisma migrate deploy --schema=backend/prisma/schema.prisma

# Seed config options (idempotent — skips existing)
node backend/dist/prisma/seedConfigOptions.js

# Seed admin accounts (idempotent — skips existing)
node backend/dist/prisma/seedSuperAdmin.js
```

---

## 7. Start with PM2

```bash
# Start the app
pm2 start ecosystem.config.js

# Save process list (needed for auto-start on reboot)
pm2 save

```
> **When to re-save?** Only if you add/delete a process (`pm2 start`, `pm2 delete`) or change `ecosystem.config.js`. Restarting or stopping does not require re-saving — the saved dump persists across reboots.
---

## 8. Auto-Start on Boot

### On Linux

```bash
pm2 startup   # generates systemd service
```

### On Windows

`pm2 startup` does **not** work on Windows. Use this instead:

```bash
npm install -g pm2-windows-startup
pm2-startup install
```

This registers PM2 as a Windows service.

---

## 9. Access

```
http://your-mini-pc-ip:5502
```

Find your IP with:

```bash
ipconfig
```

Look for `IPv4 Address` under your active adapter (e.g., `192.168.200.172`).

---

## Common PM2 Commands

| Command | What it does |
|---|---|
| `pm2 status` | List running processes |
| `pm2 logs dispatch-backend` | View backend logs (live tail) |
| `pm2 logs dispatch-backend --lines 50` | View last 50 lines |
| `pm2 flush` | Clear all log files |
| `pm2 restart dispatch-backend` | Restart the app |
| `pm2 stop all` | Stop everything |
| `pm2 delete all` | Remove processes from PM2 |
| `pm2 monit` | Live CPU / memory dashboard |
| `pm2 save` | Save current process list |
| `pm2 startup` | Generate boot startup script (Linux only) |
| `pm2 describe dispatch-backend` | Show detailed process info |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Cannot find module` / PM2 fails to start | Check `ecosystem.config.js` — `script` must be `./dist/src/index.js` (not `./dist/index.js`). Run `npm run build` |
| `ENOENT: backend/frontend/dist/index.html` | The compiled JS has the wrong relative path. Edit `backend/src/index.ts`, change both occurrences of `../../frontend/dist` to `../../../frontend/dist`. Then `npm run build` and `pm2 restart` |
| Blank page or 500 on `/` | Frontend files not found — run `npm run build` and check the path fix above |
| Port 5502 already in use | Change `PORT` in `backend/.env` and restart PM2 |
| `pg_dump` / `psql` not found | Set `PG_DUMP_PATH`, `PSQL_PATH` in `backend/.env` to the full executable path |
| `pm2 startup` returns `Init system not found` | You're on Windows — use `pm2-windows-startup` instead (section 8) |
| Old errors still show in logs | Run `pm2 flush` to clear stale log history |
