"""GTM Advisor Algorithms Package.

Deterministic algorithms for scoring, clustering, and calculations.
These replace LLM reasoning where repeatability and explainability matter.

Layer: ANALYTICAL
- Scoring: ICP fit, lead quality, message alignment
- Clustering: Market segmentation, persona grouping
- Calculators: TAM/SAM/SOM, pricing, ROI
"""

from .scoring import (
    ICPScorer,
    LeadScorer,
    MessageAlignmentScorer,
    CompetitorThreatScorer,
)
from .clustering import (
    FirmographicClusterer,
    PersonaClusterer,
    MarketSegmenter,
)
from .calculators import (
    MarketSizeCalculator,
    LeadValueCalculator,
    CampaignROICalculator,
)
from .rules import (
    RuleEngine,
    Rule,
    RuleResult,
)

__all__ = [
    # Scoring
    "ICPScorer",
    "LeadScorer",
    "MessageAlignmentScorer",
    "CompetitorThreatScorer",
    # Clustering
    "FirmographicClusterer",
    "PersonaClusterer",
    "MarketSegmenter",
    # Calculators
    "MarketSizeCalculator",
    "LeadValueCalculator",
    "CampaignROICalculator",
    # Rules
    "RuleEngine",
    "Rule",
    "RuleResult",
]
