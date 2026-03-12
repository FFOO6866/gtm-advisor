# Naming Convention Rules

## Scope: All Python files

| Context | Convention | Example |
|---------|------------|---------|
| Python variables | snake_case | `lead_score`, `analysis_id` |
| Python classes | PascalCase | `LeadHunterAgent`, `GTMAnalysisResult` |
| API JSON fields | camelCase | `fitScore`, `companyName` |
| Agent names (kebab) | kebab-case | `lead-hunter`, `market-intelligence` |
| Directories | snake_case | `market_intelligence/`, `customer_profiler/` |
| Test files | `test_*.py` | `test_base_agent.py` |
| Environment vars | UPPER_SNAKE_CASE | `OPENAI_API_KEY` |

## Agent Registration Names
Agent `name` parameter must use kebab-case:
```python
class LeadHunterAgent(BaseGTMAgent[LeadHuntingOutput]):
    def __init__(self):
        super().__init__(
            name="lead-hunter",  # kebab-case
            ...
        )
```

## File Organization
- Agent implementation: `agents/{snake_case_name}/src/agent.py`
- Agent types: `agents/{name}/src/types.py`
- Package utilities: `packages/{name}/src/{module}.py`
- Gateway routers: `services/gateway/src/routers/{resource}.py`
