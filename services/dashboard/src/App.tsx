import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AuroraBackground } from './components/AuroraBackground';
import { AgentNetwork } from './components/AgentNetwork';
import { ConversationPanel } from './components/ConversationPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { Header } from './components/Header';
import { OnboardingModal } from './components/OnboardingModal';
import { AgentActivity, Message, AnalysisResult, CompanyInfo } from './types';

function App() {
  // State
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [agentActivities, setAgentActivities] = useState<AgentActivity[]>([]);
  const [results, setResults] = useState<AnalysisResult | null>(null);
  const [activeConnections, setActiveConnections] = useState<[string, string][]>([]);

  // Simulate agent activity for demo
  const simulateAgentActivity = useCallback(async (company: CompanyInfo) => {
    setIsAnalyzing(true);

    const agents = [
      { id: 'gtm-strategist', name: 'GTM Strategist', delay: 0 },
      { id: 'market-intelligence', name: 'Market Intelligence', delay: 2000 },
      { id: 'competitor-analyst', name: 'Competitor Analyst', delay: 4000 },
      { id: 'customer-profiler', name: 'Customer Profiler', delay: 6000 },
      { id: 'lead-hunter', name: 'Lead Hunter', delay: 8000 },
      { id: 'campaign-architect', name: 'Campaign Architect', delay: 10000 },
    ];

    // Add initial strategist message
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'agent',
      agentId: 'gtm-strategist',
      content: `Great! I'm analyzing ${company.name}'s GTM requirements. Let me coordinate with my team of specialized agents...`,
      timestamp: new Date(),
    }]);

    // Simulate each agent becoming active
    for (let i = 0; i < agents.length; i++) {
      const agent = agents[i];

      await new Promise(resolve => setTimeout(resolve, agent.delay === 0 ? 500 : 2000));

      // Set agent as thinking
      setAgentActivities(prev => [
        ...prev.filter(a => a.agentId !== agent.id),
        { agentId: agent.id, status: 'thinking', progress: 0 }
      ]);

      // Show connection from strategist to this agent
      if (i > 0) {
        setActiveConnections(prev => [...prev, ['gtm-strategist', agent.id]]);
      }

      // Simulate progress
      for (let p = 0; p <= 100; p += 20) {
        await new Promise(resolve => setTimeout(resolve, 300));
        setAgentActivities(prev =>
          prev.map(a => a.agentId === agent.id ? { ...a, progress: p } : a)
        );
      }

      // Set agent as complete
      setAgentActivities(prev =>
        prev.map(a => a.agentId === agent.id ? { ...a, status: 'complete', progress: 100 } : a)
      );

      // Add agent response message
      const agentMessages: Record<string, string> = {
        'market-intelligence': `📊 Singapore fintech market is growing at 15% CAGR. Key opportunity: PSG-eligible solutions are seeing 40% higher adoption.`,
        'competitor-analyst': `🔍 Identified 3 key competitors. Your differentiator: ${company.valueProposition || 'Unique positioning'} addresses an underserved segment.`,
        'customer-profiler': `👥 Primary persona: Tech-forward SME founders (Series A-B) actively seeking efficiency tools. Decision cycle: 2-4 weeks.`,
        'lead-hunter': `🎯 Found 12 high-fit prospects matching your ICP. Top lead: TechCorp SG - 85% fit score, recently announced expansion plans.`,
        'campaign-architect': `📣 Created 3 ready-to-use email templates and 2 LinkedIn posts optimized for your target persona.`,
      };

      if (agentMessages[agent.id]) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'agent',
          agentId: agent.id,
          content: agentMessages[agent.id],
          timestamp: new Date(),
        }]);
      }
    }

    // Clear connections and show final result
    await new Promise(resolve => setTimeout(resolve, 1000));
    setActiveConnections([]);

    // Mock results with decision attribution
    setResults({
      leads: [
        { name: 'TechCorp SG', fitScore: 0.85, industry: 'Fintech', size: '50-100', scoringMethod: 'algorithm', expectedValue: 42500 },
        { name: 'DataFlow Asia', fitScore: 0.82, industry: 'SaaS', size: '20-50', scoringMethod: 'algorithm', expectedValue: 28000 },
        { name: 'CloudFirst Pte', fitScore: 0.78, industry: 'Enterprise', size: '100-200', scoringMethod: 'algorithm', expectedValue: 65000 },
      ],
      insights: [
        'Singapore fintech market growing 15% CAGR',
        'PSG grant eligibility increases conversion 40%',
        'Primary competitors weak in SME segment',
      ],
      campaigns: [
        { type: 'Email', title: 'Cold Outreach Sequence', ready: true },
        { type: 'LinkedIn', title: 'Thought Leadership Posts', ready: true },
      ],
      totalPipelineValue: 135500,
      decisionAttribution: {
        algorithmDecisions: 18,
        llmDecisions: 4,
        toolCalls: 12,
        determinismRatio: 0.82,
        breakdown: [
          { layer: 'analytical', component: 'ICP Scorer', decision: 'Fit score: 0.85', confidence: 0.92, executionTimeMs: 2.3 },
          { layer: 'analytical', component: 'ICP Scorer', decision: 'Fit score: 0.82', confidence: 0.90, executionTimeMs: 1.8 },
          { layer: 'analytical', component: 'ICP Scorer', decision: 'Fit score: 0.78', confidence: 0.88, executionTimeMs: 2.1 },
          { layer: 'analytical', component: 'Lead Scorer (BANT)', decision: 'Intent score: 0.75', confidence: 0.85, executionTimeMs: 3.2 },
          { layer: 'analytical', component: 'Lead Value Calculator', decision: 'Expected: SGD 42,500', confidence: 0.95, executionTimeMs: 0.8 },
          { layer: 'operational', component: 'Company Enrichment', decision: 'Enriched 3 companies', confidence: 1.0, executionTimeMs: 245 },
          { layer: 'operational', component: 'News Scraper', decision: 'Found 8 articles', confidence: 1.0, executionTimeMs: 512 },
          { layer: 'cognitive', component: 'LLM Synthesis', decision: 'Generated outreach', confidence: 0.78, executionTimeMs: 1850 },
          { layer: 'cognitive', component: 'LLM Explanation', decision: 'Explained fit reasons', confidence: 0.80, executionTimeMs: 920 },
          { layer: 'governance', component: 'PDPA Checker', decision: 'Data compliant', confidence: 1.0, executionTimeMs: 1.2 },
          { layer: 'governance', component: 'Budget Manager', decision: 'Within limits', confidence: 1.0, executionTimeMs: 0.5 },
        ],
      },
    });

    // Final message
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'agent',
      agentId: 'gtm-strategist',
      content: `✅ Analysis complete! I've found 12 qualified leads, 3 market insights, and prepared 2 campaign templates. Check the results panel for details.`,
      timestamp: new Date(),
    }]);

    setIsAnalyzing(false);
  }, []);

  const handleCompanySubmit = useCallback((company: CompanyInfo) => {
    setCompanyInfo(company);
    setShowOnboarding(false);

    // Add user message
    setMessages([{
      id: Date.now().toString(),
      role: 'user',
      content: `Analyze GTM strategy for ${company.name}: ${company.description}`,
      timestamp: new Date(),
    }]);

    // Start simulation
    simulateAgentActivity(company);
  }, [simulateAgentActivity]);

  const handleSendMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    }]);

    // Simulate response
    setTimeout(() => {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'agent',
        agentId: 'gtm-strategist',
        content: `I understand you'd like to know more. Let me check with my team and get back to you with specific insights.`,
        timestamp: new Date(),
      }]);
    }, 1000);
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Aurora Background */}
      <AuroraBackground />

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
            {results && (
              <ResultsPanel results={results} />
            )}
          </AnimatePresence>
        </main>
      </div>

      {/* Onboarding Modal */}
      <AnimatePresence>
        {showOnboarding && (
          <OnboardingModal onSubmit={handleCompanySubmit} />
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
