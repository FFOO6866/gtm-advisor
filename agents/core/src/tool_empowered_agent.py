"""Tool-Empowered Agent Base Class.

Extends BaseGTMAgent with the 4-layer architecture:
1. Cognitive Layer (LLM) - Reasoning, synthesis, explanation
2. Analytical Layer (Algorithms) - Deterministic scoring, clustering
3. Operational Layer (Tools) - Data operations, integrations
4. Governance Layer (Rules) - Access control, checkpoints, audit

Principle: Algorithms decide where possible, LLMs explain.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar
import time

import structlog

from .base_agent import BaseGTMAgent, AgentCapability

# Algorithms
from packages.algorithms.src import (
    ICPScorer,
    LeadScorer,
    MessageAlignmentScorer,
    CompetitorThreatScorer,
    FirmographicClusterer,
    PersonaClusterer,
    MarketSegmenter,
    MarketSizeCalculator,
    LeadValueCalculator,
    CampaignROICalculator,
    RuleEngine,
)

# Tools
from packages.tools.src import (
    BaseTool,
    ToolAccess,
    ToolResult,
    ToolRegistry,
    CompanyEnrichmentTool,
    ContactEnrichmentTool,
    EmailFinderTool,
    WebScraperTool,
    LinkedInScraperTool,
    NewsScraperTool,
    HubSpotTool,
    PipedriveTool,
)

# Governance
from packages.governance.src import (
    AccessControl,
    Permission,
    AgentPermissions,
    CheckpointManager,
    CheckpointType,
    ApprovalStatus,
    AuditLogger,
    AuditEventType,
    BudgetManager,
    PDPAChecker,
)


T = TypeVar("T")
logger = structlog.get_logger()


@dataclass
class LayerUsage:
    """Tracks which layer handled each decision."""
    layer: str  # cognitive, analytical, operational, governance
    component: str  # specific component used
    decision: str
    confidence: float
    execution_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentDecisionLog:
    """Complete log of decisions made during execution."""
    task_id: str
    agent_id: str
    started_at: datetime
    completed_at: datetime | None = None
    decisions: list[LayerUsage] = field(default_factory=list)
    llm_calls: int = 0
    algorithm_calls: int = 0
    tool_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "decisions": [
                {
                    "layer": d.layer,
                    "component": d.component,
                    "decision": d.decision,
                    "confidence": d.confidence,
                    "execution_time_ms": d.execution_time_ms,
                }
                for d in self.decisions
            ],
            "llm_calls": self.llm_calls,
            "algorithm_calls": self.algorithm_calls,
            "tool_calls": self.tool_calls,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "determinism_ratio": self._determinism_ratio(),
        }

    def _determinism_ratio(self) -> float:
        """Ratio of deterministic (algorithm) decisions to total."""
        total = self.llm_calls + self.algorithm_calls
        if total == 0:
            return 0.0
        return self.algorithm_calls / total


class ToolEmpoweredAgent(BaseGTMAgent[T], Generic[T]):
    """Base class for tool-empowered agents.

    Provides:
    - Pre-configured access to algorithms (scoring, clustering, calculators)
    - Pre-configured tools with access boundaries
    - Governance integration (access control, checkpoints, audit)
    - Budget tracking
    - PDPA compliance checking

    Example:
        class LeadHunterAgent(ToolEmpoweredAgent[LeadList]):
            def __init__(self):
                super().__init__(
                    name="lead_hunter",
                    description="Finds and qualifies leads",
                    result_type=LeadList,
                    tool_access=[ToolAccess.READ],  # Read-only
                    allowed_tools=["company_enrichment", "email_finder"],
                )

            async def _do(self, plan, context, **kwargs):
                # Use algorithm for scoring
                score = await self.score_lead(lead_data)

                # Use tool for enrichment
                enriched = await self.use_tool(
                    "company_enrichment",
                    domain="acme.com",
                )

                # LLM only for synthesis/explanation
                explanation = await self._complete(...)

                return LeadList(leads=[...])
    """

    def __init__(
        self,
        name: str,
        description: str,
        result_type: type[T],
        *,
        # Governance config
        tool_access: list[ToolAccess] | None = None,
        allowed_tools: list[str] | None = None,
        requires_approval_for: list[Permission] | None = None,
        # Algorithm config
        use_icp_scorer: bool = False,
        use_lead_scorer: bool = False,
        use_clustering: bool = False,
        use_calculators: bool = False,
        # Budget config
        max_tokens_per_task: int = 50000,
        max_cost_per_task: float = 5.0,
        # Other
        **kwargs: Any,
    ) -> None:
        super().__init__(name, description, result_type, **kwargs)

        # Tool access config
        self.tool_access = tool_access or [ToolAccess.READ]
        self.allowed_tools = allowed_tools
        self.requires_approval_for = requires_approval_for or []

        # Budget limits
        self.max_tokens_per_task = max_tokens_per_task
        self.max_cost_per_task = max_cost_per_task

        # Initialize governance components
        self._access_control = AccessControl()
        self._checkpoint_manager = CheckpointManager()
        self._audit_logger = AuditLogger()
        self._budget_manager = BudgetManager()
        self._pdpa_checker = PDPAChecker()

        # Initialize algorithms (lazy - only if configured)
        self._icp_scorer = ICPScorer() if use_icp_scorer else None
        self._lead_scorer = LeadScorer() if use_lead_scorer else None
        self._firmographic_clusterer = FirmographicClusterer() if use_clustering else None
        self._market_segmenter = MarketSegmenter() if use_clustering else None
        self._market_size_calc = MarketSizeCalculator() if use_calculators else None
        self._lead_value_calc = LeadValueCalculator() if use_calculators else None
        self._campaign_roi_calc = CampaignROICalculator() if use_calculators else None

        # Initialize tools (lazy loaded)
        self._tool_registry = ToolRegistry()
        self._tools_initialized = False

        # Decision logging
        self._current_decision_log: AgentDecisionLog | None = None

    # ==========================================================================
    # Tool Management
    # ==========================================================================

    def _ensure_tools_initialized(self) -> None:
        """Initialize tools on first use."""
        if self._tools_initialized:
            return

        # Register available tools
        tools = [
            CompanyEnrichmentTool(agent_id=self.name, allowed_access=self.tool_access),
            ContactEnrichmentTool(agent_id=self.name, allowed_access=self.tool_access),
            EmailFinderTool(agent_id=self.name, allowed_access=self.tool_access),
            WebScraperTool(agent_id=self.name, allowed_access=self.tool_access),
            LinkedInScraperTool(agent_id=self.name, allowed_access=self.tool_access),
            NewsScraperTool(agent_id=self.name, allowed_access=self.tool_access),
            HubSpotTool(agent_id=self.name, allowed_access=self.tool_access, use_mock=True),
            PipedriveTool(agent_id=self.name, allowed_access=self.tool_access, use_mock=True),
        ]

        for tool in tools:
            # Only register if in allowed list (if specified)
            if self.allowed_tools is None or tool.name in self.allowed_tools:
                self._tool_registry.register(tool)

        self._tools_initialized = True

    async def use_tool(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Use a tool with full governance checks.

        Args:
            tool_name: Name of tool to use
            **kwargs: Tool parameters

        Returns:
            Tool result

        Raises:
            PermissionError: If access denied
        """
        self._ensure_tools_initialized()
        start_time = time.time()

        # Check tool is allowed
        if self.allowed_tools and tool_name not in self.allowed_tools:
            self._audit_logger.log(
                event_type=AuditEventType.ACCESS_DENIED,
                action=f"use_tool:{tool_name}",
                agent_id=self.name,
                success=False,
                error_message="Tool not in allowed list",
            )
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool {tool_name} not allowed for agent {self.name}",
            )

        # Check budget
        if not self._budget_manager.can_spend(
            usage_type="api_calls",
            amount=1,
            agent_id=self.name,
            tool_name=tool_name,
        ):
            return ToolResult(
                success=False,
                data=None,
                error="Budget limit reached",
                rate_limited=True,
            )

        # Get and execute tool
        tool = self._tool_registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool {tool_name} not found",
            )

        result = await tool.execute(**kwargs)
        execution_time = (time.time() - start_time) * 1000

        # Record usage
        self._budget_manager.spend(
            usage_type="api_calls",
            amount=1,
            agent_id=self.name,
            tool_name=tool_name,
        )

        # Audit
        self._audit_logger.log(
            event_type=AuditEventType.TOOL_SUCCESS if result.success else AuditEventType.TOOL_ERROR,
            action=f"use_tool:{tool_name}",
            agent_id=self.name,
            input_data=kwargs,
            output_data={"success": result.success} if result.success else None,
            duration_ms=execution_time,
            success=result.success,
            error_message=result.error,
        )

        # Log decision
        if self._current_decision_log:
            self._current_decision_log.tool_calls += 1
            self._current_decision_log.decisions.append(LayerUsage(
                layer="operational",
                component=tool_name,
                decision=f"Tool call: {tool_name}",
                confidence=1.0 if result.success else 0.0,
                execution_time_ms=execution_time,
            ))

        return result

    # ==========================================================================
    # Algorithm Methods
    # ==========================================================================

    async def score_icp_fit(
        self,
        company: dict[str, Any],
        icp_criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Score company's ICP fit using algorithm (not LLM).

        Returns deterministic, explainable score.
        """
        if not self._icp_scorer:
            self._icp_scorer = ICPScorer()
            if icp_criteria:
                self._icp_scorer.configure(icp_criteria)

        start_time = time.time()
        result = self._icp_scorer.score(company)
        execution_time = (time.time() - start_time) * 1000

        # Log decision
        if self._current_decision_log:
            self._current_decision_log.algorithm_calls += 1
            self._current_decision_log.decisions.append(LayerUsage(
                layer="analytical",
                component="icp_scorer",
                decision=f"ICP score: {result.total_score:.2f}",
                confidence=result.confidence,
                execution_time_ms=execution_time,
                metadata={"score": result.total_score, "components": result.components},
            ))

        return result.to_dict()

    async def score_lead(
        self,
        lead_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Score lead quality using BANT algorithm."""
        if not self._lead_scorer:
            self._lead_scorer = LeadScorer()

        start_time = time.time()
        result = self._lead_scorer.score(lead_data)
        execution_time = (time.time() - start_time) * 1000

        if self._current_decision_log:
            self._current_decision_log.algorithm_calls += 1
            self._current_decision_log.decisions.append(LayerUsage(
                layer="analytical",
                component="lead_scorer",
                decision=f"Lead score: {result.total_score:.2f}",
                confidence=result.confidence,
                execution_time_ms=execution_time,
            ))

        return result.to_dict()

    async def cluster_companies(
        self,
        companies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Cluster companies by firmographic similarity."""
        if not self._firmographic_clusterer:
            self._firmographic_clusterer = FirmographicClusterer()

        start_time = time.time()
        result = self._firmographic_clusterer.cluster(companies)
        execution_time = (time.time() - start_time) * 1000

        if self._current_decision_log:
            self._current_decision_log.algorithm_calls += 1
            self._current_decision_log.decisions.append(LayerUsage(
                layer="analytical",
                component="firmographic_clusterer",
                decision=f"Created {len(result.clusters)} clusters",
                confidence=result.quality_score,
                execution_time_ms=execution_time,
            ))

        return result.to_dict()

    async def segment_market(
        self,
        companies: list[dict[str, Any]],
        value_props: list[str],
    ) -> dict[str, Any]:
        """Segment market by opportunity fit."""
        if not self._market_segmenter:
            self._market_segmenter = MarketSegmenter()

        start_time = time.time()
        result = self._market_segmenter.segment(companies, value_props)
        execution_time = (time.time() - start_time) * 1000

        if self._current_decision_log:
            self._current_decision_log.algorithm_calls += 1
            self._current_decision_log.decisions.append(LayerUsage(
                layer="analytical",
                component="market_segmenter",
                decision=f"Created {len(result.clusters)} segments",
                confidence=result.quality_score,
                execution_time_ms=execution_time,
            ))

        return result.to_dict()

    async def calculate_market_size(
        self,
        industry: str,
        acv: float,
        target_sizes: list[str],
        geography: list[str],
    ) -> dict[str, Any]:
        """Calculate TAM/SAM/SOM."""
        if not self._market_size_calc:
            self._market_size_calc = MarketSizeCalculator()

        start_time = time.time()
        result = self._market_size_calc.calculate(
            industry=industry,
            your_acv=acv,
            target_company_sizes=target_sizes,
            geographic_focus=geography,
        )
        execution_time = (time.time() - start_time) * 1000

        if self._current_decision_log:
            self._current_decision_log.algorithm_calls += 1
            self._current_decision_log.decisions.append(LayerUsage(
                layer="analytical",
                component="market_size_calculator",
                decision=f"TAM: {result.tam:,.0f}, SAM: {result.sam:,.0f}, SOM: {result.som:,.0f}",
                confidence=result.confidence,
                execution_time_ms=execution_time,
            ))

        return result.to_dict()

    async def calculate_lead_value(
        self,
        lead_score: float,
        company_size: str,
        acv: float,
    ) -> dict[str, Any]:
        """Calculate expected lead value."""
        if not self._lead_value_calc:
            self._lead_value_calc = LeadValueCalculator()

        start_time = time.time()
        result = self._lead_value_calc.calculate(
            lead_score=lead_score,
            company_size=company_size,
            your_acv=acv,
        )
        execution_time = (time.time() - start_time) * 1000

        if self._current_decision_log:
            self._current_decision_log.algorithm_calls += 1
            self._current_decision_log.decisions.append(LayerUsage(
                layer="analytical",
                component="lead_value_calculator",
                decision=f"Expected value: {result.expected_value:,.2f}",
                confidence=result.confidence,
                execution_time_ms=execution_time,
            ))

        return result.to_dict()

    # ==========================================================================
    # Governance Methods
    # ==========================================================================

    async def request_approval(
        self,
        checkpoint_id: str,
        title: str,
        description: str,
        context: dict[str, Any],
    ) -> bool:
        """Request human approval for an action.

        Returns True if approved, False if rejected/expired.
        """
        from packages.governance.src import create_gtm_checkpoints

        # Ensure checkpoints are registered
        for cp in create_gtm_checkpoints():
            self._checkpoint_manager.register_checkpoint(cp)

        request = await self._checkpoint_manager.request_approval(
            checkpoint_id=checkpoint_id,
            agent_id=self.name,
            title=title,
            description=description,
            context=context,
        )

        # For now, auto-approve (in production, this would wait for human)
        # In a real system, this would integrate with the dashboard
        if request.status == ApprovalStatus.PENDING:
            # Auto-approve for demo (in production, would wait)
            await self._checkpoint_manager.decide(
                request_id=request.id,
                approved=True,
                decided_by="auto_demo",
                notes="Auto-approved for demo",
            )

        final_request = await self._checkpoint_manager.wait_for_decision(
            request.id,
            timeout=1.0,  # Short timeout for demo
        )

        return final_request.status == ApprovalStatus.APPROVED

    def check_pdpa_compliance(
        self,
        data: dict[str, Any],
        purpose: str = "sales",
    ) -> dict[str, Any]:
        """Check PDPA compliance for data processing."""
        from packages.governance.src import ProcessingPurpose

        purpose_map = {
            "marketing": ProcessingPurpose.MARKETING,
            "sales": ProcessingPurpose.SALES,
            "analytics": ProcessingPurpose.ANALYTICS,
        }
        processing_purpose = purpose_map.get(purpose, ProcessingPurpose.SALES)

        # Check each field
        issues = []
        for field_name, value in data.items():
            if value and not self._pdpa_checker.can_process(
                field=field_name,
                purpose=processing_purpose,
                data_subject_id=data.get("email"),
            ):
                issues.append(f"Cannot process {field_name} without consent")

        # Detect PII in text fields
        text_fields = ["description", "notes", "content"]
        for field_name in text_fields:
            if field_name in data and isinstance(data[field_name], str):
                pii_found = self._pdpa_checker.detect_pii(data[field_name])
                if pii_found:
                    issues.extend([f"PII detected: {p['type']}" for p in pii_found])

        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "masked_data": self._pdpa_checker.mask_pii(data),
        }

    # ==========================================================================
    # Enhanced LLM Methods (with tracking)
    # ==========================================================================

    async def _complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Get completion with usage tracking."""
        start_time = time.time()
        result = await super()._complete(messages, model, **kwargs)
        execution_time = (time.time() - start_time) * 1000

        # Estimate tokens (rough: 4 chars per token)
        input_tokens = sum(len(m.get("content", "")) for m in messages) // 4
        output_tokens = len(result) // 4
        total_tokens = input_tokens + output_tokens

        # Track budget
        self._budget_manager.spend(
            usage_type="tokens",
            amount=total_tokens,
            agent_id=self.name,
        )

        if self._current_decision_log:
            self._current_decision_log.llm_calls += 1
            self._current_decision_log.total_tokens += total_tokens
            self._current_decision_log.total_cost_usd += (total_tokens / 1000) * 0.03  # Rough estimate
            self._current_decision_log.decisions.append(LayerUsage(
                layer="cognitive",
                component="llm",
                decision="LLM completion",
                confidence=0.8,  # LLM confidence is uncertain
                execution_time_ms=execution_time,
                metadata={"tokens": total_tokens},
            ))

        return result

    # ==========================================================================
    # Execution Overrides
    # ==========================================================================

    async def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute with full decision logging."""
        from uuid import uuid4

        # Initialize decision log
        self._current_decision_log = AgentDecisionLog(
            task_id=str(uuid4()),
            agent_id=self.name,
            started_at=datetime.utcnow(),
        )

        # Audit start
        self._audit_logger.log(
            event_type=AuditEventType.AGENT_START,
            action="run",
            agent_id=self.name,
            input_data={"task": task[:200]},
        )

        try:
            result = await super().run(task, context, **kwargs)

            # Complete logging
            self._current_decision_log.completed_at = datetime.utcnow()

            self._audit_logger.log(
                event_type=AuditEventType.AGENT_COMPLETE,
                action="run",
                agent_id=self.name,
                output_data=self._current_decision_log.to_dict(),
                success=True,
            )

            return result

        except Exception as e:
            self._audit_logger.log(
                event_type=AuditEventType.AGENT_ERROR,
                action="run",
                agent_id=self.name,
                success=False,
                error_message=str(e),
            )
            raise

    def get_decision_log(self) -> dict[str, Any] | None:
        """Get the current or last decision log."""
        if self._current_decision_log:
            return self._current_decision_log.to_dict()
        return None

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get audit log for this agent."""
        return self._audit_logger.query(agent_id=self.name)

    def get_budget_status(self) -> list[dict[str, Any]]:
        """Get budget status for this agent."""
        return self._budget_manager.get_budget_status(agent_id=self.name)
