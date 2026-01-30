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
    "campaign-architect": {
        "title": "Campaign Architect",
        "color": "#EF4444",
        "avatar": "📣",
        "task_description": "Design marketing campaign strategy",
    },
}

# Total number of agents (used for metrics)
TOTAL_AGENTS = len(AGENT_METADATA)


def get_agent_class(agent_id: str):
    """Get the agent class by ID. Lazy loaded to avoid import issues."""
    from agents.campaign_architect.src import CampaignArchitectAgent
    from agents.competitor_analyst.src import CompetitorAnalystAgent
    from agents.customer_profiler.src import CustomerProfilerAgent
    from agents.gtm_strategist.src import GTMStrategistAgent
    from agents.lead_hunter.src import LeadHunterAgent
    from agents.market_intelligence.src import MarketIntelligenceAgent

    agents = {
        "gtm-strategist": GTMStrategistAgent,
        "market-intelligence": MarketIntelligenceAgent,
        "competitor-analyst": CompetitorAnalystAgent,
        "customer-profiler": CustomerProfilerAgent,
        "lead-hunter": LeadHunterAgent,
        "campaign-architect": CampaignArchitectAgent,
    }
    return agents.get(agent_id)


def get_all_agent_classes() -> dict:
    """Get all agent classes."""
    from agents.campaign_architect.src import CampaignArchitectAgent
    from agents.competitor_analyst.src import CompetitorAnalystAgent
    from agents.customer_profiler.src import CustomerProfilerAgent
    from agents.gtm_strategist.src import GTMStrategistAgent
    from agents.lead_hunter.src import LeadHunterAgent
    from agents.market_intelligence.src import MarketIntelligenceAgent

    return {
        "gtm-strategist": GTMStrategistAgent,
        "market-intelligence": MarketIntelligenceAgent,
        "competitor-analyst": CompetitorAnalystAgent,
        "customer-profiler": CustomerProfilerAgent,
        "lead-hunter": LeadHunterAgent,
        "campaign-architect": CampaignArchitectAgent,
    }


def is_valid_agent(agent_id: str) -> bool:
    """Check if an agent ID is valid."""
    return agent_id in AGENT_METADATA


def get_task_description(agent_id: str) -> str:
    """Get the default task description for an agent."""
    metadata = AGENT_METADATA.get(agent_id, {})
    return metadata.get("task_description", f"Execute {agent_id} analysis")
