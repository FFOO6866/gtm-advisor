"""Hot and warm tier caching for GTM Advisor.

Three cache classes wrapping the existing CacheBackend infrastructure:
- EnrichmentCache: Company enrichment data, 24h TTL (hot tier)
- PerplexityCache: Perplexity query results, 1h TTL (hot tier)
- AnalysisSummaryCache: Analysis summaries, 7d TTL (warm tier)
"""

from .analysis_cache import AnalysisSummaryCache
from .enrichment_cache import EnrichmentCache
from .perplexity_cache import PerplexityCache

__all__ = [
    "EnrichmentCache",
    "PerplexityCache",
    "AnalysisSummaryCache",
]
