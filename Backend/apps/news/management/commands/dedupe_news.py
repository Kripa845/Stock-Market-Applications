"""
Find duplicate news articles and resolve them (logic in services/dedupe.py).

Same-source duplicates (same normalized URL or identical text) are merged into
one row, keeping tags, corrections, likes and comments; cross-source copies are
linked via duplicate_of, never deleted. Dry run unless --apply.
Usage:
    python manage.py dedupe_news
    python manage.py dedupe_news --apply
"""
from django.core.management.base import BaseCommand

from apps.news.services import dedupe


class Command(BaseCommand):
    help = "Merge same-source duplicate articles and link cross-source copies."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes (default: report only).")

    def handle(self, *args, **options):
        apply = options["apply"]
        report = dedupe.run(apply=apply)
        verb = "Merged" if apply else "Would merge"

        def losers(groups):
            return sum(len(g) - 1 for g in groups)

        self.stdout.write(f"{verb} {losers(report.url_groups)} article(s) in "
                          f"{len(report.url_groups)} same-source URL group(s)")
        for ids in report.url_groups:
            self.stdout.write(f"  keep {ids[0]} <- {ids[1:]}")
        self.stdout.write(f"{verb} {losers(report.content_groups)} article(s) in "
                          f"{len(report.content_groups)} same-source identical-text group(s)")
        for ids in report.content_groups:
            self.stdout.write(f"  keep {ids[0]} <- {ids[1:]}")
        self.stdout.write(f"{'Linked' if apply else 'Would link'} {len(report.links)} cross-source copy(ies)")
        for article_id, root_id in report.links:
            self.stdout.write(f"  {article_id} -> also reported as {root_id}")
        self.stdout.write(
            f"Left alone: {report.same_source_title_groups} same-source group(s) sharing only a title "
            "(recurring headlines, different articles)"
        )
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run: nothing written. Re-run with --apply."))
