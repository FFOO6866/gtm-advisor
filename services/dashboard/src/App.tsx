/**
 * GTM Advisor Dashboard - Main Application
 *
 * Production-ready dashboard connecting to real backend API.
 * NO mock data, NO simulations - live agent execution only.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { Routes, Route, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { AuroraBackground } from './components/AuroraBackground';
import { AgentNetwork } from './components/AgentNetwork';
import { ConversationPanel } from './components/ConversationPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { Header } from './components/Header';
import { OnboardingModal } from './components/OnboardingModal';
import { AppShell } from './components/AppShell';
import { AgentActivity, Message, AnalysisResult, CompanyInfo, AGENTS } from './types';
import {
  startAnalysis,
  connectToAnalysis,
  getAnalysisResult,
  checkHealth,
  type WebSocketMessage,
  type AnalysisRequest,
} from './api/client';
import { transformAnalysisResult } from './api/transforms';

// Import context providers
import { CompanyProvider, useCompany, useCompanyId, createCompanyFromForm } from './context/CompanyContext';
import { ToastProvider } from './components/common';
import { FeatureGate } from './components/FeatureGate';

// Import agent workspace pages
import {
  IntelligenceWorkspace,
  CampaignWorkspace,
  DemandWorkspace,
  GenericAgentWorkspace,
  StrategyWorkspace,
  CompetitorWorkspace,
  CustomerWorkspace,
  EnricherWorkspace,
  WorkforceWorkspace,
  LeadsPipeline,
  ApprovalsInbox,
  SignalsFeed,
  WhyUsPage,
  DashboardPage,
  SequencesPage,
  PlaybooksPage,
  SettingsPage,
  TodayPage,
  CampaignsPage,
  ContentPage,
  ResultsPage,
  LoginPage,
  RegisterPage,
} from './pages';

/** Wrapper that pulls companyId from context and analysisId from ?analysisId=… */
function WorkforceWorkspacePage() {
  const companyId = useCompanyId() ?? '';
  const [searchParams] = useSearchParams();
  const analysisId = searchParams.get('analysisId') ?? undefined;
  return <WorkforceWorkspace companyId={companyId} analysisId={analysisId} />;
}

function App() {
  return (
    <CompanyProvider>
      <ToastProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/" element={<Dashboard />} />

          {/* Agent workspace pages — gated (hidden in production, internal-only) */}
          <Route path="/agent/market-intelligence" element={<FeatureGate flag="agentWorkspaces"><IntelligenceWorkspace /></FeatureGate>} />
          <Route path="/agent/campaign-architect" element={<FeatureGate flag="agentWorkspaces"><CampaignWorkspace /></FeatureGate>} />
          <Route path="/agent/lead-hunter" element={<FeatureGate flag="agentWorkspaces"><DemandWorkspace /></FeatureGate>} />
          <Route path="/agent/gtm-strategist" element={<FeatureGate flag="agentWorkspaces"><StrategyWorkspace /></FeatureGate>} />
          <Route path="/agent/competitor-analyst" element={<FeatureGate flag="agentWorkspaces"><CompetitorWorkspace /></FeatureGate>} />
          <Route path="/agent/customer-profiler" element={<FeatureGate flag="agentWorkspaces"><CustomerWorkspace /></FeatureGate>} />
          <Route path="/agent/company-enricher" element={<FeatureGate flag="agentWorkspaces"><EnricherWorkspace /></FeatureGate>} />
          <Route path="/agent/:agentId" element={<FeatureGate flag="agentWorkspaces"><GenericAgentWorkspace /></FeatureGate>} />

          {/* Authenticated app — AppShell provides Header + SidebarNav + Aurora */}
          <Route element={<AppShell />}>
            {/* Launch surfaces — always visible */}
            <Route path="/today" element={<TodayPage />} />
            <Route path="/campaigns" element={<CampaignsPage />} />
            <Route path="/prospects" element={<LeadsPipeline />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/why-us" element={<WhyUsPage />} />

            {/* Gated surfaces — hidden in production, internal-only */}
            <Route path="/content" element={<FeatureGate flag="contentBeta"><ContentPage /></FeatureGate>} />
            <Route path="/insights" element={<FeatureGate flag="signalsFeed"><SignalsFeed /></FeatureGate>} />
            <Route path="/signals" element={<FeatureGate flag="signalsFeed"><SignalsFeed /></FeatureGate>} />
            <Route path="/results" element={<FeatureGate flag="attributionResults"><ResultsPage /></FeatureGate>} />
            {/* Legacy alias — /leads was the old path; /prospects is canonical. Redirect for inbound links. */}
            <Route path="/leads" element={<Navigate to="/prospects" replace />} />
            <Route path="/approvals" element={<FeatureGate flag="approvals"><ApprovalsInbox /></FeatureGate>} />
            <Route path="/dashboard" element={<FeatureGate flag="dashboardOps"><DashboardPage /></FeatureGate>} />
            <Route path="/sequences" element={<FeatureGate flag="sequences"><SequencesPage /></FeatureGate>} />
            <Route path="/playbooks" element={<FeatureGate flag="playbooks"><PlaybooksPage /></FeatureGate>} />
            <Route path="/workforce" element={<FeatureGate flag="workforce"><WorkforceWorkspacePage /></FeatureGate>} />
          </Route>
        </Routes>
      </ToastProvider>
    </CompanyProvider>
  );
}

// Session storage keys
const STORAGE_KEYS = {
  companyInfo: 'gtm_company_info',
  analysisId: 'gtm_analysis_id',
};

function Dashboard() {
  const navigate = useNavigate();
  const { setCompany } = useCompany();

  // Default: always show the modal (sign-out, direct visit, cache-clear all land here).
  // Exception: if the user clicked an agent node and navigated back, skip the modal
  // so they see the network + results they left. This is signalled by 'gtm_agent_back'
  // which handleAgentClick writes and we clear immediately here (one-shot flag).
  const [showOnboarding, setShowOnboarding] = useState(() => {
    const comingBack = !!sessionStorage.getItem('gtm_agent_back');
    if (comingBack) {
      sessionStorage.removeItem('gtm_agent_back');
      const hasCompany = !!sessionStorage.getItem(STORAGE_KEYS.companyInfo);
      const hasAnalysis = !!sessionStorage.getItem(STORAGE_KEYS.analysisId);
      return !(hasCompany && hasAnalysis);
    }
    return true;
  });
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(() => {
    const stored = sessionStorage.getItem(STORAGE_KEYS.companyInfo);
    return stored ? JSON.parse(stored) : null;
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [agentActivities, setAgentActivities] = useState<AgentActivity[]>([]);
  const [results, setResults] = useState<AnalysisResult | null>(null);
  const [activeConnections, setActiveConnections] = useState<[string, string][]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isBackendAvailable, setIsBackendAvailable] = useState<boolean>(true);

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const analysisIdRef = useRef<string | null>(null);

  // Check backend health on mount
  useEffect(() => {
    const checkBackend = async () => {
      try {
        await checkHealth();
        setIsBackendAvailable(true);
      } catch {
        setIsBackendAvailable(false);
        setError('Backend API is not available. Please ensure the gateway is running on port 8000.');
      }
    };
    checkBackend();
  }, []);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleAgentClick = useCallback((agentId: string) => {
    sessionStorage.setItem('gtm_agent_back', 'true');
    navigate(`/agent/${agentId}`);
  }, [navigate]);

  // Reset everything and show onboarding again
  const handleNewAnalysis = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEYS.companyInfo);
    sessionStorage.removeItem(STORAGE_KEYS.analysisId);
    sessionStorage.removeItem('gtm_agent_back');
    setShowOnboarding(true);
    setCompanyInfo(null);
    setMessages([]);
    setResults(null);
    setAgentActivities([]);
    setActiveConnections([]);
    setError(null);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    analysisIdRef.current = null;
  }, []);

  // Handle WebSocket messages for real-time updates
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    console.log('WebSocket message:', message);

    switch (message.type) {
      case 'analysis_started':
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'agent',
            agentId: 'gtm-strategist',
            agentName: 'GTM Strategist',
            content: message.message || 'Starting analysis...',
            timestamp: new Date(),
          },
        ]);
        break;

      case 'agent_started':
        if (message.agentId) {
          // Set agent as thinking
          setAgentActivities((prev) => [
            ...prev.filter((a) => a.agentId !== message.agentId),
            {
              agentId: message.agentId!,
              agentName: message.agentName || undefined,
              status: 'thinking',
              progress: 0,
              message: message.message || undefined,
            },
          ]);

          // Show connection from strategist
          if (message.agentId !== 'gtm-strategist') {
            setActiveConnections((prev) => [...prev, ['gtm-strategist', message.agentId!]]);
          }

          // Add message
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              role: 'agent',
              agentId: message.agentId!,
              agentName: message.agentName || undefined,
              content: message.message || `${message.agentName || message.agentId} is working...`,
              timestamp: new Date(),
            },
          ]);
        }
        break;

      case 'agent_completed':
        if (message.agentId) {
          // Set agent as complete
          setAgentActivities((prev) =>
            prev.map((a) =>
              a.agentId === message.agentId
                ? {
                    ...a,
                    status: 'complete',
                    progress: 100,
                    message: message.message || undefined,
                  }
                : a
            )
          );

          // Add completion message
          const agent = AGENTS.find((a) => a.id === message.agentId);
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              role: 'agent',
              agentId: message.agentId!,
              agentName: message.agentName || agent?.name,
              content: message.message || `${message.agentName || agent?.name || message.agentId} completed.`,
              timestamp: new Date(),
            },
          ]);
        }
        break;

      case 'analysis_completed':
        setIsAnalyzing(false);
        setActiveConnections([]);
        // Sweep any agent still showing "thinking" → "complete"
        setAgentActivities((prev) =>
          prev.map((a) =>
            a.status === 'thinking' ? { ...a, status: 'complete' as const, progress: 100 } : a
          )
        );

        // Fetch full results
        if (analysisIdRef.current) {
          getAnalysisResult(analysisIdRef.current)
            .then((response) => {
              if (response.result) {
                const decisionData = message.result as {
                  algorithm_decisions?: number;
                  llm_decisions?: number;
                  tool_calls?: number;
                  determinism_ratio?: number;
                } | null;

                const transformed = transformAnalysisResult(response.result, {
                  algorithmDecisions: decisionData?.algorithm_decisions || 0,
                  llmDecisions: decisionData?.llm_decisions || 0,
                  toolCalls: decisionData?.tool_calls || 0,
                  determinismRatio: decisionData?.determinism_ratio || 0.5,
                });
                setResults(transformed);
              }
            })
            .catch((err) => {
              console.error('Failed to fetch results:', err);
              setError('Failed to fetch analysis results');
            });
        }

        // Add a clear "what's next" completion message
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'agent',
            agentId: 'gtm-strategist',
            agentName: 'GTM Strategist',
            content: message.message ||
              'Analysis complete! Your results are ready in the panel on the right. Click any agent node to explore its detailed findings, or scroll through the results panel to review leads, competitors, and campaign recommendations.',
            timestamp: new Date(),
          },
        ]);
        break;

      case 'error':
        setIsAnalyzing(false);
        setError(message.error || 'An error occurred during analysis');
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'system',
            content: `Error: ${message.error || 'Unknown error'}`,
            timestamp: new Date(),
          },
        ]);
        break;

      case 'a2a_message':
        // A2A (Agent-to-Agent) discovery message
        if (message.agentId && message.result) {
          const a2aResult = message.result as {
            discovery_type?: string;
            to_agent?: string;
            confidence?: number;
          };

          // Show A2A connection in the network
          if (a2aResult.to_agent) {
            setActiveConnections((prev) => {
              const newConnection: [string, string] = [message.agentId!, a2aResult.to_agent!];
              // Avoid duplicates
              if (!prev.some(([from, to]) => from === newConnection[0] && to === newConnection[1])) {
                return [...prev, newConnection];
              }
              return prev;
            });
          }

          // Add A2A message to conversation
          const discoveryEmoji = getDiscoveryEmoji(a2aResult.discovery_type);
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              role: 'agent',
              agentId: message.agentId!,
              agentName: AGENTS.find(a => a.id === message.agentId)?.name,
              content: `${discoveryEmoji} ${message.message || 'Published discovery'}${a2aResult.to_agent ? ` → ${AGENTS.find(a => a.id === a2aResult.to_agent)?.name || a2aResult.to_agent}` : ' (broadcast)'}`,
              timestamp: new Date(),
            },
          ]);
        }
        break;
    }
  }, []);

  // Helper function to get emoji for discovery type
  const getDiscoveryEmoji = (discoveryType?: string): string => {
    const emojiMap: Record<string, string> = {
      company_profile: '🏢',
      company_products: '📦',
      company_tech_stack: '⚙️',
      competitor_found: '🔍',
      competitor_weakness: '🎯',
      market_trend: '📈',
      market_opportunity: '💡',
      icp_segment: '👥',
      lead_found: '🎣',
      insight: '💭',
    };
    return emojiMap[discoveryType || ''] || '📡';
  };

  // Start real analysis via API
  const runAnalysis = useCallback(
    async (company: CompanyInfo) => {
      setIsAnalyzing(true);
      setError(null);
      setResults(null);
      setAgentActivities([]);
      setActiveConnections([]);

      // Add initial strategist activity
      setAgentActivities([
        {
          agentId: 'gtm-strategist',
          agentName: 'GTM Strategist',
          status: 'thinking',
          progress: 0,
        },
      ]);

      try {
        // Build analysis request
        const request: AnalysisRequest = {
          company_name: company.name,
          website: company.website,  // Website for A2A company enrichment
          description: company.description,
          industry: company.industry,
          goals: company.goals,
          challenges: company.challenges || [],
          competitors: company.competitors,
          target_markets: company.targetMarkets || ['Singapore'],
          value_proposition: company.valueProposition,
          additional_context: company.documentContext,
          include_market_research: true,
          include_competitor_analysis: true,  // Always include - A2A may discover competitors
          include_customer_profiling: true,
          include_lead_generation: true,
          include_campaign_planning: true,
          lead_count: 25,
        };

        // Start analysis
        const status = await startAnalysis(request);
        analysisIdRef.current = status.analysis_id;
        sessionStorage.setItem(STORAGE_KEYS.analysisId, status.analysis_id);

        // Update company context with real backend company_id
        if (status.company_id) {
          const realCompanyId = status.company_id;
          sessionStorage.setItem('gtm_company_id', realCompanyId);
          // Also persist to localStorage so AppShell can hydrate after login
          localStorage.setItem('gtm_company_id', realCompanyId);
          const updatedCompany = createCompanyFromForm({
            name: company.name,
            website: company.website,
            description: company.description,
            industry: company.industry,
            goals: company.goals,
            challenges: company.challenges,
            competitors: company.competitors,
            targetMarkets: company.targetMarkets,
            valueProposition: company.valueProposition,
          }, realCompanyId);
          setCompany(updatedCompany);
        }

        // Connect WebSocket for real-time updates
        const ws = connectToAnalysis(
          status.analysis_id,
          handleWebSocketMessage,
          () => {
            console.error('WebSocket error - falling back to polling');
            // Could implement polling fallback here
          },
          () => {
            console.log('WebSocket closed');
          }
        );
        wsRef.current = ws;
      } catch (err) {
        console.error('Failed to start analysis:', err);
        setError(
          err instanceof Error ? err.message : 'Failed to start analysis'
        );
        setIsAnalyzing(false);
      }
    },
    [handleWebSocketMessage, setCompany]
  );

  const handleCompanySubmit = useCallback(
    (companyData: CompanyInfo) => {
      // Clear stale analysis ID so previous results don't leak into a new run.
      sessionStorage.removeItem(STORAGE_KEYS.analysisId);
      setCompanyInfo(companyData);
      setShowOnboarding(false);

      sessionStorage.setItem(STORAGE_KEYS.companyInfo, JSON.stringify(companyData));

      // Set company in context for workspace pages
      // Temporary ID — will be replaced with real backend company_id when analysis starts
      const companyId = `company_${Date.now()}`;
      sessionStorage.setItem('gtm_company_id', companyId);
      const contextCompany = createCompanyFromForm({
        name: companyData.name,
        website: companyData.website,
        description: companyData.description,
        industry: companyData.industry,
        goals: companyData.goals,
        challenges: companyData.challenges,
        competitors: companyData.competitors,
        targetMarkets: companyData.targetMarkets,
        valueProposition: companyData.valueProposition,
      }, companyId);
      setCompany(contextCompany);

      // Add user message
      setMessages([
        {
          id: Date.now().toString(),
          role: 'user',
          content: `Analyze GTM strategy for ${companyData.name}: ${companyData.description}`,
          timestamp: new Date(),
        },
      ]);

      // Start real analysis
      runAnalysis(companyData);
    },
    [runAnalysis, setCompany]
  );

  const handleSendMessage = useCallback(
    async (content: string) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'user',
          content,
          timestamp: new Date(),
        },
      ]);

      // Trigger a new analysis with the follow-up question
      if (companyInfo) {
        try {
          const request: AnalysisRequest = {
            company_name: companyInfo.name,
            description: companyInfo.description || '',
            industry: companyInfo.industry,
            goals: [content],
            challenges: companyInfo.challenges || [],
            competitors: companyInfo.competitors || [],
            target_markets: companyInfo.targetMarkets || [],
          };

          const response = await startAnalysis(request);
          if (response.analysis_id) {
            // Connect to WebSocket for real-time updates
            connectToAnalysis(response.analysis_id, handleWebSocketMessage);
          }
        } catch {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'agent',
              agentId: 'gtm-strategist',
              agentName: 'GTM Strategist',
              content: 'I apologize, but I encountered an issue processing your request. Please try again.',
              timestamp: new Date(),
            },
          ]);
        }
      }
    },
    [companyInfo, handleWebSocketMessage]
  );

  // Show error banner if backend unavailable
  const ErrorBanner = () =>
    error ? (
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-6 py-3 bg-red-500/90 text-white rounded-lg shadow-xl backdrop-blur-sm"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">⚠️</span>
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-4 text-white/70 hover:text-white"
          >
            ✕
          </button>
        </div>
      </motion.div>
    ) : null;

  // Show loading state while checking backend
  if (isBackendAvailable === false) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-white/70">Connecting to GTM Advisor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Aurora Background */}
      <AuroraBackground />

      {/* Error Banner */}
      <ErrorBanner />

      {/* Main Layout */}
      <div className="relative z-10 flex flex-col h-screen">
        {/* Header */}
        <Header companyName={companyInfo?.name} onNewAnalysis={handleNewAnalysis} teaser />

        {/* Main Content */}
        <main className="flex-1 flex overflow-hidden">
          {/* 3-panel analysis layout */}
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Conversation Panel */}
            <ConversationPanel
              messages={messages}
              onSendMessage={handleSendMessage}
              isAnalyzing={isAnalyzing}
              agentActivities={agentActivities}
              onStart={() => setShowOnboarding(true)}
            />

            {/* Center: Agent Network Visualization */}
            <div className="flex-1 relative">
              <AgentNetwork
                activities={agentActivities}
                activeConnections={activeConnections}
                isAnalyzing={isAnalyzing}
                onAgentClick={handleAgentClick}
              />
              {/* Click hint */}
              {!isAnalyzing && !showOnboarding && (
                <motion.div
                  className="absolute bottom-20 left-1/2 -translate-x-1/2 text-center"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 1 }}
                >
                  <p className="text-white/40 text-sm">Click any agent to explore its workspace</p>
                </motion.div>
              )}
            </div>

            {/* Right: Results Panel */}
            <AnimatePresence>
              {results && <ResultsPanel results={results} />}
            </AnimatePresence>
          </div>
        </main>
      </div>

      {/* Onboarding Modal */}
      <AnimatePresence>
        {showOnboarding && (
          <OnboardingModal
            onSubmit={handleCompanySubmit}
            isBackendAvailable={isBackendAvailable}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
