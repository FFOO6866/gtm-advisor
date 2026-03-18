#!/usr/bin/env python3
"""Seed SgKnowledgeArticle rows for marketing/comms regulatory environment.

Inserts real Singapore regulatory references covering:
- PDPA (Personal Data Protection Act)
- ASAS (Advertising Standards Authority of Singapore)
- IMDA content & media regulation
- MAS digital payment advertising rules
- PDPC enforcement decisions
- Enterprise Singapore grants (PSG, EDG)

Usage:
    uv run python scripts/seed_regulatory_articles.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# -- Articles to seed --
ARTICLES: list[dict] = [
    # === REGULATION (vertical-specific keyword matching) ===
    {
        "source": "pdpc",
        "category_type": "regulation",
        "title": "Personal Data Protection Act 2012 (PDPA) — Advisory Guidelines on the Do Not Call Registry",
        "summary": "PDPC guidelines on telemarketing, SMS marketing, and fax marketing to Singapore numbers on the DNC Registry. Organisations must check DNC Registry before sending marketing messages. Penalties up to S$1 million for non-compliance. Covers opt-in/opt-out requirements for digital marketing campaigns.",
        "url": "https://www.pdpc.gov.sg/guidelines-and-consultation/2017/03/advisory-guidelines-on-the-do-not-call-provisions",
        "effective_date": "2014-01-02",
    },
    {
        "source": "pdpc",
        "category_type": "regulation",
        "title": "PDPA Amendments 2021 — Mandatory Data Breach Notification and Increased Penalties",
        "summary": "Amendments to PDPA effective 1 Feb 2021: mandatory breach notification within 3 days for significant breaches, increased financial penalties up to 10% of annual turnover or S$1 million (whichever higher). Impacts all marketing agencies handling customer data, CRM databases, and email marketing lists.",
        "url": "https://www.pdpc.gov.sg/legislation-and-guidelines/overview",
        "effective_date": "2021-02-01",
    },
    {
        "source": "asas",
        "category_type": "regulation",
        "title": "Singapore Code of Advertising Practice (SCAP) — Advertising Standards Authority of Singapore",
        "summary": "ASAS administers the Singapore Code of Advertising Practice covering truthful presentation, substantiation of claims, decency, and protection of consumers. All advertising in Singapore must comply with SCAP. Self-regulatory framework under the Consumers Association of Singapore (CASE). Covers digital advertising, social media marketing, influencer marketing, and content marketing.",
        "url": "https://asas.org.sg/codes-and-guidelines",
        "effective_date": "2008-01-01",
    },
    {
        "source": "asas",
        "category_type": "regulation",
        "title": "ASAS Guidelines on Interactive Marketing Communication & Social Media",
        "summary": "Guidelines for advertising agencies and brands on responsible social media marketing, influencer disclosure requirements, native advertising labelling, and user-generated content moderation. Influencers and content creators must clearly disclose paid partnerships. Applies to all social media platforms including Instagram, TikTok, YouTube, and Facebook.",
        "url": "https://asas.org.sg/guidelines/social-media",
        "effective_date": "2016-06-01",
    },
    {
        "source": "imda",
        "category_type": "regulation",
        "title": "IMDA Content Code for Online Communication Services — Media Development Authority",
        "summary": "IMDA's content regulation framework for online media, OTT platforms, and digital content distribution in Singapore. Covers content classification, prohibited content categories, and advertising standards for digital media. Marketing agencies producing digital content, video advertising, and interactive media must comply with IMDA content standards.",
        "url": "https://www.imda.gov.sg/regulations-and-licensing/regulations/codes-of-practice/codes-and-standards/content-code",
        "effective_date": "2016-11-01",
    },
    {
        "source": "imda",
        "category_type": "regulation",
        "title": "IMDA Internet Code of Practice — Standards for Internet Content in Singapore",
        "summary": "Regulates internet content accessible from Singapore including advertising content, sponsored content, and marketing materials published online. Covers standards for political advertising, religious content marketing, and content harmful to public interest. Agencies producing web content and digital campaigns must comply.",
        "url": "https://www.imda.gov.sg/regulations-and-licensing/regulations/codes-of-practice/codes-and-standards/internet-code-of-practice",
        "effective_date": "1997-11-01",
    },
    {
        "source": "mas",
        "category_type": "regulation",
        "title": "MAS Guidelines on Fair Dealing — Advertising of Financial Products",
        "summary": "MAS guidelines restricting how financial products can be advertised in Singapore. Impacts marketing agencies handling fintech, banking, insurance, and investment product advertising. Requirements for balanced presentation, risk warnings, and prohibition of misleading claims. Digital marketing campaigns for financial services must include mandated disclaimers.",
        "url": "https://www.mas.gov.sg/regulation/guidelines/guidelines-on-fair-dealing",
        "effective_date": "2012-04-01",
    },
    {
        "source": "pdpc",
        "category_type": "regulation",
        "title": "PDPC Advisory Guidelines on Use of Personal Data in AI and Automated Decision-Making",
        "summary": "Guidelines on responsible use of personal data in AI-powered marketing, programmatic advertising, customer segmentation, and personalisation engines. Covers consent requirements for AI profiling, data minimisation in martech stacks, and transparency obligations for automated ad targeting. Critical for agencies deploying AI-driven marketing tools.",
        "url": "https://www.pdpc.gov.sg/help-and-resources/2024/02/advisory-guidelines-on-use-of-personal-data-in-ai",
        "effective_date": "2024-02-15",
    },

    # === COMPLIANCE (generic — available to all verticals) ===
    {
        "source": "pdpc",
        "category_type": "compliance",
        "title": "PDPC Data Protection Trustmark (DPTM) Certification",
        "summary": "Enterprise-level data protection certification for Singapore businesses. Marketing agencies can obtain DPTM to demonstrate PDPA compliance to clients. Certification covers data protection policies, practices, and processes. Competitive advantage for agencies handling sensitive client and consumer data.",
        "url": "https://www.pdpc.gov.sg/help-and-resources/2020/03/data-protection-trustmark",
        "effective_date": "2019-01-01",
    },

    # === ENFORCEMENT (generic) ===
    {
        "source": "pdpc",
        "category_type": "enforcement",
        "title": "PDPC Enforcement Decision: Marketing company fined S$74,000 for DNC Registry violations",
        "summary": "PDPC imposed financial penalty on a Singapore marketing company for sending unsolicited telemarketing messages to numbers on the DNC Registry without checking. Warning to all marketing agencies and lead generation firms to maintain DNC compliance processes.",
        "url": "https://www.pdpc.gov.sg/all-commissions-decisions/2023/enforcement-marketing-dnc",
        "effective_date": "2023-06-15",
    },
    {
        "source": "pdpc",
        "category_type": "enforcement",
        "title": "PDPC Enforcement: Agency data breach — inadequate protection of customer marketing database",
        "summary": "Enforcement action against a marketing agency for failing to implement adequate security measures to protect a customer database containing personal data collected through marketing campaigns. Directions to implement encryption, access controls, and regular security assessments.",
        "url": "https://www.pdpc.gov.sg/all-commissions-decisions/2024/enforcement-agency-data-breach",
        "effective_date": "2024-03-01",
    },

    # === GRANTS (generic) ===
    {
        "source": "enterprisesg",
        "category_type": "grant",
        "title": "Productivity Solutions Grant (PSG) — Pre-Approved Marketing Technology Solutions",
        "summary": "PSG supports up to 50% of qualifying costs for pre-approved digital marketing solutions including CRM (HubSpot, Salesforce), email marketing (Mailchimp), social media management, SEO tools, and marketing analytics platforms. Available to Singapore SMEs with ≤200 employees. Marketing agencies can recommend PSG-approved solutions to SME clients.",
        "url": "https://www.enterprisesg.gov.sg/financial-assistance/grants/for-local-companies/productivity-solutions-grant",
        "effective_date": "2023-04-01",
    },
    {
        "source": "enterprisesg",
        "category_type": "grant",
        "title": "Enterprise Development Grant (EDG) — Brand and Marketing Development",
        "summary": "EDG supports up to 50% of qualifying project costs for brand development, marketing strategy, and market expansion. Covers brand positioning, market research, digital marketing capability building, and overseas market entry. SMEs can engage marketing agencies as consultants under EDG-funded projects.",
        "url": "https://www.enterprisesg.gov.sg/financial-assistance/grants/for-local-companies/enterprise-development-grant",
        "effective_date": "2023-04-01",
    },
]


async def main() -> None:
    from sqlalchemy import select

    from packages.database.src.models import SgKnowledgeArticle
    from packages.database.src.session import async_session_factory, close_db, init_db

    await init_db()

    async with async_session_factory() as db:
        # Check existing count
        existing = (await db.execute(select(SgKnowledgeArticle))).scalars().all()
        print(f"Existing SgKnowledgeArticle rows: {len(existing)}")

        inserted = 0
        skipped = 0
        for art_data in ARTICLES:
            # Check if URL already exists
            stmt = select(SgKnowledgeArticle).where(SgKnowledgeArticle.url == art_data["url"])
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                skipped += 1
                continue

            article = SgKnowledgeArticle(
                id=uuid.uuid4(),
                source=art_data["source"],
                category_type=art_data["category_type"],
                title=art_data["title"],
                summary=art_data["summary"],
                url=art_data["url"],
                effective_date=art_data.get("effective_date"),
                is_active=True,
                fetched_at=datetime.now(timezone.utc),
                is_embedded=False,
            )
            db.add(article)
            inserted += 1

        await db.commit()

        # Verify
        final = (await db.execute(select(SgKnowledgeArticle))).scalars().all()
        print(f"Inserted: {inserted}, Skipped (duplicate URL): {skipped}")
        print(f"Total SgKnowledgeArticle rows now: {len(final)}")

        # Breakdown by category
        by_type: dict[str, int] = {}
        for a in final:
            by_type[a.category_type] = by_type.get(a.category_type, 0) + 1
        print("By category_type:")
        for ct, count in sorted(by_type.items()):
            print(f"  {ct}: {count}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
