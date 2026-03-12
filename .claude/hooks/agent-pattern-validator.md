# Agent Pattern Validator (Post-Edit Hook)

## Trigger: After editing any file matching agents/*/src/agent.py

## Validation checks to perform:

### 1. PDCA completeness
After editing an agent file, verify the following methods exist:
- `async def _plan(`
- `async def _do(`
- `async def _check(`
- `async def _act(`

If any are missing, immediately flag:
> WARNING: Agent file missing PDCA method(s): [list missing methods]
> This violates the Grace Framework contract. Add the missing method before continuing.

### 2. Real data source check
The `_do()` method should call at least one of:
- `self.use_tool(`
- `await mcp.`
- `ICPScorer` or `BANTScorer` or `MarketSegmentation`
- `bus.get_history(`

If `_do()` contains only `await self._complete_structured(` with no data source call, flag:
> WARNING: _do() appears to be pure LLM generation. Add a real data source call.

### 3. Hardcoded confidence check
If `_check()` contains `return 0.` followed by a fixed float (e.g., `return 0.85`), flag:
> WARNING: _check() returns hardcoded confidence. Compute from data quality.

### 4. Wrong import check
If the file contains `from packages.core.src.types import SubscriptionTier`, flag:
> WARNING: Import SubscriptionTier from packages.database.src.models instead.
