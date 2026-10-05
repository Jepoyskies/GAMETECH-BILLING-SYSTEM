"""One working database backup path, shared by the command and the web view.

WHY THIS EXISTS
---------------
There were two backup implementations and BOTH were broken on this deployment:

1. `manage.py backup_db` assumed SQLite and did `shutil.copy2(NAME, ...)`.
   With PostgreSQL, `DATABASES['default']['NAME']` is the database *name*
   ("gametech_db"), not a file, so it raised
   `No such file or directory: 'gametech_db'`.

2. `billing.views.settings.backup_database_view` shelled out to `pg_dump`.
   The web container has no PostgreSQL client installed (pg_dump only exists
   in the separate gametech-db container), so it raised FileNotFoundError.

A business with 2,000+ subscribers and a live ledger needs a backup button
that actually works, so the logic lives here once.

STRATEGY
--------
* SQLite          -> copy the file. Cheap and complete.
* Everything else -> prefer `pg_dump` when the binary exists (it is the
  proper tool: restores with pg_restore, preserves everything).
* pg_dump missing -> fall back to Django's own serialiser
  (`dumpdata`), gzipped. Slower and restores with `loaddata`, but it needs
  no external binary and works in any environment, which is exactly the
  situation the web container is in.

The method actually used is returned so the operator can see which one ran
and therefore how to restore it.
"""

import gzip
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

from django.conf import settings
from django.core.management import call_command


def _pg_dump_binary():
    """Locate pg_dump, or None."""
    import shutil as sh
    return sh.which("pg_dump")


def create_backup(dest_dir=None):
    """Write a backup and return (path, human description, engine_used).

    Raises RuntimeError with an operator-readable message on failure.
    """
    db = settings.DATABASES["default"]
    engine = db.get("ENGINE", "")
    dest_dir = dest_dir or os.path.join(settings.BASE_DIR, "data", "backups")
    os.makedirs(dest_dir, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ---------------------------------------------------------- SQLite
    if "sqlite" in engine:
        db_path = db.get("NAME")
        if not db_path or not os.path.exists(db_path):
            raise RuntimeError(
                "SQLite database file not found (expected at %r)." % db_path
            )
        target = os.path.join(dest_dir, f"db_backup_{stamp}.sqlite3")
        shutil.copy2(db_path, target)
        size = os.path.getsize(target)
        if size == 0:
            raise RuntimeError("Backup produced an empty file.")
        return target, f"SQLite file copy, {size/1024/1024:.1f} MB", "sqlite"

    # ------------------------------------------------------- PostgreSQL
    if "pg_dump" in (db.get("NAME") or ""):  # paranoia: never treat a db name as a file
        raise RuntimeError("Unexpected database name for a file-based backup.")

    binary = _pg_dump_binary()
    if binary:
        target = os.path.join(dest_dir, f"db_backup_{stamp}.sql")
        env = os.environ.copy()
        env["PGPASSWORD"] = db.get("PASSWORD", "") or ""
        cmd = [
            binary,
            "--host", db.get("HOST", "localhost"),
            "--port", str(db.get("PORT", 5432)),
            "--username", db.get("USER", "") or "",
            "--dbname", db.get("NAME", "") or "",
            "--file", target,
        ]
        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True, timeout=600)
        except subprocess.TimeoutExpired:
            raise RuntimeError("pg_dump timed out after 10 minutes.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "pg_dump failed: %s" % (e.stderr.decode("utf-8", "replace")[:300] or e)
            )
        size = os.path.getsize(target)
        if size == 0:
            raise RuntimeError("pg_dump produced an empty file.")
        return target, f"pg_dump SQL dump, {size/1024/1024:.1f} MB", "pg_dump"

    # ------------------------------------- fallback: Django's serialiser
    target = os.path.join(dest_dir, f"db_backup_{stamp}.json.gz")
    fd = gzip.open(target, "wt", encoding="utf-8")
    try:
        call_command("dumpdata", "--natural-foreign", "--natural-primary", stdout=fd)
    finally:
        fd.close()
    size = os.path.getsize(target)
    if size == 0:
        raise RuntimeError("dumpdata produced an empty file.")
    return (
        target,
        "Django dumpdata (gzipped JSON), %.1f MB -- restore with loaddata"
        % (size / 1024 / 1024),
        "dumpdata",
    )


def restore_hint(engine_used):
    if engine_used == "pg_dump":
        return "Restore with: psql -d gametech_db -f <file>.sql"
    if engine_used == "sqlite":
        return "Restore by copying the file over db.sqlite3"
    return "Restore with: gunzip <file>.json.gz | manage.py loaddata -"