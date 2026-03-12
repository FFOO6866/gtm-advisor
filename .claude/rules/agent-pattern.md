# Agent Pattern Rules

## Scope: agents/*/src/*.py, agents/core/src/*.py

## Rule 1: All Agents MUST Inherit BaseGTMAgent
```python
# CORRECT
from agents.core.src.base_agent import BaseGTMAgent

class MyAgent(BaseGTMAgent[MyResult]):
    ...

# WRONG - do not subclass anything else
class MyAgent(object):
    ...
```

## Rule 2: All 4 PDCA Methods Must Be Present
Every concrete agent class must define `_plan`, `_do`, `_check`, and `_act`.
Missing any of these is a bug.

## Rule 3: _do() Must Use Real Data Sources
The `_do()` method must call at least one real data source. Pure LLM generation is NOT acceptable for a _do() implementation.

Acceptable real data sources:
- `self.use_tool("company_enrichment", ...)`
- `await mcp.research_topic(...)`
- `await mcp.get_company_info(...)`
- `await mcp.find_market_news(...)`
- Algorithm calls: `ICPScorer.score(...)`, `BANTScorer.score(...)`
- `bus.get_history(analysis_id=..., discovery_type=...)`

## Rule 4: _check() Must Compute Confidence From Data
```python
# CORRECT - derived from actual data quality
async def _check(self, result: MyResult) -> float:
    score = len(result.items) / self._expected_items
    return min(0.95, score)

# WRONG - hardcoded value
async def _check(self, result: MyResult) -> float:
    return 0.85
```

## Rule 5: SubscriptionTier Import Source
```python
# CORRECT
from packages.database.src.models import SubscriptionTier

# WRONG - it re-exports from database but this creates confusion
from packages.core.src.types import SubscriptionTier
```

## Rule 6: _plan() Must Load the Domain Knowledge Pack
Every agent must load its synthesized knowledge guides in `_plan()` so `_do()` can inject them:

```python
# CORRECT — load in _plan(), access via getattr in _do()
async def _plan(self, task: str, context: dict | None = None, **kwargs) -> dict:
    context = context or {}
    kmcp = get_knowledge_mcp()
    self._knowledge_pack = await kmcp.get_agent_knowledge_pack(
        agent_name="my-agent",   # must match key in _AGENT_GUIDE_MAP
        task_context=task,
    )
    ...

async def _do(self, plan: dict, context: dict | None = None, **kwargs) -> MyResult:
    _knowledge_ctx = getattr(self, "_knowledge_pack", {}).get("formatted_injection", "")
    _knowledge_header = f"{_knowledge_ctx}\n\n---\n\n" if _knowledge_ctx else ""
    messages = [
        {"role": "system", "content": self.get_system_prompt()},
        {"role": "user", "content": f"{_knowledge_header}Your task prompt..."},
    ]
    ...
```

When no guide files exist (before running `synthesize_domain_guides.py`), `formatted_injection`
is `""` and the agent falls back to normal behaviour — no errors.

**Variable naming:** if the agent's `_do()` already uses `kmcp` for framework access,
name the `_plan()` variable `kmcp_pack` to avoid shadowing.

## Rule 7: Domain Guide Injection Goes in the User Message, Not System Prompt
The knowledge pack is task-specific context, not persistent agent identity. Always inject it
into the user message so it's treated as operational instruction, not permanent character.

## Learned Rules
These rules were distilled from code reviews and red-team sessions on this codebase.
