from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import F
from apps.companies.models import Company, TrackedCompany

from .constants import DURATIONS, FISCAL_YEARS, PAGE_SIZE
from .models import FinancialReport


def _tracked_company_ids():
    return list(TrackedCompany.objects.filter(is_tracked=True).values_list("company_id", flat=True))


def _file_url(file_name):
    """Build the document link. Set FINANCIAL_REPORT_FILE_BASE_URL in settings (ends with '/')."""
    base = getattr(settings, "FINANCIAL_REPORT_FILE_BASE_URL", "")
    return f"{base}{file_name}" if base and file_name else None


def financial_reports_page(request):
    # All Sectors: every sector present in our database.
    sectors = list(
        Company.objects.exclude(sector__isnull=True)
        .exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )
    # All Companies: tracked companies only (sector kept so the page can narrow the list).
    companies = list(
        Company.objects.filter(id__in=_tracked_company_ids())
        .order_by("symbol")
        .values("symbol", "name", "sector")
    )
    return render(request, "financial_reports/financial_reports.html", {
        "sectors": sectors,
        "companies": companies,
        "fiscal_years": FISCAL_YEARS,
        "durations": DURATIONS,
    })


def financial_reports_filters(request):
    """Dropdown values for the React page."""
    sectors = list(
        Company.objects.exclude(sector__isnull=True)
        .exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )
    companies = list(
        Company.objects.filter(id__in=_tracked_company_ids())
        .order_by("symbol")
        .values("symbol", "name", "sector")
    )
    return JsonResponse({
        "sectors": sectors,
        "companies": companies,
        "fiscal_years": FISCAL_YEARS,
        "durations": DURATIONS,
    })


def financial_reports_api(request):
    qs = FinancialReport.objects.filter(
        is_active=True,
        company_id__in=_tracked_company_ids(),
    )

    sector = request.GET.get("sector", "").strip()
    company = request.GET.get("company", "").strip().upper()
    fiscal_year = request.GET.get("fiscal_year", "").strip()
    duration = request.GET.get("duration", "").strip()

    if sector:
        qs = qs.filter(company__sector=sector)
    if company:
        qs = qs.filter(symbol=company)
    if fiscal_year:
        qs = qs.filter(fiscal_year_bs=fiscal_year)
    if duration:
        qs = qs.filter(duration=duration)

    try:
        page_no = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        page_no = 1

    paginator = Paginator(qs.order_by(F("report_date_ad").desc(nulls_last=True),"-document_id"), PAGE_SIZE)
    try:
        page = paginator.page(page_no)
    except EmptyPage:
        page = paginator.page(paginator.num_pages) if paginator.num_pages else None

    if page is None:
        return JsonResponse({"results": [], "page": 1, "num_pages": 0, "total": 0})

    start = (page.number - 1) * PAGE_SIZE
    results = [
        {
            "sn": start + i + 1,
            "date": r.report_date_bs,
            "symbol": r.symbol,
            "fiscal_year": r.fiscal_year_bs,
            "duration": r.duration,
            "title": r.title,
            "file_url": _file_url(r.file_name),
        }
        for i, r in enumerate(page.object_list)
    ]
    return JsonResponse({
        "results": results,
        "page": page.number,
        "num_pages": paginator.num_pages,
        "total": paginator.count,
    })
