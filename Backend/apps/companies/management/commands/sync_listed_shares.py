from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.market_data.services.market_stats import tracked_companies
from apps.market_indices.services.index_replication import NepseSource, ReplicationError


class Command(BaseCommand):
    help = "Fill Company.listed_shares for the tracked companies from NEPSE's security detail (stockListedShares)."

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true",
                            help="Also replace counts that are already set (e.g. after a bonus issue).")

    def handle(self, *args, overwrite=False, **options):
        companies = list(tracked_companies())
        if not overwrite:
            companies = [c for c in companies if not c.listed_shares]
        if not companies:
            self.stdout.write("Every tracked company already has listed_shares (use --overwrite to refresh).")
            return
        source = NepseSource()
        try:
            ids = {str(row.get("symbol", "")).upper(): row.get("id") for row in source.company_list()}
        except ReplicationError as exc:
            raise CommandError(str(exc)) from exc
        for company in companies:
            security_id = ids.get(company.symbol.upper())
            if not security_id:
                self.stderr.write(f"{company.symbol}: not in NEPSE's company list, skipped")
                continue
            try:
                detail = source.security_detail(security_id, company.symbol)
            except ReplicationError as exc:
                self.stderr.write(f"{company.symbol}: {exc}")
                continue
            company.listed_shares = int(Decimal(str(detail["stockListedShares"])))
            company.save(update_fields=["listed_shares"])
            self.stdout.write(f"{company.symbol}: {company.listed_shares:,}")
