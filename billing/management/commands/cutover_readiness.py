"""
CUTOVER READINESS.

One command that answers the only question that matters on the day the legacy
system is disconnected: "what is our system actually capable of, right now?"

It is a REPORT. It opens no router connection, writes nothing, and changes
nothing. Every number it prints is derived from our own database plus the
router MODE configuration, so it is safe to run at any time, including with
the legacy system already gone.

Read it as a checklist rather than a dashboard. Each line is a gate that has
to be true before automatic suspension is switched on.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from billing.models import Customer, SystemLog
from network_manager.models import MikrotikDevice


class Command(BaseCommand):
    help = "Reports cutover readiness. Changes nothing, connects to no router."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit the same report as JSON for scripting.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        r = self._collect(now)

        if options.get("json"):
            import json
            self.stdout.write(json.dumps(r, indent=2, default=str))
            return None

        ok = self._render(r)
        return None if ok else None

    # ------------------------------------------------------------------
    def _collect(self, now):
        qs = Customer.objects.exclude(pppoe_username__isnull=True).exclude(pppoe_username="")

        past_due = [c for c in qs.filter(expires_at__lte=now, status="active")
                    if c.mikrotik_device_id]
        paired = [c for c in qs if c.pair_approved]
        armable_lapsed = [c for c in past_due if c.pair_approved]

        return {
            "now": now,
            "mode": settings.ROUTER_MODE,
            "token_armed": bool(
                settings.ROUTER_WRITE_TOKEN and settings.ROUTER_WRITE_TOKEN_EXPECTED
            ),
            "customers": qs.count(),
            "routers": MikrotikDevice.objects.count(),
            "routers_with_accounts": qs.filter(
                mikrotik_device__isnull=False).values(
                "mikrotik_device").distinct().count(),
            "unpaired": qs.count() - len(paired),
            "paired": len(paired),
            "past_due": len(past_due),
            "armable_lapsed": len(armable_lapsed),
            "no_expiry": qs.filter(expires_at__isnull=True).count(),
            "imported_never_verified": qs.filter(
                sync_status="Unverified").count(),
            "ever_pushed": SystemLog.objects.filter(
                action__contains="PUSH").count(),
            "no_router": qs.filter(mikrotik_device__isnull=True).count(),
        }

    # ------------------------------------------------------------------
    def _render(self, r):
        W, S, E = self.style.WARNING, self.style.SUCCESS, self.style.ERROR
        good, warn, bad = [], [], []

        def gate(ok, label, detail, warn_only=False):
            (good if ok else (warn if warn_only else bad)).append(label)
            style = S if ok else (W if warn_only else E)
            mark = "PASS" if ok else ("WARN" if warn_only else "BLOCK")
            self.stdout.write("  [%s] %-42s %s" % (style(mark), label, detail))

        self.stdout.write(W("=" * 74))
        self.stdout.write(W("CUTOVER READINESS -- report only, nothing was changed"))
        self.stdout.write(W("=" * 74))

        self.stdout.write(self.style.HTTP_INFO("\n  ROUTER ACCESS"))
        gate(r["mode"] == "read_only",
             "router mode is read_only",
             r["mode"] + ("  (correct until you decide otherwise)" if r["mode"] == "read_only" else ""))
        gate(not r["token_armed"],
             "write tokens are not armed",
             "unarmed" if not r["token_armed"] else "ARMED -- writes are possible")
        gate(r["ever_pushed"] == 0,
             "no account has ever been pushed",
             "%d pushes in the audit log" % r["ever_pushed"])

        self.stdout.write(self.style.HTTP_INFO("\n  VERIFICATION PROGRESS"))
        self.stdout.write("         customers total              : %d" % r["customers"])
        self.stdout.write("         paired in Sync Manager       : %d" % r["paired"])
        self.stdout.write("         still to verify              : %d" % r["unpaired"])
        gate(r["unpaired"] == 0,
             "every customer has been verified",
             "%d still unverified" % r["unpaired"] if r["unpaired"] else "all verified",
             warn_only=True)

        self.stdout.write(self.style.HTTP_INFO("\n  WHAT A SUSPENSION COULD TOUCH TODAY"))
        self.stdout.write("         past-due, on a router         : %d" % r["past_due"])
        self.stdout.write("         ...of those, PAIRED (armable) : %d" % r["armable_lapsed"])
        gate(r["armable_lapsed"] == 0,
             "no unverified customer is suspensible",
             "%d armable right now" % r["armable_lapsed"])

        self.stdout.write(self.style.HTTP_INFO("\n  DATA HEALTH (warns, not blockers)"))
        gate(r["no_router"] == 0, "every customer has a router",
             "%d unassigned" % r["no_router"], warn_only=True)
        gate(r["no_expiry"] == 0, "every customer has an expiry date",
             "%d missing" % r["no_expiry"], warn_only=True)
        gate(r["imported_never_verified"] == 0, "no accounts sit unverified in sync",
             "%d Unverified" % r["imported_never_verified"], warn_only=True)

        self.stdout.write(W("\n" + "=" * 74))
        self.stdout.write("  %d passed, %d warnings, %d blockers" % (len(good), len(warn), len(bad)))
        if bad:
            self.stdout.write(E("  BLOCKERS must be resolved before automatic suspension."))
        elif warn:
            self.stdout.write(W("  No blockers. Warnings are expected before cutover."))
        else:
            self.stdout.write(S("  Ready for automatic suspension."))
        self.stdout.write(W("=" * 74))

        self.stdout.write(self.style.HTTP_INFO(
            "\n  Preview any future suspension with:"))
        self.stdout.write("      python manage.py auto_suspend --dry-run")
        return not bad
