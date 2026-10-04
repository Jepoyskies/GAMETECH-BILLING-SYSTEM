"""
Align the current plan catalogue with the legacy billing system's plan codes.

WHY THIS EXISTS
---------------
The old billing system named its internet plans with technical codes
("pppoe-50m_1349"). Staff never saw those -- they were the *router profile*
names. The new system has friendly names ("GTipid Fiber 1500") plus a
separate `router_profile` field that carries the technical code.

Importing the old SQL verbatim would overwrite friendly names with raw codes,
so CSR dropdowns would fill with "pppoe-50m_1349" instead of a readable
product name. This command bridges the two so BOTH sides stay correct:

    legacy code  ->  friendly plan name   (what staff see)
                 ->  router_profile       (what MikroTik receives)

HOW MATCHING WORKS (safety order, no guessing)
---------------------------------------------
1. EXACT NAME MATCH -- the code already exists in the new catalogue.
   Maps to itself. Zero risk, nothing changes.

2. EXACT (speed, price) MATCH -- a plan already exists with identical
   bandwidth and price under a friendly name. We reuse it and set its
   `router_profile` to the legacy code, so the router still receives the
   profile string it already knows. Identical speed means the subscriber's
   bandwidth does not change by one bit.

3. NO MATCH -- create a new plan named "<speed> Mbps Plan <price>"
   (the convention already used by "20 Mbps Plan", "50 Mbps Plan"), with
   `router_profile` set to the legacy code.

A match is NEVER accepted on price alone. Speed is the thing the router
enforces; two plans at the same price with different speeds exist in this
catalogue, so price-only matching would silently hand a customer the wrong
bandwidth.

CignalPlay rows in the legacy file are add-ons, not internet plans, and are
skipped -- they are handled by the Cignal Play subsystem.

Usage:
    python manage.py map_plans --dry-run     # report only
    python manage.py map_plans               # apply
    python manage.py map_plans --report      # show final mapping table
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import PlanMapping, SubscriptionPlan


# Legacy plan code -> (download Mbps, monthly price).
# Read directly from the `service_plans` table of the legacy export.
LEGACY_CATALOGUE = {
    "pppoe-5m":                    (5,    Decimal("500.00")),
    "pppoe-10m":                   (10,   Decimal("500.00")),
    "pppoe-15m_500":               (15,   Decimal("500.00")),
    "pppoe-15m_600":               (15,   Decimal("600.00")),
    "pppoe-15m_700":               (10,   Decimal("700.00")),
    "pppoe-15m_800":               (15,   Decimal("800.00")),
    "pppoe-15m_900":               (15,   Decimal("900.00")),
    "pppoe-20m":                   (20,   Decimal("1000.00")),
    "pppoe-20m_1149":              (20,   Decimal("1149.00")),
    "pppoe-20m-speedboost60":      (20,   Decimal("1000.00")),
    "pppoe-30m":                   (30,   Decimal("1300.00")),
    "pppoe-30m_1200":              (30,   Decimal("1200.00")),
    "pppoe-30m_1400":              (30,   Decimal("1400.00")),
    "pppoe-30m_1449":              (30,   Decimal("1449.00")),
    "pppoe-30m-speedboost80":      (30,   Decimal("1300.00")),
    "pppoe-50m":                   (50,   Decimal("1500.00")),
    "pppoe-50m_1200":              (50,   Decimal("1200.00")),
    "pppoe-50m_1300":              (50,   Decimal("1300.00")),
    "pppoe-50m_1349":              (50,   Decimal("1349.00")),
    "pppoe-50m_1400":              (40,   Decimal("1400.00")),
    "pppoe-50m_1649":              (50,   Decimal("1649.00")),
    "pppoe-50m_newplan":           (50,   Decimal("1000.00")),
    "pppoe-50m-speedboost100":     (50,   Decimal("1500.00")),
    "pppoe-75m_newplan":           (75,   Decimal("1300.00")),
    "pppoe-100m":                  (1000, Decimal("2000.00")),
    "pppoe-100m_1k":               (100,  Decimal("1000.00")),
    "pppoe-100m_1500":             (100,  Decimal("1500.00")),
    "pppoe-100m_1700":             (100,  Decimal("1700.00")),
    "pppoe-100m_3000":             (100,  Decimal("3000.00")),
    "pppoe-100m_3500":             (100,  Decimal("3500.00")),
    "pppoe-100m_newplan":          (100,  Decimal("1500.00")),
    "pppoe-100m_newplan_900":      (100,  Decimal("900.00")),
    "pppoe-120m":                  (120,  Decimal("2200.00")),
    "pppoe-200m":                  (200,  Decimal("4000.00")),
}

# Legacy codes that must resolve to a SPECIFIC existing plan even though
# another plan already matches on (speed, price). Ordered by preference --
# the first plan whose speed AND price match wins.
#
# These are deliberate: the friendly plan was already the home for this
# product tier, and pointing the legacy code at it avoids a second identical
# entry in the CSR dropdown.
PREFERRED_TARGET = {
    "pppoe-5m":                "5Mbps",
    "pppoe-10m":               "10Mbps",
    "pppoe-20m":               "GTipid Fiber 1000",
    "pppoe-50m":               "GTipid Fiber 1500",
    "pppoe-100m_1k":           "GIMI Home Fiber 1000",
    "pppoe-100m_1500":         "GIMI Home Fiber 1500",
    "pppoe-100m_newplan":      "GIMI Home Fiber 1500",
    "pppoe-75m_newplan":       "GIMI Home Fiber 1300",
}


class Command(BaseCommand):
    help = "Align the plan catalogue with legacy plan codes (name + router_profile)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing.",
        )
        parser.add_argument(
            "--report", action="store_true",
            help="Print the resulting legacy -> plan -> profile table and exit.",
        )

    # -- helpers ---------------------------------------------------------

    def _speed_of(self, plan):
        """Numeric Mbps for a plan, parsed from its declared speed."""
        if plan.speed_mbps:
            return plan.speed_mbps
        digits = "".join(ch for ch in str(plan.speed_down) if ch.isdigit())
        return int(digits) if digits else None

    def _find_speed_price_match(self, plans, speed, price):
        """First plan matching BOTH speed and price. Never price alone."""
        for plan in plans:
            if plan.price == price and self._speed_of(plan) == speed:
                return plan
        return None

    # -- main ------------------------------------------------------------

    def handle(self, *args, **kwargs):
        dry_run = kwargs["dry_run"]
        report_only = kwargs["report"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN -- no changes will be written."))
        self.stdout.write("")

        plans = list(SubscriptionPlan.objects.all())

        # ---- PHASE 1: decide, do not write ----------------------------
        #
        # Everything is resolved before anything is saved, because the
        # decision for one code can invalidate the decision for another.
        decisions = {}
        for legacy_name, (speed, price) in sorted(LEGACY_CATALOGUE.items()):
            by_name = next((p for p in plans if p.name == legacy_name), None)
            if by_name:
                decisions[legacy_name] = (by_name, "EXACT")
                continue

            target = None
            preferred = PREFERRED_TARGET.get(legacy_name)
            if preferred:
                target = next((p for p in plans if p.name == preferred), None)
            if target is None:
                target = self._find_speed_price_match(plans, speed, price)

            if target is not None:
                decisions[legacy_name] = (target, "REUSE")
            else:
                decisions[legacy_name] = (None, "CREATE")

        # ---- COLLISION CHECK -------------------------------------------
        #
        # A plan carries ONE router_profile. If two legacy codes are pointed
        # at the same plan, the second write silently overwrites the first
        # and the earlier code's subscribers get pushed to the router under
        # the WRONG profile string.
        #
        # This is not theoretical: pppoe-20m and pppoe-20m-speedboost60 both
        # matched GTipid Fiber 1000 on (speed, price) and would have ended up
        # as one plan whose profile was whichever sorted last.
        #
        # So: any plan claimed by more than one legacy code gets split, and
        # every claimant keeps its own dedicated plan with its own profile.
        claims = {}
        for legacy_name, (target, verdict) in decisions.items():
            if verdict != "REUSE":
                continue
            claims.setdefault(id(target), []).append((legacy_name, target))

        split_names = {}
        for claimants in claims.values():
            if len(claimants) < 2:
                continue
            self.stdout.write(self.style.WARNING(
                "  COLLISION: {} legacy codes all matched '{}'. Splitting so each "
                "keeps its own router_profile."
                .format(len(claimants), claimants[0][1].name)
            ))
            for legacy_name, base in claimants:
                speed, price = LEGACY_CATALOGUE[legacy_name]
                decisions[legacy_name] = (None, "CREATE")
                split_names[legacy_name] = "{} — {}".format(base.name, legacy_name)

        # ---- PHASE 2: write --------------------------------------------
        exact = reused = created = 0
        for legacy_name, (speed, price) in sorted(LEGACY_CATALOGUE.items()):
            target, verdict = decisions[legacy_name]

            if verdict == "CREATE":
                # Reuse a dedicated name if this code was split out of a
                # collision, otherwise follow the system's existing
                # "<speed> Mbps Plan <price>" convention.
                base_name = split_names.get(legacy_name) or f"{speed} Mbps Plan {int(price)}"
                target = SubscriptionPlan(
                    name=base_name,
                    speed_up=f"{speed} Mbps",
                    speed_down=f"{speed} Mbps",
                    speed_mbps=speed,
                    price=price,
                    validity_days=30,
                    router_profile=legacy_name,
                    description="Created by map_plans from legacy catalogue.",
                )
                created += 1
            elif verdict == "EXACT":
                exact += 1
            else:
                reused += 1

            desired_profile = legacy_name
            profile_changed = (target.router_profile or "") != desired_profile

            if not dry_run and not report_only:
                if verdict == "CREATE":
                    target.save()
                    plans.append(target)
                elif profile_changed:
                    target.router_profile = desired_profile
                    target.save(update_fields=["router_profile"])

                PlanMapping.objects.update_or_create(
                    legacy_name=legacy_name, defaults={"plan": target}
                )

            self.stdout.write(
                f"  {verdict:6}  {legacy_name:<22} -> {target.name} [{desired_profile}]"
                + ("   (profile updated)" if profile_changed and verdict == "REUSE" else "")
            )

        if report_only or dry_run:
            self.stdout.write("")
            self.stdout.write(
                f"Would apply: {exact} exact, {reused} reused, {created} created."
            )
            return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. {exact} exact, {reused} reused, {created} created. "
            f"{len(LEGACY_CATALOGUE)} legacy codes mapped."
        ))