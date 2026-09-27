import logging

from django.core.management.base import BaseCommand

from apps.analysis.tasks import _rebuild_persisted_market_features
from apps.companies.models import Company

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill persisted volume anomaly and news-price correlation analysis."

    def handle(self, *args, **options):
        completed = 0
        failures = []
        for company in Company.objects.order_by("symbol").iterator():
            try:
                _rebuild_persisted_market_features(company)
                completed += 1
            except Exception as exc:  # noqa: BLE001 - continue with remaining companies
                logger.exception("Backfill failed for %s: %s", company.symbol, exc)
                failures.append(company.symbol)
        self.stdout.write(self.style.SUCCESS(
            f"Processed {completed} companies; feature errors logged for {len(failures)}."
        ))
