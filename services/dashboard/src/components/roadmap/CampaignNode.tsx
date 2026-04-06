/**
 * CampaignNode — a campaign card on the GTM Roadmap canvas.
 * Displays agent-generated campaign data: name, framework rationale,
 * channels, status, KPIs. Clicking triggers the detail panel.
 */
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { motion } from 'framer-motion';
import {
  Mail, Linkedin, Globe, Image, FileText, Radio, Mic,
  CheckCircle, Clock, Play, Pause, Sparkles
} from 'lucide-react';

// Channel icon mapping
const CHANNEL_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  linkedin: Linkedin,
  social: Globe,
  social_image: Image,
  whitepaper: FileText,
  webinar: Mic,
  edm: Mail,
  landing_page: Globe,
  blog: FileText,
  ad: Radio,
};

// Status config
const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle; color: string; bg: string; label: string }> = {
  draft: { icon: Clock, color: 'text-white/40', bg: 'bg-white/5', label: 'Proposed' },
  active: { icon: Play, color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'Running' },
  paused: { icon: Pause, color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'Paused' },
  completed: { icon: CheckCircle, color: 'text-emerald-400', bg: 'bg-emerald-500/10', label: 'Complete' },
};

export interface CampaignNodeData {
  campaign: {
    id: string;
    name: string;
    description?: string;
    objective?: string;
    status: string;
    strategy_track?: string;
    framework_rationale?: string;
    knowledge_source?: string;
    channels: string[];
    content_types_needed: string[];
    estimated_impact?: string;
    recommended_by_ai: boolean;
    budget?: number;
    metrics: Record<string, unknown>;
  };
  onSelect?: (campaignId: string) => void;
  onGenerateCreative?: (campaignId: string) => void;
  onLaunch?: (campaignId: string) => void;
}

function CampaignNodeComponent({ data, selected }: NodeProps & { data: CampaignNodeData }) {
  const { campaign, onSelect } = data;
  const status = STATUS_CONFIG[campaign.status] || STATUS_CONFIG.draft;
  const StatusIcon = status.icon;

  // Extract KPIs from agent-generated metrics
  const kpis = (campaign.metrics?.kpis as string[]) || [];

  return (
    <>
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-white/30" />
      <motion.div
        whileHover={{ scale: 1.02 }}
        onClick={() => onSelect?.(campaign.id)}
        className={`w-[280px] rounded-xl border cursor-pointer transition-all ${
          selected
            ? 'border-purple-400/60 shadow-lg shadow-purple-500/20'
            : 'border-white/10 hover:border-white/20'
        } bg-surface/80 backdrop-blur-sm`}
      >
        {/* Header */}
        <div className="px-3 py-2.5 border-b border-white/5">
          <div className="flex items-start gap-2">
            <div className={`mt-0.5 p-1 rounded-md ${status.bg}`}>
              <StatusIcon className={`w-3.5 h-3.5 ${status.color}`} />
            </div>
            <div className="flex-1 min-w-0">
              {campaign.strategy_track && (
                <span className="inline-block px-1.5 py-0.5 rounded bg-indigo-500/15 text-[9px] font-medium text-indigo-300 mb-0.5 truncate max-w-full">
                  {campaign.strategy_track}
                </span>
              )}
              <p className="text-sm font-medium text-white truncate">{campaign.name}</p>
              {campaign.framework_rationale && (
                <p className="text-[10px] text-purple-300/70 truncate mt-0.5">
                  {campaign.framework_rationale}
                </p>
              )}
            </div>
            {campaign.recommended_by_ai && (
              <Sparkles className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
            )}
          </div>
        </div>

        {/* Channels — from agent output */}
        {campaign.channels.length > 0 && (
          <div className="px-3 py-1.5 flex flex-wrap gap-1.5">
            {campaign.channels.slice(0, 5).map((ch) => {
              const Icon = CHANNEL_ICONS[ch] || Globe;
              return (
                <span key={ch} className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white/5 text-[10px] text-white/50">
                  <Icon className="w-3 h-3" />
                  {ch}
                </span>
              );
            })}
          </div>
        )}

        {/* KPIs — from agent output */}
        {kpis.length > 0 && (
          <div className="px-3 py-1.5 border-t border-white/5">
            {kpis.slice(0, 2).map((kpi, i) => (
              <p key={i} className="text-[10px] text-white/40 truncate">{kpi}</p>
            ))}
          </div>
        )}

        {/* Footer — status + impact */}
        <div className="px-3 py-2 border-t border-white/5 flex items-center justify-between">
          <span className={`text-[10px] font-medium ${status.color}`}>
            {status.label}
          </span>
          {campaign.estimated_impact && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${
              campaign.estimated_impact === 'high' ? 'bg-emerald-500/10 text-emerald-400' :
              campaign.estimated_impact === 'medium' ? 'bg-amber-500/10 text-amber-400' :
              'bg-white/5 text-white/40'
            }`}>
              {campaign.estimated_impact}
            </span>
          )}
        </div>
      </motion.div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-white/30" />
    </>
  );
}

export const CampaignNode = memo(CampaignNodeComponent);
