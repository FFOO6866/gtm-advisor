/**
 * ContentPage — Content Studio for GTM campaigns.
 *
 * Paid-tier feature that closes the "Communications gap" identified in
 * product analysis. Generates LinkedIn posts and surfaces email
 * sequence templates using AI and real market signals for context.
 *
 * Tabs:
 *   1. LinkedIn Posts — theme/tone selector + AI generation via campaign-architect
 *   2. Email Templates — sequence templates with link to /sequences
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Linkedin,
  FileText,
  Sparkles,
  Copy,
  Check,
  RefreshCw,
  ChevronRight,
} from 'lucide-react';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';
import { useNavigate } from 'react-router-dom';

// ============================================================================
// Types
// ============================================================================

interface SignalEvent {
  id: string;
  headline: string;
  signal_type: string;
  urgency: string;
}

interface CompanyInfo {
  name: string;
  description: string;
  industry: string;
}

interface GeneratedContentItem {
  id: string;
  content_type: string;
  content: string;
  tone: string;
  target_persona: string;
  created_at: string;
}

interface CampaignWithContent {
  id: string;
  name: string;
  objective: string;
  email_templates: unknown[];
  linkedin_posts: unknown[];
}

type ContentTheme = 'thought_leadership' | 'product_value' | 'signal_triggered';
type ContentTone = 'professional' | 'conversational' | 'bold';
type ActiveTab = 'linkedin' | 'email';

// ============================================================================
// Constants
// ============================================================================

const LINKEDIN_CHAR_LIMIT = 3000;

// ============================================================================
// Sub-components
// ============================================================================

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-white/10 text-white'
          : 'text-white/50 hover:text-white/80 hover:bg-white/5'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function ThemeRadioCard({
  value,
  currentValue,
  onChange,
  title,
  description,
  disabled,
  disabledTooltip,
}: {
  value: ContentTheme;
  currentValue: ContentTheme;
  onChange: (v: ContentTheme) => void;
  title: string;
  description: string;
  disabled?: boolean;
  disabledTooltip?: string;
}) {
  const selected = currentValue === value;

  return (
    <div title={disabled ? disabledTooltip : undefined}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && onChange(value)}
        className={`w-full text-left p-3 rounded-xl border transition-all ${
          disabled
            ? 'opacity-40 cursor-not-allowed border-white/5'
            : selected
            ? 'border-purple-500/50 bg-purple-500/10'
            : 'border-white/10 hover:border-white/20 hover:bg-white/5'
        }`}
      >
        <div className="flex items-start gap-2.5">
          <span
            className={`mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
              selected && !disabled
                ? 'border-purple-400 bg-purple-400'
                : 'border-white/30'
            }`}
          >
            {selected && !disabled && (
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
            )}
          </span>
          <div>
            <p className={`text-sm font-medium ${disabled ? 'text-white/40' : 'text-white'}`}>
              {title}
            </p>
            <p className="text-xs text-white/50 mt-0.5 leading-relaxed">{description}</p>
          </div>
        </div>
      </button>
    </div>
  );
}

function ToneButton({
  value,
  currentValue,
  onChange,
  label,
}: {
  value: ContentTone;
  currentValue: ContentTone;
  onChange: (v: ContentTone) => void;
  label: string;
}) {
  const active = currentValue === value;
  return (
    <button
      onClick={() => onChange(value)}
      className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors border ${
        active
          ? 'bg-white/10 text-white border-white/20'
          : 'text-white/40 hover:text-white/70 border-white/5 hover:border-white/15'
      }`}
    >
      {label}
    </button>
  );
}

// ============================================================================
// LinkedIn Tab
// ============================================================================

function LinkedInTab({
  companyId,
  companyInfo,
  signals,
}: {
  companyId: string;
  companyInfo: CompanyInfo | null;
  signals: SignalEvent[];
}) {
  const [theme, setTheme] = useState<ContentTheme>('thought_leadership');
  const [tone, setTone] = useState<ContentTone>('professional');
  const [selectedSignalId, setSelectedSignalId] = useState<string>('');
  const [generatedPost, setGeneratedPost] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const hasSignals = signals.length > 0;
  const selectedSignal = signals.find(s => s.id === selectedSignalId) ?? null;

  const handleGenerate = async () => {
    if (!companyId) return;
    setGenerating(true);
    setGenError(null);

    // Derive topic from theme
    let topic: string;
    if (theme === 'signal_triggered' && selectedSignal) {
      topic = selectedSignal.headline;
    } else if (theme === 'thought_leadership') {
      topic = `${companyInfo?.name ?? ''} ${companyInfo?.industry ?? ''} market insights`.trim();
    } else {
      topic = `${companyInfo?.name ?? ''} solutions and value proposition`.trim();
    }

    try {
      const response = await apiClient.post<GeneratedContentItem[]>(
        `/companies/${companyId}/campaigns/generate-content`,
        {
          content_type: 'linkedin',
          topic,
          tone,
          target_persona: 'Business Decision Makers',
          include_cta: true,
          variations: 1,
        }
      );

      const text = response[0]?.content ?? null;
      if (typeof text === 'string' && text.trim()) {
        setGeneratedPost(text.trim());
      } else {
        setGenError('The AI returned no content. Try a different topic or tone.');
      }
    } catch {
      setGenError('Failed to connect to the content generation service. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!generatedPost) return;
    await navigator.clipboard.writeText(generatedPost);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const charCount = generatedPost.length;
  const charOverLimit = charCount > LINKEDIN_CHAR_LIMIT;

  return (
    <div className="flex gap-5 h-full">
      {/* Left: controls (2/3) */}
      <div className="flex-[2] flex flex-col gap-5 min-w-0">
        {/* Theme */}
        <div className="glass-card rounded-xl border border-white/10 p-4">
          <p className="text-xs font-semibold text-white/50 uppercase tracking-wide mb-3">
            Content Theme
          </p>
          <div className="space-y-2">
            <ThemeRadioCard
              value="thought_leadership"
              currentValue={theme}
              onChange={setTheme}
              title="Thought Leadership"
              description="Share industry insights and expertise"
            />
            <ThemeRadioCard
              value="product_value"
              currentValue={theme}
              onChange={setTheme}
              title="Product Value"
              description="Highlight your key differentiators"
            />
            <ThemeRadioCard
              value="signal_triggered"
              currentValue={theme}
              onChange={setTheme}
              title="Signal-Triggered"
              description="React to a market event or trend"
              disabled={!hasSignals}
              disabledTooltip="No signals yet — the Signal Monitor Agent will populate signals hourly"
            />
          </div>

          {/* Signal selector — only shown when Signal-Triggered is active */}
          <AnimatePresence>
            {theme === 'signal_triggered' && hasSignals && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 overflow-hidden"
              >
                <label className="block text-xs text-white/40 mb-1.5">
                  Signal to react to
                </label>
                <select
                  value={selectedSignalId}
                  onChange={e => setSelectedSignalId(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50 appearance-none"
                >
                  <option value="">Select a signal…</option>
                  {signals.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.headline}
                    </option>
                  ))}
                </select>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Tone */}
        <div className="glass-card rounded-xl border border-white/10 p-4">
          <p className="text-xs font-semibold text-white/50 uppercase tracking-wide mb-3">
            Tone
          </p>
          <div className="flex gap-2">
            <ToneButton value="professional" currentValue={tone} onChange={setTone} label="Professional" />
            <ToneButton value="conversational" currentValue={tone} onChange={setTone} label="Conversational" />
            <ToneButton value="bold" currentValue={tone} onChange={setTone} label="Bold" />
          </div>
        </div>

        {/* Generate button */}
        <motion.button
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          onClick={handleGenerate}
          disabled={generating || !companyId}
          className="w-full flex items-center justify-center gap-2 py-3 px-6 rounded-xl text-sm font-semibold text-white transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)',
          }}
        >
          {generating ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Generating…
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Generate Post
            </>
          )}
        </motion.button>

        {/* Inline error */}
        <AnimatePresence>
          {genError && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="text-xs text-orange-400/80 leading-relaxed"
            >
              {genError}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Right: preview (1/3) */}
      <div className="flex-1 flex flex-col gap-3 min-w-0">
        <p className="text-xs font-semibold text-white/50 uppercase tracking-wide">
          Generated Post
        </p>

        {generatedPost ? (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card rounded-xl border border-white/10 p-4 flex flex-col gap-3 flex-1"
          >
            <pre className="text-sm text-white leading-relaxed whitespace-pre-wrap font-sans flex-1">
              {generatedPost}
            </pre>

            {/* Character count */}
            <div className="flex items-center justify-between pt-2 border-t border-white/10">
              <span
                className={`text-xs ${
                  charOverLimit ? 'text-red-400' : 'text-white/30'
                }`}
              >
                {charCount.toLocaleString()} / {LINKEDIN_CHAR_LIMIT.toLocaleString()} chars
                {charOverLimit && ' — over limit'}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  title="Regenerate"
                  className="p-1.5 rounded-lg text-white/30 hover:text-white/70 hover:bg-white/5 transition-colors disabled:opacity-40"
                >
                  <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
                </button>
                <button
                  onClick={handleCopy}
                  title="Copy to clipboard"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white text-xs transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-green-400" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      Copy
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        ) : (
          <div className="glass-card rounded-xl border border-white/10 p-6 flex-1 flex flex-col items-center justify-center text-center">
            <Linkedin className="w-10 h-10 text-white/10 mb-3" />
            <p className="text-white/40 text-sm">Your LinkedIn post will appear here</p>
            <p className="text-white/25 text-xs mt-1">
              Select a theme and tone, then click Generate Post
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Email Templates Tab
// ============================================================================

function EmailTemplatesTab({ companyId }: { companyId: string }) {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<CampaignWithContent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) {
      setLoading(false);
      return;
    }
    apiClient
      .get<{ campaigns: CampaignWithContent[] }>(`/companies/${companyId}/campaigns`)
      .then(data => {
        const all = Array.isArray(data?.campaigns) ? data.campaigns : [];
        setCampaigns(all.filter(c => c.email_templates && c.email_templates.length > 0));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [companyId]);

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Top action row */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-white/40">
          Campaigns with email templates
        </p>
        <button
          onClick={() => navigate('/campaigns')}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs font-medium hover:bg-purple-500/30 border border-purple-500/20 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5" />
          View All Campaigns
        </button>
      </div>

      {/* Campaign list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : campaigns.length === 0 ? (
        <div className="glass-card rounded-xl border border-white/10 p-10 flex flex-col items-center justify-center text-center flex-1">
          <FileText className="w-12 h-12 text-white/10 mb-3" />
          <p className="text-white/50 text-sm">No campaigns with email templates yet</p>
          <p className="text-white/30 text-xs mt-1 mb-5">
            Run an analysis to generate campaigns with email templates
          </p>
          <button
            onClick={() => navigate('/campaigns')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-sm font-medium hover:bg-purple-500/30 border border-purple-500/20 transition-colors"
          >
            Go to Campaigns
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="space-y-3 overflow-y-auto">
          {campaigns.map((campaign, index) => {
            const emailCount = campaign.email_templates.length;
            const linkedinCount = campaign.linkedin_posts.length;

            return (
              <motion.div
                key={campaign.id}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04 }}
                className="glass-card rounded-xl border border-white/10 p-4 flex items-center gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <h3 className="text-sm font-medium text-white truncate">{campaign.name}</h3>
                    {campaign.objective && (
                      <span className="flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium border bg-purple-500/20 text-purple-300 border-purple-500/30">
                        {campaign.objective}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-white/40">
                    {emailCount} email template{emailCount !== 1 ? 's' : ''}
                    {linkedinCount > 0 ? ` · ${linkedinCount} LinkedIn post${linkedinCount !== 1 ? 's' : ''}` : ''}
                  </p>
                </div>
                <button
                  onClick={() => navigate('/campaigns')}
                  className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white text-xs transition-colors"
                >
                  View &amp; Generate
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main export
// ============================================================================

export function ContentPage() {
  const companyId = useCompanyId() ?? '';
  const [activeTab, setActiveTab] = useState<ActiveTab>('linkedin');
  const [signals, setSignals] = useState<SignalEvent[]>([]);

  // Hydrate company info from session storage (same key as Dashboard)
  const companyInfo = (() => {
    try {
      const stored = sessionStorage.getItem('gtm_company_info');
      return stored ? (JSON.parse(stored) as CompanyInfo) : null;
    } catch {
      return null;
    }
  })();

  // Fetch recent signals for context (best-effort)
  useEffect(() => {
    if (!companyId) return;
    apiClient
      .get<SignalEvent[]>(`/companies/${companyId}/signals?limit=3`)
      .then(data => setSignals(Array.isArray(data) ? data : []))
      .catch(() => {/* signals are optional context */});
  }, [companyId]);

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ── */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400" />
              Content Studio
            </h1>
            <p className="text-xs text-white/40">
              AI-generated content for your GTM campaigns
            </p>
          </div>

          {/* Tab bar */}
          <div className="flex items-center gap-1 bg-white/5 rounded-xl p-1">
            <TabButton
              active={activeTab === 'linkedin'}
              onClick={() => setActiveTab('linkedin')}
              icon={<Linkedin className="w-3.5 h-3.5" />}
              label="LinkedIn Posts"
            />
            <TabButton
              active={activeTab === 'email'}
              onClick={() => setActiveTab('email')}
              icon={<FileText className="w-3.5 h-3.5" />}
              label="Email Templates"
            />
          </div>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="flex-1 overflow-y-auto p-5">
        <AnimatePresence mode="wait">
          {activeTab === 'linkedin' ? (
            <motion.div
              key="linkedin"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              transition={{ duration: 0.15 }}
              className="h-full"
            >
              <LinkedInTab
                companyId={companyId}
                companyInfo={companyInfo}
                signals={signals}
              />
            </motion.div>
          ) : (
            <motion.div
              key="email"
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
              className="h-full"
            >
              <EmailTemplatesTab companyId={companyId} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
