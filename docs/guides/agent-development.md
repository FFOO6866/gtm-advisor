# Agent Development Guide

This guide explains how to develop agents for the GTM Advisor platform.

## Overview

All agents in GTM Advisor follow the **PDCA (Plan-Do-Check-Act)** pattern inherited from the Grace Framework. This ensures:

- Self-correcting behavior through confidence thresholds
- Consistent execution patterns
- Full observability and auditability

## Agent Architecture

### Base Classes

```
BaseGTMAgent (agents/core/src/base_agent.py)
    │
    ├── GTMStrategistAgent
    ├── MarketIntelligenceAgent
    ├── CompetitorAnalystAgent
    ├── CustomerProfilerAgent
    └── ToolEmpoweredAgent (agents/core/src/tool_empowered_agent.py)
            │
            └── LeadHunterAgent
```

### Four-Layer Architecture

For agents that need tools and algorithms (like Lead Hunter), use `ToolEmpoweredAgent`:

```
┌─────────────────────────────────────────┐
│         COGNITIVE LAYER (LLM)           │
│  • Synthesis      • Explanation         │
│  • Generation     • Reasoning           │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│        ANALYTICAL LAYER (Algorithms)    │
│  • ICP Scoring    • BANT Scoring        │
│  • Clustering     • Value Calculation   │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│       OPERATIONAL LAYER (Tools)         │
│  • Company Enrichment  • Web Scraping   │
│  • News Search         • CRM Sync       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│       GOVERNANCE LAYER (Rules)          │
│  • RBAC            • PDPA Compliance    │
│  • Audit Logging   • Budget Controls    │
└─────────────────────────────────────────┘
```

## Creating a New Agent

### Step 1: Define Result Type

```python
# agents/my_agent/src/types.py
from pydantic import BaseModel, Field
from typing import List

class MyAgentResult(BaseModel):
    """Result from MyAgent analysis."""

    summary: str = Field(..., description="Executive summary")
    findings: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Track decision attribution
    algorithm_decisions: int = Field(default=0)
    llm_decisions: int = Field(default=0)
```

### Step 2: Implement Agent

```python
# agents/my_agent/src/agent.py
from agents.core.src.base_agent import BaseGTMAgent
from packages.core.src.types import AgentStatus

from .types import MyAgentResult

class MyAgent(BaseGTMAgent[MyAgentResult]):
    """My custom GTM agent.

    This agent performs X analysis using Y methodology.

    Capabilities:
    - Capability 1: Description
    - Capability 2: Description

    Example:
        ```python
        agent = MyAgent()
        result = await agent.run(
            "Analyze X for company Y",
            context={"company_name": "Acme Corp"}
        )
        print(result.summary)
        ```
    """

    def __init__(self, min_confidence: float = 0.75):
        super().__init__(
            name="my-agent",
            description="Performs X analysis",
            result_type=MyAgentResult,
            min_confidence=min_confidence,
        )

        # Add capabilities
        self._add_capability(
            name="Analysis",
            description="Performs comprehensive X analysis"
        )

    async def _plan(self, task: str, context: dict) -> dict:
        """Analyze task and create execution plan.

        Args:
            task: The task description
            context: Additional context (company info, etc.)

        Returns:
            Plan dictionary with steps to execute
        """
        self._set_status(AgentStatus.PLANNING)

        # Create execution plan
        plan = {
            "task": task,
            "steps": [
                {"name": "gather_data", "description": "Gather relevant data"},
                {"name": "analyze", "description": "Perform analysis"},
                {"name": "synthesize", "description": "Synthesize findings"},
            ],
            "context": context,
        }

        self._log("Plan created", plan=plan)
        return plan

    async def _do(self, plan: dict) -> MyAgentResult:
        """Execute the plan.

        Args:
            plan: The execution plan from _plan()

        Returns:
            Agent result
        """
        self._set_status(AgentStatus.EXECUTING)

        # Step 1: Gather data
        data = await self._gather_data(plan["context"])

        # Step 2: Analyze using LLM
        analysis = await self._analyze(data, plan["task"])

        # Step 3: Build result
        result = MyAgentResult(
            summary=analysis.summary,
            findings=analysis.findings,
            confidence=0.0,  # Will be set in _check()
            llm_decisions=1,
        )

        return result

    async def _check(self, result: MyAgentResult) -> float:
        """Validate result and return confidence score.

        Args:
            result: The result from _do()

        Returns:
            Confidence score 0.0 to 1.0
        """
        self._set_status(AgentStatus.CHECKING)

        # Calculate confidence based on completeness
        confidence = 0.5

        if result.summary:
            confidence += 0.2
        if len(result.findings) >= 3:
            confidence += 0.2
        if result.llm_decisions > 0 or result.algorithm_decisions > 0:
            confidence += 0.1

        result.confidence = min(confidence, 1.0)

        self._log("Confidence calculated", confidence=confidence)
        return confidence

    async def _act(
        self,
        result: MyAgentResult,
        confidence: float
    ) -> MyAgentResult:
        """Adjust result if confidence is low, or finalize.

        Args:
            result: The result from _do()
            confidence: The confidence score from _check()

        Returns:
            Final or adjusted result
        """
        if confidence < self.min_confidence:
            self._set_status(AgentStatus.ADJUSTING)
            self._log(
                "Confidence below threshold, adjusting",
                confidence=confidence,
                threshold=self.min_confidence
            )

            # Try to improve the result
            # This could involve:
            # - Gathering more data
            # - Using different analysis approach
            # - Adding more context

            return result  # Return adjusted result

        self._set_status(AgentStatus.COMPLETED)
        return result

    async def _gather_data(self, context: dict) -> dict:
        """Gather data for analysis."""
        # Implementation
        return {}

    async def _analyze(self, data: dict, task: str):
        """Perform LLM analysis."""
        # Use Instructor for structured output
        return await self._llm_manager.generate_structured(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert analyst."},
                {"role": "user", "content": f"Analyze: {task}"},
            ],
            response_model=AnalysisOutput,
        )
```

### Step 3: Using Tools (ToolEmpoweredAgent)

For agents that need external tools:

```python
from agents.core.src.tool_empowered_agent import ToolEmpoweredAgent
from packages.tools.src.enrichment import CompanyEnrichmentTool
from packages.algorithms.src.scoring import ICPScorer

class MyToolAgent(ToolEmpoweredAgent[MyResult]):
    """Agent with tool and algorithm access."""

    def __init__(self):
        super().__init__(
            name="my-tool-agent",
            description="Agent with tools",
            result_type=MyResult,
            min_confidence=0.70,
        )

        # Register tools
        self._register_tool(CompanyEnrichmentTool())

        # Initialize algorithms
        self._icp_scorer = ICPScorer()

    async def _do(self, plan: dict) -> MyResult:
        """Execute with tools and algorithms."""

        # Use tools (operational layer)
        enrichment = await self.use_tool(
            "company_enrichment",
            company_name="Acme Corp",
            country="Singapore"
        )

        # Use algorithms (analytical layer)
        score = await self.score_icp_fit(
            company={
                "industry": enrichment.result["industry"],
                "employee_count": enrichment.result["employee_count"],
            },
            icp_criteria={
                "target_industries": ["fintech", "saas"],
                "min_employees": 10,
                "max_employees": 500,
            }
        )

        # Use LLM (cognitive layer)
        synthesis = await self._synthesize(enrichment, score)

        return MyResult(
            summary=synthesis,
            fit_score=score["score"],
            algorithm_decisions=1,  # ICP scoring
            llm_decisions=1,        # Synthesis
            tool_calls=1,           # Enrichment
        )
```

## Testing Agents

### Unit Tests

```python
# tests/unit/agents/test_my_agent.py
import pytest
from agents.my_agent.src import MyAgent

@pytest.fixture
def agent():
    return MyAgent(min_confidence=0.7)

class TestMyAgent:
    @pytest.mark.asyncio
    async def test_run_basic(self, agent):
        """Test basic agent execution."""
        result = await agent.run(
            "Analyze market for fintech",
            context={"company_name": "TestCorp"}
        )

        assert result is not None
        assert result.summary
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_pdca_cycle(self, agent):
        """Test full PDCA cycle executes."""
        result = await agent.run("Test task")

        # Verify all phases executed
        assert agent._current_state is not None
        assert agent._current_state.phase.value in ["plan", "do", "check", "act"]

    @pytest.mark.asyncio
    async def test_low_confidence_adjustment(self, agent):
        """Test agent adjusts on low confidence."""
        # Test with context that produces low confidence
        result = await agent.run(
            "Minimal task",
            context={}  # Sparse context
        )

        # Should still complete
        assert result is not None
```

### Integration Tests

```python
# tests/integration/agents/test_my_agent_integration.py
import pytest
from agents.my_agent.src import MyAgent

@pytest.mark.integration
class TestMyAgentIntegration:
    @pytest.mark.asyncio
    async def test_with_real_llm(self):
        """Test with actual LLM calls."""
        agent = MyAgent()
        result = await agent.run(
            "Analyze Singapore fintech market",
            context={
                "company_name": "TechStartup SG",
                "industry": "fintech",
            }
        )

        assert result.summary
        assert len(result.findings) > 0
```

## Best Practices

### 1. Use Structured Outputs

Always use Pydantic models with Instructor for LLM outputs:

```python
from instructor import from_openai
from pydantic import BaseModel

class AnalysisOutput(BaseModel):
    summary: str
    findings: list[str]
    confidence: float

client = from_openai(openai.OpenAI())
result = client.chat.completions.create(
    model="gpt-4o",
    response_model=AnalysisOutput,
    messages=[...],
)
```

### 2. Track Decision Attribution

Always track where decisions come from:

```python
result = MyResult(
    algorithm_decisions=3,  # ICP score, BANT score, value calc
    llm_decisions=1,        # Synthesis
    tool_calls=2,           # Enrichment, news search
)

# Calculate determinism ratio
total = result.algorithm_decisions + result.llm_decisions
determinism_ratio = result.algorithm_decisions / total if total > 0 else 0
```

### 3. Log Everything

Use structured logging for observability:

```python
self._log(
    "Operation completed",
    operation="icp_scoring",
    input_size=len(companies),
    output_size=len(scored),
    execution_time_ms=elapsed * 1000,
)
```

### 4. Graceful Degradation

Handle missing dependencies gracefully:

```python
try:
    from packages.tools.src.enrichment import CompanyEnrichmentTool
    ENRICHMENT_AVAILABLE = True
except ImportError:
    ENRICHMENT_AVAILABLE = False

async def _enrich(self, company: str) -> dict:
    if not ENRICHMENT_AVAILABLE:
        self._log("Enrichment not available, using basic data")
        return {"name": company}

    return await self.use_tool("company_enrichment", company_name=company)
```

### 5. Respect Governance

Check permissions before operations:

```python
from packages.governance.src.access import check_permission, Permission

async def _execute_operation(self, operation: str):
    if not check_permission(self.name, Permission.WRITE):
        raise PermissionError(f"Agent {self.name} lacks WRITE permission")

    # Proceed with operation
```

## Agent Configuration

### Environment Variables

```bash
# Agent-specific settings
GTM_AGENT_MIN_CONFIDENCE=0.75
GTM_AGENT_MAX_ITERATIONS=3
GTM_AGENT_TIMEOUT_SECONDS=300
```

### Runtime Configuration

```python
agent = MyAgent(
    min_confidence=0.8,  # Higher quality threshold
)

# Or configure at runtime
agent.min_confidence = 0.9
```

## Debugging

### Enable Debug Logging

```python
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
```

### Inspect Agent State

```python
result = await agent.run("Task")

# Check state
print(f"Iterations: {agent._current_state.iteration}")
print(f"Confidence: {agent._current_state.confidence}")
print(f"Adjustments: {agent._current_state.adjustments}")
```

## Related Documentation

- [Tool Development Guide](tool-development.md) - Creating new tools
- [Algorithm Reference](../api/algorithms.md) - Available algorithms
- [Governance Guide](governance.md) - Policy enforcement
