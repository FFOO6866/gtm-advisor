# Skill: Add a New GTM Agent

## When to use
When adding a new specialized agent to the GTM Advisor platform.

## Step-by-step

### 1. Create the directory structure
```bash
mkdir -p agents/{agent_name}/src
touch agents/{agent_name}/__init__.py
touch agents/{agent_name}/src/__init__.py
touch agents/{agent_name}/src/agent.py
touch agents/{agent_name}/src/types.py
touch agents/{agent_name}/pyproject.toml
```

### 2. Define agent types (types.py)
```python
"""Types for {AgentName} agent."""
from pydantic import BaseModel, Field

class {AgentName}Output(BaseModel):
    """Result produced by {AgentName}Agent."""
    # Define output fields here
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
```

### 3. Implement the agent (agent.py)
```python
"""
{AgentName} Agent - {One-line description}.
"""
from agents.core.src.base_agent import BaseGTMAgent
from .types import {AgentName}Output

class {AgentName}Agent(BaseGTMAgent[{AgentName}Output]):
    def __init__(self):
        super().__init__(
            name="{agent-name}",       # kebab-case
            description="{description}",
            result_type={AgentName}Output,
            min_confidence=0.7,
            max_iterations=3,
        )

    async def _plan(self, task: str, context: dict | None = None, **kwargs) -> dict:
        return {"strategy": "...", "data_sources": [...]}

    async def _do(self, plan: dict, context: dict | None = None, **kwargs) -> {AgentName}Output:
        # MUST call real data source here
        ...

    async def _check(self, result: {AgentName}Output) -> float:
        # Compute from data quality
        return min(0.95, len(result.items) / 5)

    async def _act(self, result: {AgentName}Output, confidence: float) -> {AgentName}Output:
        return result
```

### 4. Register in agent registry
Add to `services/gateway/src/agents_registry.py` in **both** `get_agent_class()` and `get_all_agent_classes()` functions:
```python
# Inside the function, add to the existing `agents` dict:
from agents.{agent_name}.src.agent import {AgentName}Agent

agents = {
    ...existing entries...,
    "{agent-name}": {AgentName}Agent,
}
```
Also add a metadata entry to the `AGENT_METADATA` dict at the top of the file:
```python
"{agent-name}": {
    "title": "{Agent Title}",
    "color": "#RRGGBB",
    "avatar": "🔧",
    "task_description": "{One-line description}",
},
```

### 5. Write tests
```bash
touch tests/unit/agents/test_{agent_name}_agent.py
```
Follow test-writer agent guidelines.

### 6. Verify PDCA completeness
Run the agent-pattern-validator checklist against your new agent.
