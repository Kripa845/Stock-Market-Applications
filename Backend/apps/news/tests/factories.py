from apps.news.models import NewsSource
from apps.news.services.ingest import resolve_source
from django.utils.text import slugify


def news_source_for(label="ShareSansar"):
    """The NewsSource a spider label resolves to, created if the test DB lacks it."""
    return resolve_source(label) or NewsSource.objects.create(
        slug=slugify(label), name=label, base_url="https://example.com",
    )
