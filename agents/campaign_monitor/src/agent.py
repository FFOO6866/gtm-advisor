"""Campaign Monitor Agent — performance tracking and optimization recommendations.

Runs against engagement event data collected by the Outreach Executor and
CRM Sync agents. For each campaign it:

- Aggregates impressions / clicks / engagements / conversions per channel and
  per creative asset.
- Compares observed rates against SG B2B benchmarks (email open ~20 %,
  email CTR ~3 %, LinkedIn engagement ~2 %, social CTR ~1 %).
- Identifies top-performing and underperforming assets.
- Uses the LLM (backed by the campaign-measurement domain guide) to turn raw
  numbers into prioritised, actionable recommendations.

Why this is not ChatGPT:
- Ingests REAL engagement events, not hypothetical data.
- Applies deterministic benchmark comparisons before any LLM call.
- Confidence is computed from data completeness — not hardcoded.
- Integrates with the synthesized campaign-measurement knowledge guide so
  recommendations are grounded in proven frameworks.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import structlog
from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# SG B2B benchmark thresholds
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, dict[str, float]] = {
    "email": {
        "open_rate_good": 20.0,
        "open_rate_excellent": 30.0,
        "ctr_good": 3.0,
        "ctr_excellent": 5.0,
    },
    "linkedin": {
        "engagement_good": 2.0,
        "engagement_excellent": 4.0,
        "ctr_good": 1.0,
        "ctr_excellent": 2.0,
    },
    "facebook": {
        "engagement_good": 1.0,
        "engagement_excellent": 2.5,
        "ctr_good": 1.0,
        "ctr_excellent": 2.0,
    },
    "instagram": {
        "engagement_good": 1.5,
        "engagement_excellent": 3.0,
        "ctr_good": 0.8,
        "ctr_excellent": 1.5,
    },
    "x": {
        "engagement_good": 0.5,
        "engagement_excellent": 1.0,
        "ctr_good": 0.5,
        "ctr_excellent": 1.0,
    },
}


def _label_performance(rate: float, good: float, excellent: float) -> str:
    """Map a metric rate to a human-readable performance label."""
    if rate >= excellent:
        return "top"
    if rate >= good:
        return "average"
    return "underperforming"


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class AssetPerformance(BaseModel):
    """Performance metrics for a single creative asset."""

    asset_id: str = Field(default="")
    asset_name: str = Field(default="")
    asset_type: str = Field(default="")
    platform: str = Field(default="")
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    engagements: int = Field(default=0)
    conversions: int = Field(default=0)
    click_through_rate: float = Field(default=0.0)
    engagement_rate: float = Field(default=0.0)
    performance_label: str = Field(default="average")  # top, average, underperforming


class ChannelMetrics(BaseModel):
    """Aggregated metrics for a marketing channel."""

    channel: str = Field(...)  # email, linkedin, facebook, x, instagram
    total_impressions: int = Field(default=0)
    total_clicks: int = Field(default=0)
    total_engagements: int = Field(default=0)
    total_conversions: int = Field(default=0)
    open_rate_pct: float = Field(default=0.0)  # email only
    click_through_rate_pct: float = Field(default=0.0)
    cost_per_click: float = Field(default=0.0)


class Recommendation(BaseModel):
    """An optimization recommendation."""

    priority: str = Field(default="medium")  # high, medium, low
    category: str = Field(default="")  # content, timing, audience, budget
    recommendation: str = Field(default="")
    expected_impact: str = Field(default="")
    asset_id: str | None = Field(default=None)


class CampaignPerformanceOutput(BaseModel):
    """Complete campaign performance report."""

    campaign_id: str = Field(default="")
    campaign_name: str = Field(default="")
    period_days: int = Field(default=7)

    # Overall metrics
    total_impressions: int = Field(default=0)
    total_clicks: int = Field(default=0)
    total_engagements: int = Field(default=0)
    total_conversions: int = Field(default=0)
    overall_ctr: float = Field(default=0.0)

    # Breakdown
    channel_metrics: list[ChannelMetrics] = Field(default_factory=list)
    asset_performance: list[AssetPerformance] = Field(default_factory=list)

    # A/B test results
    ab_test_results: dict[str, Any] = Field(default_factory=dict)

    # Recommendations
    recommendations: list[Recommendation] = Field(default_factory=list)
    top_performing_asset: str = Field(default="")
    underperforming_assets: list[str] = Field(default_factory=list)

    confidence: float = Field(default=0.0)
    data_sources_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM-structured recommendation list wrapper
# ---------------------------------------------------------------------------


class _RecommendationList(BaseModel):
    """Intermediate structured output from the LLM recommendation pass."""

    recommendations: list[Recommendation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class CampaignMonitorAgent(BaseGTMAgent[CampaignPerformanceOutput]):
    """Campaign performance monitoring and optimization recommendation agent.

    Consumes engagement events emitted by Outreach Executor / CRM Sync and
    produces a prioritised list of optimization recommendations backed by
    deterministic benchmark comparisons and LLM reasoning grounded in the
    campaign-measurement domain guide.
    """

    def __init__(self) -> None:
        super().__init__(
            name="campaign-monitor",
            description=(
                "Tracks campaign performance across channels and creative assets, "
                "compares against SG B2B benchmarks, and generates prioritised "
                "optimization recommendations."
            ),
            result_type=CampaignPerformanceOutput,
            min_confidence=0.55,
            max_iterations=1,
            model="gpt-4o",
            capabilities=[
                AgentCapability(
                    name="campaign-performance-analysis",
                    description=(
                        "Aggregate engagement events, compute per-channel / per-asset "
                        "metrics, compare to SG B2B benchmarks, and recommend improvements."
                    ),
                ),
            ],
        )
        self._knowledge_pack: dict[str, Any] = {}

    def get_system_prompt(self) -> str:
        return (
            "You are a campaign performance analyst specialising in B2B marketing "
            "for Singapore SMEs. You receive aggregated engagement metrics, benchmark "
            "comparisons, and asset-level data. Your task is to output a prioritised "
            "list of concrete, actionable optimization recommendations. Each recommendation "
            "must cite the specific metric or asset it addresses, state the expected "
            "impact (e.g. '+5% CTR'), and be categorised as: content, timing, audience, "
            "or budget. Avoid generic advice — every recommendation must be traceable "
            "to a specific data point in the metrics provided."
        )

    # ------------------------------------------------------------------
    # PDCA — Plan
    # ------------------------------------------------------------------

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}

        campaign_id = context.get("campaign_id", "")
        campaign_name = context.get("campaign_name", campaign_id)
        period_days = int(context.get("period_days", 7))
        engagement_events: list[dict[str, Any]] = context.get("engagement_events", [])

        # Load synthesized campaign-measurement domain guides.
        self._knowledge_pack = {}
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="campaign-monitor",
                task_context=task,
            )
        except Exception as e:
            logger.debug("campaign_monitor_knowledge_pack_failed", error=str(e))

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "period_days": period_days,
            "engagement_events": engagement_events,
        }

    # ------------------------------------------------------------------
    # PDCA — Do
    # ------------------------------------------------------------------

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CampaignPerformanceOutput:
        campaign_id: str = plan["campaign_id"]
        campaign_name: str = plan["campaign_name"]
        period_days: int = plan["period_days"]
        events: list[dict[str, Any]] = plan["engagement_events"]

        data_sources: list[str] = []

        # ------------------------------------------------------------------
        # 1. Aggregate per-channel and per-asset metrics from engagement events
        #    (real data source: events passed in from Outreach Executor / CRM Sync)
        # ------------------------------------------------------------------
        if events:
            data_sources.append("engagement_events")

        # Channel-level accumulators
        channel_buckets: dict[str, dict[str, int | float]] = defaultdict(lambda: {
            "impressions": 0,
            "clicks": 0,
            "engagements": 0,
            "conversions": 0,
            "opens": 0,  # email only
            "total_cost": 0.0,
        })

        # Asset-level accumulators
        asset_buckets: dict[str, dict[str, Any]] = {}

        for event in events:
            channel: str = (event.get("channel") or "unknown").lower()
            asset_id: str = event.get("asset_id") or ""
            asset_name: str = event.get("asset_name") or asset_id
            asset_type: str = event.get("asset_type") or ""
            event_type: str = (event.get("event_type") or "").lower()

            # Channel aggregation
            b = channel_buckets[channel]
            if event_type == "impression":
                b["impressions"] += 1
            elif event_type in ("click", "link_click"):
                b["clicks"] += 1
            elif event_type in ("engagement", "like", "comment", "share", "reaction"):
                b["engagements"] += 1
            elif event_type in ("conversion", "lead", "form_submit"):
                b["conversions"] += 1
            elif event_type == "open":
                b["opens"] += 1
                b["impressions"] += 1  # email open counts as an impression
            cost: float = float(event.get("cost", 0.0))
            b["total_cost"] += cost

            # Asset aggregation
            if asset_id:
                if asset_id not in asset_buckets:
                    asset_buckets[asset_id] = {
                        "asset_id": asset_id,
                        "asset_name": asset_name,
                        "asset_type": asset_type,
                        "platform": channel,
                        "impressions": 0,
                        "clicks": 0,
                        "engagements": 0,
                        "conversions": 0,
                    }
                ab = asset_buckets[asset_id]
                if event_type == "impression":
                    ab["impressions"] += 1
                elif event_type in ("click", "link_click"):
                    ab["clicks"] += 1
                elif event_type in ("engagement", "like", "comment", "share", "reaction"):
                    ab["engagements"] += 1
                elif event_type in ("conversion", "lead", "form_submit"):
                    ab["conversions"] += 1
                elif event_type == "open":
                    ab["impressions"] += 1

        # ------------------------------------------------------------------
        # 2. Build ChannelMetrics with benchmark-derived labels
        # ------------------------------------------------------------------
        channel_metrics: list[ChannelMetrics] = []
        for channel, b in channel_buckets.items():
            impressions = int(b["impressions"])
            clicks = int(b["clicks"])
            engagements = int(b["engagements"])
            conversions = int(b["conversions"])
            opens = int(b["opens"])
            total_cost = float(b["total_cost"])

            ctr_pct = (clicks / impressions * 100.0) if impressions else 0.0
            open_rate_pct = (opens / impressions * 100.0) if impressions else 0.0
            cpc = (total_cost / clicks) if clicks else 0.0

            channel_metrics.append(ChannelMetrics(
                channel=channel,
                total_impressions=impressions,
                total_clicks=clicks,
                total_engagements=engagements,
                total_conversions=conversions,
                open_rate_pct=round(open_rate_pct, 2),
                click_through_rate_pct=round(ctr_pct, 2),
                cost_per_click=round(cpc, 2),
            ))

        # ------------------------------------------------------------------
        # 3. Build AssetPerformance with performance labels
        # ------------------------------------------------------------------
        asset_performance: list[AssetPerformance] = []
        for ab in asset_buckets.values():
            impressions = int(ab["impressions"])
            clicks = int(ab["clicks"])
            engagements = int(ab["engagements"])
            conversions = int(ab["conversions"])
            platform: str = ab["platform"]

            ctr = (clicks / impressions) if impressions else 0.0
            eng_rate = (engagements / impressions) if impressions else 0.0

            benchmarks = _BENCHMARKS.get(platform, _BENCHMARKS.get("facebook", {
                "ctr_good": 1.0, "ctr_excellent": 2.0,
                "engagement_good": 1.0, "engagement_excellent": 2.5,
            }))

            # Label based on whichever metric is primary for the channel
            if platform == "email":
                label = _label_performance(
                    ctr * 100.0,
                    benchmarks.get("ctr_good", 3.0),
                    benchmarks.get("ctr_excellent", 5.0),
                )
            else:
                label = _label_performance(
                    eng_rate * 100.0,
                    benchmarks.get("engagement_good", 1.0),
                    benchmarks.get("engagement_excellent", 2.5),
                )

            asset_performance.append(AssetPerformance(
                asset_id=ab["asset_id"],
                asset_name=ab["asset_name"],
                asset_type=ab["asset_type"],
                platform=platform,
                impressions=impressions,
                clicks=clicks,
                engagements=engagements,
                conversions=conversions,
                click_through_rate=round(ctr, 4),
                engagement_rate=round(eng_rate, 4),
                performance_label=label,
            ))

        # ------------------------------------------------------------------
        # 4. Overall totals
        # ------------------------------------------------------------------
        total_impressions = sum(cm.total_impressions for cm in channel_metrics)
        total_clicks = sum(cm.total_clicks for cm in channel_metrics)
        total_engagements = sum(cm.total_engagements for cm in channel_metrics)
        total_conversions = sum(cm.total_conversions for cm in channel_metrics)
        overall_ctr = (total_clicks / total_impressions) if total_impressions else 0.0

        # ------------------------------------------------------------------
        # 5. A/B test comparison (assets sharing same asset_type = variants)
        # ------------------------------------------------------------------
        ab_test_results: dict[str, Any] = {}
        variant_groups: dict[str, list[AssetPerformance]] = defaultdict(list)
        for ap in asset_performance:
            if ap.asset_type:
                variant_groups[ap.asset_type].append(ap)

        for variant_type, variants in variant_groups.items():
            if len(variants) >= 2:
                best = max(variants, key=lambda v: v.click_through_rate)
                worst = min(variants, key=lambda v: v.click_through_rate)
                ab_test_results[variant_type] = {
                    "winner": best.asset_name,
                    "winner_ctr": best.click_through_rate,
                    "loser": worst.asset_name,
                    "loser_ctr": worst.click_through_rate,
                    "lift_pct": round(
                        (best.click_through_rate - worst.click_through_rate)
                        / max(worst.click_through_rate, 0.0001) * 100.0,
                        1,
                    ),
                    "variant_count": len(variants),
                }

        # ------------------------------------------------------------------
        # 6. Identify top performer and underperformers from real data
        # ------------------------------------------------------------------
        top_asset = ""
        underperforming: list[str] = []
        if asset_performance:
            sorted_assets = sorted(
                asset_performance,
                key=lambda ap: ap.click_through_rate,
                reverse=True,
            )
            top_asset = sorted_assets[0].asset_name
            underperforming = [
                ap.asset_name
                for ap in asset_performance
                if ap.performance_label == "underperforming"
            ]

        # ------------------------------------------------------------------
        # 7. LLM: generate actionable recommendations (real data source: LLM
        #    grounded in channel_metrics, asset_performance, benchmarks)
        # ------------------------------------------------------------------
        recommendations: list[Recommendation] = []
        try:
            _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
            _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""

            channel_summary = "\n".join(
                f"- {cm.channel}: {cm.total_impressions} impressions, "
                f"{cm.total_clicks} clicks, CTR {cm.click_through_rate_pct:.1f}%, "
                f"engagements {cm.total_engagements}, conversions {cm.total_conversions}"
                + (f", email open rate {cm.open_rate_pct:.1f}%" if cm.channel == "email" else "")
                for cm in channel_metrics
            ) or "No channel data available."

            asset_summary = "\n".join(
                f"- [{ap.performance_label.upper()}] {ap.asset_name} ({ap.platform}): "
                f"CTR {ap.click_through_rate * 100:.2f}%, "
                f"engagement rate {ap.engagement_rate * 100:.2f}%"
                for ap in asset_performance
            ) or "No asset data available."

            benchmark_notes = (
                "SG B2B benchmarks: email open rate good=20%/excellent=30%, "
                "email CTR good=3%/excellent=5%, LinkedIn engagement good=2%/excellent=4%, "
                "social CTR good=1%/excellent=2%."
            )

            ab_summary = (
                "A/B test results:\n" + "\n".join(
                    f"- {vtype}: winner={data['winner']} (CTR {data['winner_ctr']*100:.2f}%) "
                    f"vs loser={data['loser']} (CTR {data['loser_ctr']*100:.2f}%), "
                    f"lift={data['lift_pct']}%"
                    for vtype, data in ab_test_results.items()
                )
                if ab_test_results
                else "No A/B variants detected."
            )

            user_content = (
                f"{_knowledge_header}"
                f"Campaign: {campaign_name} (ID: {campaign_id}), period: {period_days} days.\n\n"
                f"CHANNEL METRICS:\n{channel_summary}\n\n"
                f"ASSET PERFORMANCE:\n{asset_summary}\n\n"
                f"A/B TESTS:\n{ab_summary}\n\n"
                f"BENCHMARKS:\n{benchmark_notes}\n\n"
                "Generate 3–6 prioritised, actionable recommendations. "
                "Each must reference a specific metric or asset, state expected impact, "
                "and be categorised as: content, timing, audience, or budget."
            )

            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": user_content},
            ]

            rec_output = await self._complete_structured(
                response_model=_RecommendationList,
                messages=messages,
            )
            if rec_output and rec_output.recommendations:
                recommendations = rec_output.recommendations
                data_sources.append("LLM:gpt-4o")

        except Exception as e:
            logger.warning("campaign_monitor_llm_recommendations_failed", error=str(e))

        return CampaignPerformanceOutput(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            period_days=period_days,
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_engagements=total_engagements,
            total_conversions=total_conversions,
            overall_ctr=round(overall_ctr, 4),
            channel_metrics=channel_metrics,
            asset_performance=asset_performance,
            ab_test_results=ab_test_results,
            recommendations=recommendations,
            top_performing_asset=top_asset,
            underperforming_assets=underperforming,
            confidence=0.0,  # Set by _check
            data_sources_used=list(set(data_sources)),
        )

    # ------------------------------------------------------------------
    # PDCA — Check
    # ------------------------------------------------------------------

    async def _check(self, result: CampaignPerformanceOutput) -> float:
        """Compute confidence from data completeness — never hardcoded."""
        score = 0.20  # Base: always given

        # Has real engagement events driving the metrics
        has_data = result.total_impressions > 0 or result.total_clicks > 0
        if has_data:
            score += 0.20

        # Per-channel breakdown computed from events
        if result.channel_metrics:
            score += 0.15

        # LLM recommendations generated
        if result.recommendations:
            score += 0.15

        # A/B test comparison performed (at least one variant pair found)
        if result.ab_test_results:
            score += 0.10

        # Asset-level breakdown present (real events had asset_id populated)
        if result.asset_performance:
            score += 0.15

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # PDCA — Act
    # ------------------------------------------------------------------

    async def _act(
        self,
        result: CampaignPerformanceOutput,
        confidence: float,
    ) -> CampaignPerformanceOutput:
        result.confidence = confidence

        if confidence < self.min_confidence:
            self._logger.warning(
                "campaign_monitor_low_confidence",
                campaign_id=result.campaign_id,
                confidence=confidence,
                min_confidence=self.min_confidence,
            )
            # Append a diagnostic recommendation so callers know why confidence is low
            if not result.recommendations:
                result.recommendations.append(Recommendation(
                    priority="high",
                    category="audience",
                    recommendation=(
                        "Insufficient engagement data to make high-confidence recommendations. "
                        "Ensure impression, click, and engagement events are being tracked "
                        "and passed in via context['engagement_events']."
                    ),
                    expected_impact="Enables data-driven optimization in future cycles.",
                ))

        self._logger.info(
            "campaign_monitor_complete",
            campaign_id=result.campaign_id,
            confidence=confidence,
            total_impressions=result.total_impressions,
            total_clicks=result.total_clicks,
            channel_count=len(result.channel_metrics),
            asset_count=len(result.asset_performance),
            recommendation_count=len(result.recommendations),
        )
        return result
