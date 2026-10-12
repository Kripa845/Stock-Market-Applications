from django.core.management.base import BaseCommand

from apps.market_indices.models import MarketIndex
from apps.market_indices.sectors import MAIN_INDICES, SUB_INDICES


class Command(BaseCommand):
    help = "Create / refresh the catalogue of NEPSE main indices and the 13 sub-indices."

    def handle(self, *args, **options):
        created = 0
        for order, (code, name) in enumerate(MAIN_INDICES, start=1):
            _, was_created = MarketIndex.objects.update_or_create(
                code=code,
                defaults={"name": name, "kind": MarketIndex.KIND_MAIN, "sector_name": "", "sort_order": order},
            )
            created += was_created
        for order, (code, name, sector) in enumerate(SUB_INDICES, start=1):
            _, was_created = MarketIndex.objects.update_or_create(
                code=code,
                defaults={"name": name, "kind": MarketIndex.KIND_SUB, "sector_name": sector, "sort_order": order},
            )
            created += was_created
        self.stdout.write(self.style.SUCCESS(
            f"{created} created, {MarketIndex.objects.count()} indices in total."
        ))
