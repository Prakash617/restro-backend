"""
Prune expired idempotency records.

The idempotency table grows with every mutating request that carries an
``Idempotency-Key``. Records only need to outlive the client's retry window
(offline queues retry for hours), so anything older than ``--max-age-days``
(24 hours by default) can be removed safely.

``apps.offline`` is a tenant app, so the table lives in every restaurant
schema. The command iterates all tenant schemas.

Run it from a cron job or a scheduled task:

    python manage.py prune_idempotency --max-age-days 1
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Delete idempotency replay records older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-days",
            type=int,
            default=1,
            help="Delete records older than this many days (default: 1).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )
        parser.add_argument(
            "--schema",
            action="append",
            dest="schemas",
            help="Only prune this tenant schema (repeatable). Defaults to all.",
        )

    def handle(self, *args, **options):
        from apps.offline.models import IdempotencyRecord
        from apps.tenants.models import Client

        max_age_days = max(0, int(options["max_age_days"]))
        cutoff = timezone.now() - timedelta(days=max_age_days)

        schemas = options.get("schemas")
        if not schemas:
            schemas = list(
                Client.objects.exclude(schema_name="public").values_list(
                    "schema_name", flat=True
                )
            )

        total = 0
        for schema in schemas:
            try:
                with schema_context(schema):
                    queryset = IdempotencyRecord.objects.filter(
                        created_at__lt=cutoff
                    )
                    count = queryset.count()
                    if count and not options["dry_run"]:
                        queryset.delete()
                    total += count
            except Exception as error:  # a schema may not be migrated yet
                self.stderr.write(
                    self.style.WARNING(f"Skipped schema '{schema}': {error}")
                )
                continue

            if count:
                self.stdout.write(f"  {schema}: {count} record(s)")

        verb = "would be deleted" if options["dry_run"] else "deleted"
        self.stdout.write(
            self.style.SUCCESS(f"{total} idempotency record(s) {verb}.")
        )
