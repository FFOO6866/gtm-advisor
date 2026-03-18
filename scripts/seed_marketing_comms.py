#!/usr/bin/env python3
"""Seed the marketing_comms vertical with comprehensive company roster.

Seeds both listed companies (EODHD-tracked) and private/unlisted companies
into the listed_companies table, all assigned to the marketing_comms vertical.

Listed companies use their real exchange/ticker for EODHD financial sync.
Private companies use exchange="PRIVATE" and a slug ticker — they won't be
picked up by EODHD sync but will appear in vertical queries and intelligence.

Usage:
    uv run python scripts/seed_marketing_comms.py
    uv run python scripts/seed_marketing_comms.py --dry-run   # preview only
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select

from packages.database.src.models import CompanyListingType, ListedCompany, MarketVertical
from packages.database.src.session import async_session_factory, close_db, init_db

# ---------------------------------------------------------------------------
# Company roster — comprehensive marketing / comms / PR / advertising
# ---------------------------------------------------------------------------
# Format: (ticker, exchange, name, website, description, is_sg_incorporated, currency)
#
# exchange="PRIVATE" → no EODHD sync; ticker is a slug (must be unique).
# For listed companies, exchange is the EODHD code (US, LSE, PA, KO, HK, SG).
# ---------------------------------------------------------------------------

# ── Global Advertising Holding Groups (Listed) ─────────────────────────────
LISTED_HOLDING_GROUPS: list[dict] = [
    {
        "ticker": "WPP", "exchange": "LSE", "name": "WPP plc", "currency": "GBP",
        "website": "https://www.wpp.com",
        "description": (
            "World's largest advertising holding company by revenue. Owns Ogilvy, VML, "
            "Burson, GroupM (now WPP Media), AKQA, Hogarth, Landor. "
            "HQ London; major SG hub with 2,000+ staff."
        ),
        "is_sg_incorporated": False,
    },
    {
        "ticker": "OMC", "exchange": "US", "name": "Omnicom Group Inc", "currency": "USD",
        "website": "https://www.omnicomgroup.com",
        "description": (
            "World's largest advertising holding company after acquiring IPG (Nov 2025). "
            "Owns BBDO, TBWA, DDB, OMD, PHD, FleishmanHillard, McCann, Weber Shandwick. "
            "SG presence: BBDO, TBWA, OMD, PHD, FleishmanHillard, McCann."
        ),
        "is_sg_incorporated": False,
    },
    {
        "ticker": "PUB", "exchange": "PA", "name": "Publicis Groupe SA", "currency": "EUR",
        "website": "https://www.publicisgroupe.com",
        "description": (
            "Third-largest advertising holding company. Owns Leo Burnett (now Publicis Leo), "
            "Saatchi & Saatchi, Starcom, Zenith, Publicis Sapient, Epsilon. "
            "Acquired Hepmil Media Group (SG-based creator network). Major SG presence."
        ),
        "is_sg_incorporated": False,
    },
    # IPG acquired by Omnicom Nov 2025, delisted from NYSE. Kept for historical data.
    # {
    #     "ticker": "IPG", "exchange": "US", "name": "Interpublic Group of Companies",
    #     "DELISTED: Acquired by Omnicom Group Nov 2025. Brands integrated into Omnicom."
    # },
    {
        "ticker": "STGW", "exchange": "US", "name": "Stagwell Inc", "currency": "USD",
        "website": "https://www.stagwellglobal.com",
        "description": (
            "Challenger holding company founded by Mark Penn (2019). Owns Assembly, "
            "72andSunny, Anomaly, Instrument, Multiview, Harris Poll. "
            "Opened new APAC HQ at one-north Singapore (2024)."
        ),
        "is_sg_incorporated": False,
    },
    {
        "ticker": "SFOR", "exchange": "LSE", "name": "S4 Capital plc", "currency": "GBP",
        "website": "https://www.s4capital.com",
        "description": (
            "Sir Martin Sorrell's digital-only holding company (post-WPP). "
            "Owns Monks (formerly MediaMonks), content + data + technology practices. "
            "SG presence through Monks Asia."
        ),
        "is_sg_incorporated": False,
    },
    {
        "ticker": "030000", "exchange": "KO", "name": "Cheil Worldwide Inc", "currency": "KRW",
        "website": "https://www.cheil.com",
        "description": (
            "Samsung Group's in-house agency, now global holding company. "
            "Owns Iris, BMB, McKinney. #1 agency in South Korea. "
            "SG office services Samsung regional campaigns."
        ),
        "is_sg_incorporated": False,
    },
    {
        "ticker": "HAVAS", "exchange": "AS", "name": "Havas NV", "currency": "EUR",
        "website": "https://www.havas.com",
        "description": (
            "Spun off from Vivendi Dec 2024, independently listed on Euronext Amsterdam. "
            "Owns BLKJ Havas in Singapore (#4 ranked SG agency). "
            "Creative, media, health & wellness networks. ~EUR 2.7B revenue."
        ),
        "is_sg_incorporated": False,
    },
]

# ── Adtech / Martech (Listed) ──────────────────────────────────────────────
LISTED_ADTECH: list[dict] = [
    {
        "ticker": "TTD", "exchange": "US", "name": "The Trade Desk Inc", "currency": "USD",
        "website": "https://www.thetradedesk.com",
        "description": "Leading demand-side platform (DSP) for programmatic digital advertising. SG APAC hub.",
    },
    {
        "ticker": "APP", "exchange": "US", "name": "AppLovin Corporation", "currency": "USD",
        "website": "https://www.applovin.com",
        "description": "Mobile app marketing and monetisation platform. AI-powered ad engine (AXON).",
    },
    {
        "ticker": "CRTO", "exchange": "US", "name": "Criteo SA", "currency": "USD",
        "website": "https://www.criteo.com",
        "description": "French adtech company specialising in performance marketing and retargeting. SG office.",
    },
    {
        "ticker": "MGNI", "exchange": "US", "name": "Magnite Inc", "currency": "USD",
        "website": "https://www.magnite.com",
        "description": "World's largest independent sell-side advertising platform (SSP). Programmatic CTV + digital.",
    },
    {
        "ticker": "PUBM", "exchange": "US", "name": "PubMatic Inc", "currency": "USD",
        "website": "https://www.pubmatic.com",
        "description": "Sell-side platform for publishers. Real-time ad auction infrastructure.",
    },
    {
        "ticker": "DV", "exchange": "US", "name": "DoubleVerify Holdings Inc", "currency": "USD",
        "website": "https://www.doubleverify.com",
        "description": "Ad verification and brand safety platform. Measures viewability, fraud, brand suitability.",
    },
    {
        "ticker": "IAS", "exchange": "US", "name": "Integral Ad Science Holding Corp", "currency": "USD",
        "website": "https://integralads.com",
        "description": "Ad verification, viewability measurement, and brand safety. Direct competitor to DoubleVerify.",
    },
    {
        "ticker": "BRZE", "exchange": "US", "name": "Braze Inc", "currency": "USD",
        "website": "https://www.braze.com",
        "description": "Customer engagement platform — push, email, in-app messaging. Martech leader.",
    },
    {
        "ticker": "ZD", "exchange": "US", "name": "Zeta Global Holdings Corp", "currency": "USD",
        "website": "https://zetaglobal.com",
        "description": "AI-powered marketing cloud with 235M+ identity profiles. Data-driven advertising.",
    },
    {
        "ticker": "HUBS", "exchange": "US", "name": "HubSpot Inc", "currency": "USD",
        "website": "https://www.hubspot.com",
        "description": "CRM + marketing automation platform. Inbound marketing pioneer. SG APAC operations.",
    },
]

# ── Consulting Parents with Major Agency Arms (Listed) ─────────────────────
LISTED_CONSULTING_AGENCY: list[dict] = [
    {
        "ticker": "ACN", "exchange": "US", "name": "Accenture plc", "currency": "USD",
        "website": "https://www.accenture.com",
        "description": (
            "Global consulting giant. Accenture Song is world's largest digital agency by revenue "
            "(acquired Droga5, Karmarama, Shackleton). SG is APAC hub."
        ),
    },
    {
        "ticker": "IBM", "exchange": "US", "name": "IBM Corporation", "currency": "USD",
        "website": "https://www.ibm.com",
        "description": (
            "IBM iX (IBM Interactive Experience) is IBM's digital agency and experience design arm — "
            "one of the world's largest digital agencies by headcount (~40,000 practitioners). "
            "Offers strategy, design, technology implementation. SG office within IBM APAC HQ."
        ),
        "is_sg_incorporated": False,
    },
]

# ── SGX-Listed Advertising/Media ───────────────────────────────────────────
LISTED_SGX: list[dict] = [
    {
        "ticker": "1D1", "exchange": "SG", "name": "UNUSUAL LIMITED", "currency": "SGD",
        "website": "https://www.unusual.com.sg",
        "description": "Singapore-listed events and entertainment company. Concert promotion, venue management.",
        "is_sg_incorporated": True,
    },
    {
        "ticker": "1F0", "exchange": "SG", "name": "SHOPPER360 LIMITED", "currency": "SGD",
        "website": "https://www.shopper360.com.my",
        "description": "SGX-listed Malaysian retail marketing group. In-store promotions, field marketing, digital.",
        "is_sg_incorporated": False,
    },
    {
        "ticker": "E27", "exchange": "SG", "name": "THE PLACE HOLDINGS LIMITED", "currency": "SGD",
        "website": "https://www.theplaceholdings.com",
        "description": "SGX-listed outdoor advertising (digital billboards) and digital media in China and Singapore.",
        "is_sg_incorporated": True,
    },
]

# ── HK-Listed Events/Experiential ─────────────────────────────────────────
LISTED_HK: list[dict] = [
    {
        "ticker": "0752", "exchange": "HK", "name": "Pico Far East Holdings Limited", "currency": "HKD",
        "website": "https://www.pico.com",
        "description": (
            "Singapore-FOUNDED experiential marketing and events company. HKEx-listed. "
            "World's #1 brand activation agency. 2,800+ staff across 40 cities."
        ),
        "is_sg_incorporated": False,
    },
]

# ── Additional Global Listed Companies (discovered via research) ─────────
LISTED_GLOBAL_ADDITIONAL: list[dict] = [
    # Korea
    {
        "ticker": "214320", "exchange": "KO", "name": "INNOCEAN Worldwide Inc", "currency": "KRW",
        "website": "https://www.innocean.com",
        "description": (
            "Hyundai Motor Group's in-house agency, now global. "
            "Creative, media, digital, data analytics. Offices in 16 countries incl. SG."
        ),
        "is_sg_incorporated": False,
    },
    # Japan / Tokyo Stock Exchange (EODHD exchange code: "T")
    {
        "ticker": "2433", "exchange": "T", "name": "Hakuhodo DY Holdings Inc", "currency": "JPY",
        "website": "https://www.hakuhodody-holdings.co.jp",
        "description": (
            "Japan's #2 advertising holding company (behind Dentsu). "
            "Owns Hakuhodo, Daiko Advertising, Yomiko Advertising, and SIX. "
            "~JPY 1.5T revenue. APAC expansion via Hakuhodo International; SG office for regional accounts."
        ),
        "is_sg_incorporated": False,
    },
    # China / Shenzhen Stock Exchange (EODHD exchange code: "SHE")
    {
        "ticker": "002027", "exchange": "SHE", "name": "BlueFocus Intelligent Communications Group Co Ltd",
        "currency": "CNY",
        "website": "https://www.bluefocus.com",
        "description": (
            "China's largest independent marketing and communications group. "
            "Owns We Are Social (global social agency), Fuseproject, and digital PR/content units. "
            "~CNY 40B+ revenue. SG relevant through We Are Social Singapore office."
        ),
        "is_sg_incorporated": False,
    },
    # France / Euronext Paris
    {
        "ticker": "DEC", "exchange": "PA", "name": "JCDecaux SA", "currency": "EUR",
        "website": "https://www.jcdecaux.com",
        "description": (
            "World's #1 outdoor advertising company. Street furniture, transport, "
            "billboard advertising across 80+ countries. SG: bus shelters, MRT, Changi Airport."
        ),
        "is_sg_incorporated": False,
    },
    # UK / LSE
    {
        "ticker": "SAA", "exchange": "LSE", "name": "M&C Saatchi plc", "currency": "GBP",
        "website": "https://www.mcsaatchi.com",
        "description": "Independent creative agency network. Founded by Maurice Saatchi (1995). Global offices incl. SG.",
        "is_sg_incorporated": False,
    },
    # Australia / ASX
    {
        "ticker": "EGG", "exchange": "AU", "name": "Enero Group Limited", "currency": "AUD",
        "website": "https://www.enero.com",
        "description": "ASX-listed boutique agency network. Owns BMF, Hotwire, CPR. PR, creative, tech marketing.",
        "is_sg_incorporated": False,
    },
    {
        "ticker": "OML", "exchange": "AU", "name": "oOh!media Limited", "currency": "AUD",
        "website": "https://www.oohmedia.com.au",
        "description": "Australia's leading out-of-home media company. 30,000+ digital and static signs across AU/NZ.",
        "is_sg_incorporated": False,
    },
    # US — additional marketing services
    {
        "ticker": "ADV", "exchange": "US", "name": "Advantage Solutions Inc", "currency": "USD",
        "website": "https://www.advantagesolutions.net",
        "description": "Outsourced sales and marketing services for consumer goods brands and retailers.",
    },
    {
        "ticker": "QNST", "exchange": "US", "name": "QuinStreet Inc", "currency": "USD",
        "website": "https://www.quinstreet.com",
        "description": "Performance marketing and lead generation in financial services and home services verticals.",
    },
    # US — Out-of-Home
    {
        "ticker": "LAMR", "exchange": "US", "name": "Lamar Advertising Company", "currency": "USD",
        "website": "https://www.lamar.com",
        "description": "Largest US outdoor advertising REIT. 362,000+ billboard, digital, and transit displays.",
    },
    {
        "ticker": "CCO", "exchange": "US", "name": "Clear Channel Outdoor Holdings Inc", "currency": "USD",
        "website": "https://www.clearchanneloutdoor.com",
        "description": "Global outdoor advertising. 640,000+ print and digital displays across 40+ countries.",
    },
    {
        "ticker": "OUT", "exchange": "US", "name": "OUTFRONT Media Inc", "currency": "USD",
        "website": "https://www.outfrontmedia.com",
        "description": "US outdoor advertising REIT. Billboards, transit media, digital networks. 500,000+ displays.",
    },
]

# ── Private / Unlisted Companies ───────────────────────────────────────────
# exchange="PRIVATE", ticker=slug, no EODHD sync.
# These represent the most important agencies/firms in Singapore and globally.

PRIVATE_COMPANIES: list[dict] = [
    # ── WPP Network Agencies (SG offices) ──────────────────────────────────
    {
        "ticker": "OGILVY-SG", "exchange": "PRIVATE", "name": "Ogilvy Singapore",
        "website": "https://www.ogilvy.com/sg",
        "description": (
            "WPP's flagship creative agency. #1 ranked agency in Singapore (Campaign Asia 2024). "
            "Full-service: advertising, PR, consulting, experience, health. 300+ staff in SG."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "VML-SG", "exchange": "PRIVATE", "name": "VML Singapore",
        "website": "https://www.vml.com",
        "description": (
            "WPP merged Wunderman Thompson + VMLY&R into VML (2023). "
            "#2 ranked agency in SG. Creative, commerce, consulting, technology."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "BURSON-SG", "exchange": "PRIVATE", "name": "Burson Singapore",
        "website": "https://www.burson.com",
        "description": (
            "WPP PR powerhouse — merger of BCW + Hill & Knowlton (2024). "
            "Corporate comms, crisis management, public affairs. Major SG office."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "GROUPM-SG", "exchange": "PRIVATE", "name": "WPP Media Singapore (GroupM)",
        "website": "https://www.groupm.com",
        "description": (
            "WPP's media investment group (rebranded from GroupM 2024). "
            "Includes Mindshare, Wavemaker, EssenceMediacom. Largest media buyer in SG."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Omnicom Network Agencies (SG offices) ──────────────────────────────
    {
        "ticker": "BBDO-SG", "exchange": "PRIVATE", "name": "BBDO Singapore",
        "website": "https://www.bbdo.com",
        "description": "Omnicom creative network. Major SG office servicing regional brands. Award-winning creative.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "TBWA-SG", "exchange": "PRIVATE", "name": "TBWA\\Singapore",
        "website": "https://www.tbwa.com",
        "description": (
            "Omnicom creative network. 'Disruption' methodology. "
            "SG office services Apple, Nissan, Singapore Airlines (historically). Known for bold creative."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "DDB-SG", "exchange": "PRIVATE", "name": "DDB Singapore",
        "website": "https://www.ddb.com",
        "description": (
            "Omnicom creative network. Being retired post Omnicom-IPG merger. "
            "Legacy Bill Bernbach creative philosophy. SG office for APAC campaigns."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "OMD-SG", "exchange": "PRIVATE", "name": "OMD Singapore",
        "website": "https://www.omd.com",
        "description": "Omnicom media agency. #1 media agency in SG by billings. Data-driven planning and buying.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "PHD-SG", "exchange": "PRIVATE", "name": "PHD Singapore",
        "website": "https://www.phdmedia.com",
        "description": "Omnicom media agency. Strategy-led media planning. Source by PHD platform. Strong SG team.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "FLEISHMAN-SG", "exchange": "PRIVATE", "name": "FleishmanHillard Singapore",
        "website": "https://fleishmanhillard.com",
        "description": "Omnicom PR/comms agency. Corporate reputation, public affairs, digital. SG APAC hub.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Publicis Network Agencies (SG offices) ─────────────────────────────
    {
        "ticker": "LEO-SG", "exchange": "PRIVATE", "name": "Publicis Leo Singapore",
        "website": "https://www.leoburnett.com",
        "description": (
            "Publicis merged Leo Burnett + Publicis Worldwide into 'Publicis Leo' (2024). "
            "McDonald's global creative AOR. Strong SG heritage. Humankind approach."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "SAATCHI-SG", "exchange": "PRIVATE", "name": "Saatchi & Saatchi Singapore",
        "website": "https://saatchi.com",
        "description": "Publicis creative network. 'Nothing is Impossible' ethos. SG office for APAC.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "STARCOM-SG", "exchange": "PRIVATE", "name": "Starcom Singapore",
        "website": "https://www.starcomww.com",
        "description": (
            "Publicis media agency. Won WOG (Whole-of-Government) master media contract "
            "for Singapore government. Major SG media agency."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "ZENITH-SG", "exchange": "PRIVATE", "name": "Zenith Singapore",
        "website": "https://www.zenithmedia.com",
        "description": "Publicis media agency. ROI-focused planning. Part of Publicis Media SG.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "SAPIENT-SG", "exchange": "PRIVATE", "name": "Publicis Sapient Singapore",
        "website": "https://www.publicissapient.com",
        "description": "Publicis digital business transformation consultancy. Engineering + experience design. SG hub.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "HEPMIL", "exchange": "PRIVATE", "name": "Hepmil Media Group",
        "website": "https://hepmilmedia.com",
        "description": (
            "Singapore-founded creator network, acquired by Publicis (2024). "
            "SGAG, MGAG, PGAG meme pages. 100M+ followers across APAC. "
            "Influencer marketing and branded content."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Dentsu Network (SG offices) — parent NOT on EODHD (TSE) ───────────
    {
        "ticker": "DENTSU-SG", "exchange": "PRIVATE", "name": "Dentsu Creative Singapore",
        "website": "https://www.dentsu.com",
        "description": (
            "Dentsu Group's creative arm in SG. Parent is listed on TSE (4324.T) — "
            "not available on EODHD. Japan's #1, world's #5 advertising company. "
            "SG services: Dentsu Creative, Carat, iProspect, Merkle."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "CARAT-SG", "exchange": "PRIVATE", "name": "Carat Singapore",
        "website": "https://www.carat.com",
        "description": "Dentsu media agency. Designing for people. Top 3 media agency in SG by billings.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "IPROSPECT-SG", "exchange": "PRIVATE", "name": "iProspect Singapore",
        "website": "https://www.iprospect.com",
        "description": "Dentsu performance marketing agency. SEO, SEM, programmatic, performance media.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Havas (SG offices) — parent is Vivendi (listed above) ──────────────
    {
        "ticker": "BLKJ-HAVAS", "exchange": "PRIVATE", "name": "BLKJ Havas Singapore",
        "website": "https://blkj.com",
        "description": (
            "Singapore's #4 ranked agency (Campaign Asia 2024). "
            "Originally BLKJ (independent), acquired by Havas (2023). "
            "Won Agency of the Year multiple times. Clients: Singtel, DBS, NTUC."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Stagwell Network (SG) ──────────────────────────────────────────────
    {
        "ticker": "ASSEMBLY-SG", "exchange": "PRIVATE", "name": "Assembly Singapore",
        "website": "https://www.assemblyglobal.com",
        "description": "Stagwell's integrated media agency. Opened SG APAC hub at one-north (2024).",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "ANOMALY-SG", "exchange": "PRIVATE", "name": "Anomaly Singapore",
        "website": "https://www.anomaly.com",
        "description": "Stagwell creative agency. Known for brand-building and innovation consulting.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Accenture Song (SG) ────────────────────────────────────────────────
    {
        "ticker": "SONG-SG", "exchange": "PRIVATE", "name": "Accenture Song Singapore",
        "website": "https://www.accenture.com/sg-en/about/accenture-song-index",
        "description": (
            "Accenture's creative/experience arm. World's largest digital agency by revenue. "
            "Includes Droga5, Karmarama capabilities. SG office 500+ staff."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Global Independent Agencies with SG Presence ──────────────────────
    {
        "ticker": "EDELMAN-SG", "exchange": "PRIVATE", "name": "Edelman Singapore",
        "website": "https://www.edelman.com.sg",
        "description": (
            "World's largest independent PR firm (family-owned, $1B+ revenue). "
            "Trust Barometer publisher. SG is APAC hub. Corporate, crisis, digital, "
            "public affairs. 200+ SG staff."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "WEARESOCIAL-SG", "exchange": "PRIVATE", "name": "We Are Social Singapore",
        "website": "https://wearesocial.com/sg",
        "description": (
            "Global socially-led creative agency. Publishes Digital Report (with Meltwater). "
            "SG office handles APAC social strategy for major brands."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "RGA-SG", "exchange": "PRIVATE", "name": "R/GA Singapore",
        "website": "https://www.rga.com",
        "description": "IPG's innovation/tech-driven agency. Business transformation, ventures, experience design.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "VAYNER-SG", "exchange": "PRIVATE", "name": "VaynerMedia Asia",
        "website": "https://vaynermedia.com",
        "description": (
            "Gary Vaynerchuk's social-first creative agency. "
            "SG office opened 2019. Social content, influencer strategy."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "DEPT-SG", "exchange": "PRIVATE", "name": "DEPT Singapore",
        "website": "https://www.deptagency.com",
        "description": "Dutch digital agency, 4,000+ staff globally. Technology + marketing + creative. SG office.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "WIEDEN-KENNEDY", "exchange": "PRIVATE", "name": "Wieden+Kennedy",
        "website": "https://www.wk.com",
        "description": (
            "World's largest independent creative advertising agency (founded Portland 1982). "
            "Famous campaigns: Nike 'Just Do It', Old Spice. No SG office but regional APAC campaigns "
            "via Tokyo and Shanghai offices. $500M+ estimated revenue."
        ),
        "is_sg_incorporated": False, "currency": "USD",
    },
    {
        "ticker": "SERVICEPLAN-SG", "exchange": "PRIVATE", "name": "Serviceplan Group",
        "website": "https://www.serviceplan.com",
        "description": (
            "Europe's largest owner-managed agency group (Munich HQ, founded 1970). "
            "Integrated: creative, media, digital, PR. 'House of Communication' model. "
            "~EUR 500M revenue. APAC expansion through strategic partnerships; no standalone SG entity."
        ),
        "is_sg_incorporated": False, "currency": "EUR",
    },
    {
        "ticker": "PWC-DIGITAL", "exchange": "PRIVATE", "name": "PwC Digital Services",
        "website": "https://www.pwc.com/sg/en/services/digital.html",
        "description": (
            "PricewaterhouseCoopers' digital consulting and experience design arm. "
            "Digital transformation, CX strategy, data analytics, martech implementation. "
            "SG office is regional hub; competes with Accenture Song and Deloitte Digital."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "DELOITTE-DIGITAL", "exchange": "PRIVATE", "name": "Deloitte Digital",
        "website": "https://www.deloittedigital.com",
        "description": (
            "Deloitte's creative digital consultancy — combines brand strategy, experience design, "
            "and technology implementation. Acquired Heat (creative agency) and Acne (Swedish agency). "
            "SG office 200+ staff; competes with Accenture Song and PwC Digital for transformation briefs."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "MONKS-SG", "exchange": "PRIVATE", "name": "Monks Singapore",
        "website": "https://www.monks.com",
        "description": (
            "S4 Capital's operating brand (formerly MediaMonks). "
            "Content, data, digital media, technology. SG APAC production hub."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "RUDER-FINN-SG", "exchange": "PRIVATE", "name": "Ruder Finn Asia",
        "website": "https://www.ruderfinn.com",
        "description": "Independent PR firm (US HQ). Healthcare, technology, financial services comms. SG office.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "BRUNSWICK-SG", "exchange": "PRIVATE", "name": "Brunswick Group Singapore",
        "website": "https://www.brunswickgroup.com",
        "description": "Elite corporate advisory/comms firm. M&A comms, crisis, capital markets. SG office.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "FTI-SG", "exchange": "PRIVATE", "name": "FTI Consulting Singapore",
        "website": "https://www.fticonsulting.com",
        "description": "Global business advisory — strategic communications division. Crisis, litigation, corp comms.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "WEBER-SG", "exchange": "PRIVATE", "name": "Weber Shandwick Singapore",
        "website": "https://webershandwick.asia",
        "description": "IPG's global PR agency. Healthcare, technology, corporate, consumer PR. Major SG operation.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "GOLIN-SG", "exchange": "PRIVATE", "name": "Golin Singapore",
        "website": "https://golin.com",
        "description": "IPG PR agency. Consumer, healthcare, technology PR. Bridge methodology. SG office.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "FINN-SG", "exchange": "PRIVATE", "name": "FINN Partners Singapore",
        "website": "https://www.finnpartners.com",
        "description": (
            "Independent PR firm (acquired Rice Communications 2023). "
            "Technology, travel, health PR. Strong SG/APAC presence via Rice legacy."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "ARCHETYPE-SG", "exchange": "PRIVATE", "name": "Archetype Singapore",
        "website": "https://www.archetype.co",
        "description": "Formerly Text100 (Ruder Finn spin-off). Technology PR specialist. SG APAC hub. B2B tech focus.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "MCCANN-SG", "exchange": "PRIVATE", "name": "McCann Singapore",
        "website": "https://www.mccann.com",
        "description": (
            "IPG's global creative network. 'Truth Well Told' philosophy. "
            "SG office handles APAC campaigns for Coca-Cola, Microsoft, L'Oréal."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "JACKMORTON-SG", "exchange": "PRIVATE", "name": "Jack Morton Singapore",
        "website": "https://www.jackmorton.com",
        "description": "IPG experiential agency. Live events, brand activations, digital experiences. SG office.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Singapore-Founded Independent Agencies ─────────────────────────────
    {
        "ticker": "TSLA-GROUP", "exchange": "PRIVATE", "name": "TSLA Group (The Secret Little Agency)",
        "website": "https://www.thesecretlittleagency.com",
        "description": (
            "Award-winning Singapore indie creative agency (founded 2009). "
            "Strategic brand building. Clients: Tiger Beer, Grab, OCBC. "
            "Won numerous local and regional creative awards."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "DSTNCT", "exchange": "PRIVATE", "name": "DSTNCT",
        "website": "https://dstnct.co",
        "description": (
            "Singapore indie agency (founded 2019). Creative, digital, production. "
            "Founded by ex-DDB/BBDO creatives. Fast-rising independent."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "GOODSTUPH", "exchange": "PRIVATE", "name": "Goodstuph",
        "website": "https://www.goodstuph.com",
        "description": (
            "Singapore indie creative agency. Social-first, content creation, brand strategy. "
            "Known for culturally-relevant SG campaigns."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "FISHERMEN", "exchange": "PRIVATE", "name": "Fishermen Integrated",
        "website": "https://www.fishermen.com.sg",
        "description": (
            "Singapore indie integrated agency. Creative, digital, events, production. "
            "Government and corporate clients. Full-service local challenger."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "VIRTUE-ASIA", "exchange": "PRIVATE", "name": "Virtue Asia",
        "website": "https://virtue.com",
        "description": "Vice Media's creative agency. Culture-driven marketing. SG APAC base.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "GOVT-VCCP", "exchange": "PRIVATE", "name": "GOVT Singapore (VCCP partnership)",
        "website": "https://govt.sg.com",
        "description": (
            "Singapore indie agency partnered with UK's VCCP. "
            "Creative, brand, digital. Strong government and statutory board portfolio."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "FORSMAN-SG", "exchange": "PRIVATE", "name": "Forsman & Bodenfors Singapore",
        "website": "https://www.forsman.com",
        "description": "Swedish indie creative agency. Opened SG office. Collaborative creativity model.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "WILD-SG", "exchange": "PRIVATE", "name": "WILD Singapore",
        "website": "https://www.wild.as",
        "description": "Independent creative agency in SG. Brand strategy and creative campaigns.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "EIGHTCREATIVES", "exchange": "PRIVATE", "name": "Eight Creative",
        "website": "https://eightcreative.com",
        "description": "Singapore indie agency. Branding, packaging, communications design.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Singapore Digital Marketing Agencies ───────────────────────────────
    {
        "ticker": "HEROES-DIGITAL", "exchange": "PRIVATE", "name": "Heroes of Digital",
        "website": "https://www.heroesofdigital.com",
        "description": (
            "Singapore's leading performance marketing agency. Google/Meta Premier Partner. "
            "SEO, SEM, social ads. SME-focused. 100+ staff."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "OOM-SG", "exchange": "PRIVATE", "name": "OOm Pte Ltd",
        "website": "https://www.oom.com.sg",
        "description": "Singapore digital marketing agency (founded 2006). SEO, SEM, social media. Google Partner.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "2STALLIONS", "exchange": "PRIVATE", "name": "2Stallions Digital Marketing",
        "website": "https://www.2stallions.com",
        "description": "SG digital agency. SEO, content marketing, web development, lead generation. Regional presence.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "CLICKR", "exchange": "PRIVATE", "name": "Clickr Media",
        "website": "https://www.clickrmedia.com",
        "description": "Singapore SEM/SEO agency. Google Premier Partner. Performance marketing specialist.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "HASHMETA", "exchange": "PRIVATE", "name": "Hashmeta",
        "website": "https://hashmeta.com",
        "description": "Singapore social media and digital marketing agency. Content creation, influencer marketing.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "MASHWIRE", "exchange": "PRIVATE", "name": "Mashwire",
        "website": "https://mashwire.com",
        "description": "Singapore digital creative agency. Social media, content, campaigns for government and corporates.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "IMPOSSIBLE-MKT", "exchange": "PRIVATE", "name": "Impossible Marketing",
        "website": "https://www.intobusiness.com.sg",
        "description": "SG digital marketing agency. SEO, SEM, social media marketing for SMEs.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "FIRSTPAGE", "exchange": "PRIVATE", "name": "First Page Digital",
        "website": "https://firstpagedigital.sg",
        "description": "SG-founded digital marketing agency. SEO, Google Ads, Facebook Ads. Expanded to APAC.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "DIGITALNOMADS", "exchange": "PRIVATE", "name": "Digital Nomads",
        "website": "https://www.digitalnomads.asia",
        "description": "Singapore digital agency. Web development, digital marketing, brand strategy.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Singapore PR / Communications Firms ────────────────────────────────
    {
        "ticker": "REDHILL-SG", "exchange": "PRIVATE", "name": "Redhill Communications",
        "website": "https://www.redhillcomms.com",
        "description": (
            "Singapore-founded PR agency (2014). Corporate, tech, healthcare comms. "
            "Expanded to HK, AU, JPN, IND. Fastest-growing indie PR in APAC."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "PRECIOUS-SG", "exchange": "PRIVATE", "name": "PRecious Communications",
        "website": "https://www.precious.co",
        "description": (
            "Singapore tech PR specialist (founded 2015). B2B tech, fintech, SaaS PR. "
            "Offices in SG, Tokyo, KL. Partner network across APAC."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "MUTANT-SG", "exchange": "PRIVATE", "name": "Mutant Communications",
        "website": "https://mutant.com.sg",
        "description": (
            "Singapore PR agency (founded 2014). 'PR unfcked' positioning. "
            "Corporate comms, media relations, content. Founded by ex-journalists."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "TATEANZUR", "exchange": "PRIVATE", "name": "Tate Anzur",
        "website": "https://tateanzur.com",
        "description": (
            "Singapore PR + public affairs consultancy. Government relations, "
            "healthcare PR, corporate communications. Founded by ex-MICA/MCI staff."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "APRW", "exchange": "PRIVATE", "name": "Asia PR Werkz (APRW)",
        "website": "https://www.aprw.asia",
        "description": (
            "Award-winning Singapore PR agency. Consumer, corporate, healthcare PR. "
            "Strong government sector portfolio. 25+ years in SG."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "HOFFMAN-SG", "exchange": "PRIVATE", "name": "The Hoffman Agency Singapore",
        "website": "https://www.hoffman.com",
        "description": "US-founded tech PR firm. B2B technology PR specialist. SG APAC hub.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "RICE-FINN", "exchange": "PRIVATE", "name": "Rice Communications (FINN Partners)",
        "website": "https://www.ricecomms.com",
        "description": (
            "Singapore-founded tech PR firm (acquired by FINN Partners 2023). "
            "Strong heritage in B2B tech, enterprise, fintech PR across APAC."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "WACHSMAN-SG", "exchange": "PRIVATE", "name": "Wachsman Singapore",
        "website": "https://www.wachsman.com",
        "description": "Web3/crypto-focused PR and advisory firm. SG office for APAC crypto comms.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Experiential / Events / Production ─────────────────────────────────
    {
        "ticker": "UNIPLAN-SG", "exchange": "PRIVATE", "name": "Uniplan Singapore",
        "website": "https://www.uniplan.com",
        "description": "German-founded experiential agency. Live events, exhibitions, brand spaces. SG APAC office.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "KINGSMEN-SG", "exchange": "PRIVATE", "name": "Kingsmen Creatives Ltd",
        "website": "https://www.kingsmen-int.com",
        "description": (
            "Singapore-founded creative services group. Exhibitions, themed environments, "
            "retail interiors. Previously SGX-listed (delisted 2022). Major SG player."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "PICO-SG", "exchange": "PRIVATE", "name": "Pico Singapore",
        "website": "https://www.pico.com",
        "description": (
            "Singapore-founded, HKEx-listed parent (0752.HK). "
            "SG operations: brand activation, events, exhibitions. 500+ SG staff."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Influencer / Creator Economy ───────────────────────────────────────
    {
        "ticker": "KOBE-GLOBAL", "exchange": "PRIVATE", "name": "Kobe Global Technologies",
        "website": "https://www.kobeglobal.com",
        "description": (
            "Singapore influencer marketing platform. AI-powered creator matching. "
            "Connects brands with influencers across APAC."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "GUSHCLOUD", "exchange": "PRIVATE", "name": "Gushcloud International",
        "website": "https://www.gushcloud.com",
        "description": (
            "Singapore-founded influencer marketing company. Talent management + brand partnerships. "
            "Offices across ASEAN. 300+ managed creators."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "NUFFNANG", "exchange": "PRIVATE", "name": "Nuffnang (part of Netccentric)",
        "website": "https://www.nuffnang.com",
        "description": (
            "Pioneer ASEAN blog advertising network (founded SG/MY 2007). "
            "Influencer marketing, content creation. Part of Netccentric group."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "MELTWATER-SG", "exchange": "PRIVATE", "name": "Meltwater Singapore",
        "website": "https://www.meltwater.com",
        "description": (
            "Norwegian-founded media intelligence company. Media monitoring, social listening, "
            "PR analytics. SG is APAC HQ. Publishes Digital Report with We Are Social."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Out-of-Home / Outdoor Advertising ──────────────────────────────────
    {
        "ticker": "JCDECAUX-SG", "exchange": "PRIVATE", "name": "JCDecaux Singapore",
        "website": "https://www.jcdecaux.com.sg",
        "description": (
            "World's largest OOH advertising company (parent listed on PA: DEC). "
            "SG: bus shelters, MRT advertising, street furniture. Changi Airport contract."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "MOOVE-SG", "exchange": "PRIVATE", "name": "Moove Media",
        "website": "https://www.moovemedia.com.sg",
        "description": (
            "Singapore OOH/transit advertising. Bus ads, MRT in-station, taxi advertising. "
            "Major SMRT/SBS transit ad partner."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "SPHMEDIA-SG", "exchange": "PRIVATE", "name": "SPH Media Trust",
        "website": "https://www.sphmedia.com.sg",
        "description": (
            "Singapore Press Holdings media arm (became CLG 2022). "
            "Owns Straits Times, Business Times, Zaobao. Major advertising inventory. "
            "Not listed separately (SPH REIT on SGX is property only)."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "MEDIACORP-SG", "exchange": "PRIVATE", "name": "Mediacorp Pte Ltd",
        "website": "https://www.mediacorp.sg",
        "description": (
            "Singapore's national media company (state-owned). "
            "Channel 5, Channel 8, CNA, 987FM. Major ad inventory across TV, radio, digital. "
            "Advertising arm: MC2 Media."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    # ── Research / Data / Analytics ────────────────────────────────────────
    {
        "ticker": "KANTAR-SG", "exchange": "PRIVATE", "name": "Kantar Singapore",
        "website": "https://www.kantar.com",
        "description": (
            "WPP-owned market research giant. Brand tracking, media measurement, "
            "consumer insights. SG APAC hub for Kantar TNS, Millward Brown."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "NIELSEN-SG", "exchange": "PRIVATE", "name": "Nielsen Singapore",
        "website": "https://www.nielsen.com",
        "description": (
            "Audience measurement and data analytics (split into Nielsen Holdings + NielsenIQ). "
            "TV ratings, digital ad measurement. SG APAC office."
        ),
        "is_sg_incorporated": True, "currency": "SGD",
    },
    {
        "ticker": "IPSOS-SG", "exchange": "PRIVATE", "name": "Ipsos Singapore",
        "website": "https://www.ipsos.com",
        "description": "French market research company (parent listed PA: IPS). SG office. Consumer, media research.",
        "is_sg_incorporated": True, "currency": "SGD",
    },
]

# Combine all company lists
ALL_COMPANIES = (
    LISTED_HOLDING_GROUPS
    + LISTED_ADTECH
    + LISTED_CONSULTING_AGENCY
    + LISTED_SGX
    + LISTED_HK
    + LISTED_GLOBAL_ADDITIONAL
    + PRIVATE_COMPANIES
)


async def seed_marketing_comms(*, dry_run: bool = False) -> int:
    """Seed all marketing_comms companies into listed_companies table.

    Returns count of companies upserted.
    """
    await init_db()

    async with async_session_factory() as session:
        # Get vertical ID
        result = await session.execute(
            select(MarketVertical).where(MarketVertical.slug == "marketing_comms")
        )
        vertical = result.scalar_one_or_none()
        if vertical is None:
            # Seed verticals first
            from packages.database.src.vertical_seeds import seed_verticals
            count = await seed_verticals(session)
            await session.commit()
            print(f"  Seeded {count} verticals")
            result = await session.execute(
                select(MarketVertical).where(MarketVertical.slug == "marketing_comms")
            )
            vertical = result.scalar_one_or_none()
            if vertical is None:
                print("ERROR: marketing_comms vertical not found after seeding!")
                return 0

        print(f"  Vertical: {vertical.name} (id={vertical.id})")
        print(f"  Companies to seed: {len(ALL_COMPANIES)}")
        print()

        created = 0
        updated = 0
        skipped = 0

        for company in ALL_COMPANIES:
            ticker = company["ticker"]
            exchange = company["exchange"]

            # Check if already exists
            existing = await session.execute(
                select(ListedCompany).where(
                    ListedCompany.ticker == ticker,
                    ListedCompany.exchange == exchange,
                )
            )
            row = existing.scalar_one_or_none()

            if row is not None:
                # Update vertical assignment if not already set
                changed = False
                if row.vertical_id is None or row.vertical_id != vertical.id:
                    row.vertical_id = vertical.id
                    changed = True
                if company.get("website") and row.website != company.get("website"):
                    row.website = company["website"]
                    changed = True
                if company.get("description") and row.description != company.get("description"):
                    row.description = company["description"]
                    changed = True

                if changed:
                    updated += 1
                    action = "UPDATE"
                else:
                    skipped += 1
                    action = "SKIP  "
            else:
                if not dry_run:
                    session.add(ListedCompany(
                        ticker=ticker,
                        exchange=exchange,
                        name=company["name"],
                        website=company.get("website"),
                        description=company.get("description"),
                        is_sg_incorporated=company.get("is_sg_incorporated", False),
                        currency=company.get("currency", "SGD"),
                        vertical_id=vertical.id,
                        listing_type=CompanyListingType.COMMON_STOCK,
                        gics_sector="Communication Services",
                        gics_industry="Advertising Agencies",
                        is_active=True,
                    ))
                created += 1
                action = "CREATE"

            status = "listed" if exchange != "PRIVATE" else "private"
            print(f"  {action} {ticker:>20}.{exchange:<8} {company['name'][:45]:<46} [{status}]")

        if not dry_run:
            await session.commit()

        print()
        print(f"  Created: {created} | Updated: {updated} | Skipped: {skipped}")
        print(f"  Total: {created + updated + skipped}")
        return created + updated


async def main() -> None:
    """Run the seed script."""
    dry_run = "--dry-run" in sys.argv

    print("=" * 78)
    print("  Marketing, Communications & Creative Agencies — Company Seed")
    print("=" * 78)
    if dry_run:
        print("  MODE: DRY RUN (no database changes)")
    print()

    try:
        count = await seed_marketing_comms(dry_run=dry_run)
        print()
        print(f"  Done. {count} companies {'would be ' if dry_run else ''}seeded/updated.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
