"""Singapore government reference data scraper.

Scrapes public data from:
- IMDA PSG marketplace (approved vendor list)
- PDPC enforcement register (recent decisions)
- EnterpriseSG press releases / programmes
- MAS regulatory calendar (consultation deadlines)

All sources are publicly available Singapore government websites.
Each method returns (items: list[dict], error: str | None).
If error is not None, items may be empty — callers should log and use fallback.
"""

from __future__ import annotations

import re

import aiohttp
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Static fallback data
# ---------------------------------------------------------------------------

PSG_STATIC_FALLBACK = [
    {
        "title": "PSG - Productivity Solutions Grant",
        "source": "imda_static",
        "category_type": "psg_overview",
        "summary": (
            "PSG supports SMEs in adopting IT solutions and equipment to enhance business processes. "
            "Eligible companies can receive up to 50% funding support on qualifying costs. "
            "Eligibility: registered in Singapore, ≥30% local shareholding, annual turnover ≤SGD 100M "
            "OR ≤200 employees. Solutions span: retail, food, logistics, precision engineering, "
            "construction, landscaping, accounting, HR, CRM, cybersecurity, digital marketing."
        ),
        "last_verified": "2026-01-01",
        "url": "https://www.imda.gov.sg/programme-listing/productivity-solutions-grant",
    },
    {
        "title": "EDG - Enterprise Development Grant",
        "source": "imda_static",
        "category_type": "grant_overview",
        "summary": (
            "EDG funds projects that help businesses grow and transform. Up to 50% funding support "
            "(70% for SMEs). Covers: Core Capabilities (business strategy, financial management), "
            "Innovation & Productivity (process redesign, automation), Market Access (overseas expansion). "
            "Minimum project cost SGD 30,000. Company must be registered in Singapore."
        ),
        "last_verified": "2026-01-01",
        "url": "https://www.enterprisesg.gov.sg/financial-assistance/grants/for-local-companies/enterprise-development-grant",
    },
    {
        "title": "MRA - Market Readiness Assistance Grant",
        "source": "imda_static",
        "category_type": "grant_overview",
        "summary": (
            "MRA helps SMEs go overseas with funding support of up to 50% of qualifying costs, capped at "
            "SGD 100,000 per company per new market. Covers: overseas market promotion, business development, "
            "market entry (incorporation, regulatory compliance). One application per company per market."
        ),
        "last_verified": "2026-01-01",
        "url": "https://www.enterprisesg.gov.sg/financial-assistance/grants/for-local-companies/market-readiness-assistance-grant",
    },
    {
        "title": "PDPA - Personal Data Protection Act compliance for B2B marketing",
        "source": "pdpc_static",
        "category_type": "compliance",
        "summary": (
            "Key PDPA rules for B2B GTM: (1) Obtain clear consent before collecting personal data for marketing. "
            "(2) Provide opt-out in every marketing communication. (3) Do Not Call (DNC) registry applies to "
            "marketing calls/SMS to Singapore numbers — check before outreach. (4) B2B email to corporate "
            "addresses under the business context exception: allowed if recipient's role is relevant to the "
            "product/service. (5) Data breach notification to PDPC within 3 days if >500 individuals affected. "
            "(6) Appoint a Data Protection Officer (DPO) — mandatory for all organisations."
        ),
        "last_verified": "2026-01-01",
        "url": "https://www.pdpc.gov.sg/overview-of-pdpa/the-legislation/personal-data-protection-act",
    },
    {
        "title": "Singapore SME Landscape 2026",
        "source": "enterprisesg_static",
        "category_type": "market_data",
        "summary": (
            "Singapore has approximately 280,000 SMEs (enterprises with <200 employees), accounting for 99% "
            "of enterprises and employing 70% of the workforce. Key tech-forward verticals: "
            "ICT/SaaS (15,000+ companies), Fintech (1,000+ MAS-licensed entities), "
            "Professional Services (50,000+), F&B (20,000+). "
            "Average SME digital adoption: 70% (up from 52% in 2020). "
            "PSG uptake rate: 20,000+ SMEs per year. Average deal size for B2B SaaS sold to Singapore SMEs: "
            "SGD 15,000–80,000 ACV. Typical sales cycle: 4–12 weeks."
        ),
        "last_verified": "2026-01-01",
        "url": "https://www.enterprisesg.gov.sg/about-us/annual-reports",
    },
]

_TIMEOUT = aiohttp.ClientTimeout(total=10)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GTMAdvisor/1.0; +https://gtm-advisor.sg)"
    ),
}

_INDUSTRY_KEYWORDS = [
    "Financial", "Healthcare", "Retail", "Education", "Technology",
    "Telecommunications", "Real Estate", "Insurance", "Legal",
    "Government", "Hospitality", "Media",
]


async def _fetch_html(url: str) -> tuple[str, str | None]:
    """Fetch a URL and return (html, error). Never raises."""
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT, headers=_HEADERS) as session, \
                session.get(url) as resp:
            return await resp.text(), None
    except Exception as e:
        return "", str(e)


class SgReferenceScraper:
    """Scrapes public Singapore government websites for grant and regulatory data."""

    async def scrape_psg_vendors(self) -> tuple[list[dict], str | None]:
        """Scrape the IMDA PSG marketplace for approved solution categories/vendors.

        Returns:
            Tuple of (items, error). Items contain dicts with title, category, url,
            source, and category_type. Falls back to PSG_STATIC_FALLBACK on parse
            failure. On network error, returns ([], error_str).
        """
        url = "https://www.imda.gov.sg/programme-listing/productivity-solutions-grant"
        html, error = await _fetch_html(url)
        if error:
            return [], error

        try:
            soup = BeautifulSoup(html, "html.parser")
            items: list[dict] = []

            # Try to find solution category links or vendor cards
            for tag in soup.find_all(["h2", "h3", "h4", "a"], limit=200):
                text = tag.get_text(strip=True)
                if not text or len(text) < 5:
                    continue
                href = tag.get("href", "") if tag.name == "a" else ""
                if href and not href.startswith("http"):
                    href = "https://www.imda.gov.sg" + href
                items.append({
                    "title": text[:300],
                    "category": "PSG Solution",
                    "url": href or url,
                    "source": "imda",
                    "category_type": "psg_vendor",
                })

            if not items:
                return PSG_STATIC_FALLBACK, None

            return items[:50], None

        except Exception:
            return PSG_STATIC_FALLBACK, None

    async def scrape_pdpc_decisions(self) -> tuple[list[dict], str | None]:
        """Scrape the PDPC enforcement decisions register.

        Extracts title, date, sector, and URL for each decision. Returns at most
        20 most recent decisions.

        Returns:
            Tuple of (items, error).
        """
        url = "https://www.pdpc.gov.sg/all-commissions-decisions"
        html, error = await _fetch_html(url)
        if error:
            return [], error

        try:
            soup = BeautifulSoup(html, "html.parser")
            items: list[dict] = []

            # Look for decision entries — each typically in a list item or article element
            for container in soup.find_all(["li", "article", "div"], limit=300):
                link = container.find("a", href=True)
                if not link:
                    continue
                title = link.get_text(strip=True)
                if not title or len(title) < 10:
                    continue
                href = link["href"]
                if not href.startswith("http"):
                    href = "https://www.pdpc.gov.sg" + href

                # Try to extract date and sector from surrounding text
                text_content = container.get_text(" ", strip=True)
                date_str = ""
                sector = ""

                date_match = re.search(r"\d{1,2}\s+\w+\s+\d{4}", text_content)
                if date_match:
                    date_str = date_match.group(0)

                for kw in _INDUSTRY_KEYWORDS:
                    if kw.lower() in text_content.lower():
                        sector = kw
                        break

                items.append({
                    "title": title[:500],
                    "date": date_str,
                    "sector": sector,
                    "url": href,
                    "source": "pdpc",
                    "category_type": "enforcement",
                })

                if len(items) >= 20:
                    break

            return items, None

        except Exception as e:
            return [], str(e)

    async def scrape_enterprisesg_programmes(self) -> tuple[list[dict], str | None]:
        """Scrape EnterpriseSG grants page for grant names, descriptions, and eligibility.

        Returns:
            Tuple of (items, error).
        """
        url = "https://www.enterprisesg.gov.sg/financial-assistance/grants"
        html, error = await _fetch_html(url)
        if error:
            return [], error

        try:
            soup = BeautifulSoup(html, "html.parser")
            items: list[dict] = []

            for tag in soup.find_all(["h2", "h3", "h4"], limit=100):
                title = tag.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                # Look for description in the next sibling paragraph
                description = ""
                sibling = tag.find_next_sibling(["p", "div"])
                if sibling:
                    description = sibling.get_text(" ", strip=True)[:500]

                # Try to find a link nearby
                link = tag.find("a", href=True) or tag.find_next("a", href=True)
                href = ""
                if link:
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://www.enterprisesg.gov.sg" + href

                items.append({
                    "title": title[:300],
                    "description": description,
                    "url": href or url,
                    "source": "enterprisesg",
                    "category_type": "grant",
                })

            return items, None

        except Exception as e:
            return [], str(e)

    async def scrape_mas_consultations(self) -> tuple[list[dict], str | None]:
        """Scrape MAS regulatory consultations page for open/recent consultations.

        Returns at most 10 most recent consultations.

        Returns:
            Tuple of (items, error).
        """
        url = "https://www.mas.gov.sg/regulation/consultations"
        html, error = await _fetch_html(url)
        if error:
            return [], error

        try:
            soup = BeautifulSoup(html, "html.parser")
            items: list[dict] = []

            for container in soup.find_all(["li", "article", "div"], limit=300):
                link = container.find("a", href=True)
                if not link:
                    continue
                title = link.get_text(strip=True)
                if not title or len(title) < 10:
                    continue
                href = link["href"]
                if not href.startswith("http"):
                    href = "https://www.mas.gov.sg" + href

                text_content = container.get_text(" ", strip=True)
                deadline = ""
                date_match = re.search(r"\d{1,2}\s+\w+\s+\d{4}", text_content)
                if date_match:
                    deadline = date_match.group(0)

                items.append({
                    "title": title[:500],
                    "deadline": deadline,
                    "url": href,
                    "source": "mas",
                    "category_type": "regulation",
                })

                if len(items) >= 10:
                    break

            return items, None

        except Exception as e:
            return [], str(e)
