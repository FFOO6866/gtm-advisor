"""Web Scraper MCP Server - Direct website data extraction.

Scrapes company websites to extract:
- Tech stack (from HTML source analysis)
- Company info (from about pages)
- Team/leadership (from team pages)
- Job postings (from careers pages)

This provides free data that would otherwise require expensive
services like BuiltWith, Clearbit, or ZoomInfo.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from packages.mcp.src.base import WebScrapingMCPServer
from packages.mcp.src.types import (
    EntityReference,
    EntityType,
    EvidencedFact,
    FactType,
    MCPQueryResult,
    MCPServerConfig,
    SourceType,
)

# Tech stack detection patterns (replaces BuiltWith)
TECH_STACK_PATTERNS = {
    # Frontend frameworks
    "react": [r"react", r"__NEXT_DATA__", r"data-reactroot", r"_next/"],
    "vue": [r"__VUE__", r"v-bind", r"v-model", r"vue\.js"],
    "angular": [r"ng-app", r"ng-controller", r"angular", r"\[\(ngModel\)\]"],
    "nextjs": [r"__NEXT_DATA__", r"_next/static", r"next/head"],
    "gatsby": [r"gatsby", r"___gatsby"],
    "svelte": [r"svelte", r"__svelte"],
    # Analytics
    "google_analytics": [r"google-analytics\.com", r"gtag\(", r"ga\.js", r"googletagmanager"],
    "segment": [r"segment\.com/analytics", r"analytics\.identify"],
    "mixpanel": [r"mixpanel\.com", r"mixpanel\.track"],
    "amplitude": [r"amplitude\.com", r"amplitude\.getInstance"],
    "hotjar": [r"hotjar\.com", r"hj\("],
    "heap": [r"heap\.io", r"heap\.track"],
    # Marketing automation
    "hubspot": [r"js\.hs-scripts\.com", r"hubspot\.com", r"hs-banner"],
    "marketo": [r"marketo\.net", r"munchkin"],
    "pardot": [r"pardot\.com", r"piAId"],
    "mailchimp": [r"mailchimp\.com", r"mc\.us"],
    "sendgrid": [r"sendgrid"],
    "intercom": [r"intercom\.io", r"Intercom\("],
    # Chat/Support
    "zendesk": [r"zdassets\.com", r"zendesk\.com"],
    "drift": [r"drift\.com", r"driftt\.com"],
    "freshchat": [r"freshchat\.com"],
    "crisp": [r"crisp\.chat"],
    "tawk": [r"tawk\.to"],
    # E-commerce
    "shopify": [r"cdn\.shopify\.com", r"Shopify\."],
    "woocommerce": [r"woocommerce", r"wc-"],
    "magento": [r"Magento", r"mage/"],
    # Payments
    "stripe": [r"js\.stripe\.com", r"Stripe\("],
    "paypal": [r"paypal\.com/sdk"],
    "braintree": [r"braintreegateway"],
    # CRM signals
    "salesforce": [r"force\.com", r"salesforce\.com", r"pardot"],
    "pipedrive": [r"pipedrive\.com"],
    # CDN/Infrastructure
    "cloudflare": [r"cloudflare", r"cf-ray"],
    "aws": [r"amazonaws\.com", r"aws\.amazon"],
    "vercel": [r"vercel\.app", r"_vercel"],
    "netlify": [r"netlify\.app", r"netlify"],
    "fastly": [r"fastly"],
    "akamai": [r"akamai"],
}

# Header signals for infrastructure detection
HEADER_TECH_SIGNALS = {
    "x-powered-by": "server_tech",
    "server": "web_server",
    "x-vercel-id": "vercel",
    "cf-ray": "cloudflare",
    "x-amz-cf-id": "aws_cloudfront",
    "x-cache": "cdn",
}

# Common page paths to scrape
ABOUT_PATHS = ["/about", "/about-us", "/company", "/our-story", "/who-we-are"]
TEAM_PATHS = ["/team", "/about/team", "/leadership", "/people", "/our-team"]
CAREERS_PATHS = ["/careers", "/jobs", "/join-us", "/open-positions", "/work-with-us"]


class WebScraperMCPServer(WebScrapingMCPServer):
    """MCP Server for direct website scraping.

    Extracts evidence-backed facts from company websites:
    - Tech stack detection (free alternative to BuiltWith)
    - Company information (free alternative to Clearbit)
    - Team/leadership info
    - Job postings (intent signals)

    Example:
        server = WebScraperMCPServer.create()
        result = await server.search("https://example.com")
        for fact in result.facts:
            print(f"{fact.fact_type}: {fact.claim}")
    """

    DEFAULT_REQUEST_DELAY = 1.5  # Be polite to servers

    def __init__(self, config: MCPServerConfig) -> None:
        """Initialize web scraper."""
        super().__init__(config)
        self._http = httpx.AsyncClient(
            timeout=config.timeout_seconds,
            follow_redirects=True,
        )

    @classmethod
    def create(cls) -> WebScraperMCPServer:
        """Create a web scraper server instance."""
        config = MCPServerConfig(
            name="web-scraper",
            source_type=SourceType.WEB_SCRAPE,
            description="Direct website scraping for company and tech stack data",
            requires_api_key=False,
            rate_limit_per_hour=200,
            cache_ttl_seconds=86400,  # 24 hours
        )
        return cls(config)

    @property
    def is_configured(self) -> bool:
        """Web scraper doesn't need configuration."""
        return True

    async def _health_check_impl(self) -> bool:
        """Check if we can make HTTP requests."""
        try:
            response = await self._http.get(
                "https://httpbin.org/status/200",
                headers=self._get_headers(),
            )
            return response.status_code == 200
        except Exception:
            return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Scrape a website for data.

        Args:
            query: Website URL or domain
            **kwargs: Additional parameters:
                - scrape_tech: Detect tech stack (default True)
                - scrape_about: Scrape about page (default True)
                - scrape_team: Scrape team page (default True)
                - scrape_careers: Scrape careers page (default True)

        Returns:
            Query result with scraped facts
        """
        scrape_tech = kwargs.get("scrape_tech", True)
        scrape_about = kwargs.get("scrape_about", True)
        scrape_team = kwargs.get("scrape_team", True)
        scrape_careers = kwargs.get("scrape_careers", True)

        # Normalize URL
        url = self._normalize_url(query)
        if not url:
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=["Invalid URL provided"],
            )

        # Check cache
        cache_key = f"scrape:{url}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        facts: list[EvidencedFact] = []
        entities: list[EntityReference] = []
        errors: list[str] = []

        try:
            # Scrape homepage
            await self._respect_rate_limit()
            homepage_content, homepage_headers = await self._fetch_page(url)

            if homepage_content:
                # Extract company name from title/meta
                company_name = self._extract_company_name(homepage_content, url)

                if company_name:
                    entities.append(
                        EntityReference(
                            entity_type=EntityType.COMPANY,
                            name=company_name,
                            website=url,
                        )
                    )

                # Tech stack detection
                if scrape_tech:
                    tech_facts = self._detect_tech_stack(
                        homepage_content, homepage_headers, url, company_name
                    )
                    facts.extend(tech_facts)

                # Meta description as company info
                description = self._extract_meta_description(homepage_content)
                if description and company_name:
                    facts.append(
                        self.create_fact(
                            claim=f"{company_name}: {description}",
                            fact_type=FactType.COMPANY_INFO.value,
                            source_name=company_name,
                            source_url=url,
                            raw_excerpt=description,
                            confidence=0.80,
                            extracted_data={"description": description},
                            related_entities=[company_name],
                        )
                    )

            # Scrape additional pages
            tasks = []
            if scrape_about:
                tasks.append(self._scrape_about_page(url, company_name or "Company"))
            if scrape_team:
                tasks.append(self._scrape_team_page(url, company_name or "Company"))
            if scrape_careers:
                tasks.append(self._scrape_careers_page(url, company_name or "Company"))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, list):
                        facts.extend(result)
                    elif isinstance(result, Exception):
                        self._logger.debug("page_scrape_failed", error=str(result))

        except Exception as e:
            errors.append(f"Scraping failed: {str(e)}")

        result = MCPQueryResult(
            facts=facts,
            entities=entities,
            query=query,
            mcp_server=self.name,
            total_results=len(facts),
            errors=errors,
        )

        self._set_cached(cache_key, result)
        return result

    def _normalize_url(self, query: str) -> str | None:
        """Normalize URL/domain to full URL."""
        query = query.strip()

        # Add protocol if missing
        if not query.startswith(("http://", "https://")):
            query = f"https://{query}"

        # Validate URL
        try:
            parsed = urlparse(query)
            if not parsed.netloc:
                return None
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return None

    async def _fetch_page(
        self, url: str
    ) -> tuple[str | None, dict[str, str]]:
        """Fetch a page and return content + headers."""
        try:
            response = await self._http.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.text, dict(response.headers)
        except Exception as e:
            self._logger.debug("fetch_failed", url=url, error=str(e))
            return None, {}

    def _extract_company_name(self, html: str, url: str) -> str | None:
        """Extract company name from page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try title tag
        title = soup.find("title")
        if title and title.text:
            # Clean up title - often "Company Name | Tagline"
            name = title.text.split("|")[0].split("-")[0].split("–")[0].strip()
            if len(name) < 50:  # Reasonable length
                return name

        # Try OG site name
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            return og_site["content"].strip()

        # Fall back to domain
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain.split(".")[0].title()

    def _extract_meta_description(self, html: str) -> str | None:
        """Extract meta description from page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try standard meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()[:500]

        # Try OG description
        og = soup.find("meta", property="og:description")
        if og and og.get("content"):
            return og["content"].strip()[:500]

        return None

    def _detect_tech_stack(
        self,
        html: str,
        headers: dict[str, str],
        url: str,
        company_name: str | None,
    ) -> list[EvidencedFact]:
        """Detect tech stack from HTML and headers."""
        facts = []
        detected_tech = []

        # Scan HTML for patterns
        html_lower = html.lower()
        for tech_name, patterns in TECH_STACK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html_lower, re.IGNORECASE):
                    detected_tech.append(tech_name)
                    break

        # Check headers
        for header, tech_category in HEADER_TECH_SIGNALS.items():
            if header.lower() in {k.lower() for k in headers}:
                header_value = headers.get(header, "")
                if header_value:
                    detected_tech.append(f"{tech_category}:{header_value[:50]}")

        # Remove duplicates
        detected_tech = list(set(detected_tech))

        if detected_tech:
            company = company_name or urlparse(url).netloc
            facts.append(
                self.create_fact(
                    claim=f"{company} uses: {', '.join(detected_tech[:15])}",
                    fact_type=FactType.TECHNOLOGY.value,
                    source_name=company,
                    source_url=url,
                    confidence=0.85,
                    extracted_data={
                        "tech_stack": detected_tech,
                        "detection_method": "html_analysis",
                    },
                    related_entities=[company] if company_name else [],
                )
            )

            # Create individual tech facts for important ones
            important_tech = ["salesforce", "hubspot", "stripe", "shopify"]
            for tech in detected_tech:
                if tech in important_tech:
                    facts.append(
                        self.create_fact(
                            claim=f"{company} uses {tech}",
                            fact_type=FactType.TECHNOLOGY.value,
                            source_name=company,
                            source_url=url,
                            confidence=0.90,
                            extracted_data={"technology": tech},
                            related_entities=[company] if company_name else [],
                        )
                    )

        return facts

    async def _scrape_about_page(
        self, base_url: str, company_name: str
    ) -> list[EvidencedFact]:
        """Scrape about page for company information."""
        facts = []

        for path in ABOUT_PATHS:
            await self._respect_rate_limit()
            url = urljoin(base_url, path)
            content, _ = await self._fetch_page(url)

            if content:
                soup = BeautifulSoup(content, "html.parser")

                # Extract main content
                main_content = soup.find("main") or soup.find("article") or soup.body
                if main_content:
                    text = main_content.get_text(separator=" ", strip=True)[:2000]

                    # Look for company facts
                    facts_found = self._extract_about_facts(text, url, company_name)
                    facts.extend(facts_found)

                break  # Found an about page

        return facts

    def _extract_about_facts(
        self, text: str, url: str, company_name: str
    ) -> list[EvidencedFact]:
        """Extract facts from about page text."""
        facts = []
        text_lower = text.lower()

        # Founded year
        year_match = re.search(r"founded\s+(?:in\s+)?(\d{4})", text_lower)
        if year_match:
            year = year_match.group(1)
            facts.append(
                self.create_fact(
                    claim=f"{company_name} was founded in {year}",
                    fact_type=FactType.COMPANY_INFO.value,
                    source_name=company_name,
                    source_url=url,
                    raw_excerpt=text_lower[max(0, year_match.start() - 50) : year_match.end() + 50],
                    confidence=0.85,
                    extracted_data={"founded_year": year},
                    related_entities=[company_name],
                )
            )

        # Employee count
        emp_patterns = [
            r"(\d+[\d,]*)\s*(?:employees|team members|people)",
            r"team of\s*(\d+[\d,]*)",
        ]
        for pattern in emp_patterns:
            match = re.search(pattern, text_lower)
            if match:
                count = match.group(1).replace(",", "")
                facts.append(
                    self.create_fact(
                        claim=f"{company_name} has approximately {count} employees",
                        fact_type=FactType.COMPANY_INFO.value,
                        source_name=company_name,
                        source_url=url,
                        confidence=0.75,
                        extracted_data={"employee_count": int(count)},
                        related_entities=[company_name],
                    )
                )
                break

        return facts

    async def _scrape_team_page(
        self, base_url: str, company_name: str
    ) -> list[EvidencedFact]:
        """Scrape team page for leadership information."""
        facts = []

        for path in TEAM_PATHS:
            await self._respect_rate_limit()
            url = urljoin(base_url, path)
            content, _ = await self._fetch_page(url)

            if content:
                soup = BeautifulSoup(content, "html.parser")

                # Look for team member cards
                executives = self._extract_team_members(soup)

                for exec_info in executives[:10]:  # Limit
                    facts.append(
                        self.create_fact(
                            claim=f"{exec_info['name']} is {exec_info['title']} at {company_name}",
                            fact_type=FactType.EXECUTIVE.value,
                            source_name=company_name,
                            source_url=url,
                            confidence=0.80,
                            extracted_data=exec_info,
                            related_entities=[company_name, exec_info["name"]],
                        )
                    )

                break

        return facts

    def _extract_team_members(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract team member info from page."""
        members = []

        # Common patterns for team cards
        patterns = [
            {"container": "div", "class_": re.compile(r"team|member|person|card")},
            {"container": "article", "class_": re.compile(r"team|member")},
            {"container": "li", "class_": re.compile(r"team|member")},
        ]

        for pattern in patterns:
            cards = soup.find_all(
                pattern["container"],
                class_=pattern.get("class_"),
            )[:20]

            for card in cards:
                # Try to find name and title
                name_elem = card.find(["h2", "h3", "h4", "strong"])
                title_elem = card.find(["p", "span"], class_=re.compile(r"title|role|position"))

                if name_elem and title_elem:
                    name = name_elem.get_text(strip=True)
                    title = title_elem.get_text(strip=True)

                    # Validate - names shouldn't be too long
                    if len(name) < 50 and len(title) < 100:
                        members.append({"name": name, "title": title})

            if members:
                break

        return members

    async def _scrape_careers_page(
        self, base_url: str, company_name: str
    ) -> list[EvidencedFact]:
        """Scrape careers page for job posting signals."""
        facts = []

        for path in CAREERS_PATHS:
            await self._respect_rate_limit()
            url = urljoin(base_url, path)
            content, _ = await self._fetch_page(url)

            if content:
                soup = BeautifulSoup(content, "html.parser")

                # Count job listings
                job_links = soup.find_all("a", href=re.compile(r"job|position|career|apply"))
                job_count = len(job_links)

                if job_count > 0:
                    facts.append(
                        self.create_fact(
                            claim=f"{company_name} has approximately {job_count} open positions",
                            fact_type=FactType.HIRING.value,
                            source_name=company_name,
                            source_url=url,
                            confidence=0.75,
                            extracted_data={
                                "job_count": job_count,
                                "signal_type": "hiring_activity",
                            },
                            related_entities=[company_name],
                        )
                    )

                # Look for specific role types (intent signals)
                text = soup.get_text().lower()
                hiring_signals = {
                    "sales": ["sales", "account executive", "sdr", "bdr"],
                    "engineering": ["engineer", "developer", "architect"],
                    "marketing": ["marketing", "growth", "content"],
                }

                for category, keywords in hiring_signals.items():
                    if any(kw in text for kw in keywords):
                        facts.append(
                            self.create_fact(
                                claim=f"{company_name} is hiring for {category} roles",
                                fact_type=FactType.HIRING.value,
                                source_name=company_name,
                                source_url=url,
                                confidence=0.70,
                                extracted_data={
                                    "hiring_category": category,
                                    "signal_type": "department_expansion",
                                },
                                related_entities=[company_name],
                            )
                        )

                break

        return facts

    async def close(self) -> None:
        """Close HTTP client."""
        await self._http.aclose()
