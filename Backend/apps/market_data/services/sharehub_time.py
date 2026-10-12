"""
ShareHub trade-time parsing.

ShareHub labels ``tradeTime`` with a trailing "Z" (UTC), but the clock values
are already Nepal time: the last trades of a session read 14:59:59 and NEPSE
closes at 15:00 NPT.  Trusting the "Z" would shift every trade by +5:45
(to around 20:45 NPT), so the "Z" is dropped and Asia/Kathmandu attached.
Nothing is converted from UTC.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

NPT = ZoneInfo("Asia/Kathmandu")


def parse_sharehub_time(raw):
    """``"2026-10-11T14:59:59Z"`` -> 2026-10-11 14:59:59+05:45 (fractional seconds kept)."""
    text = str(raw).strip().rstrip("Zz")
    if "." in text:
        base, frac = text.split(".", 1)
        text = f"{base}.{frac[:6].ljust(6, '0')}"
        naive = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%f")
    else:
        naive = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")
    return naive.replace(tzinfo=NPT)
