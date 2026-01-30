/**
 * Competitor Analyst Workspace
 *
 * SWOT analysis, competitive intelligence, and market positioning.
 * Connected to real backend API.
 */

import { useState, useCallback } from 'react';
import { AgentWorkspace } from '../components/agents/AgentWorkspace';
import {
  Card,
  Badge,
  Button,
  EmptyState,
  CompetitorListLoading,
  ErrorState,
  SkeletonCard,
  useToast,
} from '../components/common';
import { AGENTS } from '../types';
import { useCompanyId } from '../context/CompanyContext';
import { useCompetitors, useBattleCard, useMutation } from '../hooks/useApi';
import * as api from '../api/workspaces';
import type { Competitor } from '../api/workspaces';

export function CompetitorWorkspace() {
  const companyId = useCompanyId();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedCompetitorId, setSelectedCompetitorId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Fetch competitors from API
  const {
    data: competitorData,
    isLoading,
    error,
    refresh,
  } = useCompetitors(companyId);

  // Fetch battle card for selected competitor
  const { data: _battleCard, isLoading: _battleCardLoading } = useBattleCard(
    companyId,
    selectedCompetitorId
  );
  // Use void to suppress unused variable warnings for future use
  void _battleCard;
  void _battleCardLoading;

  const agent = AGENTS.find((a) => a.id === 'competitor-analyst')!;

  // Mutation to trigger agent run with proper error handling
  const triggerAgentMutation = useMutation(
    () => {
      if (!companyId) return Promise.reject(new Error('No company selected'));
      return api.triggerAgent(companyId, 'competitor-analyst');
    },
    {
      invalidateKeys: ['competitors'],
      onSuccess: () => {
        refresh();
        setIsRunning(false);
        toast.success('Competitor analysis completed');
      },
      onError: (err) => {
        setIsRunning(false);
        toast.error('Failed to run competitor analysis', err.message);
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

  const competitors = competitorData?.competitors || [];
  const selected = competitors.find((c) => c.id === selectedCompetitorId);

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'swot', label: 'SWOT Analysis', icon: '📊' },
    {
      id: 'tracking',
      label: 'Change Tracking',
      badge: competitorData?.unread_alerts_count || 0,
      icon: '🔔',
    },
    { id: 'battlecards', label: 'Battle Cards', icon: '⚔️' },
    { id: 'configure', label: 'Configure', icon: '⚙️' },
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
        <CompetitorListLoading />
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
          title="Failed to load competitors"
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
          description="Please complete onboarding to start tracking competitors."
        />
      </AgentWorkspace>
    );
  }

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
      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Threat Summary */}
          <div className="grid grid-cols-3 gap-4">
            <Card className="border-l-4 border-l-red-500">
              <p className="text-white/50 text-xs">High Threat</p>
              <p className="text-2xl font-bold text-white">
                {competitorData?.high_threat_count || 0}
              </p>
              <p className="text-xs text-red-400">Requires attention</p>
            </Card>
            <Card className="border-l-4 border-l-amber-500">
              <p className="text-white/50 text-xs">Medium Threat</p>
              <p className="text-2xl font-bold text-white">
                {competitorData?.medium_threat_count || 0}
              </p>
              <p className="text-xs text-amber-400">Monitor closely</p>
            </Card>
            <Card className="border-l-4 border-l-green-500">
              <p className="text-white/50 text-xs">Low Threat</p>
              <p className="text-2xl font-bold text-white">
                {competitorData?.low_threat_count || 0}
              </p>
              <p className="text-xs text-green-400">Under control</p>
            </Card>
          </div>

          {/* Competitor List */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Tracked Competitors</h3>
            {competitors.length === 0 ? (
              <EmptyState
                icon="🔍"
                title="No Competitors Yet"
                description="Run the competitor analyst to discover and track competitors."
                action={{ label: 'Run Analysis', onClick: handleRun }}
              />
            ) : (
              <div className="space-y-3">
                {competitors.map((competitor) => (
                  <CompetitorRow
                    key={competitor.id}
                    competitor={competitor}
                    isSelected={selectedCompetitorId === competitor.id}
                    onClick={() => setSelectedCompetitorId(competitor.id)}
                  />
                ))}
                <Button variant="ghost" className="w-full">
                  + Add Competitor
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* SWOT Tab */}
      {activeTab === 'swot' && (
        <div className="space-y-6">
          {selected ? (
            <>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">
                  SWOT Analysis: {selected.name}
                </h3>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setSelectedCompetitorId(null)}
                >
                  View All
                </Button>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <SWOTCard
                  title="Strengths"
                  items={selected.strengths}
                  color="green"
                  icon="💪"
                />
                <SWOTCard
                  title="Weaknesses"
                  items={selected.weaknesses}
                  color="red"
                  icon="⚠️"
                />
                <SWOTCard
                  title="Opportunities"
                  items={selected.opportunities}
                  color="blue"
                  icon="💡"
                />
                <SWOTCard
                  title="Threats"
                  items={selected.threats}
                  color="amber"
                  icon="🎯"
                />
              </div>
            </>
          ) : (
            <EmptyState
              icon="📊"
              title="Select a Competitor"
              description="Choose a competitor from the Overview tab to view their SWOT analysis."
            />
          )}
        </div>
      )}

      {/* Change Tracking Tab */}
      {activeTab === 'tracking' && (
        <div className="space-y-4">
          {competitorData?.unread_alerts_count === 0 ? (
            <EmptyState
              icon="🔔"
              title="No Recent Changes"
              description="We'll notify you when competitors make significant changes."
            />
          ) : (
            <p className="text-white/70">
              {competitorData?.unread_alerts_count} unread alerts across all competitors.
              Select a competitor to view their alerts.
            </p>
          )}
        </div>
      )}

      {/* Battle Cards Tab */}
      {activeTab === 'battlecards' && (
        <div className="space-y-4">
          {competitors.length === 0 ? (
            <EmptyState
              icon="⚔️"
              title="No Battle Cards"
              description="Track competitors to generate battle cards for your sales team."
            />
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {competitors.map((competitor) => (
                <BattleCardPreview
                  key={competitor.id}
                  competitor={competitor}
                  companyId={companyId}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Configure Tab */}
      {activeTab === 'configure' && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Monitoring Settings</h3>
            <div className="space-y-4">
              <SettingItem label="Scan frequency" value="Every 6 hours" />
              <SettingItem label="Track pricing changes" value="Enabled" />
              <SettingItem label="Track job postings" value="Enabled" />
              <SettingItem label="Track news mentions" value="Enabled" />
            </div>
          </Card>
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Alert Settings</h3>
            <div className="space-y-4">
              <SettingItem label="Email alerts" value="Enabled" />
              <SettingItem label="Slack integration" value="Not configured" />
              <SettingItem label="Alert threshold" value="Medium+" />
            </div>
          </Card>
        </div>
      )}
    </AgentWorkspace>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

interface CompetitorRowProps {
  competitor: Competitor;
  isSelected: boolean;
  onClick: () => void;
}

function CompetitorRow({ competitor, isSelected, onClick }: CompetitorRowProps) {
  return (
    <div
      className={`p-4 rounded-lg border cursor-pointer transition-colors ${
        isSelected
          ? 'bg-white/10 border-purple-500'
          : 'bg-white/5 border-white/10 hover:bg-white/10'
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-white font-medium">{competitor.name}</h4>
          <p className="text-white/50 text-sm">{competitor.website}</p>
        </div>
        <div className="text-right">
          <Badge
            variant={
              competitor.threat_level === 'high'
                ? 'danger'
                : competitor.threat_level === 'medium'
                ? 'warning'
                : 'success'
            }
          >
            {competitor.threat_level} threat
          </Badge>
          <p className="text-xs text-white/40 mt-1">
            Updated {formatTimeAgo(new Date(competitor.last_updated))}
          </p>
        </div>
      </div>
      {competitor.positioning && (
        <p className="text-white/60 text-sm mt-2">{competitor.positioning}</p>
      )}
    </div>
  );
}

interface SWOTCardProps {
  title: string;
  items: string[];
  color: string;
  icon: string;
}

function SWOTCard({ title, items, color, icon }: SWOTCardProps) {
  const bgColors: Record<string, string> = {
    green: 'bg-green-500/10 border-green-500/30',
    red: 'bg-red-500/10 border-red-500/30',
    blue: 'bg-blue-500/10 border-blue-500/30',
    amber: 'bg-amber-500/10 border-amber-500/30',
  };

  return (
    <Card className={`${bgColors[color]} border`}>
      <h4 className="text-white font-semibold flex items-center gap-2 mb-3">
        <span>{icon}</span> {title}
      </h4>
      {items.length === 0 ? (
        <p className="text-white/40 text-sm italic">No data yet</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="text-white/80 text-sm flex items-start gap-2">
              <span className="text-white/40">•</span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

interface BattleCardPreviewProps {
  competitor: Competitor;
  companyId: string;
}

function BattleCardPreview({ competitor, companyId }: BattleCardPreviewProps) {
  const { data: battleCard, isLoading } = useBattleCard(companyId, competitor.id);

  if (isLoading) {
    return <SkeletonCard />;
  }

  return (
    <Card>
      <h4 className="text-white font-semibold mb-3">vs {competitor.name}</h4>
      <div className="space-y-2">
        <div>
          <p className="text-xs text-green-400 font-medium">Our Advantages</p>
          <ul className="text-sm text-white/70 ml-4 list-disc">
            {(battleCard?.our_advantages || competitor.our_advantages || [])
              .slice(0, 2)
              .map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            {(battleCard?.our_advantages || competitor.our_advantages || []).length === 0 && (
              <li className="text-white/40 italic">Not analyzed yet</li>
            )}
          </ul>
        </div>
        <div>
          <p className="text-xs text-red-400 font-medium">Their Advantages</p>
          <ul className="text-sm text-white/70 ml-4 list-disc">
            {(battleCard?.their_advantages || competitor.their_advantages || [])
              .slice(0, 2)
              .map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            {(battleCard?.their_advantages || competitor.their_advantages || []).length === 0 && (
              <li className="text-white/40 italic">Not analyzed yet</li>
            )}
          </ul>
        </div>
        <div>
          <p className="text-xs text-blue-400 font-medium">Key Objection Handler</p>
          <p className="text-sm text-white/70 italic">
            {battleCard?.key_objection_handlers?.[0] ||
              competitor.key_objection_handlers?.[0] ||
              'Not analyzed yet'}
          </p>
        </div>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="mt-3"
        onClick={() =>
          window.open(
            api.getExportUrl(companyId, 'battlecards'),
            '_blank'
          )
        }
      >
        Export Battle Card
      </Button>
    </Card>
  );
}

function SettingItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/10 last:border-0">
      <span className="text-white/70">{label}</span>
      <span className="text-white font-medium">{value}</span>
    </div>
  );
}

function formatTimeAgo(date: Date): string {
  const diff = Date.now() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
