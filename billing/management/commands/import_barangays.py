"""Import the REAL barangays from the legacy dump and assign them to customers.

WHY THIS EXISTS
---------------
The legacy system had a `barangays` table with the 12 actual CDO barangays and
a `customers.barangay_id` varchar. The import dropped that entirely, and the
new system shipped with placeholder rows instead ("Barangay 1", "Barangay 2",
"Poblacion", ...). Result: 0 of 2,038 customers had a barangay, and the Barangay
filter on the Customer List and Sync Manager listed 31 options that matched
nobody.

HOW IT DECIDES
--------------
Two sources, in strict priority order, and nothing else:

  1. customers.barangay_id, when it resolves to a real barangay -- either the
     legacy integer id or the name. This is the authoritative answer.
  2. The address free text, matched against the 12 official names ONLY. If the
     address does not contain an official barangay name, the customer is left
     alone. A site like "Zayas landfill" is a real place that is not one of the
     12, and guessing PATAG for it would misroute a technician.

Device/router name is deliberately NOT used as a fallback: ccr2116.v1 serves
1,997 customers spread across Carmen, Patag, Macanhan and Balulang, so its
name says which POP they dial, not where they live.

Read-only against the routers. Touches only Barangay and Customer.barangay.
"""
import re
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import Barangay, Customer

# Spellings that appear in hand-typed addresses for the same place.
ADDRESS_ALIASES = {
    "PATAG": ["PATAG"],
    "CARMEN": ["CARMEN"],
    "APOVEL": ["APOVEL"],
    "TERRY HILLS": ["TERRY HILL", "TERRYHILLS", "TERRY HILLS"],
    "BULUA": ["BULUA"],
    "MACANHAN": ["MACANHAN"],
    "SINGAPORE": ["SINGAPORE"],
    "BALULANG": ["BALULANG"],
    "CANITOAN": ["CANITOAN"],
    "UPTOWN": ["UPTOWN"],
    "GRAN EUROPA": ["GRAN EUROPA", "GRANEUROPA", "GRAN EUROP"],
    "LUMBIA": ["LUMBIA"],
}

CUSTOMER_COLS = [
    "id", "username", "account_type", "plan_name", "expires_at", "full_name",
    "email", "phone", "address", "barangay_id", "status", "created_at",
    "latitude", "longitude", "adjusted_by_router", "adjusted_by_referral",
    "last_expiry_sms_sent", "device_name", "sms_sent_at", "mac_address", "agent",
    "referral_received", "last_sms_due", "connection", "created_form_by",
    "cignalplay_no", "cignalplay_date", "cignalplay_adjustedby", "note",
]


def split_row(text):
    """Split one (...) tuple, honouring quotes and backslash escapes."""
    out, buf, in_q, esc = [], [], False, False
    for ch in text[1:-1]:
        if in_q:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == "'":
                in_q = False
            else:
                buf.append(ch)
        else:
            if ch == "'":
                in_q = True
            elif ch == ",":
                out.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
    out.append("".join(buf).strip())
    return out


def tuples(blob):
    """Every balanced (...) tuple in a chunk of INSERT body."""
    i, n = 0, len(blob)
    while i < n:
        if blob[i] != "(":
            i += 1
            continue
        depth, in_q, esc, j = 0, False, False, i
        while j < n:
            ch = blob[j]
            if in_q:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == "'":
                    in_q = False
            else:
                if ch == "'":
                    in_q = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        yield blob[i:j + 1]
        i = j + 1


class Command(BaseCommand):
    help = "Import real barangays from the legacy SQL dump and assign to customers."

    def add_arguments(self, parser):
        parser.add_argument("sql_path", help="Path to the legacy gametech .sql dump")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        path = Path(options["sql_path"])
        if not path.exists():
            raise CommandError("SQL file not found: %s" % path)
        blob = path.read_text(encoding="utf-8", errors="replace")

        legacy = self._read_barangays(blob)
        if not legacy:
            raise CommandError("No `barangays` INSERT found -- is this the right dump?")
        self.stdout.write("Legacy barangays found: %d" % len(legacy))
        for k in sorted(legacy):
            self.stdout.write("   %2d  %s" % (k, legacy[k]))

        rows = self._read_customers(blob)
        self.stdout.write("Customer rows parsed: %d" % len(rows))

        by_id = {str(k): v.upper() for k, v in legacy.items()}
        by_name = {v.upper(): v for v in legacy.values()}
        uid, ubid, uaddr = (
            CUSTOMER_COLS.index("username"),
            CUSTOMER_COLS.index("barangay_id"),
            CUSTOMER_COLS.index("address"),
        )

        plan = []
        sources = Counter()
        for f in rows:
            uname = f[uid]
            resolved, src = None, None

            raw = (f[ubid] or "").strip()
            if raw and raw in by_id:
                resolved, src = by_id[raw], "barangay_id"
            elif raw and raw.upper() in by_name:
                resolved, src = by_name[raw.upper()], "barangay_id"

            if resolved is None:
                addr = (f[uaddr] or "").upper()
                for canon, variants in ADDRESS_ALIASES.items():
                    if any(v in addr for v in variants):
                        resolved, src = canon, "address"
                        break

            if resolved:
                plan.append((uname, resolved, src))
                sources[src] += 1
            else:
                plan.append((uname, None, None))

        assign = [p for p in plan if p[1]]
        skipped = [p for p in plan if not p[1]]
        self.stdout.write("")
        self.stdout.write("would assign : %d  (barangay_id=%d, address=%d)" % (
            len(assign), sources["barangay_id"], sources["address"]))
        self.stdout.write("would skip   : %d  (no official barangay name anywhere)" % len(skipped))
        self.stdout.write("breakdown of assignments: %s" % dict(Counter(p[1] for p in assign)))

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run -- nothing written."))
            return

        with transaction.atomic():
            kept = {n.upper() for n in legacy.values()}
            # Only drop placeholders no real customer points at. Nothing does
            # today, but this must never delete data if that ever changes.
            stale = [
                b for b in Barangay.objects.all()
                if b.name.upper() not in kept
                and not Customer.objects.filter(barangay=b).exists()
            ]
            for b in stale:
                self.stdout.write("   removing placeholder barangay %r" % b.name)
                b.delete()

            # Build the lookup by scanning, NOT with get_or_create.
            #
            # The table already held "Balulang" as a placeholder AND the legacy
            # list has BALULANG, and get_or_create(name__iexact=...) calls get()
            # with a __lookup, which raises MultipleObjectsReturned rather than
            # returning one row. Indexing by upper-cased name sidesteps the whole
            # class of problem and picks a single winner if duplicates exist.
            lookup, dupes = {}, []
            for b in Barangay.objects.all().order_by("id"):
                key = b.name.strip().upper()
                if key in lookup:
                    dupes.append(b.name)
                    continue
                lookup[key] = b
            if dupes:
                self.stdout.write(
                    self.style.WARNING(
                        "   note: duplicate-named barangays ignored: %s"
                        % ", ".join(sorted(set(dupes)))))

            for name in legacy.values():
                key = name.upper()
                if key in lookup:
                    continue
                obj = Barangay.objects.create(name=name)
                lookup[key] = obj
                self.stdout.write("   created barangay %r" % name)

            by_user = {c.pppoe_username: c for c in Customer.objects.all()}
            written = 0
            for uname, resolved, src in assign:
                cust = by_user.get(uname)
                if cust is None:
                    continue
                target = lookup[resolved]
                if cust.barangay_id != target.id:
                    cust.barangay = target
                    cust.save(update_fields=["barangay"])
                    written += 1

            self.stdout.write("customers updated: %d" % written)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Barangays now in the system: %s"
            % ", ".join(sorted(b.name for b in Barangay.objects.all()))))
        remaining = Customer.objects.filter(barangay__isnull=True).count()
        self.stdout.write("Customers still without a barangay: %d" % remaining)
        if remaining:
            self.stdout.write("  (these are addresses in areas that are not one of "
                              "the 12 official barangays -- office must confirm)")

    def _read_barangays(self, blob):
        i = blob.find("INSERT INTO `barangays`")
        if i < 0:
            return {}
        seg = blob[i:blob.index(";", i)]
        out = {}
        for m in re.finditer(r"\((\d+),\s*'([^']*)'\)", seg):
            out[int(m.group(1))] = m.group(2).strip()
        return out

    def _read_customers(self, blob):
        # phpMyAdmin CHUNKS large tables across several INSERT statements.
        # Reading only the first block silently analysed 136 of 2,038 rows,
        # which made every ratio look conclusive on 7% of the data.
        blocks, pos = [], 0
        while True:
            i = blob.find("INSERT INTO `customers`", pos)
            if i < 0:
                break
            s = blob.index("VALUES", i) + len("VALUES")
            e = blob.find("INSERT INTO", s + 10)
            blocks.append(blob[s:e if e > 0 else len(blob)])
            pos = s + 10

        ncols = len(CUSTOMER_COLS)
        out = []
        for t in tuples("\n".join(blocks)):
            f = split_row(t)
            if len(f) == ncols:
                out.append(f)
        return out