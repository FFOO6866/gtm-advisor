"""Singapore Market Vertical seed data.

12 primary verticals anchored to SSIC 2020 section codes and EODHD GicsSector values.
Call `seed_verticals(session)` once at startup / migration time.

These are stable definitions — update only when SSIC classification changes or
a new vertical becomes significant enough to benchmark separately.
"""

from __future__ import annotations

VERTICAL_SEEDS: list[dict] = [
    {
        "slug": "fintech",
        "name": "Fintech / Financial Services",
        "industry_category": "Financial Services",
        "description": (
            "Digital payments, wealth technology, insurance technology, digital banking, "
            "lending platforms, and regulated financial institutions in Singapore."
        ),
        "ssic_sections": ["K"],
        "ssic_codes": ["64191", "64921", "66120", "66191", "64992"],
        "gics_sectors": ["Financials"],
        "keywords": [
            "fintech", "payments", "wealthtech", "insurtech", "digital bank",
            "neobank", "lending", "investment platform", "robo-advisor",
            "MAS licence", "digital payment", "fund management",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "biomedical",
        "name": "Biomedical / HealthTech",
        "industry_category": "Healthcare & Life Sciences",
        "description": (
            "Pharmaceutical manufacturing, medical devices, contract research organisations, "
            "health IT, diagnostics, and biotech R&D in Singapore."
        ),
        "ssic_sections": ["Q", "M"],
        "ssic_codes": ["21000", "26600", "72100", "86100", "86210"],
        "gics_sectors": ["Health Care"],
        "keywords": [
            "biomedical", "pharmaceutical", "medtech", "healthtech", "diagnostics",
            "medical device", "CRO", "clinical trial", "genomics", "biotech",
            "health IT", "telehealth", "digital health",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "advanced_manufacturing",
        "name": "Advanced Manufacturing",
        "industry_category": "Manufacturing & Engineering",
        "description": (
            "Precision engineering, semiconductor equipment, aerospace MRO, "
            "electronics manufacturing, and Industry 4.0 in Singapore."
        ),
        "ssic_sections": ["C"],
        "ssic_codes": ["26110", "28290", "30300", "33160", "25990"],
        "gics_sectors": ["Industrials", "Information Technology"],
        "keywords": [
            "precision engineering", "semiconductor", "aerospace", "MRO", "electronics",
            "manufacturing", "Industry 4.0", "automation", "robotics", "PCB",
            "wafer fab", "cleanroom",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "logistics",
        "name": "Logistics / Supply Chain",
        "industry_category": "Trade & Logistics",
        "description": (
            "Third-party logistics, cold chain, port operations, last-mile delivery, "
            "freight forwarding, and supply chain technology in Singapore."
        ),
        "ssic_sections": ["H"],
        "ssic_codes": ["52100", "52241", "52290", "53100", "49200"],
        "gics_sectors": ["Industrials"],
        "keywords": [
            "logistics", "supply chain", "3PL", "freight", "warehousing",
            "cold chain", "last mile", "port", "shipping", "forwarding",
            "distribution", "fulfilment",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "retail_ecommerce",
        "name": "Retail / E-commerce",
        "industry_category": "Consumer & Retail",
        "description": (
            "Physical retail, direct-to-consumer brands, marketplaces, omnichannel retail, "
            "and retail technology in Singapore and Southeast Asia."
        ),
        "ssic_sections": ["G"],
        "ssic_codes": ["47111", "47191", "47910", "47990"],
        "gics_sectors": ["Consumer Discretionary", "Consumer Staples"],
        "keywords": [
            "retail", "e-commerce", "marketplace", "D2C", "omnichannel",
            "shopping", "brand", "consumer", "FMCG", "fashion", "grocery",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "proptech",
        "name": "PropTech / Real Estate",
        "industry_category": "Real Estate",
        "description": (
            "Real estate technology, property developers, construction technology, "
            "smart buildings, and REITs (tracked separately under 'reits' vertical)."
        ),
        "ssic_sections": ["L", "F"],
        "ssic_codes": ["68100", "68200", "41001", "41002", "43290"],
        "gics_sectors": ["Real Estate"],
        "keywords": [
            "proptech", "real estate", "property", "construction", "smart building",
            "facility management", "BIM", "developer", "residential", "commercial",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "reits",
        "name": "REITs & Business Trusts",
        "industry_category": "Real Estate",
        "description": (
            "Singapore-listed Real Estate Investment Trusts and Business Trusts. "
            "Benchmarked separately using DPU yield, NAV premium, and gearing ratio."
        ),
        "ssic_sections": ["K", "L"],
        "ssic_codes": ["64300"],
        "gics_sectors": ["Real Estate"],
        "keywords": [
            "REIT", "real estate investment trust", "business trust", "DPU",
            "distribution yield", "NAV", "gearing", "unitholders",
        ],
        "is_reit_vertical": True,
    },
    {
        "slug": "clean_energy",
        "name": "Clean Energy / GreenTech",
        "industry_category": "Energy & Sustainability",
        "description": (
            "Solar energy, carbon markets, waste management technology, water treatment, "
            "energy efficiency, and sustainability technology."
        ),
        "ssic_sections": ["D", "E"],
        "ssic_codes": ["35110", "35120", "38110", "36000", "35210"],
        "gics_sectors": ["Utilities", "Industrials"],
        "keywords": [
            "clean energy", "greentech", "solar", "carbon", "ESG", "sustainability",
            "renewable", "energy efficiency", "waste management", "water treatment",
            "net zero", "decarbonisation",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "maritime",
        "name": "Maritime",
        "industry_category": "Trade & Logistics",
        "description": (
            "Shipping, marine offshore, port technology, ship management, "
            "bunker trading, and maritime digitalisation."
        ),
        "ssic_sections": ["H"],
        "ssic_codes": ["50110", "50120", "50200", "52221", "77341"],
        "gics_sectors": ["Industrials", "Energy"],
        "keywords": [
            "maritime", "shipping", "vessel", "offshore", "bunker", "port",
            "marine", "tanker", "container ship", "ship management", "MPA",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "professional_services",
        "name": "Professional Services",
        "industry_category": "Professional Services",
        "description": (
            "Legal technology, HR technology, management consulting, accounting, "
            "recruitment, and B2B professional services."
        ),
        "ssic_sections": ["M", "N"],
        "ssic_codes": ["69100", "70100", "73100", "78100", "82110"],
        "gics_sectors": ["Industrials"],
        "keywords": [
            "professional services", "consulting", "legal", "HR", "human resources",
            "recruitment", "accounting", "advisory", "B2B services", "outsourcing",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "edtech",
        "name": "EdTech / Education",
        "industry_category": "Education",
        "description": (
            "Education technology, private education institutions, corporate training, "
            "SkillsFuture programmes, and K-12 technology."
        ),
        "ssic_sections": ["P"],
        "ssic_codes": ["85421", "85422", "85491", "85499", "72200"],
        "gics_sectors": ["Consumer Discretionary"],
        "keywords": [
            "edtech", "education", "learning", "training", "SkillsFuture", "upskilling",
            "LMS", "corporate training", "e-learning", "MOOCs", "tutoring",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "ict_saas",
        "name": "ICT / SaaS / Tech",
        "industry_category": "Technology",
        "description": (
            "Software-as-a-Service, cybersecurity, cloud computing, AI/ML platforms, "
            "IT services, and telecommunications in Singapore."
        ),
        "ssic_sections": ["J"],
        "ssic_codes": ["62010", "62020", "62090", "63110", "61100", "61200"],
        "gics_sectors": ["Information Technology", "Communication Services"],
        "keywords": [
            "SaaS", "software", "cloud", "cybersecurity", "AI", "machine learning",
            "IT services", "telecom", "data", "platform", "API", "enterprise software",
            "digital transformation",
        ],
        "is_reit_vertical": False,
    },
    {
        "slug": "marketing_comms",
        "name": "Marketing, Communications & PR",
        "industry_category": "Professional Services",
        "description": (
            "Advertising holding groups, creative agencies, media buying, digital marketing, "
            "public relations, influencer marketing, martech/adtech platforms, "
            "experiential marketing, OOH, and market research firms in Singapore and globally."
        ),
        "ssic_sections": ["M", "J"],
        "ssic_codes": ["73100", "73200", "70201", "63910", "59110"],
        "gics_sectors": ["Communication Services", "Consumer Discretionary"],
        "keywords": [
            "advertising", "creative agency", "media agency", "public relations",
            "digital marketing", "influencer marketing", "martech", "adtech",
            "media buying", "branding", "communications", "marketing agency",
            "out-of-home", "experiential", "content marketing", "performance marketing",
            "social media marketing", "programmatic", "market research", "PR agency",
        ],
        "is_reit_vertical": False,
    },
]

# Curated list of Singapore-founded / Singapore-HQ'd companies listed on non-SGX exchanges.
# Format: {"ticker": str, "exchange": str, "name": str, "vertical_slug": str}
#
# Rules for inclusion:
#   1. Company must be founded in Singapore OR have primary HQ in Singapore.
#   2. Exchange must be non-SGX — SGX-listed companies are covered by the main
#      `sync_exchange_roster("SG")` call and should NOT appear here (avoids duplicates).
#   3. EODHD exchange codes: "US" = NYSE/Nasdaq, "HK" = HKEx, "AU" = ASX, "LSE" = London
#
# NOTE: This list requires manual curation as new SG companies go public overseas.
# Last reviewed: 2026-03 — 19 companies across US / HK / AU exchanges.
OVERSEAS_LISTED_SG_COMPANIES: list[dict] = [
    # ── US (NYSE / Nasdaq) ──────────────────────────────────────────────────
    # Sea Limited: Shopee, Garena, SeaMoney — Singapore's largest tech company
    {"ticker": "SE", "exchange": "US", "name": "Sea Limited", "vertical_slug": "retail_ecommerce"},
    # Grab Holdings: ride-hail, delivery, GrabPay superapp
    {"ticker": "GRAB", "exchange": "US", "name": "Grab Holdings", "vertical_slug": "fintech"},
    # PropertyGuru: SG-founded proptech marketplace (NYSE SPAC merger 2022)
    {"ticker": "PGRU", "exchange": "US", "name": "PropertyGuru Group", "vertical_slug": "proptech"},
    # MoneyHero Group: financial comparison platform (formerly CompareAsiaGroup, Nasdaq 2023)
    {"ticker": "MNY", "exchange": "US", "name": "MoneyHero Group", "vertical_slug": "fintech"},
    # Coda Octopus Group: Singapore-based marine technology and survey solutions
    {"ticker": "CODA", "exchange": "US", "name": "Coda Octopus Group", "vertical_slug": "maritime"},
    # Gorilla Technology: Singapore-founded AI-powered video security and IoT intelligence
    {"ticker": "GRRR", "exchange": "US", "name": "Gorilla Technology Group", "vertical_slug": "ict_saas"},
    # ── HKEx (Hong Kong Stock Exchange) ────────────────────────────────────
    # Mapletree Investments is private; Mapletree Pan Asia Commercial Trust on SGX only.
    # Oversea-Chinese Banking Corporation (OCBC) — Singapore's second-largest bank.
    # OCBC shares are primarily traded on SGX; no separate HKEx listing.
    # Singapore Airlines: primary on SGX but also traded as GDR on LSE. See LSE section.
    # Parkway Life REIT: SGX-listed, no HKEx entry.
    # HUTCHMED (China) Limited: HK-listed biomedical spinoff with SG research centre
    {"ticker": "13", "exchange": "HK", "name": "HUTCHMED (China) Limited", "vertical_slug": "biomedical"},
    # Jardine Cycle & Carriage: Singapore-registered Jardine arm on HKEx
    {"ticker": "JCNC", "exchange": "HK", "name": "Jardine Cycle & Carriage", "vertical_slug": "retail_ecommerce"},
    # CapitaLand China Trust: Singapore REIT investing in Chinese retail assets; HKEx RMB counter
    {"ticker": "CLCT", "exchange": "HK", "name": "CapitaLand China Trust", "vertical_slug": "reits"},
    # Sembcorp Industries: energy and urban development; primary SGX but HKEx depository receipts
    {"ticker": "U96", "exchange": "HK", "name": "Sembcorp Industries (HKEx DR)", "vertical_slug": "clean_energy"},
    # ── ASX (Australian Securities Exchange) ───────────────────────────────
    # Keppel Infrastructure Trust: Singapore trust with ASX cross-listing
    {"ticker": "KIT", "exchange": "AU", "name": "Keppel Infrastructure Trust", "vertical_slug": "logistics"},
    # Moxian: Singapore-based digital media; listed on ASX
    {"ticker": "MXC", "exchange": "AU", "name": "Moxian Inc", "vertical_slug": "ict_saas"},
    # Halcyon Agri Corporation: Singapore agri-commodity company; ASX-listed
    {"ticker": "HAL", "exchange": "AU", "name": "Halcyon Agri Corporation", "vertical_slug": "advanced_manufacturing"},
    # ── LSE (London Stock Exchange) ─────────────────────────────────────────
    # Singapore Airlines: London GDR under SINGY (OTC/Pink Sheets, not formal LSE listing;
    # primary exchange SGX — omit to avoid duplicate; covered by SGX roster)
    # Standard Chartered PLC: London-listed bank with >50% revenue from Asia, SG hub
    {"ticker": "STAN", "exchange": "LSE", "name": "Standard Chartered PLC", "vertical_slug": "fintech"},
    # Olam Group: Singapore agri-food commodity; LSE-listed until 2023 (delisted Oct 2023)
    # Removed — delisted. Olam Agri spinoff is on SGX.
    # ── OTC / Pink Sheets ───────────────────────────────────────────────────
    # Singapore Airlines OTC ADR (SINGF/SINGY) — useful benchmark; primary SGX
    {"ticker": "SINGF", "exchange": "US", "name": "Singapore Airlines ADR", "vertical_slug": "logistics"},
    # Singapore Telecommunications ADR (SGAPY)
    {"ticker": "SGAPY", "exchange": "US", "name": "Singapore Telecommunications ADR", "vertical_slug": "ict_saas"},
    # DBS Group ADR (DBSDY) — largest SG bank
    {"ticker": "DBSDY", "exchange": "US", "name": "DBS Group ADR", "vertical_slug": "fintech"},
    # OCBC ADR (OVCHY)
    {"ticker": "OVCHY", "exchange": "US", "name": "OCBC Bank ADR", "vertical_slug": "fintech"},
    # United Overseas Bank ADR (UOVEY)
    {"ticker": "UOVEY", "exchange": "US", "name": "United Overseas Bank ADR", "vertical_slug": "fintech"},
]


async def seed_verticals(session: AsyncSession) -> int:  # type: ignore[name-defined]  # noqa: F821
    """Upsert the 12 verticals into market_verticals table.

    Returns count of rows upserted.
    Called from FastAPI lifespan or alembic data migration.
    """
    from sqlalchemy import select

    from packages.database.src.models import MarketVertical

    count = 0
    for seed in VERTICAL_SEEDS:
        result = await session.execute(
            select(MarketVertical).where(MarketVertical.slug == seed["slug"])
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(MarketVertical(**seed))
            count += 1
        else:
            # Update mutable fields in case they changed
            existing.name = seed["name"]
            existing.keywords = seed["keywords"]
            existing.gics_sectors = seed["gics_sectors"]
            existing.description = seed["description"]
            existing.industry_category = seed["industry_category"]
    await session.flush()
    return count
