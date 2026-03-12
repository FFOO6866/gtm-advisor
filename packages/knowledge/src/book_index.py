"""Layer 2: Curated index mapping reference books to frameworks and agents.

Static dict — no file I/O, no embeddings.  Used by BookKnowledgeExtractor to
decide which books to prioritise for which agents, and by KnowledgeMCPServer
to provide source attribution when returning framework content.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Book knowledge map
# ---------------------------------------------------------------------------

BOOK_KNOWLEDGE_MAP: dict[str, dict] = {
    "kotler_marketing_management": {
        "file": "kotler_keller_-_marketing_management_14th_edition.pdf",
        "title": "Marketing Management (14th Edition)",
        "authors": ["Philip Kotler", "Kevin Lane Keller"],
        "key_frameworks": ["STP_FRAMEWORK", "MARKETING_MIX_4P", "PORTER_FIVE_FORCES", "ICP_FRAMEWORK"],
        "chapter_topics": [
            "Market segmentation, targeting, positioning",
            "Brand equity and brand management",
            "Consumer and B2B buyer behaviour",
            "Pricing strategies",
            "Distribution channels",
            "Integrated marketing communications",
            "Digital marketing",
            "Managing customer relationships",
            "Market research and demand forecasting",
            "New product development",
        ],
        "high_value_chapters": {
            "Chapters 8–10": "Segmentation, targeting, positioning — core STP",
            "Chapters 11–12": "Brand equity and competitive positioning",
            "Chapters 14–16": "Pricing, channels, and communications",
            "Chapter 19": "Managing marketing in the global economy",
        },
        "agent_relevance": ["gtm_strategist", "customer_profiler", "campaign_architect", "competitor_analyst"],
        "extraction_priority": "high",
        "page_limit": 100,
        "notes": "34MB — large file. Cap at first 100 pages (Part I: understanding marketing). STP material is in early chapters.",
    },
    "principles_of_marketing": {
        "file": "principles of marketing.pdf",
        "title": "Principles of Marketing",
        "authors": ["Philip Kotler", "Gary Armstrong"],
        "key_frameworks": ["MARKETING_MIX_4P", "STP_FRAMEWORK", "RACE_FRAMEWORK"],
        "chapter_topics": [
            "Marketing environment scanning",
            "Consumer markets and buying behaviour",
            "Business markets and buying behaviour",
            "Marketing information and customer insights",
            "Products, services, and brands",
            "Pricing",
            "Marketing channels and retailing",
            "Advertising, PR, and digital",
        ],
        "high_value_chapters": {
            "Chapters 1–3": "Marketing fundamentals and environment",
            "Chapters 6–7": "Consumer and B2B buyer behaviour",
            "Chapters 14–15": "Advertising and integrated marketing",
        },
        "agent_relevance": ["gtm_strategist", "market_intelligence", "customer_profiler"],
        "extraction_priority": "medium",
        "page_limit": 100,
        "notes": "32MB — large file. Fundamentals book; less unique content than Kotler & Keller. Focus on B2B buyer behaviour chapters.",
    },
    "digital_marketing_strategy": {
        "file": "digital-marketing-strategy-an-integrated-approach-to-online-marketing-9780749498085-0749498080.pdf",
        "title": "Digital Marketing Strategy: An Integrated Approach to Online Marketing",
        "authors": ["Simon Kingsnorth"],
        "key_frameworks": ["RACE_FRAMEWORK", "MESSAGING_FRAMEWORKS", "GTM_FRAMEWORKS"],
        "chapter_topics": [
            "Digital marketing strategy and planning",
            "SEO and content marketing",
            "Paid media (PPC, social ads)",
            "Email marketing and automation",
            "Social media marketing",
            "Conversion rate optimisation (CRO)",
            "Analytics and attribution",
            "Customer experience and personalisation",
            "Mobile marketing",
            "AI and marketing technology",
        ],
        "high_value_chapters": {
            "Chapter 1": "Digital strategy development",
            "Chapters 3–5": "SEO, content, and PPC — highest practitioner value",
            "Chapter 9": "Email and automation",
            "Chapter 15": "Data, analytics, and measurement",
        },
        "agent_relevance": ["campaign_architect", "outreach_executor", "gtm_strategist"],
        "extraction_priority": "high",
        "page_limit": 100,
        "notes": "Best for campaign execution tactics and digital channel strategy. RACE framework is here.",
    },
    "cialdini_persuasion": {
        "file": "The Psychology of Persuasion.pdf",
        "title": "Influence: The Psychology of Persuasion",
        "authors": ["Robert B. Cialdini"],
        "key_frameworks": ["CIALDINI_PRINCIPLES", "OBJECTION_HANDLING_FRAMEWORK"],
        "chapter_topics": [
            "Reciprocity — the rule of giving",
            "Commitment and consistency",
            "Social proof",
            "Liking",
            "Authority",
            "Scarcity",
            "The combination of principles",
        ],
        "high_value_chapters": {
            "Chapter 1": "Weapons of influence — overview",
            "Chapters 2–7": "One chapter per principle — all essential",
        },
        "agent_relevance": ["campaign_architect", "outreach_executor", "lead_hunter"],
        "extraction_priority": "high",
        "page_limit": 100,
        "notes": "Entire book is relevant. Strongly distilled into CIALDINI_PRINCIPLES constant. RAG adds examples and nuance.",
    },
    "made_to_stick": {
        "file": "made-to-stick-why-some-ideas-survive-and-others-die.pdf",
        "title": "Made to Stick: Why Some Ideas Survive and Others Die",
        "authors": ["Chip Heath", "Dan Heath"],
        "key_frameworks": ["MADE_TO_STICK_SUCCESS", "MESSAGING_FRAMEWORKS"],
        "chapter_topics": [
            "Simple — finding the core",
            "Unexpected — the curse of knowledge and how to beat it",
            "Concrete — paint a picture",
            "Credible — finding credibility without authority",
            "Emotional — making people care",
            "Stories — telling for action",
        ],
        "high_value_chapters": {
            "Introduction": "The Curse of Knowledge — critical for messaging clarity",
            "Chapter 1–6": "One chapter per SUCCESs element",
            "Conclusion": "Bringing it together — sticky messaging checklist",
        },
        "agent_relevance": ["campaign_architect", "gtm_strategist", "outreach_executor"],
        "extraction_priority": "high",
        "page_limit": None,
        "notes": "Manageable size. Extract fully. Particularly valuable for the Curse of Knowledge framing and concrete storytelling.",
    },
    "ogilvy_on_advertising": {
        "file": "ogilvy-on-advertising_compress.pdf",
        "title": "Ogilvy on Advertising",
        "authors": ["David Ogilvy"],
        "key_frameworks": ["OGILVY_PRINCIPLES", "MESSAGING_FRAMEWORKS", "CAMPAIGN_BRIEF_TEMPLATE"],
        "chapter_topics": [
            "Confessions and principles",
            "How to produce advertising that sells",
            "How to run an advertising agency",
            "Competing for clients",
            "Advertising on television",
            "Direct mail — the Cinderella of advertising",
            "Corporate advertising",
            "Wanted: a renaissance in print advertising",
        ],
        "high_value_chapters": {
            "Chapter 1": "Advertising principles and philosophy",
            "Chapter 7": "How to write potent copy",
            "Chapter 10": "Direct mail — most applicable to B2B outreach",
        },
        "agent_relevance": ["campaign_architect", "outreach_executor"],
        "extraction_priority": "high",
        "page_limit": None,
        "notes": "Classic, manageable book. Direct mail chapters are directly applicable to email marketing. Extract fully.",
    },
    "new_rules_marketing_pr": {
        "file": "new-rules-of-marketing-amp-pr-how-to-use-social-media-online-video-mobile-applications-blogs-news-releases-and-viral-marketing-to-reach-buye-7nbsped-9781119651611-1119651611_compress.pdf",
        "title": "The New Rules of Marketing & PR",
        "authors": ["David Meerman Scott"],
        "key_frameworks": ["RACE_FRAMEWORK", "GTM_FRAMEWORKS", "MESSAGING_FRAMEWORKS"],
        "chapter_topics": [
            "New rules of marketing and PR",
            "Social media as a marketing tool",
            "Content marketing and thought leadership",
            "Real-time marketing",
            "News releases in the digital age",
            "Blogs and podcasts for marketing",
            "Video marketing",
            "Mobile and app marketing",
            "Newsjacking and real-time content",
        ],
        "high_value_chapters": {
            "Chapters 1–4": "Philosophy shift — old vs. new rules",
            "Chapters 8–12": "Content creation and thought leadership",
            "Chapter 18": "Reaching buyers directly — most relevant for outbound",
        },
        "agent_relevance": ["campaign_architect", "market_intelligence", "gtm_strategist"],
        "extraction_priority": "medium",
        "page_limit": 80,
        "notes": "Compressed file. Focus on content strategy and thought leadership chapters. Some chapters are dated — focus on strategic principles over tactics.",
    },
    "just_listen": {
        "file": "Just Listen by Mark Goulston PDF.pdf",
        "title": "Just Listen: Discover the Secret to Getting Through to Absolutely Anyone",
        "authors": ["Mark Goulston"],
        "key_frameworks": ["OBJECTION_HANDLING_FRAMEWORK", "SALES_QUALIFICATION"],
        "chapter_topics": [
            "The 9 core rules of persuasion",
            "Making people feel felt",
            "The make-or-break factor in all communication",
            "Talking to fill-in-the-blank people",
            "Getting through to yourself first",
            "Persuasion in crisis situations",
            "The art of empathy in business",
        ],
        "high_value_chapters": {
            "Part I": "The science of reaching people — core psychological framework",
            "Part II": "Nine core rules — all applicable to sales and negotiation",
            "Part III": "Application to specific relationship types",
        },
        "agent_relevance": ["outreach_executor", "campaign_architect", "lead_hunter"],
        "extraction_priority": "high",
        "page_limit": None,
        "notes": "Small book. Extract fully. The 'make them feel felt' principle is the single most valuable insight for objection handling.",
    },
    "art_of_marketing_pr": {
        "file": "Art-of-Marketing-and-PR.pdf",
        "title": "Art of Marketing and PR",
        "authors": ["Unknown"],
        "key_frameworks": ["MESSAGING_FRAMEWORKS", "CAMPAIGN_BRIEF_TEMPLATE"],
        "chapter_topics": [
            "Marketing fundamentals",
            "PR strategy",
            "Media relations",
            "Crisis communications",
            "Brand building",
        ],
        "agent_relevance": ["campaign_architect", "gtm_strategist"],
        "extraction_priority": "low",
        "page_limit": 50,
        "notes": "Supplementary material. Lower priority than Ogilvy and Cialdini for agent use. Extract PR and media relations chapters.",
    },
    "marketing_strategy_3": {
        "file": "3.MarketingStratergy.pdf",
        "title": "Marketing Strategy",
        "authors": ["Unknown"],
        "key_frameworks": ["GTM_FRAMEWORKS", "STP_FRAMEWORK", "PORTER_FIVE_FORCES"],
        "chapter_topics": [
            "Strategic marketing planning",
            "Competitive analysis",
            "Market entry strategies",
            "Growth strategies",
        ],
        "agent_relevance": ["gtm_strategist", "competitor_analyst", "market_intelligence"],
        "extraction_priority": "medium",
        "page_limit": 60,
        "notes": "Supplementary strategic marketing text. Focus on market analysis and competitive strategy chapters.",
    },
    "cmh_en": {
        "file": "CMH_EN_www.pdf",
        "title": "Customer Marketing Handbook",
        "authors": ["Unknown"],
        "key_frameworks": ["ICP_FRAMEWORK", "CAMPAIGN_BRIEF_TEMPLATE"],
        "chapter_topics": [
            "Customer segmentation",
            "Customer lifecycle marketing",
            "Retention and loyalty programmes",
            "Customer value management",
        ],
        "agent_relevance": ["customer_profiler", "campaign_architect"],
        "extraction_priority": "low",
        "page_limit": 60,
        "notes": "Customer retention focus. Most relevant for customer success and expansion revenue contexts.",
    },
    "paul_copley_marketing_communications": {
        "file": "Paul Copley - Marketing Communications Management_ Concepts and Theories, Cases and Practices (2004).pdf",
        "title": "Marketing Communications Management: Concepts and Theories, Cases and Practices",
        "authors": ["Paul Copley"],
        "key_frameworks": ["MESSAGING_FRAMEWORKS", "CAMPAIGN_BRIEF_TEMPLATE", "RACE_FRAMEWORK"],
        "chapter_topics": [
            "Integrated marketing communications",
            "Advertising planning",
            "Media planning and buying",
            "Direct marketing",
            "Sales promotion",
            "Public relations",
            "Sponsorship",
            "Online and digital communications",
        ],
        "high_value_chapters": {
            "Chapter 1": "IMC — integrated communications planning",
            "Chapter 4": "Advertising strategy",
            "Chapter 8": "Direct marketing — most applicable",
            "Chapter 11": "Online communications",
        },
        "agent_relevance": ["campaign_architect", "outreach_executor"],
        "extraction_priority": "medium",
        "page_limit": 80,
        "notes": "Academic but practical. IMC chapters are valuable for multi-channel campaign architecture.",
    },
    "marketing_communication_book": {
        "file": "MarketingCommunicationBook.docx",
        "title": "Marketing Communications (DOCX)",
        "authors": ["Unknown"],
        "key_frameworks": ["MESSAGING_FRAMEWORKS"],
        "chapter_topics": [
            "Marketing communications theory",
            "Message strategy",
            "Media strategy",
        ],
        "agent_relevance": ["campaign_architect"],
        "extraction_priority": "low",
        "page_limit": None,
        "notes": "DOCX format — requires python-docx extraction (not pypdf). Lower priority. Extract if time permits.",
    },
}

# ---------------------------------------------------------------------------
# Agent → Relevant books lookup
# ---------------------------------------------------------------------------

AGENT_BOOK_RELEVANCE: dict[str, list[str]] = {
    "campaign_architect": [
        "cialdini_persuasion",
        "made_to_stick",
        "ogilvy_on_advertising",
        "just_listen",
        "digital_marketing_strategy",
        "paul_copley_marketing_communications",
        "kotler_marketing_management",
    ],
    "customer_profiler": [
        "kotler_marketing_management",
        "principles_of_marketing",
        "cmh_en",
    ],
    "gtm_strategist": [
        "kotler_marketing_management",
        "digital_marketing_strategy",
        "new_rules_marketing_pr",
        "marketing_strategy_3",
        "principles_of_marketing",
    ],
    "market_intelligence": [
        "kotler_marketing_management",
        "marketing_strategy_3",
        "principles_of_marketing",
        "new_rules_marketing_pr",
    ],
    "competitor_analyst": [
        "kotler_marketing_management",
        "marketing_strategy_3",
        "principles_of_marketing",
    ],
    "lead_hunter": [
        "cialdini_persuasion",
        "just_listen",
        "kotler_marketing_management",
    ],
    "outreach_executor": [
        "cialdini_persuasion",
        "just_listen",
        "ogilvy_on_advertising",
        "digital_marketing_strategy",
        "made_to_stick",
        "paul_copley_marketing_communications",
    ],
}

# ---------------------------------------------------------------------------
# Framework → Source book attribution
# ---------------------------------------------------------------------------

FRAMEWORK_SOURCE_ATTRIBUTION: dict[str, list[str]] = {
    "CIALDINI_PRINCIPLES": ["cialdini_persuasion"],
    "MADE_TO_STICK_SUCCESS": ["made_to_stick"],
    "OGILVY_PRINCIPLES": ["ogilvy_on_advertising"],
    "MESSAGING_FRAMEWORKS": [
        "kotler_marketing_management",
        "digital_marketing_strategy",
        "paul_copley_marketing_communications",
    ],
    "STP_FRAMEWORK": ["kotler_marketing_management", "principles_of_marketing"],
    "GTM_FRAMEWORKS": ["digital_marketing_strategy", "marketing_strategy_3", "new_rules_marketing_pr"],
    "SALES_QUALIFICATION": ["just_listen", "kotler_marketing_management"],
    "ICP_FRAMEWORK": ["kotler_marketing_management", "cmh_en"],
    "SINGAPORE_SME_CONTEXT": [],  # synthesised from local market knowledge
    "CAMPAIGN_BRIEF_TEMPLATE": [
        "ogilvy_on_advertising",
        "digital_marketing_strategy",
        "paul_copley_marketing_communications",
    ],
    "OBJECTION_HANDLING_FRAMEWORK": ["just_listen", "cialdini_persuasion"],
    "RACE_FRAMEWORK": ["digital_marketing_strategy", "new_rules_marketing_pr"],
    "MARKETING_MIX_4P": ["kotler_marketing_management", "principles_of_marketing"],
    "PORTER_FIVE_FORCES": ["kotler_marketing_management", "marketing_strategy_3"],
}


def get_books_for_agent(agent_name: str) -> list[dict]:
    """Return list of book metadata dicts relevant to the given agent.

    Args:
        agent_name: Kebab-case agent name (e.g. 'campaign-architect').

    Returns:
        List of book metadata dicts from BOOK_KNOWLEDGE_MAP, sorted by
        extraction_priority (high first).
    """
    # Normalise kebab-case to underscore
    normalised = agent_name.replace("-", "_")
    book_keys = AGENT_BOOK_RELEVANCE.get(normalised, [])

    priority_order = {"high": 0, "medium": 1, "low": 2}
    books = [
        {"key": k, **BOOK_KNOWLEDGE_MAP[k]}
        for k in book_keys
        if k in BOOK_KNOWLEDGE_MAP
    ]
    return sorted(books, key=lambda b: priority_order.get(b.get("extraction_priority", "low"), 2))


def get_attribution_for_framework(framework_name: str) -> list[dict]:
    """Return source book attribution for a given framework constant name.

    Args:
        framework_name: e.g. 'CIALDINI_PRINCIPLES'

    Returns:
        List of book metadata dicts (may be empty for synthesised frameworks).
    """
    book_keys = FRAMEWORK_SOURCE_ATTRIBUTION.get(framework_name, [])
    return [{"key": k, **BOOK_KNOWLEDGE_MAP[k]} for k in book_keys if k in BOOK_KNOWLEDGE_MAP]
