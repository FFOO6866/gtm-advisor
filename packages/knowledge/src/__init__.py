from .book_index import (
    AGENT_BOOK_RELEVANCE,
    BOOK_KNOWLEDGE_MAP,
    FRAMEWORK_SOURCE_ATTRIBUTION,
    get_attribution_for_framework,
    get_books_for_agent,
)
from .extractor import BookKnowledgeExtractor, KnowledgeChunk
from .frameworks import (
    ALL_FRAMEWORK_NAMES,
    CAMPAIGN_BRIEF_TEMPLATE,
    CIALDINI_PRINCIPLES,
    GTM_FRAMEWORKS,
    ICP_FRAMEWORK,
    MADE_TO_STICK_SUCCESS,
    MARKETING_MIX_4P,
    MESSAGING_FRAMEWORKS,
    OBJECTION_HANDLING_FRAMEWORK,
    OGILVY_PRINCIPLES,
    PORTER_FIVE_FORCES,
    RACE_FRAMEWORK,
    SALES_QUALIFICATION,
    SINGAPORE_SME_CONTEXT,
    STP_FRAMEWORK,
)
from .knowledge_mcp import KnowledgeMCPServer, get_knowledge_mcp
from .research_persist import persist_research

__all__ = [
    # Layer 1 — frameworks
    "ALL_FRAMEWORK_NAMES",
    "CAMPAIGN_BRIEF_TEMPLATE",
    "CIALDINI_PRINCIPLES",
    "GTM_FRAMEWORKS",
    "ICP_FRAMEWORK",
    "MADE_TO_STICK_SUCCESS",
    "MARKETING_MIX_4P",
    "MESSAGING_FRAMEWORKS",
    "OBJECTION_HANDLING_FRAMEWORK",
    "OGILVY_PRINCIPLES",
    "PORTER_FIVE_FORCES",
    "RACE_FRAMEWORK",
    "SALES_QUALIFICATION",
    "SINGAPORE_SME_CONTEXT",
    "STP_FRAMEWORK",
    # Layer 2 — book index
    "AGENT_BOOK_RELEVANCE",
    "BOOK_KNOWLEDGE_MAP",
    "FRAMEWORK_SOURCE_ATTRIBUTION",
    "get_attribution_for_framework",
    "get_books_for_agent",
    # Layer 3 — extractor
    "BookKnowledgeExtractor",
    "KnowledgeChunk",
    # Layer 4 — MCP server + domain guide store
    "KnowledgeMCPServer",
    "get_knowledge_mcp",
    # Layer 5 — research persistence helper
    "persist_research",
]
