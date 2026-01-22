# ADR-0001: Four-Layer Tool-Empowered Agent Architecture

## Status

**Accepted**

## Context

The initial GTM Advisor implementation relied solely on LLM (Large Language Model) calls for all agent operations. This approach had several critical problems:

1. **Non-deterministic outputs**: Running the same analysis twice could produce different results
2. **Unexplainable decisions**: No clear audit trail of how conclusions were reached
3. **High latency and cost**: Every decision required an LLM call
4. **Limited accountability**: Could not attribute decisions to specific components
5. **No outcome-based pricing**: Without reproducibility, pricing based on results was impossible

User feedback crystallized this problem:

> "An agent without tools, algorithms, and domain datasets is not an 'agent' in any economically meaningful sense—it is merely an LLM prompt wrapper."

## Decision

We adopt a **Four-Layer Architecture** that separates concerns across:

### 1. Cognitive Layer (LLM)
**Purpose**: Synthesis, explanation, generation, reasoning about ambiguous situations

**When to use**:
- Generating human-readable summaries
- Explaining complex decisions in natural language
- Handling truly ambiguous or novel situations
- Creative content generation (email templates, messaging)

**Characteristics**:
- Non-deterministic
- Higher latency (~1-2s)
- Higher cost per call
- Requires careful prompt engineering

### 2. Analytical Layer (Algorithms)
**Purpose**: Deterministic scoring, calculations, and data transformations

**Components**:
- `ICPScorer`: Calculates Ideal Customer Profile fit (0-1 score)
- `BANTScorer`: Scores Budget, Authority, Need, Timeline
- `LeadValueCalculator`: Estimates deal value
- `CompanyClusterer`: Groups companies by similarity
- `RuleEngine`: Executes business rules

**When to use**:
- Lead scoring
- Company matching
- Value calculations
- Any decision that needs to be repeatable

**Characteristics**:
- Deterministic (same inputs = same outputs)
- Low latency (<10ms)
- Zero marginal cost
- Fully auditable

### 3. Operational Layer (Tools)
**Purpose**: Data acquisition, external system integration

**Components**:
- `CompanyEnrichmentTool`: Enriches company data from external sources
- `ContactEnrichmentTool`: Finds contact information
- `WebScraperTool`: Extracts data from websites
- `NewsScraperTool`: Gathers recent news
- `CRMSyncTool`: Syncs with CRM systems

**When to use**:
- Gathering external data
- Validating information
- Syncing with other systems

**Characteristics**:
- Variable latency (depends on external system)
- Rate limited
- May fail (graceful degradation required)
- Provides real data (not hallucinated)

### 4. Governance Layer (Rules)
**Purpose**: Policy enforcement, compliance, access control

**Components**:
- `RBACManager`: Role-based access control
- `PDPAChecker`: Singapore data protection compliance
- `AuditLogger`: Comprehensive audit trail
- `BudgetManager`: Cost controls per agent/user
- `CheckpointManager`: Human approval gates

**When to use**:
- Before any data operation (access check)
- After any data operation (audit log)
- Before external API calls (rate limit check)
- At operation boundaries (compliance check)

**Characteristics**:
- Must be synchronous (blocking)
- Fail-closed (deny on error)
- Complete audit trail

## Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │              USER REQUEST                │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │           GOVERNANCE CHECK               │
                    │     (RBAC, Rate Limit, Budget)          │
                    └────────────────────┬────────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                              │                              │
          ▼                              ▼                              ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   COGNITIVE (LLM)   │    │ ANALYTICAL (ALGO)   │    │  OPERATIONAL (TOOL) │
│                     │    │                     │    │                     │
│ - Task planning     │    │ - ICP scoring       │    │ - Data enrichment   │
│ - Synthesis         │    │ - BANT scoring      │    │ - News search       │
│ - Explanation       │    │ - Value calc        │    │ - Web scraping      │
│ - Generation        │    │ - Clustering        │    │ - CRM sync          │
└─────────┬───────────┘    └─────────┬───────────┘    └─────────┬───────────┘
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     │
                    ┌────────────────▼────────────────────┐
                    │           GOVERNANCE LOG             │
                    │    (Audit, Compliance, Attribution)  │
                    └────────────────────┬────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │              RESPONSE                    │
                    │   (with decision attribution)            │
                    └─────────────────────────────────────────┘
```

## Implementation

### ToolEmpoweredAgent Base Class

```python
class ToolEmpoweredAgent(BaseGTMAgent[T], Generic[T]):
    """Base class for agents using all four layers."""

    def __init__(self, ...):
        # Initialize layer components
        self._tools: dict[str, BaseTool] = {}
        self._icp_scorer = ICPScorer()
        self._bant_scorer = BANTScorer()
        self._value_calculator = LeadValueCalculator()
        self._rule_engine = RuleEngine()
        self._audit_logger = AuditLogger()
        self._access_control = RBACManager()

    async def use_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Use operational layer tool with governance."""
        # 1. Check access
        self._access_control.check(self.name, tool_name)

        # 2. Execute tool
        result = await self._tools[tool_name].execute(**kwargs)

        # 3. Log for audit
        self._audit_logger.log_tool_call(tool_name, kwargs, result)

        return result

    async def score_icp_fit(self, company, criteria) -> dict:
        """Use analytical layer for ICP scoring."""
        score = self._icp_scorer.calculate(company, criteria)
        self._audit_logger.log_algorithm("icp_scoring", score)
        return score
```

### Decision Attribution

Every agent result includes decision attribution:

```python
result = LeadHunterResult(
    qualified_leads=leads,
    algorithm_decisions=18,  # ICP + BANT + value calculations
    llm_decisions=4,         # Planning + synthesis
    tool_calls=12,           # Enrichment + news
    determinism_ratio=0.82,  # 18/(18+4) = 82% algorithmic
)
```

## Consequences

### Positive

1. **Repeatability**: Same company through ICP scorer always gets same score
2. **Explainability**: Can trace every decision to its source
3. **Cost efficiency**: Algorithms are free, LLM calls are expensive
4. **Performance**: Algorithms run in <10ms vs LLM 1-2s
5. **Testability**: Algorithms can be unit tested with deterministic assertions
6. **Outcome-based pricing**: Can charge based on results because they're reproducible

### Negative

1. **Complexity**: Four layers are more complex than pure LLM
2. **Development time**: Need to implement algorithms separately from prompts
3. **Maintenance**: More code to maintain across layers
4. **Integration challenges**: Need to coordinate between layers

### Neutral

1. **Architecture change**: Existing pure-LLM agents need refactoring
2. **Skill requirements**: Team needs algorithm development skills, not just prompt engineering
3. **Testing strategy**: Need different testing approaches for each layer

## Metrics

Track these metrics to validate the architecture:

| Metric | Target | Rationale |
|--------|--------|-----------|
| Determinism Ratio | >70% | Most decisions should be algorithmic |
| LLM Cost per Analysis | <$0.50 | Keep LLM usage efficient |
| Algorithm Latency | <10ms | Algorithms should be fast |
| Tool Success Rate | >95% | Tools should be reliable |
| Audit Completeness | 100% | Every decision must be logged |

## Alternatives Considered

### Alternative 1: Pure LLM Agents
Rely entirely on LLM for all decisions.

**Rejected because**:
- Non-deterministic outputs
- High cost per operation
- Cannot attribute decisions
- No audit trail
- Cannot support outcome-based pricing

### Alternative 2: Pure Rule-Based System
No LLM, only algorithms and rules.

**Rejected because**:
- Cannot handle novel situations
- No natural language understanding
- Cannot generate creative content
- Poor user experience for complex queries

### Alternative 3: Hybrid without Governance Layer
Three layers without explicit governance.

**Rejected because**:
- Cannot ensure compliance (PDPA)
- No clear audit trail
- Access control would be ad-hoc
- Budget control impossible

## References

- [Agent Development Guide](../guides/agent-development.md)
- [Tool Development Guide](../guides/tool-development.md)
- [Governance Guide](../guides/governance.md)
- Grace Framework CLAUDE.md (architecture principles)

## Decision Date

2024-01-15

## Decision Makers

- Architecture Team
- Based on user feedback and production requirements
