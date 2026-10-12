
import json
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.companies.models import Company, TrackedCompany
from apps.market_data.models import FloorsheetTransaction
from apps.market_data.services.sharehub_floorsheet import ShareHubError, request_floorsheet
from apps.market_data.services.sharehub_time import parse_sharehub_time

PAGE_SIZE = 500          # if ShareHub rejects 500, try 100
PAUSE_SECONDS = 1.0      # pause between requests. Do not lower it.
# No lowercase "page": ShareHub's robots.txt disallows "/*?*page=".
PAGE_PARAM_CANDIDATES = ["Page", "PageIndex", "PageNumber", "pageIndex"]
NPT = ZoneInfo("Asia/Kathmandu")
STATE_FILE = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "sharehub_done_dates.json"


def fetch(d, page=None, page_param=None):
    # ShareHub's own site sends the date without zero padding (2026-10-6); we do the same.
    params = {"Size": PAGE_SIZE, "date": f"{d.year}-{d.month}-{d.day}"}
    if page_param:
        params[page_param] = page
    try:
        return request_floorsheet(params)
    except ShareHubError as exc:
        raise CommandError(str(exc)) from exc


def parse_trade_time(s):
    """ShareHub labels times with 'Z' (UTC), but the clock values are Nepal time
    (trades run until 14:59:59). So we read the clock and attach Asia/Kathmandu."""
    return parse_sharehub_time(s)


def check_database_matches_model():
    """Stop with a clear message if the real table lacks columns the model expects."""
    table = FloorsheetTransaction._meta.db_table
    with connection.cursor() as cur:
        db_cols = {c.name for c in connection.introspection.get_table_description(cur, table)}
    missing = [f.column for f in FloorsheetTransaction._meta.concrete_fields if f.column not in db_cols]
    if missing:
        raise CommandError(
            f"Table {table} is missing columns that models.py expects: {missing}. "
            "Your database is behind your code. Run: python manage.py showmigrations market_data "
            "and paste the output here before going on."
        )


class Command(BaseCommand):
    help = "Load ShareHub floorsheet (with trade times) into FloorsheetTransaction"

    page_param = None

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", required=True, help="oldest date, YYYY-MM-DD")
        parser.add_argument("--to", dest="end", required=True, help="newest date, YYYY-MM-DD")
        parser.add_argument("--dry-run", action="store_true", help="download and report, write nothing")
        parser.add_argument("--force", action="store_true", help="redo days already marked done")
        parser.add_argument("--all-companies", action="store_true")
        parser.add_argument("--existing-only", action="store_true")
        parser.add_argument("--max-pages", type=int, default=500,
                            help="stop if one day needs more pages than this")

    def handle(self, *args, **opts):
        start = date.fromisoformat(opts["start"])
        end = date.fromisoformat(opts["end"])
        if start > end:
            raise CommandError("--from must be on or before --to")

        check_database_matches_model()

        if opts["all_companies"]:
            ids = Company.objects.values_list("id", flat=True)
        elif opts["existing_only"]:
            ids = FloorsheetTransaction.objects.values_list("company_id", flat=True).distinct()
        else:
            ids = TrackedCompany.objects.filter(is_tracked=True).values_list("company_id", flat=True)
        symbol_to_id = {c.symbol: c.id for c in Company.objects.filter(id__in=set(ids))}
        if not symbol_to_id:
            raise CommandError("No companies selected. Check TrackedCompany or use --existing-only.")
        self.stdout.write(f"Companies to load: {len(symbol_to_id)}")

        done = set(json.loads(STATE_FILE.read_text())) if STATE_FILE.exists() else set()
        today_npt = datetime.now(NPT).date()

        d = end
        while d >= start:
            key = d.isoformat()
            if key in done and not opts["force"]:
                self.stdout.write(f"{key}: already done, skipping")
            else:
                finished = self.load_day(d, symbol_to_id, opts)
                # never mark today as done: the market may still be open
                if finished and not opts["dry_run"] and d < today_npt:
                    done.add(key)
                    STATE_FILE.write_text(json.dumps(sorted(done)))
            d -= timedelta(days=1)

    def discover_page_param(self, d):
        """The name of the page parameter is a guess, so try the likely ones on page 2."""
        for name in PAGE_PARAM_CANDIDATES:
            data = fetch(d, 2, name)
            time.sleep(PAUSE_SECONDS)
            if data.get("pageIndex") == 2:
                self.stdout.write(f"Page parameter found: {name}")
                return name, data
        raise CommandError(
            f"Could not find ShareHub's page parameter (tried {PAGE_PARAM_CANDIDATES}). "
            "In Chrome open https://sharehubnepal.com/nepse/floorsheet, press F12, Network tab, "
            "click page 2, and paste the Request URL here."
        )

    def load_day(self, d, symbol_to_id, opts):
        first = fetch(d)
        total_items = first.get("totalItems") or 0
        if not total_items:
            self.stdout.write(f"{d}: no trades from ShareHub (holiday, or not published yet)")
            return d < datetime.now(NPT).date()

        total_pages = first.get("totalPages") or 1
        if total_pages > opts["max_pages"]:
            raise CommandError(
                f"{d} needs {total_pages} pages, so ShareHub is not honouring Size={PAGE_SIZE} "
                f"(it returned pageSize={first.get('pageSize')}). Stopping before sending thousands "
                "of requests. Tell me this message."
            )

        pages = {1: first}
        if total_pages > 1:
            if self.page_param is None:
                self.page_param, pages[2] = self.discover_page_param(d)
            for page in range(2, total_pages + 1):
                if page not in pages:
                    pages[page] = fetch(d, page, self.page_param)
                    time.sleep(PAUSE_SECONDS)
                if pages[page].get("pageIndex") != page:
                    raise CommandError(
                        f"Asked for page {page} but got page {pages[page].get('pageIndex')}. Stopping."
                    )

        rows = {}
        seen_symbols = set()
        for page in sorted(pages):
            for item in pages[page].get("content", []):
                if item["businessDate"][:10] != d.isoformat():
                    raise CommandError(
                        f"Asked for {d} but got {item['businessDate'][:10]}. "
                        "ShareHub did not use our date. Stopping."
                    )
                company_id = symbol_to_id.get(item["symbol"])
                if company_id is None:
                    continue
                seen_symbols.add(item["symbol"])
                txn_id = str(item["contractId"])
                rows[(company_id, txn_id)] = FloorsheetTransaction(
                    company_id=company_id,
                    date=d,
                    transaction_id=txn_id,
                    buyer_broker=str(item["buyerMemberId"]),
                    seller_broker=str(item["sellerMemberId"]),
                    quantity=int(item["contractQuantity"]),
                    rate=Decimal(str(item["contractRate"])),
                    amount=Decimal(str(item["contractAmount"])),
                    trade_time=parse_trade_time(item["tradeTime"]),
                )

        objs = list(rows.values())
        existing = set(
            FloorsheetTransaction.objects.filter(date=d).values_list("company_id", "transaction_id")
        )
        matched = sum(1 for k in rows if k in existing)
        new = len(objs) - matched
        in_db_only = len(existing) - matched

        first_t = last_t = "-"
        time_ok = True
        if objs:
            times = [o.trade_time.astimezone(NPT).time() for o in objs]
            first_t, last_t = min(times), max(times)
            time_ok = dtime(10, 0) <= first_t and last_t <= dtime(15, 30)

        not_seen = sorted(set(symbol_to_id) - seen_symbols)
        self.stdout.write(
            f"{d}: market {total_items} trades | chosen companies {len(objs)} | "
            f"match your rows {matched} | would be new {new} | "
            f"in your DB but not in ShareHub {in_db_only} | times {first_t} to {last_t}"
        )
        if not_seen:
            self.stdout.write(f"   chosen companies with no trades on ShareHub that day: {len(not_seen)} "
                              f"(e.g. {', '.join(not_seen[:8])})")
        if not time_ok:
            msg = ("Trade times fall outside 10:00-15:30 Nepal time. "
                   "The time zone assumption may be wrong.")
            if opts["dry_run"]:
                self.stdout.write(self.style.WARNING("   WARNING: " + msg))
            else:
                raise CommandError(msg + " Nothing was written for this day.")

        if opts["dry_run"]:
            return False

        FloorsheetTransaction.objects.bulk_create(
            objs,
            batch_size=2000,
            update_conflicts=True,
            unique_fields=["company", "date", "transaction_id"],
            update_fields=["trade_time", "amount"],  # only these two are filled on existing rows
        )
        return True