"""
Pure text/URL normalisation and hashing for news articles (no model imports,
so models.py and migrations can use it). Changing these changes article
identity: existing rows keep old values until re-hashed.
"""
import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid", "_ga"}

# Very short titles ("Notice", "सूचना") are too generic to group on.
MIN_CANONICAL_TITLE_LEN = 12


def normalize_url(url: str) -> str:
    """Identity form of a URL: lowercase host without www., no tracking params,
    no fragment, no trailing slash. Path case and real query params are kept
    (MeroLagani's NewsDetail.aspx?newsID=... is identified by its query)."""
    parts = urlsplit((url or "").strip())
    if not parts.scheme or not parts.netloc:
        return ""
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    if port and (parts.scheme.lower(), port) not in {("http", 80), ("https", 443)}:
        host = f"{host}:{port}"
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    )
    path = parts.path.rstrip("/") or ""
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))


def _clean_unicode(text: str) -> str:
    # NFKC folds width/compatibility variants; Cf drops zero-width joiners.
    text = unicodedata.normalize("NFKC", text or "")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def normalize_text(text: str) -> str:
    """Whitespace-collapsed text, the basis of content_hash."""
    return re.sub(r"\s+", " ", _clean_unicode(text)).strip()


def canonical_title(title: str) -> str:
    """Lowercase title with punctuation removed and Nepali digits as ASCII.
    Letters, combining marks (Devanagari vowel signs) and digits are kept."""
    out = []
    for ch in _clean_unicode(title).lower():
        cat = unicodedata.category(ch)
        if cat == "Nd":
            out.append(str(unicodedata.digit(ch)))
        elif cat[0] in "LM" or cat[0] == "N":
            out.append(ch)
        else:
            out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_content_hash(title: str, body: str) -> str:
    return _sha256(f"{normalize_text(title)}|{normalize_text(body)}")


def compute_canonical_hash(title: str) -> str:
    """Empty when the title is too short to identify a story."""
    canonical = canonical_title(title)
    if len(canonical) < MIN_CANONICAL_TITLE_LEN:
        return ""
    return _sha256(canonical)
