from django.core.management.base import BaseCommand

from apps.companies.models import Company
from apps.companies.selection import parse_symbols
from apps.market_intelligence.models import SupportResistanceSet
from apps.market_intelligence.services.support_resistance import compute_support_resistance


class Command(BaseCommand):
    help = "Compute support / resistance levels for the tracked companies (or --symbols) and print them."

    def add_arguments(self, parser):
        parser.add_argument("--symbols", help="Comma-separated symbols, e.g. NABIL,ADBL (default: all tracked)")

    def handle(self, *args, **options):
        symbols = parse_symbols(options["symbols"])
        company_ids = None
        if symbols:
            company_ids = list(Company.objects.filter(symbol__in=symbols).values_list("pk", flat=True))
            missing = set(symbols) - set(Company.objects.filter(pk__in=company_ids).values_list("symbol", flat=True))
            if missing:
                self.stderr.write(f"Unknown symbols: {', '.join(sorted(missing))}")
        result = compute_support_resistance(company_ids)
        self.stdout.write(self.style.SUCCESS(f"Support/resistance: {result}"))

        sets = SupportResistanceSet.objects.select_related("company").prefetch_related("levels")
        if company_ids is not None:
            sets = sets.filter(company_id__in=company_ids)
        for sr_set in sets.order_by("company__symbol"):
            note = f", cut at {sr_set.adjustment_cut}" if sr_set.adjustment_cut else ""
            note += f", {len(sr_set.adjustments)} adjustment(s)" if sr_set.adjustments else ""
            self.stdout.write(
                f"\n{sr_set.company.symbol}  close {sr_set.latest_close}  as of {sr_set.as_of}  "
                f"[{sr_set.status}, {sr_set.sessions_used} sessions{note}]"
            )
            for level in sr_set.levels.all():
                marker = "  <- at price" if level.at_price else ""
                self.stdout.write(
                    f"  {level.kind:10} {level.price:>12}  touches {level.touches}  "
                    f"strength {level.strength}  last {level.last_touch}{marker}"
                )
