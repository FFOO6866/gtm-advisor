# GTM Advisor → HiMeet Platform Roadmap

> Comprehensive task list incorporating technical audit findings and business plan requirements

## Business Plan Summary

### Two-Tier Model
- **Tier 1 ($700/month)**: Self-serve AI marketing execution engine
- **Tier 2 ($7,000/month)**: Advisory + Governance with human-in-the-loop

### Required Agent Restructure

| Business Plan Agent | Current Agent | Gap |
|---------------------|---------------|-----|
| Enterprise Marketing & Growth Strategy | GTM Strategist | Needs board-ready outputs, growth hypotheses |
| Continuous Market & Competitive Intelligence | Market Intelligence + Competitor Analyst | Needs continuous monitoring, not one-time |
| GTM Strategy & Commercialisation | (partial in GTM Strategist) | New: pricing/packaging optimization |
| Strategic Campaign Architecture | Campaign Architect | Needs budget modeling, ROI focus |
| Brand, Narrative & Corporate Communications | (missing) | **NEW AGENT NEEDED** |
| Marketing Performance Governance & ROI | (missing) | **NEW AGENT NEEDED** |
| Qualified Demand & Pipeline Enablement | Lead Hunter | Needs PDPA-safe intent signals |

---

## Phase 1: Critical Security & Foundation (Week 1-2)

### 1.1 Authentication & Authorization
- [ ] **Implement JWT authentication**
  - Add `/auth/login`, `/auth/register`, `/auth/refresh` endpoints
  - Create `User` model with password hashing (bcrypt)
  - Add JWT middleware to protect all `/api/v1/*` routes
  - File: `services/gateway/src/routers/auth.py`

- [ ] **Implement tier-based access control**
  - Add `SubscriptionTier` to user model (FREE, TIER1, TIER2)
  - Create permission decorator for tier-gated endpoints
  - Implement usage tracking per tier
  - File: `packages/governance/src/access.py` (extend)

- [ ] **Add API rate limiting**
  - Implement Redis-based rate limiter middleware
  - Tier 1: 100 requests/hour, Tier 2: 1000 requests/hour
  - File: `services/gateway/src/middleware/rate_limit.py`

### 1.2 Remove Mock Data Fallbacks
- [ ] **Lead Hunter: Remove fake company fallback**
  - Location: `agents/lead_hunter/src/agent.py:505-512`
  - Replace with proper error response when no data found
  - Add `data_source` field to indicate real vs enriched

- [ ] **Company Enrichment: Handle API failures gracefully**
  - Return partial data with clear `completeness_score`
  - Never return synthetic data without explicit flag

- [ ] **Add data provenance tracking**
  - Every data point should have `source`, `confidence`, `fetched_at`
  - Create `DataProvenance` model in `packages/core/src/types.py`

### 1.3 Database Persistence
- [ ] **Set up PostgreSQL schema**
  - Users, Companies, Analyses, Consents, AuditLogs
  - Use SQLAlchemy async with Alembic migrations
  - File: `packages/database/` (new package)

- [ ] **Migrate consent storage to PostgreSQL**
  - Replace in-memory `_consent_records` dict
  - Add proper CRUD operations
  - File: `packages/governance/src/compliance.py`

- [ ] **Persist analysis results**
  - Replace `_analyses: dict[UUID, dict]` in analysis.py
  - Add analysis history per company/user

---

## Phase 2: Testing Foundation (Week 2-3)

### 2.1 Unit Tests
- [ ] **Agent base class tests**
  ```
  tests/unit/agents/test_base_agent.py
  - test_pdca_cycle_completes
  - test_confidence_threshold_triggers_retry
  - test_max_iterations_raises_error
  - test_fast_execute_mode
  ```

- [ ] **Algorithm tests**
  ```
  tests/unit/algorithms/
  - test_icp_scorer.py
  - test_lead_scorer.py
  - test_calculators.py
  ```

- [ ] **Governance tests**
  ```
  tests/unit/governance/
  - test_pdpa_compliance.py
  - test_consent_management.py
  - test_pii_detection.py
  ```

### 2.2 Integration Tests
- [ ] **API endpoint tests**
  ```
  tests/integration/api/
  - test_analysis_endpoints.py
  - test_auth_endpoints.py
  - test_websocket.py
  ```

- [ ] **External service mocking**
  - Create fixtures for Perplexity, NewsAPI, EODHD
  - Use `pytest-httpx` for async HTTP mocking

### 2.3 E2E Tests
- [ ] **Full analysis flow test**
  - Start analysis → WebSocket updates → Get results
  - Verify all agents execute in correct order

---

## Phase 3: Agent Restructuring (Week 3-5)

### 3.1 New Agent: Brand & Communications Agent
- [ ] **Create `agents/brand_communications/`**
  ```python
  class BrandCommunicationsAgent(BaseGTMAgent[BrandAnalysisOutput]):
      # Tasks:
      # - Map media and influencer landscape
      # - Analyze brand narratives and credibility gaps
      # - Develop corporate narrative frameworks
      # - Identify thought leadership opportunities
      # - Monitor sentiment and tone consistency
  ```

- [ ] **Data sources needed**
  - Social listening API (Brandwatch, Mention, or Perplexity)
  - Media database integration
  - Sentiment analysis pipeline

### 3.2 New Agent: Performance Governance Agent
- [ ] **Create `agents/performance_governance/`**
  ```python
  class PerformanceGovernanceAgent(BaseGTMAgent[PerformanceReport]):
      # Tasks:
      # - Define performance governance frameworks
      # - Track full-funnel performance
      # - Analyze marketing ROI
      # - Generate executive-ready insights
      # - Support board-level reviews
  ```

- [ ] **Data integrations needed**
  - Google Analytics / GA4 API
  - Marketing platform APIs (HubSpot, Salesforce)
  - Custom metrics ingestion

### 3.3 Enhance Existing Agents

#### Market Intelligence → Continuous Intelligence
- [ ] **Add continuous monitoring capability**
  - Create scheduled job for daily/weekly scans
  - Store historical data for trend comparison
  - Add "What changed since last scan" output

- [ ] **Add competitive tracking**
  - Competitor website change detection
  - Social media monitoring
  - News alert aggregation

#### Lead Hunter → Qualified Demand Agent
- [ ] **Rename to `qualified_demand_agent`**
- [ ] **Add buyer intent signals**
  - Website visit tracking integration
  - Content engagement scoring
  - Email interaction signals

- [ ] **Improve PDPA compliance**
  - Consent verification before any outreach recommendation
  - Clear data retention policies
  - Opt-out tracking

#### Campaign Architect → Strategic Campaign Agent
- [ ] **Add budget modeling**
  - ROI prediction models
  - Budget allocation optimizer
  - Scenario comparison tool

- [ ] **Add channel orchestration**
  - Multi-channel sequencing
  - Attribution modeling
  - Performance-based reallocation

### 3.4 GTM Commercialisation Agent (New)
- [ ] **Create `agents/gtm_commercial/`**
  ```python
  class GTMCommercialAgent(BaseGTMAgent[CommercialStrategyOutput]):
      # Tasks:
      # - Analyze segments and buying committees
      # - Design GTM strategies
      # - Evaluate channel effectiveness
      # - Recommend pricing and packaging
      # - Align with sales enablement
  ```

---

## Phase 4: Tier Implementation (Week 5-7)

### 4.1 Tier 1 ($700/month) Features

#### Self-Serve Intelligence Dashboard
- [ ] **Monthly intelligence summary**
  - Automated monthly report generation
  - Competitor movement highlights
  - Opportunity/threat summary

- [ ] **Campaign builder UI**
  - Drag-and-drop campaign planner
  - Channel recommendation engine
  - Budget split calculator

#### Content Generation (Limited)
- [ ] **Integrate content generation**
  - LinkedIn post generator
  - Email template creator
  - Ad copy variations
  - Monthly limit: 50 pieces

- [ ] **Content calendar**
  - Publishing schedule suggestions
  - Platform-specific formatting

#### Self-Serve Outputs
- [ ] **Automated report generation**
  - PDF export capability
  - Scheduled email delivery
  - Dashboard widgets

### 4.2 Tier 2 ($7,000/month) Features

#### Human-in-the-Loop
- [ ] **Implement real checkpoint approval**
  - Replace auto-approve with Slack/email notifications
  - Dashboard approval interface
  - Escalation workflows
  - File: `packages/governance/src/checkpoints.py`

- [ ] **Advisory session scheduling**
  - Calendar integration (Calendly API)
  - Session notes storage
  - Action item tracking

#### Board-Ready Outputs
- [ ] **Executive report templates**
  - Board presentation format
  - Financial impact summaries
  - Strategic recommendation briefs

- [ ] **Performance governance dashboard**
  - C-suite metrics view
  - ROI tracking
  - Investment efficiency analysis

#### Advanced Agent Capabilities
- [ ] **Enable full agent suite**
  - Remove Tier 1 limitations
  - Priority processing queue
  - Dedicated support channel

---

## Phase 5: Confidence & Quality (Week 7-8)

### 5.1 Fix Confidence Scoring
- [ ] **Replace arbitrary weights with data-driven approach**
  - Track prediction accuracy over time
  - Implement calibration metrics
  - A/B test confidence calculations

- [ ] **Rename to "Completeness Score"**
  - More honest representation
  - Clear breakdown of what's missing
  - Actionable improvement suggestions

### 5.2 True Self-Correction
- [ ] **Implement actual refinement in `_act()` methods**
  - Identify specific gaps in result
  - Re-query with targeted prompts
  - Merge improvements into result

- [ ] **Add feedback loop**
  - User feedback collection
  - Result quality rating
  - Model fine-tuning pipeline

### 5.3 Agent Orchestration
- [ ] **Make GTM Strategist a true orchestrator**
  - Use A2A bus for work distribution
  - Remove direct agent calls from analysis.py
  - Implement dependency graph execution

---

## Phase 6: Infrastructure & DevOps (Week 8-9)

### 6.1 CI/CD Pipeline
- [ ] **GitHub Actions workflow**
  ```yaml
  # .github/workflows/ci.yml
  - Lint (ruff)
  - Type check (mypy)
  - Unit tests
  - Integration tests
  - Build Docker images
  - Deploy to staging
  ```

- [ ] **Deployment automation**
  - Staging environment auto-deploy on PR merge
  - Production deploy with manual approval
  - Rollback capability

### 6.2 Kubernetes Deployment
- [ ] **Create K8s manifests**
  ```
  deployment/kubernetes/
  - gateway-deployment.yaml
  - dashboard-deployment.yaml
  - redis-statefulset.yaml
  - postgres-statefulset.yaml
  - ingress.yaml
  - secrets.yaml (template)
  ```

- [ ] **Add resource limits and autoscaling**
  - HorizontalPodAutoscaler for gateway
  - Resource requests/limits
  - Pod disruption budgets

### 6.3 Observability
- [ ] **Enable full observability stack**
  - Jaeger tracing integration
  - Prometheus metrics
  - Grafana dashboards
  - Alert rules

- [ ] **Add business metrics**
  - Analysis completion rate
  - Agent success/failure rates
  - User engagement tracking

### 6.4 Security Hardening
- [ ] **Secrets management**
  - Migrate to HashiCorp Vault or AWS Secrets Manager
  - Rotate API keys automatically
  - Audit secret access

- [ ] **Network security**
  - Enable HTTPS with auto-renew certs
  - Network policies for pod isolation
  - WAF rules for API protection

---

## Phase 7: Real Data Sources (Week 9-11)

### 7.1 Lead/Company Database
- [ ] **Integrate professional data sources**
  - Option A: Apollo.io API
  - Option B: ZoomInfo API
  - Option C: LinkedIn Sales Navigator
  - Evaluate cost vs. coverage trade-offs

### 7.2 Marketing Platform Integrations
- [ ] **HubSpot full integration**
  - Replace mock with real API
  - Sync contacts, deals, campaigns
  - Bidirectional data flow

- [ ] **Google Analytics integration**
  - GA4 API connection
  - Traffic and conversion data
  - Attribution data

- [ ] **Social media APIs**
  - LinkedIn Pages API
  - Twitter/X API
  - Meta Business API

### 7.3 Financial Data Enhancement
- [ ] **Expand EODHD usage**
  - Company financials
  - Industry benchmarks
  - Economic indicators

---

## Phase 8: Frontend Enhancements (Week 11-12)

### 8.1 Dashboard Improvements
- [ ] **Add authentication UI**
  - Login/register pages
  - Password reset flow
  - Session management

- [ ] **WebSocket reconnection**
  - Exponential backoff retry
  - Connection status indicator
  - Offline queue for messages

- [ ] **Results persistence**
  - Save analysis history
  - Compare analyses
  - Export functionality

### 8.2 Tier-Specific UI
- [ ] **Tier 1 dashboard**
  - Self-serve intelligence view
  - Campaign builder
  - Content generator
  - Usage meter

- [ ] **Tier 2 dashboard**
  - Executive summary view
  - Approval workflow UI
  - Advisory session booking
  - Board report generator

### 8.3 Mobile Responsiveness
- [ ] **Responsive design audit**
  - Mobile-friendly layouts
  - Touch-optimized interactions
  - Progressive Web App (PWA)

---

## Phase 9: Rebranding (Week 12)

### 9.1 Brand Update
- [ ] **Rename to HiMeet**
  - Update all references
  - New logo integration
  - Color scheme update

- [ ] **Product naming**
  - HiMeet Platform (Tier 1)
  - HiMeet Advisory (Tier 2)
  - HiMeet Intelligence (feature module)

### 9.2 Marketing Site
- [ ] **Create landing pages**
  - Tier comparison
  - Feature highlights
  - Pricing page
  - Case studies (when available)

---

## Task Priority Matrix

| Priority | Task Area | Business Impact | Technical Risk |
|----------|-----------|-----------------|----------------|
| P0 | Authentication | Blocker | Medium |
| P0 | Remove mock data | Trust-breaking | Low |
| P0 | Basic tests | Reliability | Low |
| P1 | Database persistence | Data loss risk | Medium |
| P1 | New agents (Brand, Performance) | Feature gap | Medium |
| P1 | Tier implementation | Revenue | Medium |
| P2 | CI/CD | Velocity | Low |
| P2 | Real data sources | Quality | High (cost) |
| P2 | Confidence scoring | Trust | Medium |
| P3 | K8s deployment | Scale | Medium |
| P3 | Mobile UI | Reach | Low |
| P3 | Rebranding | Marketing | Low |

---

## Success Metrics

### Technical Health
- [ ] Test coverage > 80%
- [ ] Zero critical security vulnerabilities
- [ ] API latency p95 < 500ms
- [ ] Uptime > 99.5%

### Business Metrics
- [ ] Tier 1 MRR target: $7,000 (10 customers)
- [ ] Tier 2 MRR target: $21,000 (3 customers)
- [ ] Customer retention > 85%
- [ ] NPS > 40

### Quality Metrics
- [ ] Analysis accuracy (user-validated) > 70%
- [ ] Lead qualification accuracy > 60%
- [ ] Content generation acceptance rate > 50%

---

## Timeline Summary

| Phase | Duration | Focus |
|-------|----------|-------|
| Phase 1 | Week 1-2 | Security & Foundation |
| Phase 2 | Week 2-3 | Testing |
| Phase 3 | Week 3-5 | Agent Restructuring |
| Phase 4 | Week 5-7 | Tier Implementation |
| Phase 5 | Week 7-8 | Quality & Confidence |
| Phase 6 | Week 8-9 | Infrastructure |
| Phase 7 | Week 9-11 | Real Data Sources |
| Phase 8 | Week 11-12 | Frontend |
| Phase 9 | Week 12 | Rebranding |

**Total: ~12 weeks to production-ready HiMeet Platform**
