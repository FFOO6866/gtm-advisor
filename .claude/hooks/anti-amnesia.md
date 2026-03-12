# Anti-Amnesia Pre-Session Checklist

## Run this checklist before modifying any file

### Step 1: Orient yourself
- [ ] Read CLAUDE.md (project root) — what is the architecture?
- [ ] Identify which package/agent/service you are modifying
- [ ] Read the target module's docstring and imports

### Step 2: Import verification
Before writing any new import, verify:
- [ ] `SubscriptionTier` → `from packages.database.src.models import SubscriptionTier`
- [ ] `BudgetExceededError` → `from packages.core.src.errors import BudgetExceededError`
- [ ] `AgentBus` → `from packages.core.src.agent_bus import AgentBus`
- [ ] `BaseGTMAgent` → `from agents.core.src.base_agent import BaseGTMAgent`

### Step 3: PDCA completeness check
If modifying an agent file:
- [ ] Does the class have `_plan()`?
- [ ] Does the class have `_do()`?
- [ ] Does the class have `_check()`? (returns computed float, not hardcoded)
- [ ] Does the class have `_act()`?

### Step 4: Type hygiene
- [ ] Are you using `Pydantic v2` patterns? (`.model_dump()` not `.dict()`)
- [ ] Are you using `async/await` correctly? (no `asyncio.run()` inside async context)
- [ ] Are you using `structlog.get_logger()` for logging?

### Step 5: Test coverage
- [ ] Is there a corresponding test file in `tests/unit/` or `tests/integration/`?
- [ ] Does your change require a new test case?
