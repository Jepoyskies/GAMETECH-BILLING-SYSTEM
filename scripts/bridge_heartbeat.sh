#!/usr/bin/env bash
# Bridge heartbeat — reports the office Mini PC's REAL Tailscale state to Django.
#
# WHY THIS RUNS ON THE HOST AND NOT IN A CONTAINER:
#   The cloud reaches the MikroTik routers *through* the Mini PC's Tailscale
#   subnet route, so "no router answered" cannot tell a dead Mini PC from a
#   dead office uplink/repeater — they look identical from the droplet.
#   This script closes that gap by asking Tailscale directly whether the Mini PC
#   peer is actually online.
#   It MUST run on the host: Tailscale's LocalAPI resolves peer credentials in
#   the host PID namespace and returns HTTP 403 to container callers, so
#   `tailscale status` from inside gametech-web / gametech-celery always fails.
#
# INSTALL (on the droplet, as root):
#   1. Generate a token and add it to docker-compose.yml:
#        BRIDGE_HEARTBEAT_TOKEN=<paste>
#      under the `web:` service's environment block (same for `celery:`).
#   2. Copy this file to /root/bridge_heartbeat.sh and chmod +x it.
#   3. Add the token to /root/.bridge_token (chmod 600) and export the URL:
#        printf '%s' '<same token>' > /root/.bridge_token
#   4. crontab -e  ->  (run every 30s)
#        * * * * * /root/bridge_heartbeat.sh >/dev/null 2>&1
#
# The endpoint fails CLOSED (503) if BRIDGE_HEARTBEAT_TOKEN is unset, so a
# missing config can never be worked around by posting garbage to it.

set -uo pipefail

BRIDGE_URL="${BRIDGE_URL:-http://127.0.0.1:8000/billing/api/bridge/heartbeat/}"
TOKEN_FILE="${TOKEN_FILE:-/root/.bridge_token}"

# Tailscale peer state. Falls back to empty JSON if tailscale is missing so we
# report offline rather than crashing every 30 seconds.
TS_JSON="$(tailscale status --json 2>/dev/null || echo '{}')"

# The bridge is the peer advertising our router subnet (192.168.88.0/24). If
# several peers advertise it, prefer the one that is online.
PAYLOAD="$(BRIDGE_SUBNET="${BRIDGE_SUBNET:-192.168.88.0/24}" python3 - "$TS_JSON" <<'PY'
import json, os, sys

subnet = os.environ["BRIDGE_SUBNET"]
try:
    data = json.loads(sys.argv[1] or "{}")
except ValueError:
    data = {}

peers = list((data.get("Peer") or {}).values())
# Routers we poll live behind whichever peer advertises the subnet.
routers = [p for p in peers if subnet in (p.get("PrimaryRoutes") or [])]
candidates = routers or peers
# Prefer online, then most recently seen.
candidates.sort(key=lambda p: (bool(p.get("Online")), p.get("LastSeen") or ""), reverse=True)

p = candidates[0] if candidates else None
print(json.dumps({
    "online": bool(p and p.get("Online")),
    "hostname": (p or {}).get("HostName", ""),
    "last_seen": (p or {}).get("LastSeen", ""),
    "backend_state": data.get("BackendState", ""),
}))
PY
)"

[ -r "$TOKEN_FILE" ] || exit 0
TOKEN="$(cat "$TOKEN_FILE")"
[ -n "$TOKEN" ] || exit 0

curl -fsS --max-time 10 -X POST "$BRIDGE_URL" \
  -H "X-Bridge-Token: $TOKEN" \
  -H 'Content-Type: application/json' \
  --data "$PAYLOAD" >/dev/null || true

exit 0
