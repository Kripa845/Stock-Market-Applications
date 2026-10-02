"""
Management command to fill NewsArticle.image_url from HTML already stored in RawArticle.
No network requests are made.
Usage:
    python manage.py backfill_news_images
    python manage.py backfill_news_images --force     # re-extract articles that already have an image
    python manage.py backfill_news_images --dry-run
"""

from django.core.management.base import BaseCommand
from apps.news.models import NewsArticle
from apps.news.services.article_images import extract_image_url


class Command(BaseCommand):
    help = "Extract lead images for stored news articles from their saved raw HTML"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Also re-extract articles that already have an image_url",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would change without saving",
        )

    def handle(self, *args, **options):
        articles = NewsArticle.objects.exclude(raw_article__raw_html="")
        if not options["force"]:
            articles = articles.filter(image_url="")

        rows = articles.values_list("id", "url", "raw_article__raw_html")
        found = missing = 0

        for article_id, url, raw_html in rows.iterator(chunk_size=200):
            image_url = extract_image_url(raw_html, url)
            if not image_url:
                missing += 1
                continue
            found += 1
            if not options["dry_run"]:
                NewsArticle.objects.filter(pk=article_id).update(image_url=image_url)

        verb = "Would set" if options["dry_run"] else "Set"
        self.stdout.write(
            self.style.SUCCESS(
                "{} image_url on {} article(s); no image found for {}.".format(verb, found, missing)
            )
        )
