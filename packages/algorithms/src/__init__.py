"""GTM Advisor Algorithms Package.

Deterministic algorithms for scoring, clustering, and calculations.
These replace LLM reasoning where repeatability and explainability matter.

Layer: ANALYTICAL
- Scoring: ICP fit, lead quality, message alignment
- Clustering: Market segmentation, persona grouping
- Calculators: TAM/SAM/SOM, pricing, ROI
"""

from .calculators import (
    CampaignROICalculator,
    LeadValueCalculator,
    MarketSizeCalculator,
)
from .clustering import (
    FirmographicClusterer,
    MarketSegmenter,
    PersonaClusterer,
)
from .rules import (
    Rule,
    RuleEngine,
    RuleResult,
)
from .scoring import (
    CompetitorThreatScorer,
    ICPScorer,
    LeadScorer,
    MessageAlignmentScorer,
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
