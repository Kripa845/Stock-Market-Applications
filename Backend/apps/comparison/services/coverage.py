"""
Data-coverage report: runs the comparison profile for every tracked company and
lists what each one is missing, plus sanity checks and the source-table checks
the comparison relies on.  Read-only.
"""

from django.db.models import Count, Max
from django.utils import timezone

from apps.floorsheet.models import FloorsheetTransaction
from apps.market_data.models import DailyPrice
from apps.market_data.services.market_stats import tracked_companies
from apps.market_data.services.price_adjustments import adjustment_sessions
from apps.market_intelligence.models import CompanyTechnicalSnapshot
from apps.reports.models import CompanyEarnings, DividendAnnouncement, QuarterlyReport

from .compare import company_profile, expected_latest_session

MIN_SESSIONS_FOR_LONG_WINDOWS = 200


def coverage_report(company_ids=None, now=None):
    companies = list(tracked_companies(company_ids).order_by("symbol"))
    ids = [c.id for c in companies]
    expected = expected_latest_session(now)
    adjustments = adjustment_sessions(ids)

    def counts(queryset, field="company_id"):
        return dict(queryset.values_list(field).annotate(n=Count("id")))

    price_counts = counts(DailyPrice.objects.filter(source="crawled", company_id__in=ids))
    snapshot_counts = counts(CompanyTechnicalSnapshot.objects.filter(company_id__in=ids))
    quarter_counts = counts(QuarterlyReport.objects.filter(company_id__in=ids))
    earnings_counts = counts(CompanyEarnings.objects.filter(symbol__in=[c.symbol for c in companies]), "symbol")
    floorsheet_last = dict(FloorsheetTransaction.objects.filter(company_id__in=ids)
                           .values_list("company_id").annotate(d=Max("date")))

    rows, assumptions = [], {"company_earnings_rows": {}, "quarterly_report_null_fields": {}, "live_price": {}}
    for company in companies:
        try:
            profile = company_profile(company, adjustments.get(company.id, []))
        except Exception as exc:  # noqa: BLE001 - the report must cover every company
            rows.append({"symbol": company.symbol, "sector": company.sector, "error": type(exc).__name__})
            continue
        general, fundamentals, technicals = profile["general"], profile["fundamentals"], profile["technicals"]
        dq = profile["data_quality"]
        report = QuarterlyReport.objects.filter(company=company).order_by("-fiscal_year", "-quarter").first()
        dividend_rows = (DividendAnnouncement.objects.filter(company=company).count()
                         or DividendAnnouncement.objects.filter(company__isnull=True, symbol=company.symbol).count())
        sessions = price_counts.get(company.id, 0)

        problems = []
        if sessions < MIN_SESSIONS_FOR_LONG_WINDOWS:
            problems.append("fewer_than_200_sessions")
        if report is None or report.eps is None:
            problems.append("null_eps")
        if report is None or report.book_value is None:
            problems.append("null_book_value")
        if company.listed_shares is None:
            problems.append("null_listed_shares")
        if not dividend_rows:
            problems.append("no_dividend_record")
        if dq["price_as_of"] is None or dq["price_as_of"] < expected:
            problems.append("stale_last_price")
        if general["face_value_source"] == "default_100":
            problems.append("face_value_assumed_100")
        if any(w["code"] == "unadjusted_price_adjustment" for w in dq["warnings"]):
            problems.append("unadjusted_bonus_in_lookback")

        # Sanity checks on the computed figures.
        checks = {}
        eps, pe = general["eps_ttm"], fundamentals["pe"]
        if eps is not None and eps > 0:
            checks["pe_positive"] = pe is not None and pe > 0
        if technicals["rsi"] is not None:
            checks["rsi_in_range"] = 0 < technicals["rsi"] < 100
        if general["market_cap"] is not None:
            checks["market_cap_positive"] = general["market_cap"] > 0
        if None not in (general["week52_low"], general["week52_high"], general["ltp"]):
            checks["ltp_within_52w"] = general["week52_low"] <= general["ltp"] <= general["week52_high"]
        if fundamentals["dividend"]:
            d = fundamentals["dividend"]
            checks["dividend_total_is_sum"] = d["total_pct"] == d["cash_pct"] + d["bonus_pct"]
        failed = [name for name, ok in checks.items() if not ok]

        rows.append({
            "symbol": company.symbol,
            "sector": company.sector,
            "price_sessions": sessions,
            "snapshot_sessions": snapshot_counts.get(company.id, 0),
            "quarters_in_quarterly_report": quarter_counts.get(company.id, 0),
            "eps_present": bool(report and report.eps is not None),
            "book_value_present": bool(report and report.book_value is not None),
            "listed_shares_present": company.listed_shares is not None,
            "dividend_rows": dividend_rows,
            "price_as_of": dq["price_as_of"],
            "snapshot_as_of": dq["snapshot_as_of"],
            "null_fields": [entry["field"] for entry in dq["null_fields"]],
            "problems": problems,
            "sanity_checks_failed": failed,
            "price_adjustment_sessions": [e["date"] for e in adjustments.get(company.id, [])],
        })

        assumptions["company_earnings_rows"][company.symbol] = earnings_counts.get(company.symbol, 0)
        if report:
            assumptions["quarterly_report_null_fields"][company.symbol] = [
                name for name in ("net_profit", "net_worth", "share_count") if getattr(report, name) is None
            ]
        last_trade = None
        last_day = floorsheet_last.get(company.id)
        if last_day:
            trade = (FloorsheetTransaction.objects.filter(company=company, date=last_day)
                     .exclude(transaction_id__startswith="TX-")
                     .order_by("-trade_time", "-id").values("rate", "trade_time").first())
            last_trade = trade and {"date": last_day, "rate": trade["rate"], "trade_time": trade["trade_time"]}
        assumptions["live_price"][company.symbol] = {
            "company_ltp": company.ltp,
            "company_prices_updated_at": company.prices_updated_at,
            "latest_daily_price": {"date": dq["price_as_of"], "close": general["ltp"]}
            if general["ltp_source"] == "daily_price" else None,
            "last_floorsheet_trade": last_trade,
            "company_ltp_differs_from_last_trade": bool(last_trade and company.ltp is not None
                                                        and company.ltp != last_trade["rate"]),
        }

    return {
        "as_of": timezone.localtime(now).isoformat(),
        "expected_latest_session": expected,
        "companies": rows,
        "assumptions": assumptions,
        "tracked_count": len(companies),
    }
