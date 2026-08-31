from urllib.parse import urlparse, urlunparse, parse_qs


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "fbclid",
    "gclid",
}


def canonicalize_url(url):
    parsed = urlparse(url)

    query = parse_qs(parsed.query)

    clean_query = {
        k: v
        for k, v in query.items()
        if k not in TRACKING_PARAMS
    }

    path = parsed.path.rstrip("/")

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            path,
            "",
            "",
            "",
        )
    )