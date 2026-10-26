"""
Import quarterly report figures from a hand-made CSV (one row per company and quarter):

    symbol,fiscal_year,quarter,reported_on,net_profit,net_worth,distributable_profit,
    share_count,eps,book_value,dpps,price_on_report_date

Required: symbol, fiscal_year (2082/83 or 2082/2083), quarter (1-4).  Every other cell may
be blank.  ``eps`` is the annualized EPS as filed; leave it blank to derive it from net
profit / share count.  Numbers may use thousands separators ("1,23,456.78").

Idempotent: rows upsert on (company, fiscal year, quarter) and the file is authoritative,
so a re-import of a revised (audited) filing overwrites every column, blanks included.
Quarter 4 rows also fill YearlyDPPS.  Invalid rows are skipped and reported with the reason.

    python manage.py import_quarterly_reports --file reports.csv [--sector BANKING] [--dry-run]
"""

import csv
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.companies.services.selection import tracked_active_companies
from apps.reports.models import QuarterlyReport
from apps.reports.services import quarterly_reports
from apps.reports.services.dividends import normalise_fiscal_year

logger = logging.getLogger(__name__)

FISCAL_YEAR_RE = re.compile(r"^\d{4}/(\d{2}|\d{4})$")
REQUIRED = ("symbol", "fiscal_year", "quarter")
DECIMAL_FIELDS = ("net_profit", "net_worth", "distributable_profit", "eps", "book_value", "dpps",
                  "price_on_report_date")


class RowError(ValueError):
    pass


def _decimal(row, field):
    raw = (row.get(field) or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise RowError(f"{field} is not a number ({row[field]!r})") from None
    if not value.is_finite():
        raise RowError(f"{field} is not a number ({row[field]!r})")
    return value


def parse_row(row):
    """CSV row -> (symbol, fiscal_year, quarter, defaults); raises RowError with the reason."""
    symbol = (row.get("symbol") or "").strip().upper()
    if not symbol:
        raise RowError("symbol is blank")

    raw_year = (row.get("fiscal_year") or "").strip()
    fiscal_year = normalise_fiscal_year(raw_year) if FISCAL_YEAR_RE.match(raw_year) else ""
    if not fiscal_year:
        raise RowError(f"fiscal_year must look like 2082/83 ({raw_year!r})")

    raw_quarter = (row.get("quarter") or "").strip()
    if raw_quarter not in ("1", "2", "3", "4"):
        raise RowError(f"quarter must be 1-4 ({raw_quarter!r})")

    defaults = {field: _decimal(row, field) for field in DECIMAL_FIELDS}

    shares = _decimal(row, "share_count")
    if shares is not None and (shares != shares.to_integral_value() or shares <= 0):
        raise RowError(f"share_count must be a positive whole number ({row['share_count']!r})")
    defaults["share_count"] = int(shares) if shares is not None else None

    raw_date = (row.get("reported_on") or "").strip()
    try:
        defaults["reported_on"] = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None
    except ValueError:
        raise RowError(f"reported_on must use YYYY-MM-DD ({raw_date!r})") from None

    return symbol, fiscal_year, int(raw_quarter), defaults


class Command(BaseCommand):
    help = "Import quarterly report figures for tracked companies from a CSV file (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="CSV path (UTF-8).")
        parser.add_argument("--sector", help="Only import companies of this sector code, e.g. BANKING.")
        parser.add_argument("--dry-run", action="store_true", help="Validate and report without saving.")

    def handle(self, *args, **options):
        sector = (options["sector"] or "").strip().upper() or None
        if sector and sector not in quarterly_reports.SECTORS:
            raise CommandError(f"--sector must be one of {sorted(quarterly_reports.SECTORS)}.")
        companies = {company.symbol: company for company in tracked_active_companies()}
        in_sector = {c.symbol for c in quarterly_reports.sector_companies(sector)} if sector else None

        path = options["file"]
        try:
            source = open(path, "r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError(f"Could not open {path}: {exc}") from exc

        created = updated = 0
        skipped = []
        seen = {}
        q4_company_ids = set()
        with source, transaction.atomic():
            reader = csv.DictReader(source)
            missing = [field for field in REQUIRED if field not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f"CSV is missing the column(s): {', '.join(missing)}.")

            for line, row in enumerate(reader, start=2):
                try:
                    symbol, fiscal_year, quarter, defaults = parse_row(row)
                    company = companies.get(symbol)
                    if company is None:
                        raise RowError(f"{symbol} is not an active tracked company")
                except RowError as exc:
                    skipped.append((line, str(exc)))
                    continue
                if in_sector is not None and symbol not in in_sector:
                    continue
                key = (symbol, fiscal_year, quarter)
                if key in seen:
                    self.stderr.write(self.style.WARNING(
                        f"Line {line}: {symbol} {fiscal_year} Q{quarter} repeats line {seen[key]}; the later row wins."))
                seen[key] = line

                _, was_created = QuarterlyReport.objects.update_or_create(
                    company=company, fiscal_year=fiscal_year, quarter=quarter, defaults=defaults,
                )
                created += int(was_created)
                updated += int(not was_created)
                if quarter == 4:
                    q4_company_ids.add(company.pk)

            dpps_created, dpps_updated = (
                quarterly_reports.fill_yearly_dpps(company_ids=q4_company_ids) if q4_company_ids else (0, 0)
            )
            if options["dry_run"]:
                transaction.set_rollback(True)
            else:
                quarterly_reports.invalidate_cache()

        for line, reason in skipped:
            logger.warning("import_quarterly_reports %s line %s skipped: %s", path, line, reason)
            self.stderr.write(self.style.WARNING(f"Line {line} skipped: {reason}"))

        prefix = "[dry run, nothing saved] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Reports: {created} created, {updated} updated, {len(skipped)} skipped. "
            f"Yearly DPPS from Q4: {dpps_created} created, {dpps_updated} updated."
        ))
