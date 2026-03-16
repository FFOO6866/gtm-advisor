"""Financial Intelligence Sync — EODHD → PostgreSQL/SQLite.

Syncs three tables from the EODHD API:
  1. listed_companies   — SGX symbol roster + curated overseas-listed SG cos
  2. company_financial_snapshots — annual & quarterly income/balance/cashflow rows
  3. company_executives — CEO, CFO, Chair and other officers

Designed to be called by APScheduler jobs:
  - Weekly:    sync_exchange_roster("SG")
  - Daily:     sync_financial_snapshots(limit=50)
  - On demand: sync_company(ticker, exchange)
  - Weekly:    compute_and_store_benchmarks(vertical_slug, period_label)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import sqlalchemy as sa
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import (
    CompanyExecutive,
    CompanyFinancialSnapshot,
    CompanyListingType,
    FinancialPeriodType,
    ListedCompany,
    MarketVertical,
    VerticalBenchmark,
)
from packages.database.src.vertical_seeds import OVERSEAS_LISTED_SG_COMPANIES
from packages.integrations.eodhd.src.client import EODHDClient, get_eodhd_client
from packages.scoring.src.financial_benchmarks import CompanyMetrics, FinancialBenchmarkEngine

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# GICS industry → vertical slug mapping (used when fundamentals are loaded)
# ---------------------------------------------------------------------------
# Keys are substrings checked against gics_industry.lower(); first match wins.
# Order matters: more specific entries before broader ones.

_GICS_INDUSTRY_MAP: list[tuple[str, str]] = [
    # REITs / Real Estate Investment Trusts — must come before generic real estate
    ("real estate investment trust", "reits"),
    ("equity real estate", "reits"),
    # Maritime disambiguation within Industrials / Energy
    ("marine", "maritime"),
    ("shipping", "maritime"),
    ("oil, gas", "maritime"),
    ("energy equipment", "maritime"),
    # Logistics disambiguation within Industrials
    ("transportation infrastructure", "logistics"),
    ("air freight", "logistics"),
    ("trucking", "logistics"),
    ("road & rail", "logistics"),
    ("ground transportation", "logistics"),
    # Clean Energy within Utilities / Industrials
    ("electric utilities", "clean_energy"),
    ("water utilities", "clean_energy"),
    ("independent power", "clean_energy"),
    ("gas utilities", "clean_energy"),
    # Advanced Manufacturing disambiguation within Industrials / IT
    ("semiconductors", "advanced_manufacturing"),
    ("technology hardware", "advanced_manufacturing"),
    ("electronic equipment", "advanced_manufacturing"),
    ("electrical equipment", "advanced_manufacturing"),
    ("aerospace & defense", "advanced_manufacturing"),
    ("machinery", "advanced_manufacturing"),
    ("industrial conglomerates", "advanced_manufacturing"),
    # PropTech within Real Estate / Industrials
    ("construction & engineering", "proptech"),
    ("building products", "proptech"),
    ("real estate management", "proptech"),
    # ICT / SaaS within Information Technology / Communication Services
    ("software", "ict_saas"),
    ("it services", "ict_saas"),
    ("communications equipment", "ict_saas"),
    ("interactive media", "ict_saas"),
    ("wireless telecommunication", "ict_saas"),
    # Biomedical within Health Care
    ("pharmaceuticals", "biomedical"),
    ("health care equipment", "biomedical"),
    ("health care providers", "biomedical"),
    ("health care services", "biomedical"),
    ("biotechnology", "biomedical"),
    ("life sciences", "biomedical"),
    # Consumer / Retail
    ("food & staples", "retail_ecommerce"),
    ("food products", "retail_ecommerce"),
    ("retailing", "retail_ecommerce"),
    ("hotels, restaurants", "retail_ecommerce"),
    ("leisure products", "retail_ecommerce"),
    # Fintech / Financial
    ("banks", "fintech"),
    ("diversified financials", "fintech"),
    ("insurance", "fintech"),
    ("capital markets", "fintech"),
    # EdTech within Consumer Discretionary
    ("diversified consumer services", "edtech"),
]

# ---------------------------------------------------------------------------
# S&P 500 sector → vertical slug fallback (used when no GICS industry match)
# ---------------------------------------------------------------------------
# Maps EODHD sector strings from the index-components response to GTM verticals.
# Used only when _GICS_INDUSTRY_MAP produces no match for the GICS industry.

_SP500_SECTOR_MAP: dict[str, str] = {
    "Technology": "ict_saas",
    "Financial Services": "fintech",
    "Healthcare": "biomedical",
    "Real Estate": "reits",
    "Utilities": "clean_energy",
    "Industrials": "advanced_manufacturing",
    "Consumer Cyclical": "retail_ecommerce",
    "Consumer Defensive": "retail_ecommerce",
    "Communication Services": "ict_saas",
    "Energy": "clean_energy",
    "Basic Materials": "advanced_manufacturing",
}

# ---------------------------------------------------------------------------
# Extended name-keyword map for SGX companies (used when gics_sector is NULL)
# ---------------------------------------------------------------------------
# Each entry: (keywords_to_match_in_name_lower, vertical_slug)
# Checked in order; first match wins. Keywords are checked as substrings.

_NAME_KEYWORD_RULES: list[tuple[list[str], str]] = [
    # REITs and Business Trusts — very recognisable names.
    # " trust" (with leading space) avoids matching "industry" or "trustworthy".
    # "infrastructure trust" and "business trust" are explicit; plain " trust"
    # also covers CDL Hospitality Trusts, Parkway Life, etc.
    (["reit", "real estate investment trust", " trust", "stapled trust"], "reits"),

    # Maritime — shipbuilding, tankers, offshore, port ops.
    # List specific tickers/names before generic keywords to reduce false hits.
    (["shipbldg", "shipbuilding", "tanker", "maritime", "offshore",
      "vessel", "bunker", "seatrium",
      "pacific radiance", "atlantic navigation", "vallianz",
      "nam cheong", "kim heng", "mencast", "mtq corp",
      "mooreast", "xmh hold",
      "flex lng", "tiong woon",
      "marco polo marine", "asl marine", "ch offshore",
      "cosco shipping", "samudera", "singapore shipping",
      # Additional SGX marine companies
      "beng kuang marine", "jason marine", "penguin international",
      "uni-asia group", "ocean sky international",
      "courage investment", "boldtek",
      "grand banks yachts"], "maritime"),

    # Logistics — freight, transport ops, airport services, postal.
    # "shipping" is intentionally absent here (captured in maritime above).
    (["logistics", "freight", "3pl", "warehousing", "supply chain",
      "forwarding", "last mile", "comfortdelgro",
      "sbs transit", "sia engineering", "sats ltd",
      "vicom ltd", "heatec jietong", "hiap tong corp",
      # Additional SGX logistics companies
      "singapore post", "chasen holdings",
      "gke corporation", "lhn limited",
      "hiap seng industries", "mun siong engineering",
      "ley choon group", "nordic group",
      "huationg global", "civmec limited",
      "okp holdings", "acrometa"], "logistics"),

    # Biomedical / HealthTech
    (["healthcare", "health care", "medical ", "biomedical", "pharmaceutical",
      "pharma", "clinical", "diagnostics", "biotech", "genomics",
      "biopharma", "medtech", "gloves", "surgical", "biobank",
      "sarine", "isec healthcare", "ix biopharma",
      "pharmesis", "asia vets", "medtecs", "medi lifestyle",
      "livingstone health", "tianjin pharm", "haw par",
      # Additional SGX healthcare/biomedical companies
      "dental", "biolidics", "clearbridge health", "cordlife",
      "medinex", "meta health", "singapore paincare",
      "asiamedic", "top glove", "riverstone holdings",
      "the trendlines", "trendlines group",
      "aoxin", "alpha dx group",
      "healthbank"], "biomedical"),

    # Clean Energy / GreenTech — water, waste, environmental, renewables.
    # Agri/plantation companies are NOT clean energy — keep them out.
    (["solar", "clean energy", "greentech", "renewable", "decarboni",
      "net zero", "water treatment", "water technol",
      "waste management", "environmental tech", "env hldg",
      "ecowise", "siic environment", "memiontec", "enviro-hub",
      "isoteam", "sembcorp industries",
      "darco water", "china environmental", "ultragreen",
      "zheneng jinjiang", "reclaims global",
      "leader environmental", "sanli environmental",
      # Additional SGX clean energy / utilities / resources companies
      "china everbright water", "eneco energy", "natural cool",
      "ouhua energy", "sunpower group", "tricklestar",
      "union gas", "yunnan energy", "h2g green",
      "suntar eco", "sheffield green",
      "metis energy", "oiltek international"], "clean_energy"),

    # Natural resources / commodities — oil, gas, mining, metals, energy.
    # Mapped to clean_energy (closest SGX vertical for energy/resources).
    # Food agri (golden agri, bumitama, etc.) is handled in retail_ecommerce above.
    # Deliberate ordering after maritime so "oil" in shipping names hits maritime first.
    # "agri resources" deliberately excluded — Indofood Agri captured in retail above.
    (["natural resources", "plantation", "coal", "petroleum",
      "oil & gas", "oil and gas",
      "geo energy", "blackgold", "rex international",
      "southern alliance mining", "china mining",
      "malaysia smelting",
      "china aviation oil",
      "ptt exploration", "straits trading co",
      # Additional SGX resources companies
      "gss energy", "rh petrogas", "interra resources",
      "alita resources", "asiaphos", "cnmc goldmine",
      "fortress minerals", "gccp resources",
      "wilton resources", "resources global",
      "sinostar pec", "ap oil international",
      "samko timber", "kencana agri",
      "engro corporation", "jiutian chemical",
      "megachem limited", "chemical industries",
      "southern archipelago"], "clean_energy"),

    # PropTech / Real Estate (non-REIT property developers + construction)
    (["real estate", "property", "proptech", "developer", "construction",
      "estates", "realty", "hospitality", "hotel grand",
      "hotel properties", "serviced residence",
      "facility management", "smart building",
      "ascott", "capitaland invest", "soilbuild",
      "pollux prop", "emerging towns", "city developments",
      "wee hur", "low keng huat", "hock lian seng",
      "ta corporation", "pan-united", "csc holdings", "bonvests",
      "stamford land", "hong fok", "bukit sembawang",
      "raffles infrastructure", "bund center",
      "china yuanbang", "bbr holdings", "okh global",
      "singapore kitchen equip", "debao property",
      "ying li intl", "apac realty", "ascendas india",
      # Additional SGX property developers, hotel, and construction companies
      "af global", "banyan tree", "centurion corporation",
      "far east orchard", "guocoland", "hatten land",
      "heeton holdings", "hiap hoe", "ho bee land",
      "hongkong land", "kop limited", "ksh holdings",
      "lum chang", "oue limited", "oxley holdings",
      "pan hong holdings", "propnex", "sing holdings",
      "singapore land", "sinjia land", "tiong seng",
      "tuan sing", "uol group", "united overseas australia",
      "wing tai", "yanlord land", "yoma strategic",
      "hotel royal", "shangri-la asia",
      "far east group", "goodland group",
      "hong lai huat", "first sponsor",
      "pacific century regional",
      "regal international", "renaissance united",
      "hl global enterprises", "metro holdings",
      "hafary holdings", "kori holdings",
      "lincotrade", "anan international",
      "thakral corporation", "southern packaging group",
      "figtree holdings", "ascent bridge",
      "capital world", "anchun international",
      "aspen group", "aspen (group)",  # ASPEN (GROUP) HOLDINGS — parens need explicit match
      "astaka holdings",
      "forise international", "keong hong",
      "koh brothers group", "koh brothers eco",
      "king wan corporation",
      "gallant venture",
      "gsh corporation",    # was typo "gsah corporation"
      "hgh holdings",       # was typo "hgm holdings"
      "hor kew corporation",
      "huationg global",
      "brc asia",
      "ping an real estate",
      "the assembly place",
      "the place holdings",
      "attika group",       # Attika Group — construction/property
      ], "proptech"),

    # ICT / SaaS / Tech — software, IT services, telco, semiconductors.
    # Media/entertainment companies (mm2, spackman, vividthree) are excluded.
    (["technology", "tech ", "software", "saas", "cloud", "cybersecurity",
      "it service", "data centre", "datacenter", "data center",
      "systems auto", "nanofilm",
      "addvalue", "creative technol", "azeus", "netlink", "datapulse",
      "powermatic data", "starhub", "singtel", "telechoice",
      "ifast", "sincloud", "sinocloud",
      "tencent", "alibaba", "xiaomi", "meituan",
      "sea ltd", "grab hold", "trek 2000", "aztech",
      "cse global", "serial system",
      "revez", "accrelist", "ipc corp",
      "a-smart", "global testing", "pc partner",
      "info-tech", "china kunda",
      # Additional SGX tech/ICT companies
      "17live", "audience analytics", "captii",
      "comba telecom", "digilife", "global invacom",
      "ips securex", "neratel", "shopper360",
      "oxpay financial", "digilife technologies",
      "boustead singapore",
      "innotek limited",
      "isdn holdings",
      "frencken group",
      "venture corporation",
      "valuetronics", "versalink",
      "multi-chem limited",
      "adventus holdings",
      "nippecraft limited",
      "tye soon ltd",
      "federal int",
      "koyo international",
      "broadway industrial",
      "hoe leong corporation",
      "acesian partners",
      "aedge group",
      "combine will intl",
      "asia enterprises",
      "casa holdings",
      "annaik limited",
      "matex international",
      "amcorp global",
      "amplefield"], "ict_saas"),

    # Media / Entertainment / Leisure — digital media, film, content, gaming.
    # Mapped to retail_ecommerce (closest proxy on SGX for consumer-facing media).
    (["entertainment", "media", "culture", "film", "content",
      "vividthree", "mm2 asia", "spackman", "ghy culture",
      "arion entertainment", "kingsmen creatives",
      "edition ltd", "lifebrandz", "ghx",
      # Additional SGX media/leisure/tourism/F&B companies
      "genting singapore", "straco corporation",
      "sim leisure", "unusual limited",
      "sutl enterprise",
      "beverly jcg", "amos group"], "retail_ecommerce"),

    # Advanced Manufacturing — precision engineering, semicon, aerospace MRO.
    (["precision engineering", "semiconductor", "aerospace", "mro",
      "electronics mfg", "manufacturing",
      "robotics", "pcb ", "wafer", "cleanroom",
      "aem hold", "ums hold", "micro-mechanic", "willas-array",
      "fu yu", "nam lee pressed", "progen", "jep hold", "hg metal",
      "world precision", "brook crompton", "ellipsiz",
      "sunright", "choo chiang", "fuji offset",
      "jubilee industries", "acma ltd", "asian micro",
      "vicplas", "new toyo int", "pne industries",
      "sin heng heavy", "advanced holdings",
      "metech", "singapore tech engineering",
      "miyoshi", "lereno", "advanced systems automation",
      # Additional SGX manufacturing / industrial companies
      "cdw holding", "spindex industries",
      "vibropower corporation", "ykgi limited",
      "tai sin electric", "union steel",
      "river stone", "gp industries",
      "taiwan pacific", "hosen group",
      "es group", "gs holdings",
      "intraco limited", "ausgroup",
      "asti holdings", "jadason enterprises",
      "nsl ltd", "nsb group",
      "avarga", "samurai 2k aerosol",
      "southern packaging",
      "tat seng packaging",
      "cfm holdings", "lcs group",
      "mun siong",
      "wongt fong industries", "wong fong industries",
      "tsh corporation",
      "shs holdings",
      "far east holding"], "advanced_manufacturing"),

    # Fintech / Financial Services — banks, insurers, asset managers, exchanges.
    # Narrow keywords: "finance" and "financial" are common words so we use
    # them only in combination with company-specific names above generic terms.
    (["banking", "fintech", "insurtech", "insurer", "neobank",
      "wealthtech", "robo-advis", "digital payment",
      "dbs group", "united overseas bank", "oversea-chinese banking",
      "ocbc", "uob ", "hsbc", "bank of china",
      "great eastern", "prudential plc",
      "sing investments & finance", "singapura finance",
      "moneymax financial", "luminor financial",
      "hotung investment", "net pacific fin",
      "yangzijiang financial", "plato capital",
      "mercurius cap", "lion asiapac",
      "united overseas insurance",
      "uobam", "ifast corp",
      # Additional SGX financial companies
      "singapore exchange", "uob-kay hian",
      "hong leong finance", "ifs capital",
      "valuemax group", "aspial corporation",
      "aspial lifestyle", "amtd idea",
      "global investments", "credit bureau asia",
      "tih limited", "myp ltd",
      "chuan hup holdings",
      "capallianz",
      "polaris ltd",
      "cortina holdings",
      "eurosports global",
      "pacific century",
      "oneapex limited",
      "asia-pacific strategic"], "fintech"),

    # Retail / E-commerce — physical retail, F&B, consumer goods, food producers.
    # Place BEFORE the natural-resources rule so food companies (agri, fruit, food)
    # are captured here rather than being mis-routed to clean_energy.
    (["retail", "e-commerce", "marketplace", "shopping", "fmcg",
      "fashion", "grocery", "restaurant", "food ind", "food grp",
      "food hold", "food innov", "food industry",
      "f&b", "supermarket", "department store", "food hall",
      "old chang kee", "kimly", "japan foods", "tung lok",
      "sakae", "no signboard", "yeo hiap seng",
      "thai beverage", "delfi", "mewah",
      "fj benjamin", "cp all",
      "st group food", "envictus",
      "nutryfarm", "helens", "ossia intl",
      "the hour glass", "ever glory",
      "abundance international", "lifebrandz",
      "sino grandness", "zhongxin fruit",
      "china shenshan", "bumitama agri",
      "halcyon agri", "indofood agri",
      "golden agri", "china sunsine",
      "china sunsine chem",
      # Additional SGX F&B, consumer goods, and retail companies
      "abr holdings", "del monte pacific", "duty free",
      "food empire", "fraser and neave",
      "jumbo group", "katrina group", "khong guan",
      "noel gifts", "oceanus group", "qaf limited",
      "sheng siong", "soup holdings", "sunmoon food",
      "yhi international", "joyas international",
      "taka jewellery", "cortina hold",
      "don agro", "first resources",
      "jb foods", "qian hu corporation",
      "sri trang agro", "olam group",
      "wilmar international", "f j benjamin",
      "tan chong international",
      "abundance international",
      "emperor inc", "emperador inc",
      "sen yue holdings", "hosen group",
      "avarga ltd", "ossia international",
      "yhiana international",
      "gallant venture",
      "sitra holdings",
      "pavillon holdings",
      "travelite holdings"], "retail_ecommerce"),

    # EdTech / Education
    (["education", "learning", "training", "school", "university",
      "institute", "edtech", "skillsfuture", "tutor",
      "singapore institute", "koda ltd"], "edtech"),

    # Professional Services — staffing, security, advisory, compliance.
    (["consulting", "advisory", "legal services", "recruitment",
      "accounting", "audit", "outsourcing",
      "zico hold", "compliance",
      "lms compliance", "professional service",
      "vicom",
      # Additional SGX professional services companies
      "hrnetgroup", "secura group",
      "credit bureau",
      "acesian partners",
      "lsy corporation",
      "ly corporation",
      "vcplus limited",
      "disa limited",
      "audience analytics",
      "sien group"], "professional_services"),

    # Conglomerates with known primary business — map to best-fit vertical.
    # Keppel Corporation: energy infrastructure and offshore.
    # Jardine groups: diversified retail/property — proptech proxy.
    # Hong Leong Asia: diversified manufacturing/industrials.
    # Yongmao Holdings: tower cranes — construction equipment.
    (["keppel corporation"], "clean_energy"),
    (["jardine cycle", "jardine matheson"], "retail_ecommerce"),
    (["hong leong asia", "yongmao holdings",
      "sapphire corporation",
      "nordic group limited"], "advanced_manufacturing"),

    # Automotive / transport — auto distributors, tyres, vehicle services.
    (["automotive", "automobile", "motor", "vehicle",
      "tyres", "tires", "tyre",
      "trans-china automotive",
      "stamford tyres",
      "yhi international",
      "tan chong international"], "retail_ecommerce"),

    # Singapore blue-chips without sector data — assign from known business.
    (["singapore airlines"], "logistics"),
    (["singapore telecommunications", "singtel"], "ict_saas"),

    # Property/investment holding companies with no other keyword signal.
    # These are smaller or obscure SGX names — proptech is the closest vertical.
    (["psc corporation",
      "vibrant group",
      "ls 2 holdings",
      "oel holdings",
      "oio holdings",
      "ots holdings",
      "new wave holdings",
      "mdr limited",
      "megroup ltd",
      "shen yao",
      "usp group",
      "v2y corporation",
      "zixin group",
      "sunrise shares",
      "serial achieva",
      "shanaya",
      "sevens atelier",
      "vins holdings",
      "vin's holdings",
      "jasper investments",
      "pasture holdings",
      "prospercap",
      "international cement",
      "infinity development",
      "hs optimus"], "proptech"),

    # Tech-adjacent EV/auto stocks listed on SGX.
    (["nio inc", "byd company",
      "airports of thailand"], "ict_saas"),

    # Small resources/agri holding companies — clean_energy proxy.
    (["alset international",
      "asiatic group",
      "abundante",
      "annica holdings",
      "fuxing china",
      "gccp resources",
      "china international hldgs",
      # NOTE: "aspen group holdings" removed — Aspen Group is a property developer (→ proptech)
      "ktmg limited",
      "soon lian holdings",
      "jawala inc",          # Jawala Inc — timber plantation (Sabah forestry)
      ], "clean_energy"),

    # Rubber / industrial materials — advanced_manufacturing proxy.
    (["grp ltd", "grp limited", "rubber"], "advanced_manufacturing"),

    # Events, exhibitions, décor — professional_services proxy.
    (["dezign format"], "professional_services"),

    # F&B / consumer goods — specific companies not caught by generic keywords.
    (["incredible holdings",   # food trading
      "tsh resources",         # TSH Resources Berhad — palm oil/cocoa
      "9r limited"], "retail_ecommerce"),

    # OEL (Holdings) parentheses fix — property/investment holding.
    (["oel (holdings)", "oel holdings"], "proptech"),
]

# ---------------------------------------------------------------------------
# FX rates — simple hardcoded approximations for SGD conversion
# ---------------------------------------------------------------------------

_FX_TO_SGD: dict[str, float] = {
    "SGD": 1.0,
    "USD": 1.35,
    "HKD": 0.17,
    "MYR": 0.30,
    "AUD": 0.88,
}


def _to_sgd(value: float | None, currency: str) -> float | None:
    """Convert a monetary value to SGD using hardcoded FX rates.

    Unknown currencies fall back to 1:1 (SGD assumed).
    Returns None when value is None.
    """
    if value is None:
        return None
    rate = _FX_TO_SGD.get(currency.upper(), 1.0)
    return value * rate


# ---------------------------------------------------------------------------
# Listing type mapper
# ---------------------------------------------------------------------------

_LISTING_TYPE_MAP: dict[str, CompanyListingType] = {
    "Real Estate Investment Trust": CompanyListingType.REIT,
    "Business Trust": CompanyListingType.BUSINESS_TRUST,
    "ETF": CompanyListingType.ETF,
    "Preferred Stock": CompanyListingType.PREFERRED,
}


def _map_listing_type(raw_type: str) -> CompanyListingType:
    """Map an EODHD instrument type string to CompanyListingType enum."""
    return _LISTING_TYPE_MAP.get(raw_type, CompanyListingType.COMMON_STOCK)


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------


class FinancialIntelligenceSync:
    """Syncs EODHD financial data into the market intelligence database.

    Called by APScheduler jobs:
      - Weekly: sync_exchange_roster("SG") — refresh full SGX company list
      - Daily: sync_financial_snapshots(limit=50) — update top companies by market cap
      - On demand: sync_company(ticker, exchange) — single company refresh

    Rate limiting: EODHD has request limits. We add a configurable delay
    between individual fundamentals calls (default 0.5s).
    """

    REQUEST_DELAY_SECONDS = 0.5  # polite delay between EODHD API calls

    def __init__(
        self,
        session: AsyncSession,
        eodhd_client: EODHDClient | None = None,
        request_delay: float = REQUEST_DELAY_SECONDS,
    ) -> None:
        self._session = session
        self._client = eodhd_client or get_eodhd_client()
        self.request_delay = request_delay
        self._engine = FinancialBenchmarkEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_exchange_roster(self, exchange: str = "SG") -> dict[str, int]:
        """Sync the full symbol list for an exchange into ListedCompany table.

        Also upserts the OVERSEAS_LISTED_SG_COMPANIES curated list.

        Returns:
            {"created": N, "updated": N, "skipped": N}
        """
        counts: dict[str, int] = {"created": 0, "updated": 0, "skipped": 0}

        symbols = await self._client.get_exchange_symbol_list(exchange)
        logger.info(
            "sync_exchange_roster_start",
            exchange=exchange,
            symbol_count=len(symbols),
        )

        for i, symbol in enumerate(symbols):
            if not symbol.code:
                counts["skipped"] += 1
                continue

            listing_type = _map_listing_type(symbol.type)
            created = await self._upsert_listed_company(
                ticker=symbol.code,
                exchange=exchange,
                name=symbol.name,
                currency=symbol.currency,
                listing_type=listing_type,
                isin=symbol.isin,
                is_sg_incorporated=True,
            )
            if created:
                counts["created"] += 1
            else:
                counts["updated"] += 1

            if (i + 1) % 50 == 0:
                logger.info(
                    "sync_exchange_roster_progress",
                    exchange=exchange,
                    processed=i + 1,
                    total=len(symbols),
                )

        await self._session.flush()

        # Upsert curated overseas-listed SG companies
        for entry in OVERSEAS_LISTED_SG_COMPANIES:
            created = await self._upsert_listed_company(
                ticker=entry["ticker"],
                exchange=entry["exchange"],
                name=entry["name"],
                currency=None,
                listing_type=CompanyListingType.COMMON_STOCK,
                isin=None,
                is_sg_incorporated=True,
                vertical_slug=entry.get("vertical_slug"),
            )
            if created:
                counts["created"] += 1
            else:
                counts["updated"] += 1

        await self._session.flush()

        logger.info("sync_exchange_roster_done", exchange=exchange, **counts)
        return counts

    async def sync_sp500_roster(self) -> dict[str, int]:
        """Sync S&P 500 constituents into listed_companies.

        Uses EODHD index components (no per-company API calls needed).
        GICS sector/industry from the response feeds vertical assignment.

        Returns:
            {"created": N, "updated": N, "skipped": N}
        """
        counts: dict[str, int] = {"created": 0, "updated": 0, "skipped": 0}

        constituents = await self._client.get_sp500_constituents()

        for constituent in constituents:
            code = constituent.get("code", "")
            if not code:
                counts["skipped"] += 1
                continue

            name = constituent.get("name", "")
            industry = constituent.get("industry", "")
            sector = constituent.get("sector", "")

            # Resolve vertical: Level 1 — GICS industry substring match
            vertical_slug: str | None = None
            if industry:
                industry_lower = industry.lower()
                for substring, slug in _GICS_INDUSTRY_MAP:
                    if substring in industry_lower:
                        vertical_slug = slug
                        break

            # Level 2 — sector-level fallback
            if vertical_slug is None and sector:
                vertical_slug = _SP500_SECTOR_MAP.get(sector)

            created = await self._upsert_listed_company(
                ticker=code,
                exchange="US",
                name=name,
                currency="USD",
                listing_type=CompanyListingType.COMMON_STOCK,
                isin=None,
                is_sg_incorporated=False,
                vertical_slug=vertical_slug,
                gics_sector=sector or None,
                gics_industry=industry or None,
            )
            if created:
                counts["created"] += 1
            else:
                counts["updated"] += 1

        await self._session.flush()

        logger.info("sync_sp500_roster_done", **counts)
        return counts

    async def sync_sp500_financials(self, limit: int = 503) -> dict[str, int]:
        """Fetch full fundamentals for S&P 500 companies.

        Queries listed_companies where exchange='US' and is_sg_incorporated=False,
        then calls sync_company() for each to populate financial snapshots,
        executives, and market-cap fields used by compute_and_store_benchmarks().

        Args:
            limit: Max companies to process (default: all 503 S&P 500 members).

        Returns:
            {"synced": N, "failed": N}
        """
        result = await self._session.execute(
            select(ListedCompany)
            .where(
                ListedCompany.exchange == "US",
                ListedCompany.is_sg_incorporated == False,  # noqa: E712
            )
            .order_by(ListedCompany.name)
            .limit(limit)
        )
        companies = result.scalars().all()

        counts: dict[str, int] = {"synced": 0, "failed": 0, "skipped": 0}
        total = len(companies)
        # Strip timezone so comparison works against SQLite's naive datetimes.
        cutoff = (datetime.now(UTC) - timedelta(days=7)).replace(tzinfo=None)

        logger.info("sync_sp500_financials_start", total=total)

        for i, company in enumerate(companies):
            last_synced = company.last_synced_at
            if last_synced is not None:
                last_synced = last_synced.replace(tzinfo=None)
            if last_synced and last_synced > cutoff:
                counts["skipped"] += 1
                continue

            try:
                success = await self.sync_company(company.ticker, company.exchange)
                if success:
                    counts["synced"] += 1
                else:
                    counts["failed"] += 1
            except Exception:
                logger.exception(
                    "sync_sp500_financials_error",
                    ticker=company.ticker,
                )
                counts["failed"] += 1

            await asyncio.sleep(self.request_delay)

            if (i + 1) % 50 == 0:
                logger.info(
                    "sync_sp500_financials_progress",
                    processed=i + 1,
                    total=total,
                    **counts,
                )
                await self._session.commit()

        logger.info("sync_sp500_financials_done", total=total, **counts)
        return counts

    async def sync_exchange_financials(
        self,
        exchange: str,
        *,
        is_active: bool = True,
        limit: int = 1000,
    ) -> dict[str, int]:
        """Fetch full fundamentals for all listed companies on a given exchange.

        Queries listed_companies by exchange and is_active, then calls
        sync_company() for each.  Skips companies that already have a
        last_synced_at within the last 7 days to avoid redundant API calls.

        Args:
            exchange: Exchange code (e.g. "SG", "US").
            is_active: Filter to active listings only (default True).
            limit: Max companies to process (default 1000).

        Returns:
            {"synced": N, "failed": N, "skipped": N}
        """
        result = await self._session.execute(
            select(ListedCompany)
            .where(
                ListedCompany.exchange == exchange,
                ListedCompany.is_active == is_active,  # noqa: E712
            )
            .order_by(ListedCompany.name)
            .limit(limit)
        )
        companies = result.scalars().all()

        counts: dict[str, int] = {"synced": 0, "failed": 0, "skipped": 0}
        total = len(companies)
        # Strip timezone so comparison works against SQLite's naive datetimes.
        cutoff = (datetime.now(UTC) - timedelta(days=7)).replace(tzinfo=None)

        logger.info("sync_exchange_financials_start", exchange=exchange, total=total)

        for i, company in enumerate(companies):
            # Skip recently synced companies
            last_synced = company.last_synced_at
            if last_synced is not None:
                last_synced = last_synced.replace(tzinfo=None)
            if last_synced and last_synced > cutoff:
                counts["skipped"] += 1
                continue

            try:
                success = await self.sync_company(company.ticker, company.exchange)
                if success:
                    counts["synced"] += 1
                else:
                    counts["failed"] += 1
            except Exception:
                logger.exception(
                    "sync_exchange_financials_error",
                    exchange=exchange,
                    ticker=company.ticker,
                )
                counts["failed"] += 1

            await asyncio.sleep(self.request_delay)

            if (i + 1) % 50 == 0:
                logger.info(
                    "sync_exchange_financials_progress",
                    exchange=exchange,
                    processed=i + 1,
                    total=total,
                    **counts,
                )
                await self._session.commit()

        logger.info("sync_exchange_financials_done", exchange=exchange, total=total, **counts)
        return counts

    async def sync_company(self, ticker: str, exchange: str = "SG") -> bool:
        """Fetch full fundamentals for one company and persist all data.

        Updates: ListedCompany snapshot fields + CompanyFinancialSnapshot rows
        + CompanyExecutive rows.

        Returns True on success, False on failure.
        """
        fundamentals = await self._client.get_full_fundamentals(ticker, exchange)
        if fundamentals is None:
            logger.warning("sync_company_no_data", ticker=ticker, exchange=exchange)
            return False

        currency = fundamentals.currency or "USD"
        fx_rate = _FX_TO_SGD.get(currency.upper(), 1.0)

        # Determine listing type from fundamentals
        listing_type = _map_listing_type(fundamentals.listing_type)

        # Resolve vertical: industry substring → sector fallback → gics_sector
        vertical_id = None
        vertical_slug: str | None = None
        effective_industry = fundamentals.gics_industry or fundamentals.industry or ""
        if effective_industry:
            for substring, slug in _GICS_INDUSTRY_MAP:
                if substring in effective_industry.lower():
                    vertical_slug = slug
                    break
        if vertical_slug is None:
            effective_sector = fundamentals.sector or fundamentals.gics_sector or ""
            if effective_sector:
                vertical_slug = _SP500_SECTOR_MAP.get(effective_sector)
        if vertical_slug is not None:
            vertical_id = await self._resolve_vertical_by_slug(vertical_slug)
        else:
            vertical_id = await self._resolve_vertical_id(fundamentals.gics_sector)

        # Upsert the ListedCompany record with all enriched fields
        result = await self._session.execute(
            select(ListedCompany).where(
                ListedCompany.ticker == ticker,
                ListedCompany.exchange == exchange,
            )
        )
        company = result.scalar_one_or_none()

        if company is None:
            company = ListedCompany(
                ticker=ticker,
                exchange=exchange,
                name=fundamentals.name or ticker,
                listing_type=listing_type,
                currency=currency,
            )
            self._session.add(company)

        # Update General / Highlights fields
        company.name = fundamentals.name or company.name
        company.listing_type = listing_type
        company.currency = currency
        company.description = fundamentals.description
        company.website = fundamentals.website
        company.employees = fundamentals.employees
        company.address = fundamentals.address
        company.gics_sector = fundamentals.gics_sector or fundamentals.sector or company.gics_sector
        company.gics_industry = fundamentals.gics_industry or fundamentals.industry or company.gics_industry
        company.isin = fundamentals.isin
        # Only auto-assign vertical if the company has no existing assignment.
        # This preserves manually curated verticals set by assign_verticals_to_companies().
        if vertical_id is not None and company.vertical_id is None:
            company.vertical_id = vertical_id
        company.last_synced_at = datetime.now(UTC)

        # Snapshot financials — convert to SGD
        company.market_cap_sgd = _to_sgd(fundamentals.market_cap, currency)
        company.pe_ratio = fundamentals.pe_ratio
        company.ev_ebitda = fundamentals.ev_ebitda
        company.revenue_ttm_sgd = _to_sgd(fundamentals.revenue_ttm, currency)
        company.gross_margin = fundamentals.gross_margin_ttm
        company.profit_margin = fundamentals.profit_margin_ttm
        company.roe = fundamentals.return_on_equity_ttm
        company.dividend_yield = fundamentals.dividend_yield

        # ESG Scores
        company.esg_score = fundamentals.esg_score
        company.esg_environment = fundamentals.esg_environment
        company.esg_social = fundamentals.esg_social
        company.esg_governance = fundamentals.esg_governance

        # Analyst Consensus
        company.analyst_rating = fundamentals.analyst_rating
        company.analyst_target_price = fundamentals.analyst_target_price
        if fundamentals.analyst_strong_buy is not None:
            company.analyst_count = (
                (fundamentals.analyst_strong_buy or 0)
                + (fundamentals.analyst_buy or 0)
                + (fundamentals.analyst_hold or 0)
                + (fundamentals.analyst_sell or 0)
                + (fundamentals.analyst_strong_sell or 0)
            )

        await self._session.flush()  # ensure company.id is set

        await asyncio.sleep(self.request_delay)

        # Persist CompanyFinancialSnapshot rows
        await self._persist_financial_snapshots(company, fundamentals, fx_rate, currency)

        await asyncio.sleep(self.request_delay)

        # Persist CompanyExecutive rows
        officers = await self._client.get_executives(ticker, exchange)
        await self._persist_executives(company, officers)

        await self._session.flush()

        logger.info("sync_company_done", ticker=ticker, exchange=exchange)
        return True

    async def sync_financial_snapshots(self, limit: int = 50) -> dict[str, int]:
        """Sync full financials for top N companies by market cap.

        Run daily to keep high-value companies fresh. Skips companies
        synced within the last 7 days and commits every 50 companies
        to protect against SIGTERM kills.

        Returns:
            {"synced": N, "skipped": N, "failed": N}
        """
        result = await self._session.execute(
            select(ListedCompany)
            .order_by(ListedCompany.market_cap_sgd.desc().nullslast())
            .limit(limit)
        )
        companies = result.scalars().all()

        counts: dict[str, int] = {"synced": 0, "skipped": 0, "failed": 0}
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)

        logger.info("sync_financial_snapshots_start", total=len(companies))

        for idx, company in enumerate(companies, 1):
            # Skip recently synced companies (7-day window)
            # Strip tzinfo for consistent naive-vs-naive comparison
            # (SQLite returns naive, PostgreSQL may return tz-aware)
            last_synced = company.last_synced_at
            if last_synced is not None:
                last_synced = last_synced.replace(tzinfo=None)
            if (
                last_synced is not None
                and last_synced > cutoff
            ):
                counts["skipped"] += 1
                continue

            try:
                success = await self.sync_company(company.ticker, company.exchange)
                if success:
                    counts["synced"] += 1
                else:
                    counts["failed"] += 1
            except Exception:
                logger.exception(
                    "sync_financial_snapshots_error",
                    ticker=company.ticker,
                    exchange=company.exchange,
                )
                counts["failed"] += 1

            # Periodic commit every 50 companies to protect against SIGTERM
            if idx % 50 == 0:
                await self._session.commit()
                logger.info("sync_financial_snapshots_checkpoint", processed=idx)

            await asyncio.sleep(self.request_delay)

        logger.info("sync_financial_snapshots_done", **counts)
        return counts

    async def compute_and_store_benchmarks(
        self, vertical_slug: str, period_label: str
    ) -> bool:
        """Recompute VerticalBenchmark for a vertical+period from stored snapshots.

        Returns True if benchmark was computed with sufficient data (>= 3 companies).
        """
        # Look up the vertical
        vertical_result = await self._session.execute(
            select(MarketVertical).where(MarketVertical.slug == vertical_slug)
        )
        vertical = vertical_result.scalar_one_or_none()
        if vertical is None:
            logger.warning("compute_benchmarks_no_vertical", slug=vertical_slug)
            return False

        # Determine period_type from label format
        period_type = (
            FinancialPeriodType.QUARTERLY
            if "-Q" in period_label
            else FinancialPeriodType.ANNUAL
        )

        # Query all snapshots for this vertical + period_label, joined to ListedCompany.
        # For quarterly labels ("2024-Q3"), filter by year + quarter month range
        # to avoid mixing Q1-Q4 data together.
        date_filter = _period_label_to_date_filter(period_label)
        snapshots_result = await self._session.execute(
            select(CompanyFinancialSnapshot, ListedCompany)
            .join(ListedCompany, CompanyFinancialSnapshot.company_id == ListedCompany.id)
            .where(
                ListedCompany.vertical_id == vertical.id,
                CompanyFinancialSnapshot.period_type == period_type,
                *date_filter,
            )
        )
        rows = snapshots_result.all()

        if not rows:
            logger.info(
                "compute_benchmarks_no_snapshots",
                slug=vertical_slug,
                period=period_label,
            )
            return False

        # Map to CompanyMetrics
        is_reit_vertical = vertical.is_reit_vertical
        company_metrics: list[CompanyMetrics] = []
        for snapshot, listed in rows:
            company_metrics.append(
                CompanyMetrics(
                    ticker=listed.ticker,
                    name=listed.name,
                    exchange=listed.exchange,
                    is_reit=not is_reit_vertical
                    and listed.listing_type == CompanyListingType.REIT,
                    revenue_growth_yoy=snapshot.revenue_growth_yoy,
                    gross_margin=snapshot.gross_margin,
                    ebitda_margin=snapshot.ebitda_margin,
                    net_margin=snapshot.net_margin,
                    roe=snapshot.roe,
                    net_debt_ebitda=snapshot.net_debt_ebitda,
                    revenue_ttm_sgd=snapshot.revenue,
                    sga_to_revenue=snapshot.sga_to_revenue,
                    rnd_to_revenue=snapshot.rnd_to_revenue,
                    operating_margin=snapshot.operating_margin,
                    capex_to_revenue=(
                        abs(snapshot.capex) / snapshot.revenue
                        if snapshot.capex is not None and snapshot.revenue and snapshot.revenue > 0
                        else None
                    ),
                )
            )

        benchmark = self._engine.compute_benchmark(
            vertical_slug=vertical_slug,
            period_label=period_label,
            period_type=period_type.value,
            companies=company_metrics,
        )

        if benchmark.company_count < 3:
            logger.info(
                "compute_benchmarks_insufficient_data",
                slug=vertical_slug,
                period=period_label,
                company_count=benchmark.company_count,
            )
            return False

        # Upsert VerticalBenchmark row
        vb_result = await self._session.execute(
            select(VerticalBenchmark).where(
                VerticalBenchmark.vertical_id == vertical.id,
                VerticalBenchmark.period_type == period_type,
                VerticalBenchmark.period_label == period_label,
            )
        )
        vb = vb_result.scalar_one_or_none()

        bm_dict = benchmark.to_vertical_benchmark_dict()

        if vb is None:
            vb = VerticalBenchmark(
                vertical_id=vertical.id,
                period_type=period_type,
                period_label=period_label,
            )
            self._session.add(vb)

        vb.company_count = bm_dict["company_count"]
        vb.revenue_growth_yoy = bm_dict["revenue_growth_yoy"]
        vb.gross_margin = bm_dict["gross_margin"]
        vb.ebitda_margin = bm_dict["ebitda_margin"]
        vb.net_margin = bm_dict["net_margin"]
        vb.roe = bm_dict["roe"]
        vb.net_debt_ebitda = bm_dict["net_debt_ebitda"]
        vb.revenue_ttm_sgd = bm_dict["revenue_ttm_sgd"]
        vb.sga_to_revenue = bm_dict["sga_to_revenue"]
        vb.rnd_to_revenue = bm_dict["rnd_to_revenue"]
        vb.operating_margin_dist = bm_dict["operating_margin"]
        vb.capex_to_revenue = bm_dict["capex_to_revenue"]
        vb.leaders = bm_dict["leaders"]
        vb.laggards = bm_dict["laggards"]
        vb.computed_at = datetime.now(UTC)

        await self._session.flush()

        logger.info(
            "compute_benchmarks_done",
            slug=vertical_slug,
            period=period_label,
            company_count=benchmark.company_count,
        )
        return True

    # Keywords indicating a listing is a derived security (not an operating company)
    _DERIVED_SECURITY_KEYWORDS: ClassVar[list[str]] = [
        " pref", "preference", " sdr ", "sdr 1", " warrant", " rights",
        " notes", "structured product", "etf ", " trust cert",
    ]

    async def deactivate_stub_listings(self) -> dict[str, int]:
        """Mark stub and derived-security listings as is_active=False.

        A listing is a stub if its name is identical to its ticker (EODHD
        could not resolve a real company name).  Derived securities (preference
        shares, SDRs, warrants, rights) are identified by keywords in the name.

        Safe to run multiple times — only modifies rows where is_active=True.
        Returns {"deactivated": N, "kept": N}.
        """
        result = await self._session.execute(
            select(ListedCompany).where(ListedCompany.is_active == True)  # noqa: E712
        )
        companies = result.scalars().all()

        deactivated = 0
        kept = 0
        for company in companies:
            name_lower = company.name.lower()
            is_stub = company.name == company.ticker
            is_derived = any(
                kw in name_lower for kw in self._DERIVED_SECURITY_KEYWORDS
            )
            if is_stub or is_derived:
                company.is_active = False
                deactivated += 1
            else:
                kept += 1

        await self._session.flush()
        logger.info(
            "deactivate_stubs_done",
            deactivated=deactivated,
            kept=kept,
        )
        return {"deactivated": deactivated, "kept": kept}

    async def assign_verticals_to_companies(self) -> dict[str, int]:
        """Assign vertical_id to listed_companies using a three-level lookup.

        Level 1 (primary):   REIT listing_type → reits vertical
        Level 2 (secondary): gics_industry substring match via _GICS_INDUSTRY_MAP
        Level 3 (tertiary):  gics_sector exact match (unambiguous sectors only)
        Level 4 (fallback):  company name keyword match via _NAME_KEYWORD_RULES

        Safe to run multiple times — only touches rows where vertical_id IS NULL.
        Returns {"assigned": N, "no_match": N}
        """
        import uuid as _uuid

        vertical_rows = (
            await self._session.execute(
                select(
                    MarketVertical.id,
                    MarketVertical.slug,
                    MarketVertical.gics_sectors,
                    MarketVertical.is_reit_vertical,
                )
            )
        ).all()

        # Build slug → UUID lookup (all verticals)
        slug_to_id: dict[str, _uuid.UUID] = {}
        # Map: gics_sector (lower) → vertical UUID — skip ambiguous multi-vertical sectors
        _AMBIGUOUS_SECTORS = {"industrials", "real estate"}
        gics_sector_map: dict[str, _uuid.UUID] = {}
        reit_vertical_id: _uuid.UUID | None = None

        for row in vertical_rows:
            vid: _uuid.UUID = row.id
            slug_to_id[row.slug] = vid
            if row.is_reit_vertical:
                reit_vertical_id = vid
            for gs in (row.gics_sectors or []):
                gs_lower = gs.lower()
                if gs_lower not in _AMBIGUOUS_SECTORS:
                    # Only register unambiguous sectors (1:1 sector→vertical)
                    gics_sector_map[gs_lower] = vid

        # Get all companies that have not yet been assigned a vertical
        companies = (
            await self._session.execute(
                select(ListedCompany).where(ListedCompany.vertical_id.is_(None))
            )
        ).scalars().all()

        assigned = 0
        no_match = 0

        for company in companies:
            vertical_id: _uuid.UUID | None = None

            # Level 1: REIT listing type → reits vertical
            if company.listing_type == CompanyListingType.REIT and reit_vertical_id:
                vertical_id = reit_vertical_id

            # Level 2: gics_industry substring match (most specific GICS data)
            if not vertical_id and company.gics_industry:
                industry_lower = company.gics_industry.lower()
                for substring, slug in _GICS_INDUSTRY_MAP:
                    if substring in industry_lower:
                        vertical_id = slug_to_id.get(slug)
                        break

            # Level 3: gics_sector exact match (unambiguous sectors only)
            if not vertical_id and company.gics_sector:
                vertical_id = gics_sector_map.get(company.gics_sector.lower())

            # Level 4: company name keyword match (last resort when GICS absent)
            if not vertical_id and company.name:
                name_lower = company.name.lower()
                for keywords, slug in _NAME_KEYWORD_RULES:
                    if any(kw in name_lower for kw in keywords):
                        vertical_id = slug_to_id.get(slug)
                        break

            if vertical_id:
                company.vertical_id = vertical_id
                assigned += 1
            else:
                no_match += 1

        await self._session.flush()
        return {"assigned": assigned, "no_match": no_match}

    async def upgrade_to_gics_assignment(self) -> dict[str, int]:
        """Re-assign companies that have gics_industry data but were previously
        assigned via name-keyword matching. GICS data is more accurate.

        Processes all companies where vertical_id IS NOT NULL and
        gics_industry IS NOT NULL. If the GICS industry maps to a different
        vertical, the assignment is upgraded.

        Returns {"upgraded": N, "unchanged": N}
        """
        companies = (
            await self._session.execute(
                select(ListedCompany).where(
                    ListedCompany.vertical_id.isnot(None),
                    ListedCompany.gics_industry.isnot(None),
                )
            )
        ).scalars().all()

        # Build vertical_id_by_slug lookup
        vertical_rows = (
            await self._session.execute(
                select(MarketVertical.id, MarketVertical.slug)
            )
        ).all()
        vertical_id_by_slug = {row.slug: row.id for row in vertical_rows}

        upgraded = 0
        unchanged = 0

        for company in companies:
            # Try GICS industry match (Level 2 — more accurate than name keywords)
            gics_slug = None
            industry_lower = company.gics_industry.lower()
            for substring, slug in _GICS_INDUSTRY_MAP:
                if substring in industry_lower:
                    gics_slug = slug
                    break

            if not gics_slug:
                unchanged += 1
                continue

            new_vertical_id = vertical_id_by_slug.get(gics_slug)
            if new_vertical_id and new_vertical_id != company.vertical_id:
                company.vertical_id = new_vertical_id
                upgraded += 1
            else:
                unchanged += 1

        await self._session.flush()
        return {"upgraded": upgraded, "unchanged": unchanged}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _upsert_listed_company(
        self,
        ticker: str,
        exchange: str,
        name: str,
        currency: str | None,
        listing_type: CompanyListingType,
        isin: str | None,
        is_sg_incorporated: bool,
        vertical_slug: str | None = None,
        gics_sector: str | None = None,
        gics_industry: str | None = None,
    ) -> bool:
        """Insert or update a ListedCompany row.

        Returns True if the row was newly created, False if updated.
        """
        result = await self._session.execute(
            select(ListedCompany).where(
                ListedCompany.ticker == ticker,
                ListedCompany.exchange == exchange,
            )
        )
        existing = result.scalar_one_or_none()

        # Resolve vertical if a slug is provided
        vertical_id = None
        if vertical_slug:
            vertical_id = await self._resolve_vertical_by_slug(vertical_slug)

        if existing is None:
            company = ListedCompany(
                ticker=ticker,
                exchange=exchange,
                name=name,
                currency=currency or "SGD",
                listing_type=listing_type,
                isin=isin,
                is_sg_incorporated=is_sg_incorporated,
                vertical_id=vertical_id,
                gics_sector=gics_sector,
                gics_industry=gics_industry,
            )
            self._session.add(company)
            return True

        # Update mutable fields
        existing.name = name
        if currency:
            existing.currency = currency
        existing.listing_type = listing_type
        if isin:
            existing.isin = isin
        if vertical_id is not None and existing.vertical_id is None:
            existing.vertical_id = vertical_id
        if gics_sector:
            existing.gics_sector = gics_sector
        if gics_industry:
            existing.gics_industry = gics_industry
        return False

    async def _resolve_vertical_id(self, gics_sector: str | None) -> Any | None:
        """Find the MarketVertical.id whose gics_sectors JSON contains gics_sector."""
        if not gics_sector:
            return None
        result = await self._session.execute(select(MarketVertical))
        verticals = result.scalars().all()
        for vertical in verticals:
            sectors: list[str] = vertical.gics_sectors or []
            if gics_sector in sectors:
                return vertical.id
        return None

    async def _resolve_vertical_by_slug(self, slug: str) -> Any | None:
        """Return the id for a MarketVertical by slug, or None."""
        result = await self._session.execute(
            select(MarketVertical).where(MarketVertical.slug == slug)
        )
        vertical = result.scalar_one_or_none()
        return vertical.id if vertical else None

    async def _persist_financial_snapshots(
        self,
        company: ListedCompany,
        fundamentals: Any,
        fx_rate: float,
        currency: str,
    ) -> None:
        """Merge income/balance/cashflow rows into CompanyFinancialSnapshot rows.

        Each row is keyed by (company_id, period_type, period_end_date).
        Revenue growth YoY is computed by comparing periods within the batch.
        """
        for period_type, income_rows, balance_rows, cashflow_rows in [
            (
                FinancialPeriodType.ANNUAL,
                fundamentals.annual_income,
                fundamentals.annual_balance,
                fundamentals.annual_cashflow,
            ),
            (
                FinancialPeriodType.QUARTERLY,
                fundamentals.quarterly_income,
                fundamentals.quarterly_balance,
                fundamentals.quarterly_cashflow,
            ),
        ]:
            # Index balance and cashflow rows by date for O(1) lookup
            balance_by_date = {r.date: r for r in balance_rows}
            cashflow_by_date = {r.date: r for r in cashflow_rows}

            # Sort income rows newest-first so we can compute revenue_growth_yoy
            sorted_income = sorted(income_rows, key=lambda r: r.date, reverse=True)

            # Build revenue map by date for YoY growth calculation
            revenue_by_date: dict[str, float | None] = {
                r.date: r.total_revenue for r in sorted_income
            }

            for income_row in sorted_income:
                date_key = income_row.date
                balance_row = balance_by_date.get(date_key)
                cashflow_row = cashflow_by_date.get(date_key)

                revenue = _apply_fx(income_row.total_revenue, fx_rate)
                gross_profit = _apply_fx(income_row.gross_profit, fx_rate)
                ebitda = _apply_fx(income_row.ebitda, fx_rate)
                ebit = _apply_fx(income_row.ebit, fx_rate)
                net_income = _apply_fx(income_row.net_income, fx_rate)
                eps = income_row.diluted_eps  # per-share — no FX adjustment

                total_assets = _apply_fx(
                    balance_row.total_assets if balance_row else None, fx_rate
                )
                total_equity = _apply_fx(
                    balance_row.total_equity if balance_row else None, fx_rate
                )
                total_debt = _apply_fx(
                    balance_row.short_long_term_debt_total if balance_row else None,
                    fx_rate,
                )
                cash = _apply_fx(
                    balance_row.cash_and_equivalents if balance_row else None, fx_rate
                )

                op_cf = _apply_fx(
                    cashflow_row.total_cash_from_operating_activities
                    if cashflow_row
                    else None,
                    fx_rate,
                )
                capex = _apply_fx(
                    cashflow_row.capital_expenditures if cashflow_row else None,
                    fx_rate,
                )

                # Computed margins
                gross_margin = _safe_div(gross_profit, revenue)
                ebitda_margin = _safe_div(ebitda, revenue)
                net_margin = _safe_div(net_income, revenue)

                # Derived ratios
                roe = _safe_div(net_income, total_equity)
                net_debt = (
                    (total_debt - cash)
                    if total_debt is not None and cash is not None
                    else None
                )
                net_debt_ebitda = _safe_div(net_debt, ebitda)

                # FCF = operating CF + capex (capex is negative in EODHD)
                free_cash_flow = (
                    (op_cf + capex)
                    if op_cf is not None and capex is not None
                    else op_cf
                )

                # Revenue growth YoY — compare to the next-oldest period
                revenue_growth_yoy = _compute_yoy_growth(
                    date_key, revenue_by_date, period_type
                )

                # Upsert the snapshot row
                snap_result = await self._session.execute(
                    select(CompanyFinancialSnapshot).where(
                        CompanyFinancialSnapshot.company_id == company.id,
                        CompanyFinancialSnapshot.period_type == period_type,
                        CompanyFinancialSnapshot.period_end_date == date_key,
                    )
                )
                snap = snap_result.scalar_one_or_none()

                if snap is None:
                    snap = CompanyFinancialSnapshot(
                        company_id=company.id,
                        period_type=period_type,
                        period_end_date=date_key,
                        filing_currency=currency,
                        fx_to_sgd=fx_rate,
                    )
                    self._session.add(snap)

                # Operational detail (FX-adjusted)
                cost_of_revenue = _apply_fx(income_row.cost_of_revenue, fx_rate)
                selling_general_administrative = _apply_fx(
                    income_row.selling_general_administrative, fx_rate
                )
                research_development = _apply_fx(income_row.research_development, fx_rate)
                operating_income = _apply_fx(income_row.operating_income, fx_rate)
                interest_expense = _apply_fx(income_row.interest_expense, fx_rate)
                depreciation_amortization = _apply_fx(
                    income_row.depreciation_amortization, fx_rate
                )

                # Derived ratios from operational detail
                sga_to_revenue = _validated_sga_ratio(
                    reported_sga=selling_general_administrative,
                    gross_profit=gross_profit,
                    operating_income=operating_income,
                    research_development=research_development,
                    revenue=revenue,
                )
                rnd_to_revenue = _safe_div(research_development, revenue)
                operating_margin = _safe_div(operating_income, revenue)

                snap.filing_currency = currency
                snap.fx_to_sgd = fx_rate
                snap.revenue = revenue
                snap.gross_profit = gross_profit
                snap.ebitda = ebitda
                snap.ebit = ebit
                snap.net_income = net_income
                snap.eps = eps
                snap.cost_of_revenue = cost_of_revenue
                snap.selling_general_administrative = selling_general_administrative
                snap.research_development = research_development
                snap.operating_income = operating_income
                snap.interest_expense = interest_expense
                snap.depreciation_amortization = depreciation_amortization
                snap.gross_margin = gross_margin
                snap.ebitda_margin = ebitda_margin
                snap.net_margin = net_margin
                snap.sga_to_revenue = sga_to_revenue
                snap.rnd_to_revenue = rnd_to_revenue
                snap.operating_margin = operating_margin
                snap.revenue_growth_yoy = revenue_growth_yoy
                snap.total_assets = total_assets
                snap.total_equity = total_equity
                snap.total_debt = total_debt
                snap.cash_and_equivalents = cash
                snap.net_debt = net_debt
                snap.roe = roe
                snap.net_debt_ebitda = net_debt_ebitda
                snap.operating_cash_flow = op_cf
                snap.capex = capex
                snap.free_cash_flow = free_cash_flow

    async def _persist_executives(
        self, company: ListedCompany, officers: list[dict[str, Any]]
    ) -> None:
        """Upsert CompanyExecutive rows from EODHD officer dicts."""
        current_year = datetime.now(UTC).year

        for officer in officers:
            name: str = officer.get("Name", "").strip()
            if not name:
                continue

            title: str = officer.get("Title", "").strip()
            title_lower = title.lower()
            year_born_raw = officer.get("YearBorn")
            since_raw = officer.get("Since")

            is_ceo = "chief executive" in title_lower or "ceo" in title_lower
            is_cfo = "financial" in title_lower or "cfo" in title_lower
            is_chair = "chairman" in title_lower or "chair" in title_lower

            age: int | None = None
            if year_born_raw is not None:
                try:
                    year_born = int(year_born_raw)
                    if 1900 < year_born < current_year:
                        age = current_year - year_born
                except (TypeError, ValueError):
                    pass

            since_date: str | None = None
            if since_raw:
                # EODHD may return "YYYY-MM-DD" or just "YYYY"
                since_str = str(since_raw).strip()
                if len(since_str) >= 4 and since_str[:4].isdigit():
                    since_date = since_str[:10]  # truncate to YYYY-MM-DD if longer

            exec_result = await self._session.execute(
                select(CompanyExecutive).where(
                    CompanyExecutive.listed_company_id == company.id,
                    CompanyExecutive.name == name,
                )
            )
            executive = exec_result.scalar_one_or_none()

            if executive is None:
                executive = CompanyExecutive(
                    listed_company_id=company.id,
                    name=name,
                    title=title,
                    is_ceo=is_ceo,
                    is_cfo=is_cfo,
                    is_chair=is_chair,
                    age=age,
                    since_date=since_date,
                )
                self._session.add(executive)
            else:
                executive.title = title
                executive.is_ceo = is_ceo
                executive.is_cfo = is_cfo
                executive.is_chair = is_chair
                executive.age = age
                if since_date:
                    executive.since_date = since_date
                executive.updated_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Module-level pure helpers
# ---------------------------------------------------------------------------


def _apply_fx(value: float | None, fx_rate: float) -> float | None:
    """Multiply value by FX rate; return None when value is None."""
    if value is None:
        return None
    return value * fx_rate


def _period_label_to_date_filter(period_label: str) -> list:
    """Build SQLAlchemy WHERE clauses to match period_end_date for a given label.

    Annual labels (e.g. "2024") → startswith("2024")
    Quarterly labels (e.g. "2024-Q3") → year matches AND month in quarter range.

    Quarter month ranges:
      Q1: 01-03, Q2: 04-06, Q3: 07-09, Q4: 10-12

    Returns a list of SQLAlchemy conditions (to be splatted into .where(*conditions)).
    """
    import re as _re

    m = _re.match(r"^(\d{4})-Q([1-4])$", period_label)
    if m:
        year, quarter = m.group(1), int(m.group(2))
        # Quarter end-month: Q1→03, Q2→06, Q3→09, Q4→12
        # Filter by year prefix AND month in the quarter's 3-month range
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        year_prefix = f"{year}-"
        return [
            CompanyFinancialSnapshot.period_end_date.startswith(year_prefix),
            func.cast(
                func.substr(CompanyFinancialSnapshot.period_end_date, 6, 2),
                sa.Integer,
            ).between(start_month, end_month),
        ]
    # Annual: just match year prefix
    return [
        CompanyFinancialSnapshot.period_end_date.startswith(period_label[:4]),
    ]


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Return numerator / denominator, or None on division by zero / None inputs."""
    if numerator is None or denominator is None or denominator == 0.0:
        return None
    return numerator / denominator


def _validated_sga_ratio(
    reported_sga: float | None,
    gross_profit: float | None,
    operating_income: float | None,
    research_development: float | None,
    revenue: float | None,
) -> float | None:
    """Compute a validated SGA-to-revenue ratio.

    EODHD sometimes reports only part of SGA when companies split
    "Selling" and "General & Administrative" expenses in their filings.
    This detects the anomaly using the income statement identity:

        GP - OpInc >= SGA + R&D

    When reported SGA appears implausibly low (< 40% of the implied
    total), the function derives a corrected value from:

        corrected_sga = GP - OpInc - R&D

    This may slightly overstate SGA for companies with D&A or
    restructuring charges below the gross-profit line, but produces
    a far better signal than the partially-reported value.

    The raw ``selling_general_administrative`` column is never
    modified — only the derived ``sga_to_revenue`` ratio is corrected.

    Returns:
        sga_to_revenue ratio (float) or None if unreliable.
    """
    # Need revenue to produce a ratio
    if revenue is None or revenue <= 0:
        return _safe_div(reported_sga, revenue)

    # Without GP and OpInc we can't cross-check — use reported value
    if gross_profit is None or operating_income is None:
        return _safe_div(reported_sga, revenue)

    # If no SGA was reported at all, the company may not break out
    # this line item (e.g. banks).  Do NOT impute — return None.
    if reported_sga is None:
        return None

    # What the income statement identity implies for SGA
    implied_sga = gross_profit - operating_income - (research_development or 0)

    # If implied SGA is non-positive, the income statement structure is
    # unusual (e.g. operating income exceeds gross profit minus R&D);
    # fall back to the reported value.
    if implied_sga <= 0:
        return _safe_div(reported_sga, revenue)

    # If reported SGA is within 60% of implied, it's accurate enough.
    if reported_sga >= implied_sga * 0.6:
        return _safe_div(reported_sga, revenue)

    # ---- Anomaly detected: reported SGA is < 60% of implied ----
    # Use the implied value as a corrected estimate.
    corrected_ratio = implied_sga / revenue

    # Sanity bound — ratio must be in (0, 100%]; otherwise discard.
    if corrected_ratio <= 0 or corrected_ratio > 1.0:
        return None

    return corrected_ratio


def _compute_yoy_growth(
    date_key: str,
    revenue_by_date: dict[str, float | None],
    period_type: FinancialPeriodType,
) -> float | None:
    """Compute YoY revenue growth for a given period date.

    For annual periods, the prior year is found by subtracting 1 from the year.
    For quarterly periods, the prior year quarter is 4 entries earlier in the
    sorted list (approximate — relies on EODHD returning consistent quarterly dates).

    Returns None when prior period data is unavailable.
    """
    current_revenue = revenue_by_date.get(date_key)
    if current_revenue is None:
        return None

    # Build a sorted list of date keys (ascending) to find the prior period
    all_dates = sorted(revenue_by_date.keys())
    try:
        idx = all_dates.index(date_key)
    except ValueError:
        return None

    if period_type == FinancialPeriodType.ANNUAL:
        # Prior year: same date but one year earlier
        try:
            year = int(date_key[:4])
            prior_date = f"{year - 1}{date_key[4:]}"
        except (ValueError, IndexError):
            return None
        prior_revenue = revenue_by_date.get(prior_date)
    else:
        # Quarterly: 4 quarters back in the date list
        prior_idx = idx - 4
        if prior_idx < 0:
            return None
        prior_date = all_dates[prior_idx]
        prior_revenue = revenue_by_date.get(prior_date)

    if prior_revenue is None or prior_revenue == 0.0:
        return None

    # Apply FX to both so the ratio is currency-neutral (rate cancels out)
    return (current_revenue - prior_revenue) / abs(prior_revenue)
