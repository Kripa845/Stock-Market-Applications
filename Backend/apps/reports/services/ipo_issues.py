"""
Saving crawled public issues (IPO, FPO, right share ...) from ShareSansar's "Existing Issues".

Kept out of the Scrapy pipeline so the upsert is tested without Scrapy.  Re-running a crawl
updates rows in place: the key is (source, source_id), see ``IpoIssue``.
"""

from django.utils import timezone

from apps.companies.models import Company
from apps.reports.models import IpoIssue

# ShareSansar's ``type`` query value per tab of the Existing Issues page (checked 2026-10-28;
# there is no type 6).
SHARESANSAR_TYPES = {
    1: IpoIssue.IssueType.IPO,
    2: IpoIssue.IssueType.FPO,
    3: IpoIssue.IssueType.RIGHT,
    4: IpoIssue.IssueType.MUTUAL_FUND,
    5: IpoIssue.IssueType.IPO_LOCAL,
    7: IpoIssue.IssueType.DEBENTURE,
    8: IpoIssue.IssueType.IPO_MIGRANT,
    9: IpoIssue.IssueType.IPO_QII,
}

_FIELDS = ("company_name", "units", "price", "ratio", "issue_manager", "open_date", "close_date",
           "final_date", "listing_date", "source_status", "announcement_url")


def issue_source_id(issue_type, source_company_id, units):
    """None when the row cannot be keyed (no company id or no units)."""
    if not source_company_id or units is None:
        return None
    return f"{issue_type}-{source_company_id}-{units}"


def upsert_issue(data, *, source):
    """
    Save one crawled issue.  ``data``: issue_type, source_id, symbol and the ``_FIELDS``
    (dates as date or None, units int or None, price Decimal or None).

    Returns "created", "updated" or "skipped" (unknown type or no source id).
    """
    issue_type = data.get("issue_type")
    source_id = str(data.get("source_id") or "").strip()
    if issue_type not in IpoIssue.IssueType.values or not source_id:
        return "skipped"

    symbol = (data.get("symbol") or "").strip().upper()
    defaults = {field: data.get(field) for field in _FIELDS}
    defaults.update(
        issue_type=issue_type,
        symbol=symbol,
        company_name=(defaults["company_name"] or "").strip()[:300],
        ratio=(defaults["ratio"] or "").strip()[:20],
        issue_manager=(defaults["issue_manager"] or "").strip()[:200],
        announcement_url=(defaults["announcement_url"] or "").strip()[:1000],
        company=Company.objects.filter(symbol__iexact=symbol).first() if symbol else None,
        scraped_at=timezone.now(),
    )
    row = _same_issue(source, source_id, defaults["open_date"])
    if row is None:
        taken = IpoIssue.objects.filter(source=source, source_id=source_id).exists()
        IpoIssue.objects.create(
            source=source, source_id=f"{source_id}-{defaults['open_date'] or 'pending'}" if taken else source_id, **defaults,
        )
        return "created"
    for field, value in defaults.items():
        setattr(row, field, value)
    row.save()
    return "updated"


def _same_issue(source, source_id, open_date):
    """
    The stored row for this issue, or None.  The key can repeat (API Power issued two right
    shares of 5,670,000 units), so a stored row is the same issue only while it has no opening
    date yet or the same one; another issue under that key is stored as "<key>-<open date>".
    """
    candidates = IpoIssue.objects.filter(source=source, source_id__startswith=source_id).order_by("id")
    for row in candidates:
        if row.source_id != source_id and not row.source_id.startswith(f"{source_id}-"):
            continue      # "ipo-1-100" must not match "ipo-1-1000"
        if row.open_date is None or row.open_date == open_date:
            return row
    return None
