"""
Router reachability pre-flight.

WHY THIS EXISTS
---------------
The owner runs a split topology:

    DigitalOcean droplet  -- the SYSTEM (database, web, Celery)
    Mini PC on-site       -- the only host with a route to the routers
    MikroTik routers      -- 172.30.120.0/24 and the test unit

Verified from the droplet on 2026-10-03: 172.30.120.1/.2/.3 time out on EVERY
port, while 192.168.88.2 (the test unit, 0 customers) answers on 8728. The
droplet simply has no route to the production routers. Until the mini PC
proxies or bridges that traffic, three of four routers -- holding 2,040 of
2,041 subscribers -- are unreachable from the system.

That makes two mistakes catastrophic rather than annoying:

1. Enabling ROUTER_MODE=live while the routers are unreachable. Every
   provisioning, suspension and reconnection would time out one by one. On a
   1 vCPU box with a 2s socket timeout, that is how you get a mass outage
   instead of a config error.

2. Pointing a device at a port that is not the RouterOS API. Three devices are
   currently on port 700, which is WinBox. No amount of retrying will ever
   authenticate there -- the API service defaults to 8728 (8729 for api-ssl).

This command answers both questions BEFORE anyone turns on writes. It is
strictly read-only: it opens TCP sockets and inspects stored configuration.
It never calls the RouterOS API, never writes to a router, and never writes
to the database.

    python manage.py router_preflight
    python manage.py router_preflight --json
"""

import json
import socket
from dataclasses import asdict, dataclass, field

from django.core.management.base import BaseCommand

# Ports that are not the RouterOS API. RouterOS exposes:
#   8728  api
#   8729  api-ssl
#   8700  ssh
#   22    ssh
#   80/443 www / www-ssl
#   700   WinBox   <-- not an API service
#   8291  api (CHR)
NOT_API_PORTS = {
    22: "SSH",
    23: "telnet",
    80: "www",
    443: "www-ssl",
    445: "SMB",
    8291: "api (CHR only -- valid)",
    8700: "SSH (not the API)",
    8729: "api-ssl",
    8728: "api",
}

VALID_API_PORTS = {8728, 8729, 8291}


@dataclass
class DeviceReport:
    device_id: int
    device_name: str
    ip_address: str
    configured_port: int
    port_is_api: bool
    port_note: str
    customers_linked: int
    reachable: bool
    probe_note: str
    verdict: str
    blocking_problems: list = field(default_factory=list)


class Command(BaseCommand):
    help = (
        "Read-only reachability and port check for every MikroTik device. "
        "Run this before enabling ROUTER_MODE=live. Never writes anything."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit machine-readable JSON instead of a table.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=2.0,
            help="Per-port TCP timeout in seconds (default 2.0).",
        )

    def handle(self, *args, **kwargs):
        as_json = kwargs["json"]
        timeout = kwargs["timeout"]

        from network_manager.models import MikrotikDevice

        devices = list(MikrotikDevice.objects.all().order_by("id"))
        reports = []
        for device in devices:
            reports.append(self._probe(device, timeout))

        if as_json:
            self.stdout.write(json.dumps(
                [asdict(r) for r in reports], indent=2, default=str))
            return

        self._render(reports)

    # ------------------------------------------------------------------
    def _probe(self, device, timeout):
        from billing.models import Customer

        try:
            port = int(device.api_port)
        except (TypeError, ValueError):
            port = 0

        # A malformed port must not stop us reporting the OTHER problems, and
        # the customer count must not depend on the device being a real row.
        linked = 0
        if getattr(device, "id", None) is not None:
            try:
                linked = Customer.objects.filter(mikrotik_device_id=device.id).count()
            except (TypeError, ValueError):
                linked = 0

        port_is_api = port in VALID_API_PORTS
        port_note = NOT_API_PORTS.get(port, "unknown port")

        problems = []
        if port == 0:
            problems.append("api_port is not a number")
        elif not port_is_api:
            problems.append(
                "api_port {} is {} -- this is NOT the RouterOS API. The API "
                "service listens on 8728 (or 8729 for api-ssl). Nothing will "
                "ever authenticate on this port.".format(port, port_note)
            )

        reachable, note = self._tcp_probe(device.ip_address, port, timeout)

        if not reachable:
            problems.append(
                "No TCP connection to {}:{}. {}".format(
                    device.ip_address, port, note)
            )

        verdict = "READY" if not problems else "BLOCKED"

        return DeviceReport(
            device_id=device.id,
            device_name=device.device_name,
            ip_address=device.ip_address,
            configured_port=port,
            port_is_api=port_is_api,
            port_note=port_note,
            customers_linked=linked,
            reachable=reachable,
            probe_note=note,
            verdict=verdict,
            blocking_problems=problems,
        )

    def _tcp_probe(self, ip, port, timeout):
        """Open a TCP socket. This is the ONLY network call we make.

        It does not authenticate and it sends nothing, so it cannot change a
        router even if the credentials were wrong.
        """
        if not ip:
            return False, "no IP address configured"
        if not port:
            return False, "no port configured"
        sock = socket.socket()
        sock.settimeout(timeout)
        try:
            sock.connect((ip, port))
            return True, "connected"
        except socket.timeout:
            return False, "timed out after {}s".format(timeout)
        except OSError as exc:
            return False, "{}: {}".format(exc.__class__.__name__, exc)
        finally:
            sock.close()

    # ------------------------------------------------------------------
    def _render(self, reports):
        style = self.style
        self.stdout.write("")
        self.stdout.write("Router pre-flight (read-only -- no router or database writes)")
        self.stdout.write("=" * 78)

        if not reports:
            self.stdout.write(style.WARNING("  No routers configured yet."))
            return

        ready = [r for r in reports if r.verdict == "READY"]
        blocked = [r for r in reports if r.verdict == "BLOCKED"]

        for r in reports:
            mark = style.SUCCESS("READY  ") if r.verdict == "READY" \
                else style.ERROR("BLOCKED")
            self.stdout.write("{}  {} (id {})".format(
                mark, r.device_name, r.device_id))
            self.stdout.write("    address     : {}:{}  [{}]".format(
                r.ip_address, r.configured_port, r.port_note))
            self.stdout.write("    reachable   : {}".format(r.probe_note))
            self.stdout.write("    customers   : {}".format(r.customers_linked))
            for p in r.blocking_problems:
                self.stdout.write(style.WARNING("    ! " + p))
            self.stdout.write("")

        at_risk = sum(r.customers_linked for r in blocked)
        self.stdout.write("-" * 78)
        self.stdout.write("Ready: {}   Blocked: {}".format(len(ready), len(blocked)))
        if at_risk:
            self.stdout.write(style.ERROR(
                "CUSTOMERS ON UNREACHABLE ROUTERS: {}".format(at_risk)))
            self.stdout.write(
                "  Enabling ROUTER_MODE=live while these are unreachable would\n"
                "  make every provisioning, suspension and reconnection time out\n"
                "  one at a time. Bridge the traffic from the mini PC first."
            )
        self.stdout.write("")