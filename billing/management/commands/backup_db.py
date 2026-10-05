from django.core.management.base import BaseCommand, CommandError

from billing.backup import create_backup, restore_hint


class Command(BaseCommand):
    help = "Creates a database backup. Works on PostgreSQL and SQLite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dest", type=str, default=None,
            help="Directory to write the backup into (default: <BASE_DIR>/data/backups).",
        )

    def handle(self, *args, **kwargs):
        try:
            path, description, engine = create_backup(dest_dir=kwargs.get("dest"))
        except Exception as e:
            # Non-zero exit so cron/monitoring notices a failed backup.
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(f"Backup written: {path}"))
        self.stdout.write(f"  method : {description}")
        self.stdout.write(f"  restore: {restore_hint(engine)}")