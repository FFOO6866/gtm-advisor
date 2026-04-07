/**
 * CampaignsPage — Campaign Plans backed by the real backend Campaign API.
 *
 * Fetches from GET /api/v1/companies/{id}/campaigns, supports creating
 * plans via a 3-step wizard (POST), and deep-linking from signal-triggered
 * playbooks via URLSearchParams. Execution (activate/pause) is feature-gated.
 *
 * Launch posture: "Campaign Plans" — planning-oriented, no execution.
 * In v1 the Activate/Pause CTAs are hidden behind FEATURES.campaignActivation
 * to avoid implying outreach capabilities that are not exposed yet.
 */

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Megaphone,
  Plus,
  Mail,
  ChevronRight,
  CheckCircle,
  ArrowLeft,
  Zap,
  Radio,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';
import { FEATURES } from '../config/features';

// ============================================================================
// Types
// ============================================================================

interface Campaign {
  id: string;
  company_id: string;
  name: string;
  description?: string;
  objective: string; // 'awareness' | 'lead_gen' | 'conversion' | 'retention'
  status: string;    // 'draft' | 'active' | 'paused' | 'completed'
  target_personas: string[];
  target_industries: string[];
  key_messages: string[];
  value_propositions: string[];
  call_to_action?: string;
  channels: string[];
  email_templates: unknown[];
  linkedin_posts: unknown[];
  budget?: number;
  currency: string;
  start_date?: string;
  end_date?: string;
  created_at: string;
  updated_at?: string;
}

interface CampaignListResponse {
  campaigns: Campaign[];
  total: number;
  by_status: Record<string, number>;
  by_objective: Record<string, number>;
  total_budget: number;
}

type WizardStep = 1 | 2 | 3;
type Objective = 'lead_gen' | 'awareness' | 'conversion' | 'retention';

// ============================================================================
// Constants
// ============================================================================

const OBJECTIVE_CONFIG: Record<
  Objective,
  { label: string; description: string; color: string; bg: string; border: string; icon: React.ReactNode }
> = {
  lead_gen: {
    label: 'Lead Generation',
    description: 'Attract and convert new prospects into qualified leads',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    icon: <Zap className="w-5 h-5" />,
  },
  awareness: {
    label: 'Brand Awareness',
    description: 'Increase visibility and recognition in your target market',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    icon: <Radio className="w-5 h-5" />,
  },
  conversion: {
    label: 'Conversion',
    description: 'Turn engaged prospects into paying customers',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    icon: <TrendingUp className="w-5 h-5" />,
  },
  retention: {
    label: 'Customer Retention',
    description: 'Keep existing customers engaged and reduce churn',
    color: 'text-cyan-400',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    icon: <Users className="w-5 h-5" />,
  },
};

const STATUS_CONFIG: Record<string, { label: string; pill: string }> = {
  draft:     { label: 'Draft',     pill: 'bg-white/5 text-white/40 border-white/10' },
  active:    { label: 'Active',    pill: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  paused:    { label: 'Paused',    pill: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  completed: { label: 'Completed', pill: 'bg-white/10 text-white/50 border-white/20' },
};

const CHANNEL_OPTIONS: { value: string; label: string }[] = [
  { value: 'email',    label: 'Email' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'events',   label: 'Events' },
  { value: 'referral', label: 'Referral' },
];

// ============================================================================
// Sub-components
// ============================================================================

function ObjectiveCard({
  objective,
  selected,
  onSelect,
}: {
  objective: Objective;
  selected: boolean;
  onSelect: () => void;
}) {
  const cfg = OBJECTIVE_CONFIG[objective];
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onSelect}
      className={`w-full text-left glass-card p-4 rounded-xl border-2 transition-all ${
        selected
          ? `${cfg.border} ring-1 ring-current/40`
          : 'border-white/10 hover:border-white/20'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-lg ${cfg.bg} flex items-center justify-center flex-shrink-0 ${cfg.color}`}>
          {cfg.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-white">{cfg.label}</span>
            {selected && <CheckCircle className={`w-3.5 h-3.5 flex-shrink-0 ${cfg.color}`} />}
          </div>
          <p className="text-xs text-white/50 leading-relaxed">{cfg.description}</p>
        </div>
      </div>
    </motion.button>
  );
}

function CampaignCard({
  campaign,
  onActivate,
  onPause,
  activating,
}: {
  campaign: Campaign;
  onActivate: (id: string) => void;
  onPause: (id: string) => void;
  activating: string | null;
}) {
  const navigate = useNavigate();
  const cfg = OBJECTIVE_CONFIG[campaign.objective as Objective] ?? OBJECTIVE_CONFIG.lead_gen;
  const statusCfg = STATUS_CONFIG[campaign.status] ?? STATUS_CONFIG.draft;
  const isBusy = activating === campaign.id;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 rounded-2xl border border-white/10 hover:border-white/20 transition-colors flex flex-col gap-4"
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className={`w-10 h-10 rounded-xl ${cfg.bg} flex items-center justify-center flex-shrink-0 ${cfg.color}`}>
            {cfg.icon}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-white truncate mb-1">{campaign.name}</h3>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${cfg.border} ${cfg.bg} ${cfg.color}`}
            >
              {cfg.label}
            </span>
          </div>
        </div>
        <span
          className={`flex-shrink-0 px-2.5 py-1 rounded-full text-[10px] font-medium border ${statusCfg.pill}`}
        >
          {statusCfg.label}
        </span>
      </div>

      {/* Description */}
      {campaign.description && (
        <p className="text-xs text-white/40 leading-relaxed -mt-2 line-clamp-2">{campaign.description}</p>
      )}

      {/* Content counts */}
      <div className="flex items-center gap-3 text-xs text-white/40">
        <span className="flex items-center gap-1">
          <Mail className="w-3 h-3" />
          {campaign.email_templates.length} email{campaign.email_templates.length !== 1 ? 's' : ''}
        </span>
        <span className="text-white/20">·</span>
        <span>{campaign.linkedin_posts.length} LinkedIn post{campaign.linkedin_posts.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Channels */}
      {campaign.channels.length > 0 && (
        <div className="flex flex-wrap gap-1.5 -mt-1">
          {campaign.channels.map(ch => (
            <span
              key={ch}
              className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-white/40 border border-white/10 capitalize"
            >
              {ch}
            </span>
          ))}
        </div>
      )}

      {/* Budget */}
      {campaign.budget != null && (
        <p className="text-xs text-white/40 -mt-1">
          Budget: <span className="text-white/70 font-medium">{campaign.currency} {campaign.budget.toLocaleString()}</span>
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto pt-1">
        {FEATURES.campaignActivation && campaign.status === 'draft' && (
          <button
            disabled={isBusy}
            onClick={() => onActivate(campaign.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isBusy ? (
              <span className="w-3 h-3 border border-emerald-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <CheckCircle className="w-3 h-3" />
            )}
            Activate
          </button>
        )}
        {FEATURES.campaignActivation && campaign.status === 'active' && (
          <button
            disabled={isBusy}
            onClick={() => onPause(campaign.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 text-xs font-medium border border-yellow-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isBusy ? (
              <span className="w-3 h-3 border border-yellow-400 border-t-transparent rounded-full animate-spin" />
            ) : null}
            Pause
          </button>
        )}
        {FEATURES.contentBeta && (
          <button
            onClick={() => navigate(`/content?campaign=${campaign.id}`)}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white text-xs font-medium border border-white/10 transition-colors"
          >
            View Content
            <ChevronRight className="w-3 h-3" />
          </button>
        )}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Campaign Builder Wizard
// ============================================================================

function CampaignWizard({
  companyId,
  initialStep,
  initialName,
  onClose,
  onSuccess,
}: {
  companyId: string;
  initialStep?: WizardStep;
  initialName?: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [step, setStep] = useState<WizardStep>(initialStep ?? 1);
  const [objective, setObjective] = useState<Objective>('lead_gen');
  const [campaignName, setCampaignName] = useState(initialName ?? '');
  const [description, setDescription] = useState('');
  const [selectedChannels, setSelectedChannels] = useState<string[]>(['email']);
  const [budget, setBudget] = useState('');
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const toggleChannel = (value: string) => {
    setSelectedChannels(prev =>
      prev.includes(value) ? prev.filter(c => c !== value) : [...prev, value],
    );
  };

  const handleLaunch = async () => {
    if (!campaignName.trim()) return;
    setLaunching(true);
    setLaunchError(null);
    try {
      await apiClient.post(`/companies/${companyId}/campaigns`, {
        name: campaignName.trim(),
        objective,
        channels: selectedChannels,
        description: description.trim() || undefined,
        budget: budget ? parseFloat(budget) : undefined,
        currency: 'SGD',
      });
      onSuccess();
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : 'Failed to create campaign');
      setLaunching(false);
    }
  };

  const canAdvanceStep1 = true; // objective always has a default
  const canAdvanceStep2 = campaignName.trim().length > 0;

  const objCfg = OBJECTIVE_CONFIG[objective];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 16 }}
        className="glass-card w-full max-w-lg rounded-2xl border border-white/15 overflow-hidden"
      >
        {/* Wizard header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-white">New Campaign</h2>
            <p className="text-xs text-white/40 mt-0.5">Step {step} of 3</p>
          </div>
          <div className="flex items-center gap-1.5">
            {([1, 2, 3] as WizardStep[]).map(s => (
              <div
                key={s}
                className={`w-2 h-2 rounded-full transition-colors ${
                  s < step ? 'bg-purple-400' : s === step ? 'bg-purple-500' : 'bg-white/15'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Step content */}
        <div className="px-6 py-5 max-h-[60vh] overflow-y-auto">
          <AnimatePresence mode="wait">
            {/* Step 1: Objective */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-3"
              >
                <p className="text-sm text-white/60 mb-4">What is the primary goal of this campaign?</p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {(Object.keys(OBJECTIVE_CONFIG) as Objective[]).map(obj => (
                    <ObjectiveCard
                      key={obj}
                      objective={obj}
                      selected={objective === obj}
                      onSelect={() => setObjective(obj)}
                    />
                  ))}
                </div>
              </motion.div>
            )}

            {/* Step 2: Details */}
            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-5"
              >
                <p className="text-sm text-white/60">Give your campaign a name and configure channels.</p>

                {/* Campaign name */}
                <div>
                  <label className="block text-xs font-medium text-white/50 mb-2">
                    Campaign name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={campaignName}
                    onChange={e => setCampaignName(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder-white/20 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 transition-colors"
                    placeholder="e.g. Q1 Lead Generation Campaign"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-xs font-medium text-white/50 mb-2">Description (optional)</label>
                  <textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder-white/20 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 transition-colors resize-none"
                    placeholder="Brief description of the campaign goals…"
                  />
                </div>

                {/* Channels */}
                <div>
                  <label className="block text-xs font-medium text-white/50 mb-2">Channels</label>
                  <div className="grid grid-cols-2 gap-2">
                    {CHANNEL_OPTIONS.map(ch => (
                      <label
                        key={ch.value}
                        className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl border cursor-pointer transition-colors ${
                          selectedChannels.includes(ch.value)
                            ? 'border-purple-500/40 bg-purple-500/10'
                            : 'border-white/10 hover:border-white/20 bg-white/5'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedChannels.includes(ch.value)}
                          onChange={() => toggleChannel(ch.value)}
                          className="accent-purple-500"
                        />
                        <span className="text-sm text-white/80">{ch.label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Budget */}
                <div>
                  <label className="block text-xs font-medium text-white/50 mb-2">Budget in SGD (optional)</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-white/30">SGD</span>
                    <input
                      type="number"
                      min="0"
                      step="100"
                      value={budget}
                      onChange={e => setBudget(e.target.value)}
                      className="w-full pl-12 pr-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder-white/20 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 transition-colors"
                      placeholder="0"
                    />
                  </div>
                </div>
              </motion.div>
            )}

            {/* Step 3: Review */}
            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <p className="text-sm text-white/60 mb-2">Review your campaign before launching.</p>

                <div className="glass-card rounded-xl border border-white/10 p-4 space-y-3">
                  {/* Objective */}
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${objCfg.bg} ${objCfg.color}`}>
                      {objCfg.icon}
                    </div>
                    <div>
                      <p className="text-xs text-white/40">Objective</p>
                      <p className="text-sm font-semibold text-white">{objCfg.label}</p>
                    </div>
                  </div>

                  <div className="border-t border-white/5 pt-3 space-y-2">
                    <div className="flex items-start justify-between text-xs gap-3">
                      <span className="text-white/40 flex-shrink-0">Campaign name</span>
                      <span className="text-white font-medium text-right">{campaignName}</span>
                    </div>
                    {description && (
                      <div className="flex items-start justify-between text-xs gap-3">
                        <span className="text-white/40 flex-shrink-0">Description</span>
                        <span className="text-white/70 text-right line-clamp-2">{description}</span>
                      </div>
                    )}
                    <div className="flex items-start justify-between text-xs gap-3">
                      <span className="text-white/40 flex-shrink-0">Channels</span>
                      <span className="text-white font-medium text-right capitalize">
                        {selectedChannels.length > 0 ? selectedChannels.join(', ') : 'None'}
                      </span>
                    </div>
                    {budget && (
                      <div className="flex items-start justify-between text-xs gap-3">
                        <span className="text-white/40 flex-shrink-0">Budget</span>
                        <span className="text-white font-medium">SGD {parseFloat(budget).toLocaleString()}</span>
                      </div>
                    )}
                  </div>
                </div>

                {launchError && (
                  <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    {launchError}
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer actions */}
        <div className="px-6 py-4 border-t border-white/10 flex items-center justify-between gap-3">
          <button
            onClick={step === 1 ? onClose : () => setStep(prev => (prev - 1) as WizardStep)}
            className="flex items-center gap-1.5 text-xs text-white/50 hover:text-white/80 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {step === 1 ? 'Cancel' : 'Back'}
          </button>

          {step < 3 ? (
            <button
              disabled={step === 1 ? !canAdvanceStep1 : !canAdvanceStep2}
              onClick={() => setStep(prev => (prev + 1) as WizardStep)}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 text-white text-xs font-semibold hover:from-purple-500 hover:to-violet-500 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              disabled={launching}
              onClick={handleLaunch}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 text-white text-xs font-semibold hover:from-purple-500 hover:to-violet-500 transition-all disabled:opacity-50"
            >
              {launching ? (
                <>
                  <span className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
                  Launching…
                </>
              ) : (
                <>
                  <Zap className="w-3.5 h-3.5" />
                  Launch Campaign
                </>
              )}
            </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ============================================================================
// Empty state
// ============================================================================

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center px-6">
      <div className="w-16 h-16 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-4 border border-purple-500/20">
        <Megaphone className="w-8 h-8 text-purple-400" />
      </div>
      <h3 className="text-base font-semibold text-white mb-2">No campaigns yet</h3>
      <p className="text-sm text-white/40 max-w-xs leading-relaxed mb-6">
        Build your first campaign to start driving awareness, leads, and conversions for your business.
      </p>
      <button
        onClick={onNew}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 text-white text-sm font-semibold hover:from-purple-500 hover:to-violet-500 transition-all"
      >
        <Plus className="w-4 h-4" />
        Create Your First Campaign
      </button>
    </div>
  );
}

// ============================================================================
// Main page
// ============================================================================

export function CampaignsPage() {
  const companyId = useCompanyId() ?? '';
  const [searchParams] = useSearchParams();

  const [listData, setListData] = useState<CampaignListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardInitialStep, setWizardInitialStep] = useState<WizardStep>(1);
  const [wizardInitialName, setWizardInitialName] = useState<string>('');
  const [activating, setActivating] = useState<string | null>(null);

  // URLSearchParams: signal-triggered deep-link
  useEffect(() => {
    const signal = searchParams.get('signal');
    const playbook = searchParams.get('playbook');
    if (signal && playbook === 'signal_triggered') {
      const headline = searchParams.get('headline') || 'Signal-Triggered Campaign';
      setWizardInitialStep(2);
      setWizardInitialName(headline);
      setShowWizard(true);
    }
  }, [searchParams]);

  const fetchCampaigns = useCallback(async () => {
    if (!companyId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.get<CampaignListResponse>(`/companies/${companyId}/campaigns`);
      setListData(data);
    } catch {
      setListData(null);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  const handleActivate = async (campaignId: string) => {
    setActivating(campaignId);
    try {
      await apiClient.post(`/companies/${companyId}/campaigns/${campaignId}/activate`, {});
      await fetchCampaigns();
    } finally {
      setActivating(null);
    }
  };

  const handlePause = async (campaignId: string) => {
    setActivating(campaignId);
    try {
      await apiClient.post(`/companies/${companyId}/campaigns/${campaignId}/pause`, {});
      await fetchCampaigns();
    } finally {
      setActivating(null);
    }
  };

  const openFreshWizard = () => {
    setWizardInitialStep(1);
    setWizardInitialName('');
    setShowWizard(true);
  };

  const handleWizardSuccess = () => {
    setShowWizard(false);
    fetchCampaigns();
  };

  const campaigns = listData?.campaigns ?? [];

  return (
    <>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold text-white flex items-center gap-2">
                <Megaphone className="w-5 h-5 text-purple-400" />
                Campaign Plans
              </h1>
              {/* Summary row — planning posture at v1: no "active" count */}
              {!loading && listData && campaigns.length > 0 && (
                <p className="text-xs text-white/40 mt-0.5">
                  {listData.total} plan{listData.total !== 1 ? 's' : ''}
                  {FEATURES.campaignActivation && (
                    <> · {listData.by_status.active ?? 0} active</>
                  )}
                  {listData.total_budget > 0 && (
                    <> · SGD {listData.total_budget.toLocaleString()} budgeted</>
                  )}
                </p>
              )}
              {!loading && (!listData || campaigns.length === 0) && (
                <p className="text-xs text-white/40 mt-0.5">
                  Plan and document your GTM campaigns.
                </p>
              )}
              {loading && <p className="text-xs text-white/40 mt-0.5">Loading…</p>}
            </div>

            <button
              onClick={openFreshWizard}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 text-white text-xs font-semibold hover:from-purple-500 hover:to-violet-500 transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              New Plan
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : campaigns.length === 0 ? (
            <EmptyState onNew={openFreshWizard} />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {campaigns.map(campaign => (
                <CampaignCard
                  key={campaign.id}
                  campaign={campaign}
                  onActivate={handleActivate}
                  onPause={handlePause}
                  activating={activating}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Campaign Builder Wizard */}
      <AnimatePresence>
        {showWizard && (
          <CampaignWizard
            companyId={companyId}
            initialStep={wizardInitialStep}
            initialName={wizardInitialName}
            onClose={() => setShowWizard(false)}
            onSuccess={handleWizardSuccess}
          />
        )}
      </AnimatePresence>
    </>
  );
}
