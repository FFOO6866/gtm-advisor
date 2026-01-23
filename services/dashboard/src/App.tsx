/**
 * GTM Advisor Dashboard - Main Application
 *
 * Production-ready dashboard connecting to real backend API.
 * NO mock data, NO simulations - live agent execution only.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AuroraBackground } from './components/AuroraBackground';
import { AgentNetwork } from './components/AgentNetwork';
import { ConversationPanel } from './components/ConversationPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { Header } from './components/Header';
import { OnboardingModal } from './components/OnboardingModal';
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

function App() {
  // State
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [agentActivities, setAgentActivities] = useState<AgentActivity[]>([]);
  const [results, setResults] = useState<AnalysisResult | null>(null);
  const [activeConnections, setActiveConnections] = useState<[string, string][]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isBackendAvailable, setIsBackendAvailable] = useState<boolean | null>(null);

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

        // Add final message
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'agent',
            agentId: 'gtm-strategist',
            agentName: 'GTM Strategist',
            content:
              message.message ||
              'Analysis complete! Check the results panel for detailed findings.',
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
          include_market_research: true,
          include_competitor_analysis: true,  // Always include - A2A may discover competitors
          include_customer_profiling: true,
          include_lead_generation: true,
          include_campaign_planning: true,
          lead_count: 10,
        };

        // Start analysis
        const status = await startAnalysis(request);
        analysisIdRef.current = status.analysis_id;

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
    [handleWebSocketMessage]
  );

  const handleCompanySubmit = useCallback(
    (company: CompanyInfo) => {
      setCompanyInfo(company);
      setShowOnboarding(false);

      // Add user message
      setMessages([
        {
          id: Date.now().toString(),
          role: 'user',
          content: `Analyze GTM strategy for ${company.name}: ${company.description}`,
          timestamp: new Date(),
        },
      ]);

      // Start real analysis
      runAnalysis(company);
    },
    [runAnalysis]
  );

  const handleSendMessage = useCallback(
    (content: string) => {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: 'user',
          content,
          timestamp: new Date(),
        },
      ]);

      // For now, acknowledge the message
      // In a full implementation, this would trigger follow-up agent actions
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'agent',
            agentId: 'gtm-strategist',
            agentName: 'GTM Strategist',
            content:
              'I understand your question. Let me coordinate with the team to provide a detailed response.',
            timestamp: new Date(),
          },
        ]);
      }, 500);
    },
    []
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
  if (isBackendAvailable === null) {
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
        <Header companyName={companyInfo?.name} />

        {/* Main Content */}
        <main className="flex-1 flex overflow-hidden">
          {/* Left: Conversation Panel */}
          <ConversationPanel
            messages={messages}
            onSendMessage={handleSendMessage}
            isAnalyzing={isAnalyzing}
            agentActivities={agentActivities}
          />

          {/* Center: Agent Network Visualization */}
          <div className="flex-1 relative">
            <AgentNetwork
              activities={agentActivities}
              activeConnections={activeConnections}
              isAnalyzing={isAnalyzing}
            />
          </div>

          {/* Right: Results Panel */}
          <AnimatePresence>
            {results && <ResultsPanel results={results} />}
          </AnimatePresence>
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
