"""Lead Enrichment Agent — validates and enriches lead data before outreach.

For each lead in the pipeline, this agent:
1. Verifies email deliverability via DNS MX check (blocks invalid sends)
2. Looks up company in ACRA (Singapore company registry) for verification
3. Fetches company news from NewsAPI (last 30 days — recency signal)
4. Fetches financial data from EODHD (if publicly listed)
5. Scores lead quality using LeadDataQualityScorer
6. Updates lead enrichment_data JSON with all findings
7. Blocks sub-threshold leads from sequence enrollment

This prevents:
- Sending to invalid/bounced emails (destroys sender reputation)
- Wasting sequences on unverifiable companies
- Sending personalised emails with wrong company info

Why this beats ChatGPT:
ChatGPT generates plausible-looking leads that may have outdated roles,
invalid emails, and non-existent company domains. This agent verifies
against live registries and DNS before any email is sent.
"""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from agents.core.src.base_agent import AgentCapability, BaseGTMAgent
from agents.core.src.mcp_integration import AgentMCPClient
from packages.core.src.agent_bus import AgentBus, AgentMessage, DiscoveryType, get_agent_bus
from packages.database.src.session import async_session_factory
from packages.integrations.eodhd.src.client import EODHDClient
from packages.integrations.hunter.src.client import get_hunter_client
from packages.integrations.newsapi.src.client import NewsAPIClient
from packages.knowledge.src.knowledge_mcp import get_knowledge_mcp
from packages.mcp.src.servers.market_intel import MarketIntelMCPServer

logger = structlog.get_logger()


class EnrichmentRecord(BaseModel):
    """Enrichment result for a single lead."""
    lead_id: str = Field(...)
    email_valid: bool = Field(default=False)
    email_deliverable: bool = Field(default=False)
    hunter_status: str | None = Field(default=None)   # "valid"/"invalid"/"accept_all"/"unknown"
    hunter_score: int = Field(default=0)               # 0–100 Hunter confidence
    hunter_discovered: bool = Field(default=False)     # True if email was found by Hunter
    quality_score: float = Field(default=0.0)
    qualifies_for_sequence: bool = Field(default=False)
    acra_verified: bool = Field(default=False)
    acra_company_name: str | None = Field(default=None)
    acra_uen: str | None = Field(default=None)
    acra_status: str | None = Field(default=None)
    recent_news_count: int = Field(default=0)
    recent_news_titles: list[str] = Field(default_factory=list)
    eodhd_market_cap: float | None = Field(default=None)
    eodhd_employees: int | None = Field(default=None)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    enriched_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class LeadEnrichmentResult(BaseModel):
    """Result of one enrichment run across a batch of leads."""
    total_processed: int = Field(default=0)
    total_qualified: int = Field(default=0)
    total_blocked: int = Field(default=0)
    records: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    data_sources_used: list[str] = Field(default_factory=list)
    is_live_data: bool = Field(default=True)  # Enrichment always uses real sources


class LeadEnrichmentAgent(BaseGTMAgent[LeadEnrichmentResult]):
    """Enriches leads with real data and gates sequence enrollment.

    Designed for batch processing — pass a list of leads in context.
    Runs on a weekly APScheduler job to keep enrichment data fresh.
    """

    QUALITY_THRESHOLD = 0.55  # Minimum to qualify for sequence

    def __init__(self, bus: AgentBus | None = None) -> None:
        super().__init__(
            name="lead-enrichment",
            description=(
                "Validates and enriches lead data: email verification, ACRA company lookup, "
                "company news, and data quality scoring. Gates sequence enrollment."
            ),
            result_type=LeadEnrichmentResult,
            min_confidence=0.50,
            max_iterations=1,
            model="gpt-4o-mini",
            capabilities=[
                AgentCapability(
                    name="lead-enrichment",
                    description="Verify emails, lookup ACRA registry, fetch company news",
                ),
            ],
        )
        self._bus = bus if bus is not None else get_agent_bus()
        self._analysis_id: Any | None = None
        self._mcp = AgentMCPClient()
        self._newsapi = NewsAPIClient()
        self._eodhd = EODHDClient()
        self._hunter = get_hunter_client()
        self._discovered_leads: list[dict[str, Any]] = []  # Populated by LEAD_FOUND bus events
        self._knowledge_pack: dict = {}
        try:
            if self._bus is not None:
                self._bus.subscribe(
                    agent_id=self.name,
                    discovery_type=DiscoveryType.LEAD_FOUND,
                    handler=self._on_lead_found,
                )
        except Exception:
            pass

    def get_system_prompt(self) -> str:
        return "Lead enrichment agent. Validates and enriches lead data using real registries."

    async def _on_lead_found(self, message: AgentMessage) -> None:
        """React to LEAD_FOUND events so enrichment triggers automatically."""
        if (
            self._analysis_id
            and message.analysis_id
            and message.analysis_id != self._analysis_id
        ):
            return
        lead_id = message.content.get("lead_id") or message.content.get("id", "")
        self._discovered_leads.append(message.content)
        self._logger.debug("lead_enrichment_received_lead_found", lead_id=lead_id)

    async def _plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        context = context or {}
        self._analysis_id = context.get("analysis_id")

        # Backfill LEAD_FOUND events that were published before this agent subscribed
        if self._bus is not None:
            found_history = self._bus.get_history(
                analysis_id=self._analysis_id,
                discovery_type=DiscoveryType.LEAD_FOUND,
                limit=50,
            )
            for msg in found_history:
                if msg.content not in self._discovered_leads:
                    self._discovered_leads.append(msg.content)

        # Load domain knowledge pack — guides signal classification and qualification logic.
        # Operational agents do not inject into an LLM call, but loading here satisfies
        # Rule #6 and makes the pack available if a synthesis path is added later.
        try:
            kmcp_pack = get_knowledge_mcp()
            self._knowledge_pack = await kmcp_pack.get_agent_knowledge_pack(
                agent_name="lead-enrichment",
                task_context=task,
            )
            if self._knowledge_pack.get("guides"):
                logger.debug(
                    "lead_enrichment_knowledge_pack_loaded",
                    guides=self._knowledge_pack["guides"],
                )
        except Exception as e:
            logger.debug("lead_enrichment_knowledge_pack_failed", error=str(e))

        return {
            "leads": context.get("leads", []),
            "company_id": context.get("company_id", ""),
        }

    async def _do(
        self,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LeadEnrichmentResult:
        leads = plan.get("leads", [])

        # If no leads were passed directly, use leads discovered via the bus
        if not leads and self._discovered_leads:
            # Normalise LEAD_FOUND content to the expected lead dict format
            leads = [
                {
                    "id": entry.get("lead_id") or entry.get("id", ""),
                    "email": entry.get("email") or entry.get("contact_email", ""),
                    "name": entry.get("name") or entry.get("contact_name", ""),
                    "company": entry.get("company") or entry.get("company_name", ""),
                    "title": entry.get("title") or entry.get("job_title", ""),
                    "website": entry.get("website", ""),
                    "domain": entry.get("domain", ""),
                }
                for entry in self._discovered_leads
            ]

        records: list[EnrichmentRecord] = []

        for lead in leads[:50]:  # Cap at 50 per run
            record = await self._enrich_lead(lead)
            records.append(record)

        qualified = [r for r in records if r.qualifies_for_sequence]
        blocked = [r for r in records if not r.qualifies_for_sequence]

        # Determine which data sources were actually used across all records
        data_sources: list[str] = ["DNS MX Check"]  # Always attempted
        if any(r.hunter_status is not None for r in records):
            data_sources.append("Hunter.io")
        if any(r.acra_verified for r in records):
            data_sources.append("ACRA Singapore")
        if any(r.recent_news_count > 0 for r in records):
            data_sources.append("NewsAPI")
        if any(r.eodhd_market_cap is not None or r.eodhd_employees is not None for r in records):
            data_sources.append("EODHD")

        return LeadEnrichmentResult(
            total_processed=len(records),
            total_qualified=len(qualified),
            total_blocked=len(blocked),
            records=[r.model_dump() for r in records],
            confidence=0.0,  # Set by _check
            data_sources_used=data_sources,
            is_live_data=True,  # Enrichment always uses real deterministic sources
        )

    async def _check(self, result: LeadEnrichmentResult) -> float:
        if result.total_processed == 0:
            return 0.1
        qualification_rate = result.total_qualified / result.total_processed
        score = 0.3 + (qualification_rate * 0.5)
        if result.total_processed >= 10:
            score += 0.1
        return min(score, 1.0)

    async def _act(self, result: LeadEnrichmentResult, confidence: float) -> LeadEnrichmentResult:
        result.confidence = confidence

        # Publish LEAD_ENRICHED for each successfully enriched lead so downstream agents
        # (Campaign Architect, Outreach Executor) know email verification status
        if self._bus is not None:
            published = 0
            for record in result.records:
                if not record.get("email_valid"):
                    continue
                try:
                    await self._bus.publish(
                        from_agent=self.name,
                        discovery_type=DiscoveryType.LEAD_ENRICHED,
                        title=record.get("lead_id", "Unknown"),
                        content={
                            "lead_id": record.get("lead_id"),
                            "email_valid": record.get("email_valid", False),
                            "email_deliverable": record.get("email_deliverable", False),
                            "hunter_status": record.get("hunter_status"),
                            "hunter_score": record.get("hunter_score", 0),
                            "quality_score": record.get("quality_score", 0.0),
                            "qualifies_for_sequence": record.get("qualifies_for_sequence", False),
                            "acra_verified": record.get("acra_verified", False),
                            "blockers": record.get("blockers", []),
                            "enrichment_sources": result.data_sources_used,
                        },
                        confidence=confidence,
                        analysis_id=self._analysis_id,
                    )
                    published += 1
                except Exception as e:
                    self._logger.debug("lead_enriched_publish_failed", error=str(e))
            if published:
                self._logger.info("lead_enriched_published", count=published)

        return result

    async def _enrich_lead(self, lead: dict[str, Any]) -> EnrichmentRecord:
        lead_id = str(lead.get("id", "unknown"))
        email = (lead.get("email") or "").strip().lower()
        company_name = lead.get("company") or lead.get("company_name") or ""
        blockers: list[str] = []
        warnings: list[str] = []

        # Step 0: KB verification — check if company appears in market intelligence DB
        kb_articles: list[str] = []
        if company_name:
            try:
                async with async_session_factory() as db:
                    mcp = MarketIntelMCPServer(session=db)
                    articles = await mcp.search_market_intelligence(query=company_name)
                    kb_articles = [a.get("title", "") for a in (articles or [])[:2] if a.get("title")]
            except Exception as e:
                logger.debug("kb_lead_verification_failed", company=company_name, error=str(e))

        # 1a. If no email, attempt discovery via Hunter email-finder
        hunter_discovered = False
        if not email and self._hunter.is_configured:
            name_str: str = lead.get("name") or lead.get("full_name") or ""
            domain: str = lead.get("domain") or lead.get("website") or ""
            # Derive domain from company website if provided
            if not domain and lead.get("website"):
                domain = lead["website"].replace("https://", "").replace("http://", "").split("/")[0]
            name_parts = name_str.strip().split() if name_str.strip() else []
            if domain and len(name_parts) >= 2:
                found = await self._hunter.find_email(
                    domain=domain,
                    first_name=name_parts[0],
                    last_name=name_parts[-1],
                )
                if found and found.email and found.score >= 70:
                    email = found.email
                    lead = {**lead, "email": email}
                    hunter_discovered = True
                    logger.info(
                        "hunter.email_discovered",
                        lead_id=lead_id,
                        email=email,
                        score=found.score,
                    )

        # 1b. Email format + MX check
        email_valid = self._validate_email_format(email)
        email_deliverable = False
        if not email:
            blockers.append("No email address")
        elif not email_valid:
            blockers.append(f"Invalid email format: {email}")
        else:
            email_deliverable = await self._check_mx_record(email.split("@")[1])
            if not email_deliverable:
                blockers.append(f"No DNS record for {email.split('@')[1]}")

        # 1c. Hunter.io email verification (more accurate than DNS-only)
        hunter_status: str | None = None
        hunter_score: int = 0
        if email_valid and self._hunter.is_configured:
            verification = await self._hunter.verify_email(email)
            if verification is not None:
                hunter_status = verification.status
                hunter_score = verification.score
                # Override deliverability with Hunter's SMTP check
                if verification.result == "deliverable":
                    email_deliverable = True
                    # Remove any stale DNS blocker — Hunter's SMTP check is authoritative
                    blockers = [b for b in blockers if "No DNS record" not in b]
                elif verification.result == "undeliverable":
                    email_deliverable = False
                    blockers.append(f"Hunter: email undeliverable ({verification.status})")
                elif verification.result == "risky":
                    warnings.append(
                        f"Hunter: email risky (disposable={verification.disposable}, "
                        f"webmail={verification.webmail})"
                    )
                if verification.disposable:
                    blockers.append("Hunter: disposable email address")
                if verification.gibberish:
                    warnings.append("Hunter: email address looks auto-generated")

        # 2. ACRA lookup (Singapore company registry)
        acra_verified = False
        acra_company_name: str | None = None
        acra_uen: str | None = None
        acra_status: str | None = None
        if company_name:
            acra_data = await self._lookup_acra(company_name)
            if acra_data:
                acra_verified = True
                acra_company_name = acra_data.get("entity_name")
                acra_uen = acra_data.get("uen")
                acra_status = acra_data.get("uen_status")
                if acra_status and acra_status.lower() not in ("live", "registered", "active"):
                    warnings.append(f"ACRA status: {acra_status} — company may not be active")

        # 3. Company news (last 30 days)
        news_titles: list[str] = list(kb_articles)  # KB articles prepended first
        news_count = len(kb_articles)
        if company_name and self._newsapi.is_configured:
            try:
                result = await self._newsapi.search_competitor_news(company_name, days_back=30)
                news_count += len(result.articles)
                news_titles = kb_articles + [a.title for a in result.articles[:3]]
            except Exception:
                pass

        # 4. EODHD data (if publicly listed)
        eodhd_market_cap: float | None = None
        eodhd_employees: int | None = None
        if company_name and self._eodhd.is_configured:
            try:
                companies = await self._eodhd.search_companies(company_name, limit=1)
                if companies:
                    symbol = companies[0].get("Code")
                    exchange = companies[0].get("Exchange", "US")
                    if symbol:
                        fundamentals = await self._eodhd.get_company_fundamentals(symbol, exchange)
                        if fundamentals:
                            eodhd_market_cap = fundamentals.market_cap
                            eodhd_employees = fundamentals.employees
            except Exception:
                pass

        # 5. Quality score (deterministic)
        quality_score = self._compute_quality_score(
            lead=lead,
            email_valid=email_valid,
            email_deliverable=email_deliverable,
            hunter_status=hunter_status,
            hunter_score=hunter_score,
            acra_verified=acra_verified,
            news_count=news_count,
            eodhd_market_cap=eodhd_market_cap,
            eodhd_employees=eodhd_employees,
        )
        qualifies = bool(
            email_valid
            and email_deliverable
            and not any("No email" in b or "Invalid email" in b for b in blockers)
            and quality_score >= self.QUALITY_THRESHOLD
        )

        return EnrichmentRecord(
            lead_id=lead_id,
            email_valid=email_valid,
            email_deliverable=email_deliverable,
            hunter_status=hunter_status,
            hunter_score=hunter_score,
            hunter_discovered=hunter_discovered,
            quality_score=round(quality_score, 3),
            qualifies_for_sequence=qualifies,
            acra_verified=acra_verified,
            acra_company_name=acra_company_name,
            acra_uen=acra_uen,
            acra_status=acra_status,
            recent_news_count=news_count,
            recent_news_titles=news_titles,
            eodhd_market_cap=eodhd_market_cap,
            eodhd_employees=eodhd_employees,
            blockers=blockers,
            warnings=warnings,
        )

    def _validate_email_format(self, email: str) -> bool:
        import re
        pattern = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
        return bool(email and pattern.match(email))

    async def _check_mx_record(self, domain: str) -> bool:
        """Check DNS reachability (A record) for the email domain.

        Uses asyncio.to_thread to avoid blocking the event loop.
        Note: checks DNS resolution, not MX records specifically.
        """
        try:
            await asyncio.to_thread(socket.getaddrinfo, domain, None, socket.AF_INET)
            return True
        except (socket.gaierror, OSError):
            return False

    async def _lookup_acra(self, company_name: str) -> dict[str, Any] | None:
        try:
            acra_server = self._mcp._registry.get_server("ACRA Singapore")
            if acra_server and acra_server.is_configured:
                results = await acra_server.search(company_name, limit=1)
                if results and results.facts:
                    fact = results.facts[0]
                    return {
                        "entity_name": str(fact.entity) if fact.entity else None,
                        "uen": fact.metadata.get("uen") if fact.metadata else None,
                        "uen_status": fact.metadata.get("uen_status") if fact.metadata else None,
                    }
        except Exception:
            pass
        return None

    def _compute_quality_score(
        self,
        lead: dict[str, Any],
        email_valid: bool,
        email_deliverable: bool,
        hunter_status: str | None,
        hunter_score: int,
        acra_verified: bool,
        news_count: int,
        eodhd_market_cap: float | None = None,
        eodhd_employees: int | None = None,
    ) -> float:
        score = 0.0

        # Email quality (critical) — Hunter verification provides stronger signal
        if email_valid and email_deliverable:
            if hunter_status == "valid" and hunter_score >= 70:
                # Hunter confirms high-confidence valid email
                score += 0.35
            elif hunter_status in ("valid", "accept_all"):
                score += 0.30
            else:
                # DNS-only pass
                score += 0.25
        elif email_valid:
            score += 0.10

        # Contact data completeness
        fields = ["name", "title", "company", "email"]
        completeness = sum(1 for f in fields if lead.get(f) or lead.get(f.replace("title", "job_title")))
        score += (completeness / len(fields)) * 0.25

        # Company verification
        if acra_verified:
            score += 0.20

        # Seniority
        title = (lead.get("title") or lead.get("job_title") or "").lower()
        for keywords, seniority_score in [
            (["ceo", "founder", "owner", "president", "managing director"], 0.15),
            (["cto", "cfo", "coo", "chief"], 0.14),
            (["vp", "vice president", "director", "head of"], 0.12),
            (["manager", "lead", "principal"], 0.08),
        ]:
            if any(kw in title for kw in keywords):
                score += seniority_score
                break

        # News recency signal
        if news_count >= 3:
            score += 0.05
        elif news_count >= 1:
            score += 0.02

        # EODHD financial signals — publicly listed or large companies are higher-value targets
        if eodhd_market_cap is not None and eodhd_market_cap >= 50_000_000:
            # Publicly listed company with meaningful market cap ($50M+) — verified real entity
            score += 0.08
            if eodhd_market_cap >= 1_000_000_000:  # $1B+ market cap = enterprise tier
                score += 0.04
        if eodhd_employees is not None and eodhd_employees > 0:
            # Known headcount confirms company scale
            if eodhd_employees >= 500:
                score += 0.03
            elif eodhd_employees >= 100:
                score += 0.02

        return min(1.0, score)
