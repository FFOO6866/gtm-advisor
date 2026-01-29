# React Component Structure

> Implementation guide for HiMeet Platform UI

## Directory Structure

```
services/dashboard/src/
├── components/
│   ├── common/                    # Shared UI components
│   │   ├── Card.tsx
│   │   ├── Button.tsx
│   │   ├── Badge.tsx
│   │   ├── Modal.tsx
│   │   ├── Tabs.tsx
│   │   ├── ProgressBar.tsx
│   │   ├── MetricCard.tsx
│   │   ├── InsightCard.tsx
│   │   ├── LoadingSpinner.tsx
│   │   └── TierGate.tsx           # Locks features by tier
│   │
│   ├── layout/                    # Layout components
│   │   ├── AppShell.tsx           # Main app wrapper
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   ├── CommandCenter.tsx      # Main dashboard
│   │   └── PageContainer.tsx
│   │
│   ├── agents/                    # Agent-specific components
│   │   ├── AgentNetwork.tsx       # Visual network (existing)
│   │   ├── AgentCard.tsx          # Card for command center
│   │   ├── AgentWorkspace.tsx     # Base workspace template
│   │   ├── AgentStatusBadge.tsx
│   │   ├── AgentConnectionLine.tsx
│   │   │
│   │   ├── strategy/              # Strategy Agent
│   │   │   ├── StrategyWorkspace.tsx
│   │   │   ├── StrategicPriorityCard.tsx
│   │   │   ├── GrowthHypothesisCard.tsx
│   │   │   └── RiskAssessmentPanel.tsx
│   │   │
│   │   ├── intelligence/          # Intelligence Agent
│   │   │   ├── IntelligenceWorkspace.tsx
│   │   │   ├── CompetitorTracker.tsx
│   │   │   ├── MarketTrendCard.tsx
│   │   │   └── AlertsPanel.tsx
│   │   │
│   │   ├── campaign/              # Campaign Agent
│   │   │   ├── CampaignWorkspace.tsx
│   │   │   ├── CampaignBuilder.tsx
│   │   │   ├── ContentGenerator.tsx
│   │   │   ├── BudgetModeler.tsx
│   │   │   └── ChannelSelector.tsx
│   │   │
│   │   ├── demand/                # Qualified Demand Agent
│   │   │   ├── DemandWorkspace.tsx
│   │   │   ├── AccountCard.tsx
│   │   │   ├── IntentSignalsPanel.tsx
│   │   │   ├── PipelineChart.tsx
│   │   │   └── PDPAStatusBadge.tsx
│   │   │
│   │   ├── performance/           # Performance Agent (Tier 2)
│   │   │   ├── PerformanceWorkspace.tsx
│   │   │   ├── ScoreCard.tsx
│   │   │   ├── FunnelChart.tsx
│   │   │   ├── ROIAnalysis.tsx
│   │   │   └── BoardReportGenerator.tsx
│   │   │
│   │   └── brand/                 # Brand Agent (Tier 2)
│   │       ├── BrandWorkspace.tsx
│   │       ├── NarrativeFramework.tsx
│   │       └── SentimentTracker.tsx
│   │
│   ├── advisory/                  # Advisory Hub (Tier 2)
│   │   ├── AdvisoryHub.tsx
│   │   ├── ApprovalQueue.tsx
│   │   ├── ApprovalCard.tsx
│   │   ├── SessionScheduler.tsx
│   │   └── StrategicNotes.tsx
│   │
│   ├── intelligence/              # Intelligence Feed
│   │   ├── IntelligenceFeed.tsx
│   │   ├── FeedItem.tsx
│   │   └── FeedFilters.tsx
│   │
│   ├── reports/                   # Reports & Exports
│   │   ├── ReportBuilder.tsx
│   │   ├── ReportPreview.tsx
│   │   └── ExportOptions.tsx
│   │
│   └── settings/                  # Settings
│       ├── SettingsPage.tsx
│       ├── CompanyProfile.tsx
│       ├── IntegrationsPanel.tsx
│       ├── IntegrationCard.tsx
│       └── BillingPanel.tsx
│
├── pages/                         # Page-level components
│   ├── Dashboard.tsx              # Command Center
│   ├── AgentPage.tsx              # Dynamic agent workspace
│   ├── AdvisoryPage.tsx           # Advisory Hub
│   ├── ReportsPage.tsx
│   ├── SettingsPage.tsx
│   ├── LoginPage.tsx
│   └── OnboardingPage.tsx
│
├── hooks/                         # Custom hooks
│   ├── useAgent.ts                # Agent state & actions
│   ├── useInsights.ts             # Insights feed
│   ├── useWebSocket.ts            # Real-time updates
│   ├── useTier.ts                 # Subscription tier
│   └── useApprovals.ts            # Approval queue
│
├── context/                       # React Context
│   ├── AuthContext.tsx
│   ├── TierContext.tsx
│   ├── AgentContext.tsx
│   └── WebSocketContext.tsx
│
├── api/                           # API clients
│   ├── client.ts                  # HTTP client (existing)
│   ├── agents.ts                  # Agent endpoints
│   ├── insights.ts                # Insights endpoints
│   ├── reports.ts                 # Reports endpoints
│   └── auth.ts                    # Auth endpoints
│
├── types/                         # TypeScript types
│   ├── agent.ts
│   ├── insight.ts
│   ├── campaign.ts
│   ├── lead.ts
│   └── report.ts
│
└── utils/                         # Utilities
    ├── formatting.ts
    ├── validation.ts
    └── permissions.ts
```

---

## Key Component Specifications

### 1. CommandCenter.tsx

```tsx
/**
 * Main dashboard showing agent network and intelligence feed
 */

interface CommandCenterProps {
  companyId: string;
}

const CommandCenter: React.FC<CommandCenterProps> = ({ companyId }) => {
  const { agents, isLoading } = useAgents(companyId);
  const { insights } = useInsights(companyId);
  const { tier } = useTier();

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      {/* Agent Network Hub - Full width */}
      <div className="col-span-12">
        <AgentNetworkHub
          agents={agents}
          tier={tier}
          onAgentClick={(agentId) => navigate(`/agent/${agentId}`)}
        />
      </div>

      {/* Intelligence Feed - Left side */}
      <div className="col-span-12 lg:col-span-7">
        <IntelligenceFeed
          insights={insights}
          onInsightClick={(insight) => navigate(`/agent/${insight.agentId}`)}
        />
      </div>

      {/* Quick Actions + Metrics - Right side */}
      <div className="col-span-12 lg:col-span-5 space-y-6">
        <QuickActionsPanel tier={tier} />
        <PerformanceSummary />
      </div>
    </div>
  );
};
```

### 2. AgentWorkspace.tsx (Base Template)

```tsx
/**
 * Base template for all agent workspaces
 * Individual agents extend this with their specific tabs
 */

interface AgentWorkspaceProps {
  agentId: string;
  agentName: string;
  agentIcon: string;
  status: 'active' | 'processing' | 'idle';
  lastRun: Date;
  tabs: TabDefinition[];
  children: React.ReactNode;
  onRun: () => void;
}

interface TabDefinition {
  id: string;
  label: string;
  badge?: number;
  component: React.ComponentType;
}

const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({
  agentId,
  agentName,
  agentIcon,
  status,
  lastRun,
  tabs,
  children,
  onRun,
}) => {
  const [activeTab, setActiveTab] = useState(tabs[0].id);
  const { tier } = useTier();

  return (
    <PageContainer>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <BackButton to="/" />
          <span className="text-3xl">{agentIcon}</span>
          <div>
            <h1 className="text-2xl font-bold text-white">{agentName}</h1>
            <AgentStatusBadge status={status} lastRun={lastRun} />
          </div>
        </div>
        <Button variant="primary" onClick={onRun}>
          Run ▶
        </Button>
      </div>

      {/* Status Bar */}
      <AgentStatusBar
        agentId={agentId}
        status={status}
        nextScheduledRun={/* from agent config */}
      />

      {/* Tabs */}
      <Tabs
        tabs={tabs}
        activeTab={activeTab}
        onChange={setActiveTab}
      />

      {/* Tab Content */}
      <div className="mt-6">
        {tabs.find(t => t.id === activeTab)?.component}
      </div>

      {/* Connected Agents Footer */}
      <ConnectedAgentsPanel agentId={agentId} />
    </PageContainer>
  );
};
```

### 3. IntelligenceWorkspace.tsx

```tsx
/**
 * Intelligence Agent workspace
 */

const IntelligenceWorkspace: React.FC = () => {
  const { agentId } = useParams();
  const { insights, alerts, isLoading } = useAgentInsights(agentId);
  const { runAgent } = useAgent(agentId);

  const tabs: TabDefinition[] = [
    {
      id: 'insights',
      label: 'Insights',
      badge: insights.filter(i => i.isNew).length,
      component: <InsightsTab insights={insights} />
    },
    {
      id: 'alerts',
      label: 'Alerts',
      badge: alerts.length,
      component: <AlertsTab alerts={alerts} />
    },
    {
      id: 'history',
      label: 'History',
      component: <HistoryTab agentId={agentId} />
    },
    {
      id: 'configure',
      label: 'Configure',
      component: <ConfigureTab agentId={agentId} />
    },
  ];

  return (
    <AgentWorkspace
      agentId={agentId}
      agentName="Intelligence Agent"
      agentIcon="📡"
      status={/* from hook */}
      lastRun={/* from hook */}
      tabs={tabs}
      onRun={runAgent}
    />
  );
};

// Insights Tab Component
const InsightsTab: React.FC<{ insights: Insight[] }> = ({ insights }) => {
  const [filter, setFilter] = useState({ type: 'all', period: 'month' });

  const grouped = useMemo(() => ({
    high: insights.filter(i => i.priority === 'high'),
    medium: insights.filter(i => i.priority === 'medium'),
    opportunities: insights.filter(i => i.type === 'opportunity'),
  }), [insights]);

  return (
    <div className="space-y-6">
      <InsightFilters value={filter} onChange={setFilter} />

      <InsightSection title="High Priority" priority="high">
        {grouped.high.map(insight => (
          <InsightCard key={insight.id} insight={insight} expanded />
        ))}
      </InsightSection>

      <InsightSection title="Medium Priority" priority="medium" collapsible>
        {grouped.medium.map(insight => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </InsightSection>

      <InsightSection title="Opportunities" priority="opportunity" collapsible>
        {grouped.opportunities.map(insight => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </InsightSection>
    </div>
  );
};
```

### 4. InsightCard.tsx

```tsx
/**
 * Displays a single insight with actions
 */

interface InsightCardProps {
  insight: Insight;
  expanded?: boolean;
  onSendToAgent?: (agentId: string) => void;
  onDismiss?: () => void;
}

const InsightCard: React.FC<InsightCardProps> = ({
  insight,
  expanded = false,
  onSendToAgent,
  onDismiss,
}) => {
  const [isExpanded, setIsExpanded] = useState(expanded);
  const priorityColors = {
    high: 'border-red-500 bg-red-500/10',
    medium: 'border-amber-500 bg-amber-500/10',
    opportunity: 'border-green-500 bg-green-500/10',
    info: 'border-gray-500 bg-gray-500/10',
  };

  return (
    <Card className={`border-l-4 ${priorityColors[insight.priority]}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Badge variant={insight.priority}>
            {insight.priority.toUpperCase()}
          </Badge>
          <h3 className="text-lg font-semibold text-white mt-2">
            {insight.title}
          </h3>
        </div>
        <span className="text-sm text-white/50">
          {formatRelativeTime(insight.createdAt)}
        </span>
      </div>

      {/* Summary */}
      <p className="text-white/70 mt-2">{insight.summary}</p>

      {/* Expandable Details */}
      {isExpanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-4 space-y-3"
        >
          {/* Evidence */}
          {insight.evidence && (
            <div className="flex items-start gap-2">
              <span>📊</span>
              <div>
                <span className="text-sm font-medium text-white">Evidence</span>
                <p className="text-sm text-white/70">{insight.evidence}</p>
              </div>
            </div>
          )}

          {/* Implication */}
          {insight.implication && (
            <div className="flex items-start gap-2">
              <span>💡</span>
              <div>
                <span className="text-sm font-medium text-white">Implication</span>
                <p className="text-sm text-white/70">{insight.implication}</p>
              </div>
            </div>
          )}

          {/* Recommended Action */}
          {insight.recommendedAction && (
            <div className="flex items-start gap-2">
              <span>✅</span>
              <div>
                <span className="text-sm font-medium text-white">Recommended Action</span>
                <p className="text-sm text-white/70">{insight.recommendedAction}</p>
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-white/10">
        {!expanded && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? 'Collapse' : 'View Full Analysis'}
          </Button>
        )}

        <DropdownMenu>
          <DropdownTrigger>
            <Button variant="ghost" size="sm">
              Send to Agent →
            </Button>
          </DropdownTrigger>
          <DropdownContent>
            <DropdownItem onClick={() => onSendToAgent?.('campaign')}>
              Campaign Agent
            </DropdownItem>
            <DropdownItem onClick={() => onSendToAgent?.('strategy')}>
              Strategy Agent
            </DropdownItem>
            <DropdownItem onClick={() => onSendToAgent?.('demand')}>
              Demand Agent
            </DropdownItem>
          </DropdownContent>
        </DropdownMenu>

        <Button
          variant="ghost"
          size="sm"
          onClick={onDismiss}
        >
          Dismiss
        </Button>
      </div>
    </Card>
  );
};
```

### 5. CampaignBuilder.tsx

```tsx
/**
 * Campaign planning interface
 */

interface CampaignBuilderProps {
  onGenerate: (config: CampaignConfig) => Promise<CampaignPlan>;
}

const CampaignBuilder: React.FC<CampaignBuilderProps> = ({ onGenerate }) => {
  const [config, setConfig] = useState<CampaignConfig>({
    objective: '',
    targetAudience: '',
    budget: 5000,
    duration: 3,
    channels: [],
  });
  const [plan, setPlan] = useState<CampaignPlan | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const recommendedChannels = useMemo(() =>
    getChannelRecommendations(config.targetAudience, config.budget),
    [config.targetAudience, config.budget]
  );

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const result = await onGenerate(config);
      setPlan(result);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Configuration Panel */}
      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">
          Campaign Configuration
        </h3>

        <div className="space-y-4">
          <FormField label="Campaign Objective">
            <Input
              placeholder="e.g., Generate leads for enterprise segment"
              value={config.objective}
              onChange={(e) => setConfig({ ...config, objective: e.target.value })}
            />
          </FormField>

          <FormField label="Target Audience">
            <Select
              options={AUDIENCE_OPTIONS}
              value={config.targetAudience}
              onChange={(v) => setConfig({ ...config, targetAudience: v })}
            />
          </FormField>

          <FormField label="Monthly Budget (SGD)">
            <Input
              type="number"
              value={config.budget}
              onChange={(e) => setConfig({ ...config, budget: Number(e.target.value) })}
            />
          </FormField>

          <FormField label="Duration (months)">
            <Select
              options={[1, 2, 3, 6, 12].map(n => ({ value: n, label: `${n} month${n > 1 ? 's' : ''}` }))}
              value={config.duration}
              onChange={(v) => setConfig({ ...config, duration: v })}
            />
          </FormField>

          <FormField label="Channels (AI recommended)">
            <div className="space-y-2">
              {CHANNEL_OPTIONS.map(channel => (
                <Checkbox
                  key={channel.id}
                  label={channel.name}
                  checked={config.channels.includes(channel.id)}
                  recommended={recommendedChannels.includes(channel.id)}
                  onChange={(checked) => {
                    setConfig({
                      ...config,
                      channels: checked
                        ? [...config.channels, channel.id]
                        : config.channels.filter(c => c !== channel.id)
                    });
                  }}
                />
              ))}
            </div>
          </FormField>

          <Button
            variant="primary"
            className="w-full"
            onClick={handleGenerate}
            disabled={!config.objective || isGenerating}
          >
            {isGenerating ? 'Generating...' : 'Generate Campaign Plan →'}
          </Button>
        </div>
      </Card>

      {/* Generated Plan Panel */}
      <Card>
        {!plan ? (
          <EmptyState
            icon="📋"
            title="No plan generated yet"
            description="Configure your campaign and click Generate to create a plan"
          />
        ) : (
          <CampaignPlanView
            plan={plan}
            onGenerateContent={(phase) => {/* navigate to content generator */}}
            onEdit={() => {/* open edit modal */}}
            onExport={() => {/* export to PDF */}}
          />
        )}
      </Card>
    </div>
  );
};
```

### 6. ContentGenerator.tsx

```tsx
/**
 * AI content generation interface
 */

const ContentGenerator: React.FC = () => {
  const { tier } = useTier();
  const { usage, limit } = useContentUsage();
  const [contentType, setContentType] = useState<ContentType>('linkedin');
  const [config, setConfig] = useState<ContentConfig>({});
  const [variations, setVariations] = useState<ContentVariation[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  const canGenerate = tier === 'tier2' || usage < limit;

  return (
    <div className="space-y-6">
      {/* Usage Meter */}
      <Card className="bg-purple-500/10 border-purple-500/30">
        <div className="flex items-center justify-between">
          <span className="text-white/70">
            Content this month: {usage}/{limit} pieces
          </span>
          {tier === 'tier1' && (
            <Button variant="ghost" size="sm">
              Upgrade for unlimited
            </Button>
          )}
        </div>
        <ProgressBar value={usage} max={limit} className="mt-2" />
      </Card>

      {/* Content Type Selector */}
      <div className="flex gap-2">
        {CONTENT_TYPES.map(type => (
          <Button
            key={type.id}
            variant={contentType === type.id ? 'primary' : 'ghost'}
            onClick={() => setContentType(type.id)}
          >
            {type.icon} {type.label}
          </Button>
        ))}
      </div>

      {/* Configuration */}
      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">
          {getContentTypeLabel(contentType)}
        </h3>

        <div className="space-y-4">
          <FormField label="Topic/Theme">
            <Input
              placeholder="What should this content be about?"
              value={config.topic || ''}
              onChange={(e) => setConfig({ ...config, topic: e.target.value })}
            />
          </FormField>

          <div className="grid grid-cols-3 gap-4">
            <FormField label="Tone">
              <Select
                options={TONE_OPTIONS}
                value={config.tone}
                onChange={(v) => setConfig({ ...config, tone: v })}
              />
            </FormField>

            <FormField label="Target Persona">
              <Select
                options={PERSONA_OPTIONS}
                value={config.persona}
                onChange={(v) => setConfig({ ...config, persona: v })}
              />
            </FormField>

            <FormField label="Include CTA?">
              <Checkbox
                checked={config.includeCTA}
                onChange={(v) => setConfig({ ...config, includeCTA: v })}
              />
            </FormField>
          </div>

          <FormField label="Key points to include (optional)">
            <Textarea
              placeholder="• Point 1&#10;• Point 2"
              value={config.keyPoints || ''}
              onChange={(e) => setConfig({ ...config, keyPoints: e.target.value })}
            />
          </FormField>

          <Button
            variant="primary"
            onClick={handleGenerate}
            disabled={!canGenerate || !config.topic || isGenerating}
          >
            {isGenerating ? 'Generating...' : 'Generate 3 Variations →'}
          </Button>
        </div>
      </Card>

      {/* Generated Variations */}
      {variations.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white">
            Generated Variations
          </h3>

          {variations.map((variation, index) => (
            <ContentVariationCard
              key={index}
              variation={variation}
              label={`Variation ${String.fromCharCode(65 + index)}`}
              onCopy={() => copyToClipboard(variation.content)}
              onEdit={() => openEditModal(variation)}
              onSave={() => saveToLibrary(variation)}
              onSchedule={() => openScheduleModal(variation)}
            />
          ))}
        </div>
      )}
    </div>
  );
};
```

### 7. TierGate.tsx

```tsx
/**
 * Component that locks features based on subscription tier
 */

interface TierGateProps {
  requiredTier: 'tier1' | 'tier2';
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

const TierGate: React.FC<TierGateProps> = ({
  requiredTier,
  children,
  fallback
}) => {
  const { tier, isLoading } = useTier();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const hasAccess =
    requiredTier === 'tier1' ? ['tier1', 'tier2'].includes(tier) :
    requiredTier === 'tier2' ? tier === 'tier2' :
    false;

  if (!hasAccess) {
    return fallback || (
      <Card className="bg-white/5 border-white/10">
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <span className="text-4xl mb-4">🔒</span>
          <h3 className="text-lg font-semibold text-white mb-2">
            {requiredTier === 'tier2' ? 'Advisory Feature' : 'Premium Feature'}
          </h3>
          <p className="text-white/70 mb-4 max-w-md">
            {requiredTier === 'tier2'
              ? 'This feature is available on HiMeet Advisory ($7,000/month)'
              : 'Upgrade to HiMeet Platform to access this feature'
            }
          </p>
          <Button variant="primary">
            Upgrade Now
          </Button>
        </div>
      </Card>
    );
  }

  return <>{children}</>;
};

// Usage example:
<TierGate requiredTier="tier2">
  <BoardReportGenerator />
</TierGate>
```

### 8. ApprovalQueue.tsx (Tier 2)

```tsx
/**
 * Approval queue for human-in-the-loop governance
 */

const ApprovalQueue: React.FC = () => {
  const { approvals, isLoading, approve, reject, requestChanges } = useApprovals();
  const pendingCount = approvals.filter(a => a.status === 'pending').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">
          Approval Queue
          {pendingCount > 0 && (
            <Badge variant="warning" className="ml-2">{pendingCount}</Badge>
          )}
        </h2>
      </div>

      {approvals.length === 0 ? (
        <EmptyState
          icon="✅"
          title="All caught up!"
          description="No pending approvals"
        />
      ) : (
        <div className="space-y-4">
          {approvals.map(approval => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              onApprove={() => approve(approval.id)}
              onReject={() => reject(approval.id)}
              onRequestChanges={(notes) => requestChanges(approval.id, notes)}
            />
          ))}
        </div>
      )}
    </div>
  );
};

interface ApprovalCardProps {
  approval: Approval;
  onApprove: () => void;
  onReject: () => void;
  onRequestChanges: (notes: string) => void;
}

const ApprovalCard: React.FC<ApprovalCardProps> = ({
  approval,
  onApprove,
  onReject,
  onRequestChanges,
}) => {
  const [showChangesModal, setShowChangesModal] = useState(false);

  return (
    <Card className="border-l-4 border-amber-500">
      <div className="flex items-start justify-between">
        <div>
          <Badge variant="warning">PENDING</Badge>
          <h3 className="text-lg font-semibold text-white mt-2">
            {approval.title}
          </h3>
        </div>
        <span className="text-sm text-white/50">
          {formatRelativeTime(approval.createdAt)}
        </span>
      </div>

      <p className="text-white/70 mt-2">{approval.description}</p>

      {/* Context from agent */}
      <div className="mt-4 p-3 bg-white/5 rounded-lg">
        <span className="text-sm font-medium text-white/50">
          {approval.agentName} requests:
        </span>
        <p className="text-white mt-1">{approval.requestDetails}</p>
      </div>

      {/* Checkpoint reason */}
      <div className="mt-3 flex items-center gap-2 text-sm text-white/50">
        <span>⚠️</span>
        <span>Checkpoint triggered: {approval.checkpointReason}</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-white/10">
        <Button variant="ghost" onClick={() => {/* view full context */}}>
          View Full Context
        </Button>
        <div className="flex-1" />
        <Button
          variant="ghost"
          onClick={() => setShowChangesModal(true)}
        >
          💬 Request Changes
        </Button>
        <Button
          variant="danger"
          onClick={onReject}
        >
          ✗ Reject
        </Button>
        <Button
          variant="primary"
          onClick={onApprove}
        >
          ✓ Approve
        </Button>
      </div>

      {/* Changes Modal */}
      <Modal
        isOpen={showChangesModal}
        onClose={() => setShowChangesModal(false)}
        title="Request Changes"
      >
        <Textarea
          placeholder="Describe the changes you'd like..."
          className="min-h-[100px]"
        />
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={() => setShowChangesModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => {/* submit */}}>
            Send to Agent
          </Button>
        </div>
      </Modal>
    </Card>
  );
};
```

---

## State Management

### Agent Context

```tsx
// context/AgentContext.tsx

interface AgentState {
  agents: Record<string, Agent>;
  activeAgent: string | null;
  isRunning: Record<string, boolean>;
}

interface AgentContextValue extends AgentState {
  runAgent: (agentId: string) => Promise<void>;
  getInsights: (agentId: string) => Insight[];
  sendToAgent: (fromAgent: string, toAgent: string, data: any) => void;
}

const AgentContext = createContext<AgentContextValue | null>(null);

export const AgentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(agentReducer, initialState);
  const ws = useWebSocket();

  // Listen for real-time updates
  useEffect(() => {
    ws.on('agent_update', (data) => {
      dispatch({ type: 'AGENT_UPDATE', payload: data });
    });

    ws.on('insight', (data) => {
      dispatch({ type: 'NEW_INSIGHT', payload: data });
    });

    ws.on('a2a_message', (data) => {
      dispatch({ type: 'A2A_MESSAGE', payload: data });
    });
  }, [ws]);

  const runAgent = async (agentId: string) => {
    dispatch({ type: 'AGENT_RUN_START', payload: { agentId } });
    try {
      await api.agents.run(agentId);
    } catch (error) {
      dispatch({ type: 'AGENT_RUN_ERROR', payload: { agentId, error } });
    }
  };

  return (
    <AgentContext.Provider value={{ ...state, runAgent, /* ... */ }}>
      {children}
    </AgentContext.Provider>
  );
};
```

---

## Routing Structure

```tsx
// App.tsx routing

<Routes>
  {/* Public routes */}
  <Route path="/login" element={<LoginPage />} />
  <Route path="/onboarding" element={<OnboardingPage />} />

  {/* Protected routes */}
  <Route element={<ProtectedRoute />}>
    <Route element={<AppShell />}>
      {/* Main dashboard */}
      <Route path="/" element={<Dashboard />} />

      {/* Agent workspaces */}
      <Route path="/agent/strategy" element={<StrategyWorkspace />} />
      <Route path="/agent/intelligence" element={<IntelligenceWorkspace />} />
      <Route path="/agent/campaign" element={<CampaignWorkspace />} />
      <Route path="/agent/demand" element={<DemandWorkspace />} />
      <Route path="/agent/gtm-commercial" element={<GTMCommercialWorkspace />} />

      {/* Tier 2 agents */}
      <Route path="/agent/performance" element={
        <TierGate requiredTier="tier2">
          <PerformanceWorkspace />
        </TierGate>
      } />
      <Route path="/agent/brand" element={
        <TierGate requiredTier="tier2">
          <BrandWorkspace />
        </TierGate>
      } />

      {/* Advisory (Tier 2) */}
      <Route path="/advisory" element={
        <TierGate requiredTier="tier2">
          <AdvisoryPage />
        </TierGate>
      } />

      {/* Reports */}
      <Route path="/reports" element={<ReportsPage />} />
      <Route path="/reports/board" element={
        <TierGate requiredTier="tier2">
          <BoardReportPage />
        </TierGate>
      } />

      {/* Settings */}
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/settings/integrations" element={<IntegrationsPage />} />
    </Route>
  </Route>
</Routes>
```

---

## Implementation Order

1. **Phase 1**: Core infrastructure
   - `TierGate`, `TierContext`
   - Updated `AgentContext` with real-time
   - Base `AgentWorkspace` template

2. **Phase 2**: Command Center
   - Updated `AgentNetwork` with click navigation
   - `IntelligenceFeed`
   - `QuickActionsPanel`

3. **Phase 3**: Priority agents
   - `IntelligenceWorkspace` (continuous monitoring)
   - `CampaignWorkspace` + `ContentGenerator`
   - `DemandWorkspace`

4. **Phase 4**: Tier 2 features
   - `AdvisoryHub` + `ApprovalQueue`
   - `PerformanceWorkspace`
   - `BoardReportGenerator`

5. **Phase 5**: Polish
   - Mobile responsiveness
   - Animations
   - Accessibility
