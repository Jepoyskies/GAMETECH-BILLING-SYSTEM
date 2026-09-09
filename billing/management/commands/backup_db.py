import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Creates a backup of the SQLite database and zips it."

    def handle(self, *args, **kwargs):
        # The database is db.sqlite3 in the root directory
        db_path = settings.DATABASES["default"]["NAME"]

        # Create a backups directory if it doesn't exist
        backup_dir = os.path.join(settings.BASE_DIR, "data", "backups")
        os.makedirs(backup_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"db_backup_{timestamp}.sqlite3"
        backup_filepath = os.path.join(backup_dir, backup_filename)

        try:
            # Copy the database file
            shutil.copy2(db_path, backup_filepath)

            # Zip the file to save space
            zip_filename = f"db_backup_{timestamp}"
            shutil.make_archive(
                os.path.join(backup_dir, zip_filename),
                "zip",
                backup_dir,
                backup_filename,
            )

            # Remove the unzipped copy
            os.remove(backup_filepath)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully backed up database to {zip_filename}.zip"
                )
            )

            # Here you could easily add boto3 to upload to S3 or Google Drive API

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to backup database: {e}"))
