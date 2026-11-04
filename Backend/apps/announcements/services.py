"""
Announcement sync from the JSON feed the ShareHub page itself loads:
    GET https://sharehubnepal.com/data/api/v1/announcement?Size=..&Page=..
No browser, no login. REPLACES the Playwright services.py (same function name,
so tasks.py / the management command / views keep working).
"""
import logging
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.utils import timezone as dj_tz
from django.utils.dateparse import parse_datetime

from .models import Announcement

log = logging.getLogger(__name__)

ENDPOINT = "https://sharehubnepal.com/data/api/v1/announcement"
PAGE_SIZE = 100      # if the server rejects this, try 50 or 12 (the site itself uses 12)
MAX_PAGES = 200      # safety cap
NPT = ZoneInfo("Asia/Kathmandu")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockDashboard/1.0)", "Accept": "application/json"}

# Base URL for iconUrl ("sharehub/images/..."). Right-click a logo on the page ->
# "Copy image address" to find it, then set SHAREHUB_ICON_BASE in settings.
ICON_BASE = getattr(settings, "SHAREHUB_ICON_BASE", "")


def fetch_page(page, retry=0):
    r = requests.get(ENDPOINT, params={"Size": PAGE_SIZE, "Page": page}, headers=HEADERS, timeout=30)
    if r.status_code == 429 and retry < 3:
        time.sleep(int(r.headers.get("Retry-After", 30)))
        return fetch_page(page, retry + 1)
    r.raise_for_status()
    return r.json()["data"]


def normalize(item):
    # announcementDate has no timezone; the site shows it as-is, and the values line up with
    # Nepal market hours, so it is Nepal local time.
    published = parse_datetime(item["announcementDate"])
    if published and dj_tz.is_naive(published):
        published = published.replace(tzinfo=NPT)
    icon = item.get("iconUrl") or ""
    if icon and not icon.startswith("http") and ICON_BASE:
        icon = ICON_BASE.rstrip("/") + "/" + icon.lstrip("/")
    return {
        "symbol": (item.get("symbol") or "").upper(),
        "company_name": item.get("securityName") or "",
        "logo_url": icon,
        "title": item.get("title") or item.get("subTitle") or "",
        "is_event": bool(item.get("isEvent")),
        "type": item.get("type") or "",
        "category": item.get("category") or "",
        "source": item.get("source") or "",
        "details_url": item.get("newsUrl") or item.get("attachmentUrl") or "",
        "published_at": published,
        "raw": item,
    }


def sync_announcements(days_back=7, debug=False):
    tracked = {s.upper() for s in settings.TRACKED_SYMBOLS}
    cutoff = dj_tz.now() - timedelta(days=days_back)
    saved = seen = 0
    for page in range(1, MAX_PAGES + 1):
        data = fetch_page(page)
        items = data.get("content", [])
        if debug:
            print(f"page {page}: {len(items)} items (total {data.get('totalItems')})")
        done = False
        for item in items:
            row = normalize(item)
            if not row["published_at"]:
                continue
            if row["published_at"] < cutoff:
                done = True  # feed is newest-first, so everything after this is older
                continue
            seen += 1
            # keep the 20 tracked companies + market-wide items with no symbol
            if row["symbol"] and row["symbol"] not in tracked:
                continue
            Announcement.objects.update_or_create(external_id=str(item["id"]), defaults=row)
            saved += 1
        if done or not data.get("hasNext"):
            break
        time.sleep(0.5)  # be polite
    if debug:
        print(f"within window: {seen}, kept (tracked/market-wide): {saved}")
    return saved