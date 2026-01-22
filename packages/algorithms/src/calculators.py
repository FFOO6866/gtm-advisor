"""Business Calculators for GTM.

Deterministic calculations for:
- Market sizing (TAM/SAM/SOM)
- Lead value estimation
- Campaign ROI projection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketSizeResult:
    """Market sizing result."""
    tam: float  # Total Addressable Market
    sam: float  # Serviceable Addressable Market
    som: float  # Serviceable Obtainable Market
    tam_companies: int
    sam_companies: int
    som_companies: int
    currency: str = "SGD"
    methodology: str = ""
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tam": {"value": self.tam, "companies": self.tam_companies},
            "sam": {"value": self.sam, "companies": self.sam_companies},
            "som": {"value": self.som, "companies": self.som_companies},
            "currency": self.currency,
            "methodology": self.methodology,
            "assumptions": self.assumptions,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class LeadValueResult:
    """Lead value estimation result."""
    expected_value: float  # Expected monetary value
    probability_to_close: float
    average_deal_size: float
    time_to_close_days: int
    confidence: float
    factors: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_value": round(self.expected_value, 2),
            "probability_to_close": round(self.probability_to_close, 3),
            "average_deal_size": round(self.average_deal_size, 2),
            "time_to_close_days": self.time_to_close_days,
            "confidence": round(self.confidence, 2),
            "factors": {k: round(v, 3) for k, v in self.factors.items()},
        }


@dataclass
class CampaignROIResult:
    """Campaign ROI projection."""
    projected_revenue: float
    projected_cost: float
    projected_roi: float  # (revenue - cost) / cost
    expected_leads: int
    expected_conversions: int
    break_even_conversions: int
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "projected_revenue": round(self.projected_revenue, 2),
            "projected_cost": round(self.projected_cost, 2),
            "projected_roi": round(self.projected_roi, 2),
            "expected_leads": self.expected_leads,
            "expected_conversions": self.expected_conversions,
            "break_even_conversions": self.break_even_conversions,
            "assumptions": self.assumptions,
            "confidence": round(self.confidence, 2),
        }


class MarketSizeCalculator:
    """Calculate TAM/SAM/SOM for market sizing.

    Uses bottom-up methodology with company counts and ACV.
    """

    # Singapore market benchmarks (can be overridden)
    DEFAULT_BENCHMARKS = {
        "fintech": {"company_count": 1200, "avg_spend": 50000},
        "saas": {"company_count": 2500, "avg_spend": 30000},
        "ecommerce": {"company_count": 5000, "avg_spend": 20000},
        "healthtech": {"company_count": 400, "avg_spend": 60000},
        "edtech": {"company_count": 300, "avg_spend": 25000},
        "logistics": {"company_count": 800, "avg_spend": 40000},
        "professional_services": {"company_count": 15000, "avg_spend": 15000},
        "other": {"company_count": 10000, "avg_spend": 20000},
    }

    def __init__(
        self,
        benchmarks: dict[str, dict] | None = None,
        currency: str = "SGD",
    ):
        self.benchmarks = benchmarks or self.DEFAULT_BENCHMARKS
        self.currency = currency

    def calculate(
        self,
        industry: str,
        your_acv: float,
        target_company_sizes: list[str],
        geographic_focus: list[str],
        serviceable_percentage: float = 0.3,
        obtainable_percentage: float = 0.05,
    ) -> MarketSizeResult:
        """Calculate market size.

        Args:
            industry: Target industry
            your_acv: Your average contract value
            target_company_sizes: Size ranges you serve
            geographic_focus: Target geographies
            serviceable_percentage: % of TAM you can serve (default 30%)
            obtainable_percentage: % of SAM you can realistically capture (default 5%)

        Returns:
            Market size breakdown
        """
        assumptions = []

        # Get industry benchmark
        industry_lower = industry.lower().replace(" ", "_")
        benchmark = self.benchmarks.get(industry_lower, self.benchmarks["other"])

        # TAM: All companies in industry
        tam_companies = benchmark["company_count"]

        # Adjust for geography (Singapore = 1x, APAC = 10x, Global = 50x)
        geo_multiplier = 1.0
        if any("apac" in g.lower() for g in geographic_focus):
            geo_multiplier = 10.0
            assumptions.append("APAC expansion assumed (10x Singapore)")
        elif any("global" in g.lower() for g in geographic_focus):
            geo_multiplier = 50.0
            assumptions.append("Global scope assumed (50x Singapore)")
        else:
            assumptions.append("Singapore-focused market")

        tam_companies = int(tam_companies * geo_multiplier)
        tam = tam_companies * your_acv
        assumptions.append(f"TAM: {tam_companies:,} companies × {self.currency} {your_acv:,.0f} ACV")

        # SAM: Companies matching your target criteria
        size_factor = self._size_coverage_factor(target_company_sizes)
        sam_companies = int(tam_companies * size_factor * serviceable_percentage)
        sam = sam_companies * your_acv
        assumptions.append(f"SAM: {serviceable_percentage*100:.0f}% serviceable × {size_factor*100:.0f}% size fit")

        # SOM: Realistically obtainable
        som_companies = int(sam_companies * obtainable_percentage)
        som = som_companies * your_acv
        assumptions.append(f"SOM: {obtainable_percentage*100:.0f}% obtainable market share")

        # Confidence based on data quality
        confidence = 0.5  # Base confidence for estimates
        if industry_lower in self.benchmarks:
            confidence += 0.2
        if len(geographic_focus) == 1 and "singapore" in geographic_focus[0].lower():
            confidence += 0.2  # Higher confidence for local market

        return MarketSizeResult(
            tam=tam,
            sam=sam,
            som=som,
            tam_companies=tam_companies,
            sam_companies=sam_companies,
            som_companies=som_companies,
            currency=self.currency,
            methodology="Bottom-up: Company count × ACV",
            assumptions=assumptions,
            confidence=confidence,
        )

    def _size_coverage_factor(self, target_sizes: list[str]) -> float:
        """Calculate what % of market your target sizes represent."""
        # Singapore SME distribution (approximate)
        size_distribution = {
            "1-10": 0.50,
            "11-50": 0.30,
            "51-200": 0.12,
            "201-500": 0.05,
            "500+": 0.03,
        }

        coverage = 0.0
        for size in target_sizes:
            coverage += size_distribution.get(size, 0.10)

        return min(coverage, 1.0)


class LeadValueCalculator:
    """Calculate expected value of a lead.

    Uses probability-weighted expected value.
    """

    # Default conversion rates by lead quality
    DEFAULT_CONVERSION_RATES = {
        "hot": 0.30,
        "warm": 0.15,
        "cold": 0.05,
    }

    # Time to close by company size (days)
    DEFAULT_SALES_CYCLES = {
        "micro": 14,
        "small": 30,
        "medium": 60,
        "large": 90,
        "enterprise": 180,
    }

    def __init__(
        self,
        conversion_rates: dict[str, float] | None = None,
        sales_cycles: dict[str, int] | None = None,
    ):
        self.conversion_rates = conversion_rates or self.DEFAULT_CONVERSION_RATES
        self.sales_cycles = sales_cycles or self.DEFAULT_SALES_CYCLES

    def calculate(
        self,
        lead_score: float,
        company_size: str,
        your_acv: float,
        engagement_signals: list[str] | None = None,
        custom_deal_size: float | None = None,
    ) -> LeadValueResult:
        """Calculate expected value of a lead.

        Args:
            lead_score: Lead quality score (0-1)
            company_size: Company size bucket
            your_acv: Your average contract value
            engagement_signals: Engagement indicators
            custom_deal_size: Override deal size if known

        Returns:
            Lead value estimation
        """
        factors = {}

        # Base conversion probability from lead score
        if lead_score >= 0.8:
            base_prob = self.conversion_rates["hot"]
            quality = "hot"
        elif lead_score >= 0.5:
            base_prob = self.conversion_rates["warm"]
            quality = "warm"
        else:
            base_prob = self.conversion_rates["cold"]
            quality = "cold"

        factors["base_probability"] = base_prob

        # Adjust for engagement
        engagement_bonus = 0.0
        if engagement_signals:
            high_intent = ["demo_requested", "pricing_viewed", "trial_started"]
            for signal in engagement_signals:
                if any(h in signal.lower() for h in high_intent):
                    engagement_bonus += 0.05

        engagement_bonus = min(engagement_bonus, 0.15)
        factors["engagement_bonus"] = engagement_bonus

        # Final probability
        probability = min(base_prob + engagement_bonus, 0.50)  # Cap at 50%

        # Deal size
        deal_size = custom_deal_size or your_acv

        # Adjust deal size by company size
        size_multipliers = {
            "micro": 0.5,
            "small": 0.8,
            "medium": 1.0,
            "large": 1.5,
            "enterprise": 2.5,
        }
        size_mult = size_multipliers.get(company_size.lower(), 1.0)
        adjusted_deal_size = deal_size * size_mult
        factors["size_multiplier"] = size_mult

        # Expected value
        expected_value = probability * adjusted_deal_size

        # Time to close
        time_to_close = self.sales_cycles.get(company_size.lower(), 45)

        # Confidence
        confidence = 0.5 + (lead_score * 0.3) + (0.1 if engagement_signals else 0)

        return LeadValueResult(
            expected_value=expected_value,
            probability_to_close=probability,
            average_deal_size=adjusted_deal_size,
            time_to_close_days=time_to_close,
            confidence=confidence,
            factors=factors,
        )

    def calculate_pipeline_value(
        self,
        leads: list[dict[str, Any]],
        your_acv: float,
    ) -> dict[str, Any]:
        """Calculate total pipeline value from multiple leads.

        Args:
            leads: List of leads with score and company_size
            your_acv: Your ACV

        Returns:
            Pipeline summary
        """
        total_expected = 0.0
        by_quality = {"hot": 0, "warm": 0, "cold": 0}

        for lead in leads:
            result = self.calculate(
                lead_score=lead.get("score", 0.5),
                company_size=lead.get("company_size", "small"),
                your_acv=your_acv,
                engagement_signals=lead.get("engagement_signals"),
            )
            total_expected += result.expected_value

            # Categorize
            if lead.get("score", 0.5) >= 0.8:
                by_quality["hot"] += 1
            elif lead.get("score", 0.5) >= 0.5:
                by_quality["warm"] += 1
            else:
                by_quality["cold"] += 1

        return {
            "total_pipeline_value": round(total_expected, 2),
            "lead_count": len(leads),
            "by_quality": by_quality,
            "average_lead_value": round(total_expected / len(leads), 2) if leads else 0,
        }


class CampaignROICalculator:
    """Project ROI for GTM campaigns."""

    # Default metrics
    DEFAULT_METRICS = {
        "email_open_rate": 0.25,
        "email_click_rate": 0.03,
        "landing_page_conversion": 0.05,
        "demo_to_opportunity": 0.30,
        "opportunity_to_close": 0.25,
    }

    def __init__(self, metrics: dict[str, float] | None = None):
        self.metrics = metrics or self.DEFAULT_METRICS

    def calculate(
        self,
        campaign_budget: float,
        target_audience_size: int,
        your_acv: float,
        campaign_type: str = "email",
        custom_metrics: dict[str, float] | None = None,
    ) -> CampaignROIResult:
        """Calculate projected campaign ROI.

        Args:
            campaign_budget: Total campaign budget
            target_audience_size: Size of target audience
            your_acv: Your average contract value
            campaign_type: Type of campaign (email, linkedin, content, paid)
            custom_metrics: Override default conversion metrics

        Returns:
            ROI projection
        """
        metrics = {**self.metrics, **(custom_metrics or {})}
        assumptions = []

        # Campaign type multipliers
        type_multipliers = {
            "email": {"reach": 1.0, "conversion": 1.0},
            "linkedin": {"reach": 0.8, "conversion": 1.2},
            "content": {"reach": 0.5, "conversion": 1.5},
            "paid": {"reach": 2.0, "conversion": 0.8},
        }
        multiplier = type_multipliers.get(campaign_type, {"reach": 1.0, "conversion": 1.0})

        # Calculate funnel
        reached = int(target_audience_size * multiplier["reach"])
        assumptions.append(f"Audience reached: {reached:,}")

        # Email/content engagement
        engaged = int(reached * metrics["email_open_rate"])
        clicked = int(engaged * metrics["email_click_rate"] * 10)  # 10x for content views

        # Conversions
        leads = int(clicked * metrics["landing_page_conversion"] * multiplier["conversion"])
        assumptions.append(f"Expected leads: {leads}")

        opportunities = int(leads * metrics["demo_to_opportunity"])
        conversions = int(opportunities * metrics["opportunity_to_close"])
        assumptions.append(f"Expected conversions: {conversions}")

        # Revenue and ROI
        projected_revenue = conversions * your_acv
        projected_roi = (projected_revenue - campaign_budget) / campaign_budget if campaign_budget > 0 else 0

        # Break-even
        if your_acv > 0:
            break_even = int(campaign_budget / your_acv) + 1
        else:
            break_even = 0

        # Confidence based on audience size and metrics
        confidence = 0.4
        if target_audience_size >= 1000:
            confidence += 0.2
        if custom_metrics:
            confidence += 0.1

        return CampaignROIResult(
            projected_revenue=projected_revenue,
            projected_cost=campaign_budget,
            projected_roi=projected_roi,
            expected_leads=leads,
            expected_conversions=conversions,
            break_even_conversions=break_even,
            assumptions=assumptions,
            confidence=confidence,
        )

    def compare_campaigns(
        self,
        campaigns: list[dict[str, Any]],
        your_acv: float,
    ) -> list[dict[str, Any]]:
        """Compare multiple campaign options.

        Args:
            campaigns: List of campaign configs with budget, audience, type
            your_acv: Your ACV

        Returns:
            Ranked campaign comparisons
        """
        results = []

        for i, campaign in enumerate(campaigns):
            roi_result = self.calculate(
                campaign_budget=campaign.get("budget", 0),
                target_audience_size=campaign.get("audience_size", 0),
                your_acv=your_acv,
                campaign_type=campaign.get("type", "email"),
            )

            results.append({
                "campaign_name": campaign.get("name", f"Campaign {i+1}"),
                "budget": campaign.get("budget", 0),
                "projected_roi": roi_result.projected_roi,
                "projected_revenue": roi_result.projected_revenue,
                "expected_conversions": roi_result.expected_conversions,
                "efficiency_score": roi_result.projected_roi / (campaign.get("budget", 1) / 1000),
            })

        # Sort by ROI
        results.sort(key=lambda x: x["projected_roi"], reverse=True)

        return results
