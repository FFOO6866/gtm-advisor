/**
 * Campaign Architect Agent Workspace
 *
 * Campaign planning, content generation, and messaging.
 */

import { useState } from 'react';
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
} from 'lucide-react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import { Card, Badge, Button, EmptyState } from '../components/common';
import { AGENTS } from '../types';

interface CampaignPlan {
  name: string;
  objective: string;
  phases: CampaignPhase[];
  totalBudget: number;
  duration: string;
  expectedROI: number;
}

interface CampaignPhase {
  name: string;
  duration: string;
  budget: number;
  channels: string[];
  content: string[];
  kpis: string[];
}

// Mock campaign plan
const MOCK_CAMPAIGN: CampaignPlan = {
  name: 'Enterprise AI Transformation',
  objective: 'Generate qualified leads for enterprise segment',
  totalBudget: 15000,
  duration: '3 months',
  expectedROI: 3.2,
  phases: [
    {
      name: 'Awareness',
      duration: 'Week 1-4',
      budget: 5000,
      channels: ['LinkedIn Ads', 'Blog Content', 'Organic Social'],
      content: ['3 thought leadership posts', '2 case studies', 'Daily social posts'],
      kpis: ['5K impressions', '500 engagements', '100 website visits'],
    },
    {
      name: 'Consideration',
      duration: 'Week 5-8',
      budget: 6000,
      channels: ['Webinar', 'Retargeting', 'Email Nurture'],
      content: ['1 webinar', 'Retargeting ads', '5-email sequence'],
      kpis: ['100 webinar registrations', '50 MQLs'],
    },
    {
      name: 'Conversion',
      duration: 'Week 9-12',
      budget: 4000,
      channels: ['Direct Outreach', 'Demo Campaigns', 'Sales Enablement'],
      content: ['Personalized outreach', 'Demo landing page', 'Sales deck'],
      kpis: ['20 demo requests', '5 SQLs', '2 closed deals'],
    },
  ],
};

const CONTENT_TYPES = [
  { id: 'linkedin', label: 'LinkedIn Post', icon: <Linkedin className="w-4 h-4" /> },
  { id: 'email', label: 'Email', icon: <Mail className="w-4 h-4" /> },
  { id: 'blog', label: 'Blog Post', icon: <FileText className="w-4 h-4" /> },
  { id: 'ad', label: 'Ad Copy', icon: <Target className="w-4 h-4" /> },
];

export function CampaignWorkspace() {
  const [activeTab, setActiveTab] = useState('active');
  const [isRunning, setIsRunning] = useState(false);
  const [selectedContentType, setSelectedContentType] = useState('linkedin');
  const [generatedContent, setGeneratedContent] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [contentUsage] = useState({ used: 23, limit: 50 });
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const agent = AGENTS.find((a) => a.id === 'campaign-architect')!;

  const handleRun = async () => {
    setIsRunning(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsRunning(false);
  };

  const handleGenerateContent = async () => {
    setIsGenerating(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Mock generated content
    const mockContent = [
      `📊 34% of Singapore enterprises adopted AI marketing tools this year.

But here's what the data doesn't tell you:

The 34% who adopted aren't just "using AI" — they're seeing:
• 3x faster campaign execution
• 40% reduction in agency spend
• Real-time competitive intelligence

We just helped a fintech scale their marketing team's output by 5x.

Curious how? Let's chat. 👇

#AIMarketing #Singapore #MarTech`,
      `Last month, our CMO asked me: "Can AI really replace our marketing agency?"

Here's what we discovered after 90 days:

❌ AI can't replace creativity
❌ AI can't build relationships
❌ AI can't understand your brand soul

✅ AI CAN execute 10x faster
✅ AI CAN analyze competitors 24/7
✅ AI CAN free your team for strategy

The result? We cut costs 40% AND improved results.

The future isn't AI vs humans. It's AI + humans.

What's your take?`,
      `What if your marketing team could work 3x faster?

Not by working longer hours.
Not by hiring more people.
Not by cutting corners.

By using AI as your execution layer.

Here's what that looks like in practice:
→ Competitive intel delivered daily (not quarterly)
→ Campaigns launched in days (not weeks)
→ Content created in minutes (not hours)

This isn't future tech. It's happening now in Singapore.

DM me if you want to see how 👇`,
    ];

    setGeneratedContent(mockContent);
    setIsGenerating(false);
  };

  const handleCopy = (index: number, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const tabs = [
    { id: 'active', label: 'Active Campaigns', icon: '📢' },
    { id: 'builder', label: 'Campaign Builder', icon: '🛠️' },
    { id: 'content', label: 'Content Generator', badge: contentUsage.limit - contentUsage.used, icon: '✏️' },
    { id: 'templates', label: 'Templates', icon: '📋' },
  ];

  return (
    <AgentWorkspace
      agent={agent}
      status="idle"
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
          <CampaignCard campaign={MOCK_CAMPAIGN} />

          <Card className="border-dashed border-2 border-white/20">
            <div className="flex items-center justify-center py-8">
              <Button variant="ghost" leftIcon={<Sparkles className="w-4 h-4" />}>
                + Create New Campaign
              </Button>
            </div>
          </Card>
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
                    <option value="3" selected>3 months</option>
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
                Content this month: {contentUsage.used}/{contentUsage.limit} pieces
              </span>
              <Button variant="ghost" size="sm">
                Upgrade for unlimited
              </Button>
            </div>
            <div className="mt-2 h-2 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                initial={{ width: 0 }}
                animate={{ width: `${(contentUsage.used / contentUsage.limit) * 100}%` }}
              />
            </div>
          </Card>

          {/* Content Type Selector */}
          <div className="flex gap-2">
            {CONTENT_TYPES.map((type) => (
              <Button
                key={type.id}
                variant={selectedContentType === type.id ? 'secondary' : 'ghost'}
                onClick={() => setSelectedContentType(type.id)}
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
                  defaultValue="AI transforming enterprise marketing ROI"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-white/30 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-white/70 mb-1">Tone</label>
                  <select className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500">
                    <option value="professional">Professional</option>
                    <option value="conversational">Conversational</option>
                    <option value="bold">Bold</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-white/70 mb-1">Target Persona</label>
                  <select className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500">
                    <option value="cto">Enterprise CTO</option>
                    <option value="cmo">CMO</option>
                    <option value="founder">Founder</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-white/70 mb-1">Include CTA?</label>
                  <select className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-purple-500">
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm text-white/70 mb-1">Key points to include (optional)</label>
                <textarea
                  placeholder="• Point 1&#10;• Point 2"
                  rows={3}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-white/30 focus:outline-none focus:border-purple-500 resize-none"
                />
              </div>
              <Button
                variant="primary"
                onClick={handleGenerateContent}
                isLoading={isGenerating}
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
function CampaignCard({ campaign }: { campaign: CampaignPlan }) {
  const [expandedPhase, setExpandedPhase] = useState<number | null>(0);

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-xl font-semibold text-white">{campaign.name}</h3>
          <p className="text-white/60 mt-1">{campaign.objective}</p>
        </div>
        <Badge variant="success">Active</Badge>
      </div>

      {/* Campaign Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <DollarSign className="w-5 h-5 text-green-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">SGD {campaign.totalBudget.toLocaleString()}</div>
          <div className="text-xs text-white/50">Total Budget</div>
        </div>
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <Calendar className="w-5 h-5 text-blue-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">{campaign.duration}</div>
          <div className="text-xs text-white/50">Duration</div>
        </div>
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <Target className="w-5 h-5 text-purple-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">{campaign.phases.length}</div>
          <div className="text-xs text-white/50">Phases</div>
        </div>
        <div className="text-center p-3 bg-white/5 rounded-lg">
          <Sparkles className="w-5 h-5 text-amber-400 mx-auto mb-1" />
          <div className="text-lg font-semibold text-white">{campaign.expectedROI}x</div>
          <div className="text-xs text-white/50">Expected ROI</div>
        </div>
      </div>

      {/* Phases */}
      <div className="space-y-3">
        {campaign.phases.map((phase, index) => (
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
                        {phase.channels.map((channel) => (
                          <li key={channel} className="text-sm text-white/80">• {channel}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h5 className="text-xs font-medium text-white/50 uppercase mb-2">Content</h5>
                      <ul className="space-y-1">
                        {phase.content.map((item) => (
                          <li key={item} className="text-sm text-white/80">• {item}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h5 className="text-xs font-medium text-white/50 uppercase mb-2">KPIs</h5>
                      <ul className="space-y-1">
                        {phase.kpis.map((kpi) => (
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

      {/* Actions */}
      <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-white/10">
        <Button variant="ghost">Edit Campaign</Button>
        <Button variant="secondary">Export to PDF</Button>
      </div>
    </Card>
  );
}
