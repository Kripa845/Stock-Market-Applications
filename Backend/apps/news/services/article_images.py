"""
Lead-image extraction for crawled news articles.

Works on raw HTML, so the crawler uses it at scrape time and the
``backfill_news_images`` command reuses it on HTML already stored in
RawArticle. Only the image URL is kept; the file itself stays on the
source site.

Order of preference:
    1. og:image / og:image:secure_url   (set by every portal crawled today)
    2. twitter:image / twitter:image:src
    3. <link rel="image_src">
    4. the first real <img> inside the article body
"""

import re
from urllib.parse import quote, urljoin, urlparse

from parsel import Selector


META_XPATHS = [
    "//meta[@property='og:image:secure_url']/@content",
    "//meta[@property='og:image']/@content",
    "//meta[@name='og:image']/@content",
    "//meta[@name='twitter:image']/@content",
    "//meta[@name='twitter:image:src']/@content",
    "//meta[@property='twitter:image']/@content",
    "//link[@rel='image_src']/@href",
]

# Where the article body usually lives; the first <img> found here is the fallback.
BODY_IMAGE_XPATHS = [
    "//article//img",
    "//*[contains(@class, 'entry-content')]//img",
    "//*[contains(@class, 'news-detail') or contains(@class, 'newsdetail')]//img",
    "//*[contains(@class, 'post-content') or contains(@class, 'article-content')]//img",
]

# Site chrome rather than an article picture.
# Matched as whole words in the file name, so "silicon.jpg" is not mistaken for an icon.
NOT_ARTICLE_IMAGE = re.compile(
    r"(?:^|[/_.-])(?:logo|favicon|sprite|placeholder|spinner|loader|avatar|blank|pixel|icon)s?(?:[_.-][^/]*)?$",
    re.IGNORECASE,
)

MAX_URL_LENGTH = 1000  # NewsArticle.image_url max_length


def normalize_image_url(value, page_url=""):
    """Absolute, percent-encoded http(s) URL, or "" when the value is unusable."""
    value = (value or "").strip()

    if not value or value.startswith("data:"):
        return ""

    url = urljoin(page_url, value) if page_url else value

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""

    if parsed.path.lower().endswith(".svg") or NOT_ARTICLE_IMAGE.search(parsed.path):
        return ""

    # Portals publish paths with raw spaces ("appoint ceo.jpg"); encode them,
    # leaving existing %-escapes and URL delimiters untouched.
    url = quote(url, safe=":/?#[]@!$&'()*+,;=%~")

    return url if len(url) <= MAX_URL_LENGTH else ""


def extract_image_url(html, page_url=""):
    """Best lead image for an article page, or "" if none is found."""
    if not html:
        return ""

    selector = Selector(text=html)

    for xpath in META_XPATHS:
        for value in selector.xpath(xpath).getall():
            url = normalize_image_url(value, page_url)
            if url:
                return url

    for xpath in BODY_IMAGE_XPATHS:
        for img in selector.xpath(xpath):
            # Lazy-loading themes keep the real source in data-* attributes.
            value = (
                img.attrib.get("data-src")
                or img.attrib.get("data-lazy-src")
                or img.attrib.get("src")
            )
            url = normalize_image_url(value, page_url)
            if url:
                return url

    return ""
