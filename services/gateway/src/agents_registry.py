"""Shared agent registry for the gateway service.

Provides a single source of truth for agent classes and metadata.
"""

from typing import TYPE_CHECKING

# Lazy imports to avoid circular dependencies
if TYPE_CHECKING:
    pass

# Agent metadata for UI display
AGENT_METADATA = {
    "gtm-strategist": {
        "title": "GTM Strategist",
        "color": "#8B5CF6",
        "avatar": "🎯",
        "task_description": "Develop comprehensive go-to-market strategy",
    },
    "market-intelligence": {
        "title": "Market Intelligence",
        "color": "#10B981",
        "avatar": "📊",
        "task_description": "Analyze market trends and opportunities",
    },
    "competitor-analyst": {
        "title": "Competitor Analyst",
        "color": "#F59E0B",
        "avatar": "🔍",
        "task_description": "Analyze competitor landscape",
    },
    "customer-profiler": {
        "title": "Customer Profiler",
        "color": "#EC4899",
        "avatar": "👥",
        "task_description": "Define ideal customer profiles",
    },
    "lead-hunter": {
        "title": "Lead Hunter",
        "color": "#3B82F6",
        "avatar": "🎣",
        "task_description": "Identify and qualify potential leads",
    },
    "campaign-strategist": {
        "title": "Campaign Strategist",
        "color": "#7C3AED",
        "avatar": "🗺",
        "task_description": "Produce a phased 12-month GTM roadmap",
    },
    "campaign-architect": {
        "title": "Campaign Architect",
        "color": "#EF4444",
        "avatar": "📣",
        "task_description": "Design marketing campaign strategy",
    },
    "edm-designer": {
        "title": "EDM Designer",
        "color": "#6366F1",
        "avatar": "✉",
        "task_description": "Generate responsive HTML email campaigns",
    },
    "graphic-designer": {
        "title": "Graphic Designer",
        "color": "#F97316",
        "avatar": "🖼",
        "task_description": "Produce visual creative assets for campaigns",
    },
    "social-publisher": {
        "title": "Social Publisher",
        "color": "#14B8A6",
        "avatar": "📲",
        "task_description": "Publish approved creative assets to social platforms",
    },
    "campaign-monitor": {
        "title": "Campaign Monitor",
        "color": "#A855F7",
        "avatar": "📈",
        "task_description": "Track campaign performance and surface optimisation recommendations",
    },
    "strategy-proposer": {
        "title": "Strategy Proposer",
        "color": "#0EA5E9",
        "avatar": "🗂",
        "task_description": "Synthesise insights and propose high-level strategies for user approval",
    },
}

# Total number of agents (used for metrics)
TOTAL_AGENTS = len(AGENT_METADATA)


def get_agent_class(agent_id: str):
    """Get the agent class by ID. Lazy loaded to avoid import issues."""
    from agents.campaign_architect.src import CampaignArchitectAgent
    from agents.campaign_monitor.src import CampaignMonitorAgent
    from agents.campaign_strategist.src import CampaignStrategistAgent
    from agents.competitor_analyst.src import CompetitorAnalystAgent
    from agents.customer_profiler.src import CustomerProfilerAgent
    from agents.edm_designer.src import EDMDesignerAgent
    from agents.graphic_designer.src import GraphicDesignerAgent
    from agents.gtm_strategist.src import GTMStrategistAgent
    from agents.lead_hunter.src import LeadHunterAgent
    from agents.market_intelligence.src import MarketIntelligenceAgent
    from agents.social_publisher.src import SocialPublisherAgent
    from agents.strategy_proposer.src import StrategyProposerAgent

    agents = {
        "gtm-strategist": GTMStrategistAgent,
        "market-intelligence": MarketIntelligenceAgent,
        "competitor-analyst": CompetitorAnalystAgent,
        "customer-profiler": CustomerProfilerAgent,
        "lead-hunter": LeadHunterAgent,
        "campaign-architect": CampaignArchitectAgent,
        "campaign-strategist": CampaignStrategistAgent,
        "edm-designer": EDMDesignerAgent,
        "graphic-designer": GraphicDesignerAgent,
        "social-publisher": SocialPublisherAgent,
        "campaign-monitor": CampaignMonitorAgent,
        "strategy-proposer": StrategyProposerAgent,
    }
    return agents.get(agent_id)


def get_all_agent_classes() -> dict:
    """Get all agent classes."""
    from agents.campaign_architect.src import CampaignArchitectAgent
    from agents.campaign_monitor.src import CampaignMonitorAgent
    from agents.campaign_strategist.src import CampaignStrategistAgent
    from agents.competitor_analyst.src import CompetitorAnalystAgent
    from agents.customer_profiler.src import CustomerProfilerAgent
    from agents.edm_designer.src import EDMDesignerAgent
    from agents.graphic_designer.src import GraphicDesignerAgent
    from agents.gtm_strategist.src import GTMStrategistAgent
    from agents.lead_hunter.src import LeadHunterAgent
    from agents.market_intelligence.src import MarketIntelligenceAgent
    from agents.social_publisher.src import SocialPublisherAgent
    from agents.strategy_proposer.src import StrategyProposerAgent

    return {
        "gtm-strategist": GTMStrategistAgent,
        "market-intelligence": MarketIntelligenceAgent,
        "competitor-analyst": CompetitorAnalystAgent,
        "customer-profiler": CustomerProfilerAgent,
        "lead-hunter": LeadHunterAgent,
        "campaign-architect": CampaignArchitectAgent,
        "campaign-strategist": CampaignStrategistAgent,
        "edm-designer": EDMDesignerAgent,
        "graphic-designer": GraphicDesignerAgent,
        "social-publisher": SocialPublisherAgent,
        "campaign-monitor": CampaignMonitorAgent,
        "strategy-proposer": StrategyProposerAgent,
    }


def is_valid_agent(agent_id: str) -> bool:
    """Check if an agent ID is valid."""
    return agent_id in AGENT_METADATA


def get_task_description(agent_id: str) -> str:
    """Get the default task description for an agent."""
    metadata = AGENT_METADATA.get(agent_id, {})
    return metadata.get("task_description", f"Execute {agent_id} analysis")
