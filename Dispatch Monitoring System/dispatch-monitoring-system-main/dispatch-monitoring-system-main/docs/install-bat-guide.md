# .BAT Files User Guide (Windows)

---

## 1. install.bat — First-Time Setup

Run this **once** on a brand-new machine to install everything from scratch.

### Before You Begin

You need to install these **first** before running the installer:

#### 1. Install Node.js 20+

- Go to [nodejs.org](https://nodejs.org/) and download the **LTS** version (20.x).
- Run the installer — just click Next through everything, defaults are fine.
- After install, open **Command Prompt** and type `node -v` to verify it shows `v20.x.x`.

#### 2. Install PostgreSQL 16+

- Go to [postgresql.org](https://www.postgresql.org/download/) and download version 16+ for Windows.
- Run the installer.
- **IMPORTANT:** During installation:
  - Set a password for the `postgres` user — **remember this password**, you'll need it later.
  - Make sure **"PostgreSQL Server"** and **"Command Line Tools"** is checked (it's usually on by default).
- Keep the default port (5432) unless you have a reason to change it.

#### 3. Internet Connection

The installer downloads packages from the internet, so make sure you're connected.

### What the Installer Does (Step by Step)

1. **Checks prerequisites** — Verifies Node.js and PostgreSQL CLI are installed.
2. **Sets up the database** — Asks for your PostgreSQL admin password, then creates a user (`dispatch`) and database (`dispatch_db`).
3. **Configures the app** — Detects your PC's local IP, asks for a web port (default 5502), generates a JWT secret, and asks where to save backups.
4. **Installs dependencies** — Downloads all required npm packages (takes a few minutes).
5. **Generates Prisma client** — Prepares the database layer.
6. **Builds the app** — Compiles backend and frontend code.
7. **Runs database migrations & seeds** — Creates tables and adds initial data (including the super admin account).
8. **Sets up PM2** — Installs PM2 globally, starts the app, and optionally registers it to auto-start when Windows boots.

### When It's Done

Open your browser and go to `http://YOUR_IP:5502` (or whatever port you chose).

Login with the super admin credentials created during seeding.

### Note on PM2 Setup

The installer handles PM2 automatically — it installs it, starts the app, and sets it to auto-start on boot. You don't need to do anything manually. If you prefer to set it up manually instead, see the [Manual Setup Guide](manual-setup.md).

---

## 2. change-port.bat — Changing IP / Port

Run this if you move to a different network or want to use a different port number.

### When to Use

| Scenario | Why |
|---|---|
| Your PC got a new IP address | The app won't be reachable at the old IP |
| You want a different port | e.g., port 5502 is already in use |
| You moved to a different network | The IP address changes |
| You changed your network adapter | The auto-detected IP might differ |

### How to Use

1. **Double-click `change-port.bat`** or run it from the project folder.
2. It shows your current IP and port.
3. Choose what to change:
   - `1` — IP address only
   - `2` — Port number only
   - `3` — Both IP and port
4. Enter the new value(s):
   - IP must be in format `xxx.xxx.xxx.xxx` (e.g., `192.168.1.14`)
   - Port must be a number between 1 and 65535 (e.g., `5502`)
5. Review the summary showing old vs. new values.
6. Say `Y` when asked to restart PM2 (recommended).
7. Done — the app is now running on the new IP/port.

### After Changing

Update any browser bookmarks or shortcuts that point to the old address.

---

## Important Notes

- The 2 scripts are **Windows-only**.
- They are **safe to run multiple times** (idempotent) — running `install.bat` again won't break anything.
- If something fails, read the error message carefully — most errors tell you exactly what's missing.
