"""
Categorizer wrapper forwarding to the unified categorization service.
"""

from apps.news.services.categorization import categorize_article

__all__ = ["categorize_article"]