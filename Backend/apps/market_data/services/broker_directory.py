"""
Broker directory: every NEPSE member broker with its website and offices.

Sources (checked 2026-10-16):

    NEPSE member list      POST nepalstock.com.np /api/nots/member?&size=500 through the
                           logged-in nepse-data-api client.  Official: broker number, name,
                           membership type, status (A / SUSPEND), dealer flag, TMS link,
                           contact person and number.  No website.
    ShareHub broker pages  https://sharehubnepal.com/broker/<slug>, listed in its sitemap
                           (robots.txt allows /broker/, disallows /api/).  Each page embeds
                           its data as a Next.js payload: website, TMS URL and branches
                           (address, phone, email; head office first).

SEBON's intermediary list and Merolagani's broker list were checked too: neither has
websites.  ``sync_broker_directory`` merges both sources into ``Broker`` rows keyed by
broker number.  NEPSE wins for the official fields; ShareHub only adds what NEPSE lacks.
Nothing is guessed: when ShareHub has no page for a broker, its stored website,
address, email and branches are kept (set them in the admin), otherwise left empty.

Run:  python manage.py sync_broker_directory            (about 2 minutes: 1 page/second)
"""

import json
import re
import time
import urllib.request

from django.db import transaction
from django.utils import timezone

from apps.market_data.models import Broker

NEPSE_MEMBER_PATH = "/api/nots/member?&size=500"
NEPSE_MEMBER_FILTER = {
    "memberName": "", "contactPerson": "", "contactNumber": "", "memberCode": "",
    "provinceId": 0, "districtId": 0, "municipalityId": 0,
}
SHAREHUB_SITEMAP = "https://sharehubnepal.com/data/api/v1/sitemap/broker.xml"
SHAREHUB_PROFILE_RE = re.compile(r"<loc>\s*(https://sharehubnepal\.com/broker/broker-\d+-[a-z0-9-]+)\s*</loc>")
SHAREHUB_DELAY_SECONDS = 1
USER_AGENT = "personal-stock-project/1.0"
TIMEOUT_SECONDS = 30

# The Next.js flight payload: self.__next_f.push([1,"<JS string>"]).
FLIGHT_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
KEEP_WHEN_EMPTY = {"website", "address", "email", "branches"}


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


# ----------------------------------------------------------------------
# Fetch
# ----------------------------------------------------------------------

def fetch_nepse_members(client=None):
    """NEPSE's member rows (one per broker number)."""
    from apps.market_data.services.live_prices import _nepse_client

    client = client or _nepse_client()
    response = client.session.post(
        f"{client.BASE_URL}{NEPSE_MEMBER_PATH}", json=NEPSE_MEMBER_FILTER, headers=client._get_auth_headers(),
    )
    response.raise_for_status()
    return response.json().get("content") or []


def parse_sharehub_profile(html):
    """The broker object embedded in one ShareHub broker page, or None."""
    for chunk in FLIGHT_CHUNK_RE.findall(html):
        if '\\"initialData\\"' not in chunk:
            continue
        try:
            text = json.loads(f'"{chunk}"')
            start = text.index('"initialData":') + len('"initialData":')
            payload, _ = json.JSONDecoder().raw_decode(text[start:])
        except (ValueError, json.JSONDecodeError):
            continue
        data = (payload or {}).get("data") or {}
        if data.get("code"):
            return data
    return None


def fetch_sharehub_profiles(log=print, delay=SHAREHUB_DELAY_SECONDS):
    """{broker_code: profile} for every broker page in ShareHub's sitemap."""
    profiles = {}
    for url in sorted(set(SHAREHUB_PROFILE_RE.findall(_get(SHAREHUB_SITEMAP)))):
        try:
            profile = parse_sharehub_profile(_get(url))
        except OSError as exc:
            log(f"ShareHub: {url} failed ({exc})")
            profile = None
        if profile:
            profiles[str(profile["code"]).strip()] = profile
        else:
            log(f"ShareHub: no broker data in {url}")
        time.sleep(delay)
    return profiles


# ----------------------------------------------------------------------
# Merge + save
# ----------------------------------------------------------------------

def _clean(value, limit):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _website(value):
    url = _clean(value, 200)
    if url and "://" not in url:
        url = f"https://{url}"
    return url.rstrip("/")


def _branches(profile):
    rows = sorted((profile or {}).get("branches") or [], key=lambda branch: branch.get("order") or 0)
    return [
        {
            "name": _clean(branch.get("name"), 100),
            "address": _clean(branch.get("address"), 255),
            "phone": _clean(branch.get("contactNumber"), 150),
            "email": _clean(branch.get("email"), 254),
        }
        for branch in rows
    ]


def directory_fields(member, profile=None):
    """Broker field values from one NEPSE member row and its ShareHub profile (may be None)."""
    branches = _branches(profile)
    head = branches[0] if branches else {}
    status = _clean(member.get("activeStatus"), 20)
    tms = _clean((member.get("memberTMSLinkMapping") or {}).get("tmsLink") or (profile or {}).get("tmsUrl"), 100)
    return {
        "name": _clean(member.get("memberName"), 200),
        "membership_type": _clean((member.get("membershipTypeMaster") or {}).get("membershipType"), 100),
        "nepse_status": status,
        "is_active": status == "A",
        "is_dealer": member.get("isDealer") == "Y",
        "contact_person": _clean(member.get("authorizedContactPerson"), 150),
        "tms_link": tms,
        "website": _website((profile or {}).get("website")),
        "address": head.get("address", ""),
        "phone": head.get("phone") or _clean(member.get("authorizedContactPersonNumber"), 150),
        "email": head.get("email", ""),
        "branches": branches,
    }


def sync_broker_directory(members, profiles, now=None):
    """
    Upsert one Broker per NEPSE member.  ``profiles``: {broker_code: ShareHub profile}.
    Brokers NEPSE no longer lists are marked inactive, never deleted (floorsheet history
    still refers to them).  Returns counts.
    """
    now = now or timezone.now()
    counts = {"created": 0, "updated": 0, "with_website": 0, "delisted": 0}
    seen = set()
    with transaction.atomic():
        for member in members:
            try:
                number = int(member.get("memberCode"))
            except (TypeError, ValueError):
                continue
            code = str(number)
            fields = directory_fields(member, profiles.get(code))
            if not fields["name"]:
                continue
            broker = (Broker.objects.filter(broker_no=number).first()
                      or Broker.objects.filter(broker_code=code).first())
            created = broker is None
            if created:
                broker = Broker(broker_code=code)
            broker.broker_no = number
            for field, value in fields.items():
                # ShareHub-only fields keep their stored value (e.g. set in the admin) when
                # this run has nothing for them: a missing page must not wipe a website.
                if field in KEEP_WHEN_EMPTY and not value:
                    continue
                setattr(broker, field, value)
            broker.directory_synced_at = now
            broker.save()
            seen.add(broker.pk)
            counts["created" if created else "updated"] += 1
            counts["with_website"] += bool(fields["website"])
        if seen:
            counts["delisted"] = (Broker.objects.exclude(pk__in=seen).filter(is_active=True)
                                  .update(is_active=False, nepse_status="NOT_LISTED"))
    return counts
