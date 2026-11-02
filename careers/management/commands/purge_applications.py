from django.core.management.base import BaseCommand

from careers.services import RETENTION_DAYS, purge_applications


class Command(BaseCommand):
    help = f"Anonymize applications closed for {RETENTION_DAYS} days or more."

    def handle(self, *args, **options):
        count = purge_applications()
        self.stdout.write(f"Anonymized {count} application(s).")
