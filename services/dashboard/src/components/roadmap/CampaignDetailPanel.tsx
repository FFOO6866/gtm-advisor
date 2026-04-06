/**
 * CampaignDetailPanel — side panel for campaign details.
 * All content displayed is agent-generated.
 * Action buttons trigger backend endpoints that run agents.
 */
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Sparkles, Play, Image, Mail, CheckCircle,
  TrendingUp, BookOpen
} from 'lucide-react';
import type { RoadmapCampaign, CreativeAsset } from '../../api/roadmap';
import { roadmapApi } from '../../api/roadmap';

interface CampaignDetailPanelProps {
  campaign: RoadmapCampaign | null;
  companyId: string;
  onClose: () => void;
  onGenerateCreative: (campaignId: string) => void;
  onLaunch: (campaignId: string) => void;
}

export function CampaignDetailPanel({
  campaign,
  companyId,
  onClose,
  onGenerateCreative,
  onLaunch,
}: CampaignDetailPanelProps) {
  const [assets, setAssets] = useState<CreativeAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [attribution, setAttribution] = useState<Record<string, unknown> | null>(null);

  // Load assets when campaign is selected
  useEffect(() => {
    if (!campaign?.id || !companyId) return;
    setLoading(true);
    roadmapApi
      .getCampaignAssets(companyId, campaign.id)
      .then(setAssets)
      .catch(() => setAssets([]))
      .finally(() => setLoading(false));

    // Load performance data if campaign is active/completed
    if (campaign.status === 'active' || campaign.status === 'completed') {
      roadmapApi
        .getCampaignAttribution(companyId, campaign.id)
        .then(setAttribution)
        .catch(() => setAttribution(null));
    }
  }, [campaign?.id, companyId, campaign?.status]);

  if (!campaign) return null;

  const kpis = (campaign.metrics?.kpis as string[]) || [];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ x: 400, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 400, opacity: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="fixed right-0 top-0 h-full w-[400px] bg-surface/95 backdrop-blur-xl border-l border-white/10 z-50 overflow-y-auto"
      >
        {/* Header */}
        <div className="sticky top-0 bg-surface/95 backdrop-blur-xl border-b border-white/10 px-5 py-4 flex items-start gap-3 z-10">
          <div className="flex-1">
            <h2 className="text-base font-semibold text-white">{campaign.name}</h2>
            <p className="text-xs text-white/40 mt-0.5">
              {campaign.status} · {campaign.phase?.replace('_', ' ')}
            </p>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          {/* Framework Rationale (agent-generated) */}
          {campaign.framework_rationale && (
            <div>
              <h3 className="text-xs font-semibold text-purple-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                Framework Rationale
              </h3>
              <p className="text-sm text-white/70">{campaign.framework_rationale}</p>
              {campaign.knowledge_source && (
                <p className="text-[10px] text-white/30 mt-1">Source: {campaign.knowledge_source}</p>
              )}
            </div>
          )}

          {/* Description (agent-generated) */}
          {campaign.description && (
            <div>
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Objective</h3>
              <p className="text-sm text-white/70">{campaign.description}</p>
            </div>
          )}

          {/* Channels */}
          {campaign.channels.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Channels</h3>
              <div className="flex flex-wrap gap-1.5">
                {campaign.channels.map((ch) => (
                  <span key={ch} className="px-2 py-1 rounded-lg bg-white/5 text-xs text-white/60">
                    {ch}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Content Types Needed */}
          {campaign.content_types_needed?.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Content Needed</h3>
              <div className="flex flex-wrap gap-1.5">
                {campaign.content_types_needed.map((ct) => (
                  <span key={ct} className="px-2 py-1 rounded-lg bg-purple-500/10 text-xs text-purple-300">
                    {ct.replace('_', ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* KPIs (agent-generated) */}
          {kpis.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5" />
                Target KPIs
              </h3>
              <ul className="space-y-1">
                {kpis.map((kpi, i) => (
                  <li key={i} className="text-sm text-white/60 flex items-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-emerald-400" />
                    {kpi}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Creative Assets (produced by EDM Designer / Graphic Designer agents) */}
          <div>
            <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Image className="w-3.5 h-3.5" />
              Creative Assets
            </h3>
            {loading ? (
              <div className="text-xs text-white/30">Loading agent-generated assets...</div>
            ) : assets.length === 0 ? (
              <div className="text-xs text-white/30 bg-white/5 rounded-lg p-3 text-center">
                No assets yet. Click &quot;Generate Creative&quot; to run the design agents.
              </div>
            ) : (
              <div className="space-y-2">
                {assets.map((asset) => (
                  <div key={asset.id} className="flex items-center gap-3 p-2 rounded-lg bg-white/5">
                    {asset.image_url ? (
                      <img src={asset.image_url} alt={asset.name} className="w-10 h-10 rounded object-cover" />
                    ) : (
                      <div className="w-10 h-10 rounded bg-white/10 flex items-center justify-center">
                        <Mail className="w-4 h-4 text-white/30" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-white/70 truncate">{asset.name}</p>
                      <p className="text-[10px] text-white/30">{asset.asset_type} · {asset.status}</p>
                    </div>
                    {asset.status === 'approved' && (
                      <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Performance (from Campaign Monitor agent) */}
          {attribution && (
            <div>
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5" />
                Performance
              </h3>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries((attribution as Record<string, Record<string, unknown>>).email || {}).map(([key, val]) => (
                  <div key={key} className="p-2 rounded-lg bg-white/5">
                    <p className="text-[10px] text-white/30">{key.replace('_', ' ')}</p>
                    <p className="text-sm font-semibold text-white">{String(val)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons — these trigger agent runs, not local logic */}
          <div className="space-y-2 pt-2 border-t border-white/10">
            {campaign.status === 'draft' && (
              <button
                onClick={() => onGenerateCreative(campaign.id)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 transition-colors text-sm font-medium"
              >
                <Sparkles className="w-4 h-4" />
                Generate Creative (AI Agents)
              </button>
            )}
            {(campaign.status === 'draft' || campaign.status === 'active') && (
              <button
                onClick={() => onLaunch(campaign.id)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 transition-colors text-sm font-medium"
              >
                <Play className="w-4 h-4" />
                {campaign.status === 'draft' ? 'Launch Campaign' : 'View Live'}
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
