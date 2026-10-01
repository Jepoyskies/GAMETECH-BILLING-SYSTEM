"""
Statically audit every SystemLog.objects.create() call in the codebase.

WHY
---
`SystemLog` has a fixed shape:

    table_name  CharField(255)      REQUIRED
    record_id   CharField(255)      REQUIRED
    action      CharField(50)       REQUIRED  <- short verb: CREATE/UPDATE/DELETE
    changed_by  CharField(255)      REQUIRED
    target_name / old_data / new_data  optional

Two failure modes are trivial to write and INVISIBLE at runtime, because nearly
every call site is wrapped in a bare `try/except: pass`:

1. **Wrong field names.** e.g. `user=`, `ip_address=`, `timestamp=`. Django
   raises `TypeError: SystemLog() got unexpected keyword arguments`, the bare
   except swallows it, and the audit entry is silently lost forever.
2. **`action` longer than 50 chars.** Postgres rejects the insert on a
   varchar(50) overflow. Also swallowed. ERR-089 was exactly this: the
   "Configured Portal Login for Agent" audit trail had never once been written.

This finds both WITHOUT executing anything, so the remaining call sites can be
triaged safely. It is a REPORT tool: it changes no data, and only exits non-zero
with `--strict`, so it is safe in CI.

Usage
-----
    python manage.py audit_systemlog_calls
    python manage.py audit_systemlog_calls --strict     # exit 1 if problems found
    python manage.py audit_systemlog_calls --path dispatch
"""

import ast
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from billing.models import SystemLog

VALID_FIELDS = {
    "id", "table_name", "record_id", "action", "changed_by",
    "target_name", "changed_at", "old_data", "new_data",
}
REQUIRED_FIELDS = {"table_name", "record_id", "action", "changed_by"}
MAX_ACTION_LEN = SystemLog._meta.get_field("action").max_length

# Fields people reach for that SystemLog does not have, and where it belongs.
KNOWN_BAD = {
    "user": "changed_by",
    "username": "changed_by",
    "actor": "changed_by",
    "performed_by": "changed_by",
    "ip_address": "old_data",
    "ip": "old_data",
    "timestamp": "changed_at",
    "description": "new_data",
    "message": "new_data",
    "details": "new_data",
    "module": "table_name",
    "model": "table_name",
    "entity": "table_name",
    "pk": "record_id",
    "obj_id": "record_id",
}

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "migrations", "static", "templates", "history", "docs", "archived_scripts",
}


class Command(BaseCommand):
    help = "Statically detect SystemLog.objects.create() calls with wrong fields or an over-long action."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Exit non-zero if problems are found.")
        parser.add_argument("--path", default="", help="Limit the scan to one top-level app directory.")
        parser.add_argument(
            "--show-dynamic", action="store_true",
            help="Also list action= values built at runtime (need manual length review).",
        )

    # ------------------------------------------------------------------ helpers

    def _roots(self, only):
        base = Path(settings.BASE_DIR)
        if only:
            p = base / only
            return [p] if p.is_dir() else []
        return [p for p in sorted(base.iterdir()) if p.is_dir() and p.name not in SKIP_DIRS]

    @staticmethod
    def _is_systemlog_create(node):
        """True for SystemLog.objects.create(...) and SystemLog.objects.get_or_create()."""
        f = node.func
        if not isinstance(f, ast.Attribute) or f.attr not in ("create", "get_or_create"):
            return False
        owner = f.value
        # SystemLog.objects
        if isinstance(owner, ast.Attribute) and owner.attr == "objects":
            src = owner.value
            if isinstance(src, ast.Name) and src.id == "SystemLog":
                return True
        # SystemLog(...) manager style: SystemLog.objects is expected, but also
        # allow a module-qualified `billing.models.SystemLog.objects`.
        if isinstance(owner, ast.Attribute) and owner.attr == "objects":
            src = owner.value
            if isinstance(src, ast.Attribute) and src.attr == "SystemLog":
                return True
        return False

    @staticmethod
    def _static_len(node):
        """
        Length of an action value that is knowable at parse time.
        Returns (length, is_dynamic).
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return len(node.value), False
        if isinstance(node, ast.JoinedStr):
            # Sum only the literal chunks; any placeholder makes it dynamic.
            total = sum(len(p.value) for p in node.values if isinstance(p, ast.Constant))
            dynamic = any(isinstance(p, ast.FormattedValue) for p in node.values)
            return total, dynamic
        return None, True

    def _scan_file(self, path, base):
        findings = []
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            return findings

        rel = path.relative_to(base).as_posix()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not self._is_systemlog_create(node):
                continue

            kwargs = {}
            for kw in node.keywords:
                if kw.arg is None:
                    continue  # **kwargs spread, cannot verify statically
                kwargs[kw.arg] = kw.value

            def add(kind, detail):
                findings.append({"file": rel, "line": node.lineno, "kind": kind, "detail": detail})

            # 1. Unknown / non-existent fields
            unknown = [k for k in kwargs if k not in VALID_FIELDS]
            for k in unknown:
                hint = f" Did you mean '{KNOWN_BAD[k]}'?" if k in KNOWN_BAD else ""
                add("UNKNOWN FIELD", f"'{k}' is not a SystemLog field -> TypeError, entry lost.{hint}")

            # 2. Missing required fields
            missing = REQUIRED_FIELDS - set(kwargs)
            if missing:
                add("MISSING FIELD", f"required not supplied: {sorted(missing)} -> IntegrityError, entry lost.")

            # 3. Over-long action
            act = kwargs.get("action")
            if act is not None:
                length, dynamic = self._static_len(act)
                if length is not None and length > MAX_ACTION_LEN:
                    extra = " (literal parts already exceed the limit)" if dynamic else ""
                    add(
                        "ACTION TOO LONG",
                        f"action is {length}+ chars, max_length={MAX_ACTION_LEN}{extra} "
                        f"-> varchar overflow, entry lost. Use a short verb and put detail in new_data.",
                    )
                elif dynamic:
                    add("ACTION DYNAMIC", "action is built at runtime; verify it stays a short verb <= %d chars." % MAX_ACTION_LEN)

        return findings

    # ------------------------------------------------------------------ main

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)
        roots = self._roots(options["path"])
        if not roots:
            self.stdout.write(self.style.ERROR("No matching directory to scan."))
            return

        findings, scanned, dyn = [], 0, []
        for root in roots:
            for path in root.rglob("*.py"):
                if any(part in SKIP_DIRS for part in path.parts):
                    continue
                scanned += 1
                for f in self._scan_file(path, base):
                    (dyn if f["kind"] == "ACTION DYNAMIC" else findings).append(f)

        self.stdout.write(self.style.NOTICE(f"Scanned {scanned} python file(s) under {len(roots)} app(s)."))

        if options["show_dynamic"] and dyn:
            self.stdout.write(self.style.WARNING(f"\n{len(dyn)} dynamic action(s) to review manually:\n"))
            for f in dyn:
                self.stdout.write(f"  {f['file']}:{f['line']}")
            self.stdout.write("")

        if not findings:
            self.stdout.write(self.style.SUCCESS(
                f"OK: no definite SystemLog defects. ({len(dyn)} dynamic action(s) pending manual review.)"
            ))
            return

        self.stdout.write(self.style.ERROR(f"\n{len(findings)} definite SystemLog defect(s):\n"))
        for f in findings:
            self.stdout.write(f"  {f['file']}:{f['line']}  [{f['kind']}]")
            self.stdout.write(f"      {f['detail']}")
        self.stdout.write("")
        self.stdout.write(
            "These are SILENT failures: a bare `except: pass` swallows the TypeError /\n"
            "DB error, so the audit entry is never written. See ERR-089.\n"
            f"({len(dyn)} additional dynamic action(s) need manual review.)\n"
        )
        if options["strict"]:
            raise SystemExit(1)
