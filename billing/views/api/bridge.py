"""Bridge heartbeat — the only way to *positively confirm* the office Mini PC is up.

The Mini PC is a Tailscale subnet router, not an app server. The cloud reaches
the MikroTik routers *through* it, so "cannot reach the routers" is ambiguous on
its own: it cannot tell a dead Mini PC from a dead office uplink/repeater, and
both look identical from the droplet.

`scripts/bridge_heartbeat.sh` runs on the droplet **host** and POSTs the real
Tailscale peer state here every 30s. It has to run on the host because
Tailscale's LocalAPI resolves peer credentials in the host PID namespace and
returns 403 to container callers.

That one fact — "did the Mini PC talk to us, and did it have internet?" — splits
the ambiguous case in two and removes the guesswork:

    tunnel UP   + routers DOWN -> the Mini PC is fine; the fault is the LAN
                                  between it and the routers (cable/switch/router)
    tunnel DOWN + routers DOWN -> our side: Mini PC is off, or its uplink is dead

Security: token-gated and fails CLOSED. Without BRIDGE_HEARTBEAT_TOKEN set this
endpoint returns 503 and stores nothing — otherwise anyone on the public internet
could POST a fake "online" and blind the whole monitoring system.
"""

import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Kept short on purpose: a missed cron tick should read as "stale", not "offline",
# but a genuinely silent bridge must be obvious within ~90s.
BRIDGE_HEARTBEAT_TTL = 120


@csrf_exempt
@require_POST
def api_bridge_heartbeat(request):
    """Receive the Tailscale peer state for the office bridge from the host cron."""
    expected = getattr(settings, "BRIDGE_HEARTBEAT_TOKEN", "") or ""
    if not expected:
        # Fail closed: never accept monitoring data we cannot authenticate.
        return JsonResponse(
            {"ok": False, "error": "BRIDGE_HEARTBEAT_TOKEN is not configured"},
            status=503,
        )

    supplied = request.headers.get("X-Bridge-Token", "")
    if not secrets.compare_digest(supplied, expected):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        import json

        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    online = bool(payload.get("online"))
    state = {
        "online": online,
        "hostname": str(payload.get("hostname") or "")[:64],
        "last_seen": str(payload.get("last_seen") or "")[:40],
        "backend_state": str(payload.get("backend_state") or "")[:40],
        "received_at": time.time(),
    }
    cache.set("bridge_tunnel", state, BRIDGE_HEARTBEAT_TTL)
    return JsonResponse({"ok": True, "bridge": state})
