"""
Repair news articles whose published_at is in the future because a Bikram
Sambat date (e.g. "१२ श्रावण २०८३") was parsed as a Gregorian year.

The real date is re-read from the article header stored in RawArticle.raw_html
and converted BS -> AD.  When the URL carries a /YYYY/MM/DD/ date it must agree,
otherwise the article is left untouched and reported.  No network requests.
Usage:
    python manage.py repair_news_dates --dry-run
    python manage.py repair_news_dates
"""

import re
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from parsel import Selector

from apps.news.models import NewsArticle
from crawlers.crawlers.utils.dates import parse_bikram_sambat

HEADER_SELECTORS = ("#content > div > header *::text", "article header *::text")
URL_DATE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def header_text(raw_html):
    selector = Selector(text=raw_html or "")
    for css in HEADER_SELECTORS:
        text = " ".join(" ".join(selector.css(css).getall()).split())
        if text:
            yield text


class Command(BaseCommand):
    help = "Re-derive future-dated published_at values from the stored article header (BS -> AD)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=False, help="Report without saving")

    def handle(self, *args, **options):
        cutoff = timezone.now() + timedelta(days=1)
        articles = NewsArticle.objects.filter(published_at__gt=cutoff).select_related("raw_article")
        fixed = skipped = 0

        for article in articles:
            repaired = next(
                (dt for dt in (parse_bikram_sambat(text) for text in header_text(article.raw_article.raw_html)) if dt),
                None,
            )
            url_match = URL_DATE.search(article.url)
            url_date = date(*map(int, url_match.groups())) if url_match else None

            if repaired is None or repaired > cutoff or (url_date and repaired.date() != url_date):
                skipped += 1
                self.stderr.write(
                    f"SKIP #{article.id} {article.url}: stored {article.published_at}, "
                    f"header gives {repaired}, URL date {url_date}"
                )
                continue

            fixed += 1
            self.stdout.write(f"#{article.id} {article.url}: {article.published_at} -> {repaired}")
            if not options["dry_run"]:
                NewsArticle.objects.filter(pk=article.pk).update(published_at=repaired)

        verb = "Would repair" if options["dry_run"] else "Repaired"
        self.stdout.write(self.style.SUCCESS(f"{verb} {fixed} article(s); skipped {skipped}."))
