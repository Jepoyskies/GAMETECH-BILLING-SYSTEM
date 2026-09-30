#!/usr/bin/env bash
# Serialise every `docker compose` invocation on the droplet behind a file lock.
#
# WHY: ERR-069 / ERR-075. Two sessions calling `docker compose up -d` at the same
# time each recreate the other's containers mid-flight, which leaves the web,
# celery and celery-beat containers sitting in `Created` state. `restart:
# unless-stopped` does NOT rescue a container that has never started, so the
# stack stays dark until someone notices. We hit exactly this on 2026-09-30.
#
# USAGE (always prefer this over bare `docker compose ...`):
#   ssh root@143.198.207.144 "/root/GAMETECH-BILLING-SYSTEM/scripts/safe_compose.sh up -d"
#
# Routine code deploys should still use `docker restart gametech-web` (AGENTS.md
# Rule 32v2) and do not need this script at all.

set -euo pipefail

LOCK_FILE=/var/lock/gametech-compose.lock
COMPOSE_DIR=/root/GAMETECH-BILLING-SYSTEM

# Refuse to run from the wrong directory: compose derives the project name from
# the working directory, and a mismatch creates a second project that fights
# over ports.
cd "$COMPOSE_DIR"

# -w waits instead of failing immediately, so a queued deploy still lands.
exec 9>"$LOCK_FILE"
if ! flock -w 600 9; then
  echo "ERROR: another compose operation is still running after 10 minutes." >&2
  exit 1
fi

docker compose "$@"
