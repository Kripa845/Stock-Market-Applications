from django.core.management.base import BaseCommand

from apps.market_data.models import Broker, FloorsheetTransaction


class Command(BaseCommand):
    help = "Compare numeric floorsheet broker codes with named broker records."

    def handle(self, *args, **options):
        found = set()
        for field in ("buyer_broker", "seller_broker"):
            for code in FloorsheetTransaction.objects.values_list(field, flat=True).distinct():
                try:
                    found.add(int(str(code).strip()))
                except (TypeError, ValueError):
                    continue

        names = dict(
            Broker.objects.filter(broker_no__in=found)
            .exclude(name="")
            .values_list("broker_no", "name")
        )
        missing = sorted(found - set(names))
        count = Broker.objects.filter(broker_no__isnull=False).count()
        self.stdout.write(f"Broker records with broker_no: {count}")
        if count != 91:
            self.stderr.write(self.style.WARNING(
                f"Expected 91 broker records after a complete crawl; found {count}."
            ))
        self.stdout.write(f"Numeric floorsheet brokers found: {len(found)}")
        if missing:
            self.stdout.write("Broker numbers without names: " + ", ".join(map(str, missing)))
        else:
            self.stdout.write(self.style.SUCCESS("Every numeric floorsheet broker has a name."))
