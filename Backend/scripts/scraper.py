"""
Scrape financial reports from nepalipaisa.com into a local database.

Usage:
    pip install requests
    python scraper.py --symbols-file tracked_symbols.txt          # tracked companies only (incremental)
    python scraper.py --symbols-file tracked_symbols.txt --full   # re-crawl every page
    python scraper.py --max-pages 5                               # no symbol list: latest pages of everything

tracked_symbols.txt: one stock symbol per line (e.g. HURJA).

Writes to SQLite (reports.db) so it runs anywhere. To use MySQL/Postgres,
only the `connect()` / `upsert()` functions need changing; the table layout
is in SCHEMA below.
"""
import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

API = "https://nepalipaisa.com/api/GetFinancialReportDocuments"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ReportsSync/1.0)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://nepalipaisa.com/financial-report",
}
PER_PAGE = 10
DELAY_SECONDS = 1.0   # be polite to the site
HARD_PAGE_LIMIT = 300

SCHEMA = """
CREATE TABLE IF NOT EXISTS financial_reports (
    document_id     INTEGER PRIMARY KEY,   -- financialReportDocumentId from the API
    company_id      INTEGER,
    symbol          TEXT NOT NULL,
    company_name    TEXT,
    duration        TEXT,                  -- categoryName: Monthly, 1st Quarter ... Annual
    fiscal_year_bs  TEXT,                  -- e.g. 2083/2084
    fiscal_year_ad  TEXT,                  -- e.g. 2026/2027
    report_date_bs  TEXT,                  -- e.g. 2083-07-20
    report_date_ad  TEXT,                  -- e.g. 2026-11-06
    title           TEXT,
    file_name       TEXT,                  -- file on nepalipaisa (pdf or jpg)
    is_active       INTEGER,
    scraped_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_fr_symbol   ON financial_reports(symbol);
CREATE INDEX IF NOT EXISTS idx_fr_fy       ON financial_reports(fiscal_year_bs);
CREATE INDEX IF NOT EXISTS idx_fr_duration ON financial_reports(duration);
CREATE INDEX IF NOT EXISTS idx_fr_date     ON financial_reports(report_date_ad);
"""


def connect(path="reports.db"):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def upsert(con, row):
    con.execute(
        """
        INSERT INTO financial_reports
            (document_id, company_id, symbol, company_name, duration,
             fiscal_year_bs, fiscal_year_ad, report_date_bs, report_date_ad,
             title, file_name, is_active, scraped_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(document_id) DO UPDATE SET
            company_name=excluded.company_name, duration=excluded.duration,
            fiscal_year_bs=excluded.fiscal_year_bs, fiscal_year_ad=excluded.fiscal_year_ad,
            report_date_bs=excluded.report_date_bs, report_date_ad=excluded.report_date_ad,
            title=excluded.title, file_name=excluded.file_name,
            is_active=excluded.is_active, scraped_at=excluded.scraped_at
        """,
        (
            row["financialReportDocumentId"],
            row.get("companyId"),
            (row.get("stockSymbol") or "").strip(),
            (row.get("companyName") or "").strip(),
            row.get("categoryName"),
            row.get("fiscalYearBS"),
            row.get("fiscalYearAD"),
            row.get("reportDateBS"),
            row.get("reportDateAD"),
            (row.get("reportName") or "").strip(),
            row.get("fileName"),
            1 if row.get("isActive") else 0,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )


def fetch_page(session, symbol, page):
    params = {
        "stockSymbol": symbol,
        "sectorCode": "",
        "fiscalYearId": 0,
        "reportCategoryId": 0,
        "pageNo": page,
        "itemsPerPage": PER_PAGE,
        "pagePerDisplay": 5,
    }
    for attempt in range(3):
        try:
            r = session.get(API, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            payload = r.json()
            return (payload.get("result") or {}).get("data") or []
        except (requests.RequestException, ValueError) as exc:
            print(f"  retry {attempt + 1}/3 ({symbol or 'ALL'} p{page}): {exc}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {symbol or 'ALL'} page {page}")


def known_ids(con):
    return {r[0] for r in con.execute("SELECT document_id FROM financial_reports")}


def crawl(con, session, symbol, full, max_pages, tracked):
    seen = known_ids(con)
    new_count = 0
    for page in range(1, min(max_pages, HARD_PAGE_LIMIT) + 1):
        rows = fetch_page(session, symbol, page)
        if not rows:
            break
        page_new = 0
        for row in rows:
            sym = (row.get("stockSymbol") or "").strip().upper()
            if tracked and sym not in tracked:
                continue
            if row["financialReportDocumentId"] not in seen:
                page_new += 1
            upsert(con, row)
        con.commit()
        new_count += page_new
        # Incremental mode: results are newest-first, so a page with nothing new means we're caught up.
        if not full and page_new == 0:
            break
        if len(rows) < PER_PAGE:
            break
        time.sleep(DELAY_SECONDS)
    return new_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols-file", help="text file with one tracked symbol per line")
    ap.add_argument("--db", default="reports.db")
    ap.add_argument("--full", action="store_true", help="crawl all pages instead of stopping when caught up")
    ap.add_argument("--max-pages", type=int, default=HARD_PAGE_LIMIT)
    args = ap.parse_args()

    con = connect(args.db)
    session = requests.Session()

    if args.symbols_file:
        with open(args.symbols_file, encoding="utf-8") as fh:
            symbols = [s.strip().upper() for s in fh if s.strip() and not s.startswith("#")]
        tracked = set(symbols)
        total = 0
        for i, sym in enumerate(symbols, 1):
            n = crawl(con, session, sym, args.full, args.max_pages, tracked)
            total += n
            print(f"[{i}/{len(symbols)}] {sym}: {n} new")
            time.sleep(DELAY_SECONDS)
        print(f"Done. {total} new reports.")
    else:
        n = crawl(con, session, "", args.full, args.max_pages, set())
        print(f"Done. {n} new reports.")


if __name__ == "__main__":
    main()