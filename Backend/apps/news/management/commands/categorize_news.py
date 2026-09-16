"""
Management command to categorize existing news articles.
Usage:
    python manage.py categorize_news
    python manage.py categorize_news --all
    python manage.py categorize_news --article-id 1
    python manage.py categorize_news --force
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from apps.news.models import NewsArticle
from apps.news.services.categorization import (
    categorize_article,
    invalidate_company_cache,
)


class Command(BaseCommand):
    help = "Categorize existing news articles using embedding similarity"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            dest="all",
            default=False,
            help="Categorize all articles",
        )
        parser.add_argument(
            "--article-id",
            type=int,
            default=None,
            help="Categorize a specific article by ID",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force re-categorization of already processed articles",
        )

    def handle(self, *args, **options):
        invalidate_company_cache()

        if options["article_id"]:
            try:
                article = NewsArticle.objects.get(pk=options["article_id"])
            except NewsArticle.DoesNotExist:
                self.stderr.write(
                    "Article with id={} not found.".format(options["article_id"])
                )
                return
            self._categorize_one(article, force=True)
            return

        threshold = getattr(
            settings, "COMPANY_TAG_SIMILARITY_THRESHOLD", 0.75
        )
        self.stdout.write("Using similarity threshold: {}".format(threshold))

        qs = NewsArticle.objects.all().order_by("-id")
        if not options["all"] and not options["force"]:
            qs = qs.filter(is_processed=False)

        total = qs.count()
        self.stdout.write("Found {} articles to process.".format(total))

        success = 0
        failed = 0
        for article in qs.iterator(chunk_size=100):
            try:
                tags = categorize_article(
                    article, force_recompute=options["force"]
                )
                success += 1
                if tags:
                    tag_str = ", ".join(
                        "{}({:.2f})".format(t.company.symbol, t.confidence)
                        for t in tags
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            "  [{}] {}... -> {}".format(
                                article.id, article.headline[:60], tag_str
                            )
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "  [{}] {}... -> no tags (needs review)".format(
                                article.id, article.headline[:60]
                            )
                        )
                    )
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR("  [{}] failed: {}".format(article.id, exc))
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Categorization complete. Success={}, Failed={}".format(
                    success, failed
                )
            )
        )

    def _categorize_one(self, article, force=False):
        try:
            tags = categorize_article(article, force_recompute=force)
            if tags:
                tag_str = ", ".join(
                    "{}({:.2f})".format(t.company.symbol, t.confidence)
                    for t in tags
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        "  [{}] {}... -> {}".format(
                            article.id, article.headline[:60], tag_str
                        )
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "  [{}] {}... -> no tags".format(
                            article.id, article.headline[:60]
                        )
                    )
                )
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR("  [{}] failed: {}".format(article.id, exc))
            )
