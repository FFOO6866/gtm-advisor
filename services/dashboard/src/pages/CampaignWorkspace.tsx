/**
 * Campaign Architect Agent Workspace
 *
 * Campaign planning, content generation, and messaging.
 * Connected to real backend API.
 */

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  FileText,
  Mail,
  Linkedin,
  Copy,
  Check,
  Calendar,
  Target,
  DollarSign,
  Play,
  Pause,
} from 'lucide-react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import {
  Card,
  Badge,
  Button,
  EmptyState,
  CampaignListLoading,
  ErrorState,
  useToast,
} from '../components/common';
import { AGENTS } from '../types';
import { useCompanyId } from '../context/CompanyContext';
import { useCampaigns, useMutation } from '../hooks/useApi';
import * as api from '../api/workspaces';
import type { Campaign, CampaignUpdate } from '../api/workspaces';

const CONTENT_TYPES = [
  { id: 'linkedin', label: 'LinkedIn Post', icon: <Linkedin className="w-4 h-4" /> },
  { id: 'email', label: 'Email', icon: <Mail className="w-4 h-4" /> },
  { id: 'blog', label: 'Blog Post', icon: <FileText className="w-4 h-4" /> },
  { id: 'ad', label: 'Ad Copy', icon: <Target className="w-4 h-4" /> },
];

// Default content generation limits per tier
// TODO: These should come from user settings API (tier_limits field)
const DEFAULT_CONTENT_LIMITS = {
  free: 10,
  starter: 50,
  pro: 200,
  enterprise: Infinity,
} as const;

export function CampaignWorkspace() {
  const companyId = useCompanyId();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('active');
  const [isRunning, setIsRunning] = useState(false);
  const [selectedContentType, setSelectedContentType] = useState<'linkedin' | 'email' | 'blog' | 'ad'>('linkedin');
  const [generatedContent, setGeneratedContent] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // Content generation form state (controlled components)
  const [contentTopic, setContentTopic] = useState('');
  const [contentTone, setContentTone] = useState<'professional' | 'conversational' | 'bold'>('professional');
  const [targetPersona, setTargetPersona] = useState('cto');
  const [includeCta, setIncludeCta] = useState(true);
  const [keyPoints, setKeyPoints] = useState('');

  // Fetch campaigns from API
  const { data: campaignData, isLoading, error, refresh } = useCampaigns(companyId);

  const agent = AGENTS.find((a) => a.id === 'campaign-architect')!;

  // Derived data
  const campaigns = campaignData?.campaigns || [];
  const activeCampaigns = campaigns.filter((c) => c.status === 'active');
  const contentUsed = campaignData?.content_pieces_this_month || 0;
  // Content limit - using starter tier default until user settings API provides tier info
  // TODO: Fetch from useUserSettings once userId is available in context
  const contentLimit = DEFAULT_CONTENT_LIMITS.starter;

  // Mutations - only execute when companyId is available
  const updateMutation = useMutation(
    ({ campaignId, data }: { campaignId: string; data: CampaignUpdate }) => {
      if (!companyId) return Promise.reject(new Error('No company selected'));
      return api.updateCampaign(companyId, campaignId, data);
    },
    {
      invalidateKeys: ['campaigns'],
      onSuccess: () => refresh(),
      onError: (err) => {
        toast.error('Failed to update campaign', err.message);
      },
    }
  );

  // Mutation to trigger agent run
  const triggerAgentMutation = useMutation(
    () => {
      if (!companyId) return Promise.reject(new Error('No company selected'));
      return api.triggerAgent(companyId, 'campaign-architect');
    },
    {
      invalidateKeys: ['campaigns'],
      onSuccess: () => {
        refresh();
        setIsRunning(false);
        toast.success('Campaign analysis completed');
      },
      onError: (err) => {
        setIsRunning(false);
        toast.error('Failed to run campaign agent', err.message);
      },
    }
  );

  // Mutation to generate content
  const generateContentMutation = useMutation(
    (request: api.ContentGenerationRequest) => {
      if (!companyId) return Promise.reject(new Error('No company selected'));
      return api.generateContent(companyId, request);
    },
    {
      invalidateKeys: ['campaigns'],
      onError: (err) => {
        toast.error('Failed to generate content', err.message);
      },
    }
  );

  const handleRun = useCallback(async () => {
    if (!companyId) {
      toast.error('Please complete onboarding first', 'No company selected');
      return;
    }
    setIsRunning(true);
    await triggerAgentMutation.mutate(undefined);
  }, [companyId, triggerAgentMutation, toast]);

  const handleGenerateContent = useCallback(async () => {
    if (!companyId) {
      toast.error('Please complete onboarding first', 'No company selected');
      return;
    }
    if (!contentTopic.trim()) {
      toast.warning('Please enter a topic for the content');
      return;
    }
    setIsGenerating(true);
    try {
      const result = await generateContentMutation.mutate({
        content_type: selectedContentType,
        topic: contentTopic,
        tone: contentTone,
        target_persona: targetPersona,
        include_cta: includeCta,
        key_points: keyPoints.trim() ? keyPoints.split('\n').filter(Boolean) : undefined,
        variations: 3,
      });
      if (result) {
        setGeneratedContent(result.map((item) => item.content));
        toast.success('Content generated successfully');
      }
    } finally {
      setIsGenerating(false);
    }
  }, [companyId, contentTopic, contentTone, targetPersona, includeCta, keyPoints, selectedContentType, generateContentMutation, toast]);

  const handleCopy = (index: number, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const tabs = [
    { id: 'active', label: 'Active Campaigns', badge: activeCampaigns.length, icon: '📢' },
    { id: 'builder', label: 'Campaign Builder', icon: '🛠️' },
    { id: 'content', label: 'Content Generator', badge: contentLimit - contentUsed, icon: '✏️' },
    { id: 'templates', label: 'Templates', icon: '📋' },
  ];

  // Loading state
  if (isLoading) {
    return (
      <AgentWorkspace
        agent={agent}
        status="active"
        lastRun={new Date()}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRun={handleRun}
        isRunning={isRunning}
      >
        <CampaignListLoading />
      </AgentWorkspace>
    );
  }

  // Error state
  if (error) {
    return (
      <AgentWorkspace
        agent={agent}
        status="error"
        lastRun={new Date()}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRun={handleRun}
        isRunning={isRunning}
      >
        <ErrorState
          title="Failed to load campaigns"
          message={error.message}
          onRetry={refresh}
        />
      </AgentWorkspace>
    );
  }

  // No company selected
  if (!companyId) {
    return (
      <AgentWorkspace
        agent={agent}
        status="idle"
        lastRun={new Date()}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRun={handleRun}
        isRunning={isRunning}
      >
        <EmptyState
          icon="🏢"
          title="No Company Selected"
          description="Please complete onboarding to start creating campaigns."
        />
      </AgentWorkspace>
    );
  }

  return (
    <AgentWorkspace
      agent={agent}
      status={activeCampaigns.length > 0 ? 'active' : 'idle'}
      lastRun={new Date(Date.now() - 24 * 60 * 60 * 1000)}
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onRun={handleRun}
      isRunning={isRunning}
    >
      {/* Active Campaigns Tab */}
      {activeTab === 'active' && (
        <div className="space-y-6">
          {campaigns.length === 0 ? (
            <EmptyState
              icon="📢"
              title="No Campaigns Yet"
              description="Create your first campaign to start reaching your target audience."
              action={{ label: 'Create Campaign', onClick: () => setActiveTab('builder') }}
            />
          ) : (
            <>
              {campaigns.map((campaign) => (
                <CampaignCard
                  key={campaign.id}
                  campaign={campaign}
                  onStatusChange={(status) =>
                    updateMutation.execute({
                      campaignId: campaign.id,
                      data: { status },
                    })
                  }
                />
              ))}

              <Card className="border-dashed border-2 border-white/20">
                <div className="flex items-center justify-center py-8">
                  <Button
                    variant="ghost"
                    leftIcon={<Sparkles className="w-4 h-4" />}
                    onClick={() => setActiveTab('builder')}
                  >
                    + Create New Campaign
                  </Button>
                </div>
              </Card>
            </>
          )}
        </div>
      )}

      {/* Campaign Builder Tab */}
      {activeTab === 'builder' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Campaign Configuration</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-white/70 mb-1">Campaign Objective</label>
                <input
                  type="text"
                  placeholder="e.g., Generate leads for enterprise segment"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-white/30 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm text-white/70 mb-1">Target Audience</label>
                <select className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500">
                  <option value="">Select audience...</option>
                  <option value="enterprise-cto">Enterprise CTOs</option>
                  <option value="sme-founder">SME Founders</option>
                  <option value="marketing-director">Marketing Directors</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-white/70 mb-1">Budget (SGD/month)</label>
                  <input
                    type="number"
                    defaultValue={5000}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-white/70 mb-1">Duration</label>
                  <select className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500">
                    <option value="1">1 month</option>
                    <option value="3">3 months</option>
                    <option value="6">6 months</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm text-white/70 mb-2">Channels (AI recommended)</label>
                <div className="space-y-2">
                  {['LinkedIn Ads', 'Content Marketing', 'Email Nurture', 'Webinars'].map((channel) => (
                    <label key={channel} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        defaultChecked={channel !== 'Webinars'}
                        className="w-4 h-4 rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500"
                      />
                      <span className="text-white/80">{channel}</span>
                      {channel === 'LinkedIn Ads' && (
                        <Badge variant="purple">Recommended</Badge>
                      )}
                    </label>
                  ))}
                </div>
              </div>
              <Button variant="primary" className="w-full">
                Generate Campaign Plan →
              </Button>
            </div>
          </Card>

          <Card>
            <EmptyState
              icon="📋"
              title="No plan generated yet"
              description="Configure your campaign on the left and click Generate to create a detailed plan."
            />
          </Card>
        </div>
      )}

      {/* Content Generator Tab */}
      {activeTab === 'content' && (
        <div className="space-y-6">
          {/* Usage Meter */}
          <Card className="bg-purple-500/10 border-purple-500/30">
            <div className="flex items-center justify-between">
              <span className="text-white/70">
                Content this month: {contentUsed}/{contentLimit} pieces
              </span>
              <Button variant="ghost" size="sm">
                Upgrade for unlimited
              </Button>
            </div>
            <div className="mt-2 h-2 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                initial={{ width: 0 }}
                animate={{ width: `${(contentUsed / contentLimit) * 100}%` }}
              />
            </div>
          </Card>

          {/* Content Type Selector */}
          <div className="flex gap-2">
            {CONTENT_TYPES.map((type) => (
              <Button
                key={type.id}
                variant={selectedContentType === type.id ? 'secondary' : 'ghost'}
                onClick={() => setSelectedContentType(type.id as typeof selectedContentType)}
                leftIcon={type.icon}
              >
                {type.label}
              </Button>
            ))}
          </div>

          {/* Generator Form */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">
              Generate {CONTENT_TYPES.find((t) => t.id === selectedContentType)?.label}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-white/70 mb-1">Topic/Theme</label>
                <input
                  type="text"
                  placeholder="What should this content be about?"
                  value={contentTopic}
                  onChange={(e) => setContentTopic(e.target.value)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-white/30 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-white/70 mb-1">Tone</label>
                  <select
                    value={contentTone}
                    onChange={(e) => setContentTone(e.target.value as typeof contentTone)}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="professional">Professional</option>
                    <option value="conversational">Conversational</option>
                    <option value="bold">Bold</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-white/70 mb-1">Target Persona</label>
                  <select
                    value={targetPersona}
                    onChange={(e) => setTargetPersona(e.target.value)}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="cto">Enterprise CTO</option>
                    <option value="cmo">CMO</option>
                    <option value="founder">Founder</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-white/70 mb-1">Include CTA?</label>
                  <select
                    value={includeCta ? 'yes' : 'no'}
                    onChange={(e) => setIncludeCta(e.target.value === 'yes')}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm text-white/70 mb-1">Key points to include (optional)</label>
                <textarea
                  placeholder="• Point 1&#10;• Point 2"
                  value={keyPoints}
                  onChange={(e) => setKeyPoints(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-white/30 focus:outline-none focus:border-purple-500 resize-none"
                />
              </div>
              <Button
                variant="primary"
                onClick={handleGenerateContent}
                isLoading={isGenerating}
                disabled={!contentTopic.trim()}
                leftIcon={<Sparkles className="w-4 h-4" />}
              >
                Generate 3 Variations
              </Button>
            </div>
          </Card>

          {/* Generated Content */}
          <AnimatePresence>
            {generatedContent.length > 0 && (
              <motion.div
                className="space-y-4"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <h3 className="text-lg font-semibold text-white">Generated Variations</h3>
                {generatedContent.map((content, index) => (
                  <Card key={index}>
                    <div className="flex items-center justify-between mb-3">
                      <Badge variant="purple">Variation {String.fromCharCode(65 + index)}</Badge>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCopy(index, content)}
                          leftIcon={copiedIndex === index ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        >
                          {copiedIndex === index ? 'Copied!' : 'Copy'}
                        </Button>
                        <Button variant="ghost" size="sm" leftIcon={<Calendar className="w-3 h-3" />}>
                          Schedule
                        </Button>
                      </div>
                    </div>
                    <pre className="text-white/80 text-sm whitespace-pre-wrap font-sans">{content}</pre>
                  </Card>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-3 gap-4">
          {['Welcome Email', 'Follow-up Sequence', 'Event Invitation', 'Case Study Promo', 'Newsletter', 'Product Launch'].map((template) => (
            <Card key={template} className="hover:border-purple-500/50 cursor-pointer transition-colors">
              <div className="text-center py-4">
                <span className="text-3xl mb-3 block">📄</span>
                <h4 className="font-medium text-white">{template}</h4>
                <p className="text-sm text-white/50 mt-1">Click to use</p>
              </div>
            </Card>
          ))}
        </div>
      )}
    </AgentWorkspace>
  );
}

// Campaign Card Component
interface CampaignCardProps {
  campaign: Campaign;
  onStatusChange: (status: string) => void;
}

function CampaignCard({ campaign, onStatusChange }: CampaignCardProps) {
  const [expandedPhase, setExpandedPhase] = useState<number | null>(0);

  const phases = campaign.phases || [];
  const totalBudget = campaign.budget || 0;
  const duration = campaign.duration || '3 months';
  const expectedROI = campaign.expected_roi || 0;

  const statusBadge = {
    draft: 'default',
    active: 'success',
    paused: 'warning',
    completed: 'default',
    cancelled: 'danger',
  } as const;

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-xl font-semibold text-white">{campaign.name}</h3>
          <p className="text-white/60 mt-1">{campaign.objective}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusBadge[campaign.status] || 'default'}>
            {campaign.status.charAt(0).toUpperCase() + campaign.status.slice(1)}
          </Badge>
          {campaign.status === 'active' ? (
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<Pause className="w-3 h-3" />}
              onClick={() => onStatusChange('paused')}
            >
              Pause
            </Button>
          ) : campaign.status === 'paused' || campaign.status === 'draft' ? (
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<Play className="w-3 h-3" />}
              onClick={() => onStatusChange('active')}
            >
              {campaign.status === 'draft' ? 'Launch' : 'Resume'}
            </Button>
          ) : null}
        </div>
      </div>

      {/* Campaign Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <DollarSign className="w-5 h-5 text-green-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">SGD {totalBudget.toLocaleString()}</div>
          <div className="text-xs text-white/50">Total Budget</div>
        </div>
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <Calendar className="w-5 h-5 text-blue-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">{duration}</div>
          <div className="text-xs text-white/50">Duration</div>
        </div>
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <Target className="w-5 h-5 text-purple-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">{phases.length}</div>
          <div className="text-xs text-white/50">Phases</div>
        </div>
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <Sparkles className="w-5 h-5 text-amber-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">{expectedROI}x</div>
          <div className="text-xs text-white/50">Expected ROI</div>
        </div>
      </div>

      {/* Phases */}
      {phases.length > 0 && (
        <div className="space-y-3">
          {phases.map((phase, index) => (
            <div
              key={phase.name}
              className="border border-white/10 rounded-lg overflow-hidden"
            >
              <button
                className="w-full px-4 py-3 flex items-center justify-between bg-white/5 hover:bg-white/10 transition-colors"
                onClick={() => setExpandedPhase(expandedPhase === index ? null : index)}
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-xs flex items-center justify-center">
                    {index + 1}
                  </span>
                  <span className="font-medium text-white">{phase.name}</span>
                  <span className="text-white/50 text-sm">({phase.duration})</span>
                </div>
                <span className="text-white/50">{expandedPhase === index ? '▼' : '▶'}</span>
              </button>

              <AnimatePresence>
                {expandedPhase === index && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="px-4 py-3 bg-white/[0.02]"
                  >
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <h5 className="text-xs font-medium text-white/50 uppercase mb-2">Channels</h5>
                        <ul className="space-y-1">
                          {(phase.channels || []).map((channel) => (
                            <li key={channel} className="text-sm text-white/80">• {channel}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h5 className="text-xs font-medium text-white/50 uppercase mb-2">Content</h5>
                        <ul className="space-y-1">
                          {(phase.content || []).map((item) => (
                            <li key={item} className="text-sm text-white/80">• {item}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h5 className="text-xs font-medium text-white/50 uppercase mb-2">KPIs</h5>
                        <ul className="space-y-1">
                          {(phase.kpis || []).map((kpi) => (
                            <li key={kpi} className="text-sm text-white/80">• {kpi}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                    <div className="flex justify-end mt-4">
                      <Button variant="ghost" size="sm">
                        Generate Content for Phase →
                      </Button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-white/10">
        <Button variant="ghost">Edit Campaign</Button>
        <Button
          variant="secondary"
          onClick={() => window.open(api.getExportUrl(campaign.company_id, 'campaigns'), '_blank')}
        >
          Export to PDF
        </Button>
      </div>
    </Card>
  );
}
