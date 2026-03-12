# Gold Standards: Annotated Examples

## 1. Correctly Implemented Agent (MarketIntelligenceAgent pattern)

A correctly implemented agent:
- Inherits BaseGTMAgent with type parameter
- _plan() returns structured dict with strategy
- _do() calls REAL data sources (MCP, tools, algorithms)
- _check() computes confidence from data completeness
- _act() returns result when confidence OK

```python
class GoldStandardAgent(BaseGTMAgent[GoldResult]):
    def __init__(self):
        super().__init__(
            name="gold-standard",
            description="Example of correct implementation",
            result_type=GoldResult,
            min_confidence=0.7,
            max_iterations=3,
        )
        # _mcp is NOT inherited — must be explicitly created if using MCP servers
        from agents.core.src.mcp_integration import AgentMCPClient
        self._mcp = AgentMCPClient()

    async def _plan(self, task: str, context: dict | None = None, **kwargs) -> dict:
        # Returns structured strategy - not empty, not just "{'task': task}"
        return {
            "search_queries": [f"Singapore {context.get('industry', '')} market"],
            "data_sources": ["perplexity", "newsapi"],
            "target_count": 10,
        }

    async def _do(self, plan: dict, context: dict | None = None, **kwargs) -> GoldResult:
        # Step 1: Get real data (not just LLM)
        facts = await self._mcp.research_topic(
            plan["search_queries"][0],
            industry=context.get("industry"),
        )

        # Step 2: Synthesize with LLM (using real data as context)
        context_str = "\n".join(f.claim for f in facts[:5])
        result = await self._complete_structured(
            GoldResult,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": f"Based on: {context_str}\n\nAnalyze: {plan}"},
            ],
        )
        return result

    async def _check(self, result: GoldResult) -> float:
        # Computed from data, not hardcoded
        has_items = len(result.items) > 0
        has_sources = len(result.sources) > 0
        completeness = (int(has_items) + int(has_sources)) / 2
        return min(0.95, completeness * 0.9)

    async def _act(self, result: GoldResult, confidence: float) -> GoldResult:
        # Just return if confidence is acceptable
        return result
```

## 2. Correct Repository Pattern

```python
class AnalysisRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, analysis_id: UUID, company_id: UUID) -> Analysis:
        obj = Analysis(id=analysis_id, company_id=company_id, status="running")
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def save_result(self, analysis_id: UUID, result: GTMAnalysisResult) -> None:
        stmt = (
            update(Analysis)
            .where(Analysis.id == analysis_id)
            .values(
                status="completed",
                result_data=result.model_dump(mode="json"),
                completed_at=datetime.utcnow(),
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
```

## 3. Correct Test Pattern

```python
@pytest.mark.unit
class TestLeadHunterAgent:
    async def test_check_returns_low_confidence_for_empty_leads(
        self, mock_llm_manager
    ):
        agent = LeadHunterAgent(llm_manager=mock_llm_manager)
        result = LeadHuntingOutput(leads=[], total_found=0, qualified_count=0)
        confidence = await agent._check(result)
        assert confidence < 0.5, f"Expected low confidence, got {confidence}"

    async def test_do_calls_enrichment_tool(self, mock_llm_manager):
        agent = LeadHunterAgent(llm_manager=mock_llm_manager)
        with patch.object(agent, "use_tool", new_callable=AsyncMock) as mock_tool:
            mock_tool.return_value = {"companies": []}
            await agent._do(plan={"search_queries": ["test"]}, context={})
        mock_tool.assert_called()  # Proves real data source was called
```

## 4. Correct AgentBus Usage

```python
# Publishing (from an agent)
await bus.publish(
    from_agent="lead-hunter",
    to_agent=None,  # Broadcast
    discovery_type=DiscoveryType.LEAD_FOUND,
    title="New lead found: TechCorp",
    content={"company_name": "TechCorp", "fit_score": 0.82},
    confidence=0.82,
    analysis_id=analysis_id,
)

# Subscribing (from another agent)
# subscribe() takes ONE discovery_type (singular) and handler= (not callback=)
# Call subscribe() once per type, or pass None for wildcard (all types)
bus.subscribe(
    agent_id="campaign-architect",
    discovery_type=DiscoveryType.LEAD_FOUND,
    handler=self._on_discovery,
)
bus.subscribe(
    agent_id="campaign-architect",
    discovery_type=DiscoveryType.PERSONA_DEFINED,
    handler=self._on_discovery,
)
```
