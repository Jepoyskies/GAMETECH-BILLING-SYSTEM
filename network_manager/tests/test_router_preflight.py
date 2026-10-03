"""
Router pre-flight tests.

The pre-flight is the gate in front of ROUTER_MODE=live, so its own
correctness matters more than almost anything else here: a false READY would
let an operator enable writes against routers that cannot be reached.

WHAT IS PINNED
--------------
* A device on a non-API port (700/WinBox, 8700/SSH) is BLOCKED, never READY.
* An unreachable device is BLOCKED.
* A healthy device on 8728 with a live socket is READY.
* The probe is read-only: it opens a socket and sends nothing.
* The count of customers at risk is reported, because "blocked" means
  something very different at 2,040 customers than at 0.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from billing.models import Barangay, Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice


def make_device(name, ip, port, linked_customers=0):
    dev, _ = MikrotikDevice.objects.get_or_create(
        device_name=name,
        defaults={
            "ip_address": ip,
            "api_username": "admin",
            "api_password": "x",
            "api_port": port,
        },
    )
    if linked_customers:
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="P1000",
            defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps",
                      "price": 1000.0},
        )
        barangay, _ = Barangay.objects.get_or_create(name="Lab")
        for i in range(linked_customers):
            Customer.objects.create(
                full_name="Cust {}".format(i),
                pppoe_username="{}_{}".format(name, i),
                status="active",
                installation_status="installed",
                plan=plan,
                barangay=barangay,
            )
            Customer.objects.filter(
                pppoe_username="{}_{}".format(name, i)
            ).update(mikrotik_device=dev)
    return dev


class RouterPreflightTests(TestCase):
    def _run(self, **kwargs):
        out = StringIO()
        call_command("router_preflight", stdout=out, **kwargs)
        return out.getvalue()

    # -- port validation ---------------------------------------------
    def test_winbox_port_700_is_blocked(self):
        """700 is WinBox. Nothing will ever authenticate there."""
        make_device("ccr2116.v1", "172.30.120.1", 700)
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(True, "connected")
        ):
            output = self._run()

        self.assertIn("BLOCKED", output)
        self.assertIn("NOT the RouterOS API", output)
        self.assertIn("700", output)

    def test_ssh_port_8700_is_blocked(self):
        make_device("ssh_router", "172.30.120.9", 8700)
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(True, "connected")
        ):
            output = self._run()
        self.assertIn("BLOCKED", output)

    def test_api_port_8728_is_accepted(self):
        make_device("good", "10.1.1.1", 8728)
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(True, "connected")
        ):
            output = self._run()
        self.assertIn("READY", output)
        self.assertNotIn("NOT the RouterOS API", output)

    def test_api_ssl_port_8729_is_accepted(self):
        make_device("ssl", "10.1.1.2", 8729)
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(True, "connected")
        ):
            output = self._run()
        self.assertIn("READY", output)

    # -- reachability ------------------------------------------------
    def test_unreachable_router_is_blocked(self):
        make_device("dead", "172.30.120.5", 8728)
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(False, "timed out after 2.0s")
        ):
            output = self._run()

        self.assertIn("BLOCKED", output)
        self.assertIn("timed out", output)

    def test_customers_at_risk_are_reported(self):
        """2,040 unreachable customers is not the same as zero."""
        make_device("big", "172.30.120.6", 8728, linked_customers=3)
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(False, "timed out")
        ):
            output = self._run()

        self.assertIn("CUSTOMERS ON UNREACHABLE ROUTERS: 3", output)
        self.assertIn("Bridge the traffic", output)

    def test_blocked_router_warns_against_enabling_live_mode(self):
        """The whole point: stop a mass-outage config mistake."""
        make_device("down", "172.30.120.7", 8728, linked_customers=2)
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(False, "timed out")
        ):
            output = self._run()

        self.assertIn("ROUTER_MODE=live", output)
        self.assertIn("time out", output)

    # -- read-only guarantees ----------------------------------------
    def test_probe_sends_nothing_and_authenticates_nowhere(self):
        """A read-only check must not authenticate or write."""
        import socket as socket_mod

        make_device("quiet", "10.2.2.2", 8728)

        seen = []
        real_socket = socket_mod.socket

        class SpySocket:
            def __init__(self, *a, **kw):
                self._s = real_socket(*a, **kw)

            def settimeout(self, t):
                seen.append(("settimeout", t))
                return self._s.settimeout(t)

            def connect(self, addr):
                seen.append(("connect", addr))
                return self._s.connect(addr)

            def send(self, *a):
                seen.append(("SEND", a))
                return self._s.send(*a)

            def sendall(self, *a):
                seen.append(("SENDALL", a))
                return self._s.sendall(*a)

            def close(self):
                return self._s.close()

        with mock.patch("socket.socket", return_value=SpySocket()):
            with mock.patch("socket.getaddrinfo", return_value=[(
                2, 1, 6, "", ("10.2.2.2", 8728))]):
                self._run(timeout=0.05)

        methods = [s[0] for s in seen]
        self.assertIn("connect", methods)
        self.assertNotIn(
            "SEND", methods,
            "The pre-flight must open a socket and STOP. Sending anything "
            "would make it a write.",
        )
        self.assertNotIn("SENDALL", methods)

    def test_probe_never_writes_to_the_database(self):
        from billing.models import SystemLog

        make_device("noWrite", "10.3.3.3", 8728)
        before = SystemLog.objects.count()
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(True, "connected")
        ):
            self._run()
        self.assertEqual(
            SystemLog.objects.count(), before,
            "The pre-flight is a diagnostic and must leave no trace.",
        )

    def test_json_output_is_machine_readable(self):
        import json as json_mod

        make_device("json_router", "10.4.4.4", 8728)
        out = StringIO()
        with mock.patch(
            "network_manager.management.commands.router_preflight."
            "Command._tcp_probe", return_value=(True, "connected")
        ):
            call_command("router_preflight", stdout=out, json=True)

        payload = json_mod.loads(out.getvalue())
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["verdict"], "READY")
        self.assertIn("configured_port", payload[0])
        self.assertIn("customers_linked", payload[0])

    def test_handles_no_devices_gracefully(self):
        output = self._run()
        self.assertIn("No routers configured", output)

    def test_bad_port_value_does_not_crash(self):
        """A garbage api_port must BLOCK loudly, never crash the gate.

        api_port is a non-nullable IntegerField, so this exercises the int()
        failure branch directly rather than through the database.
        """
        dev = make_device("weird", "10.5.5.5", 8728)

        class GarbledPort:
            """Stands in for a device whose port cannot be parsed."""

            device_name = dev.device_name
            ip_address = dev.ip_address
            id = dev.id
            api_port = "not-a-port"

        from network_manager.management.commands.router_preflight import Command

        report = Command()._probe(GarbledPort(), 0.05)

        self.assertEqual(report.verdict, "BLOCKED")
        self.assertFalse(report.port_is_api)
        self.assertEqual(report.configured_port, 0)
        self.assertTrue(
            any("not a number" in p for p in report.blocking_problems),
            "A non-numeric port must be called out explicitly, not silently "
            "treated as zero.",
        )