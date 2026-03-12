/**
 * DashboardPage — Metrics overview for the GTM Advisor dashboard.
 *
 * Shows pending approvals, active leads, market signals, active sequences,
 * and a recent executions list. All data is fetched in parallel.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Bell, Users, Radio, Mail } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';

// ============================================================================
// Interfaces
// ============================================================================

interface SignalEvent {
  id: string;
  urgency: string;
  is_actioned: boolean;
}

interface EnrollmentResponse {
  id: string;
  status: string;
  emails_sent: number;
}

interface ExecutionRun {
  id: string;
  status: string;
  steps_completed: number;
  emails_sent: number;
  completed_at?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function RunStatusDot({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: 'bg-green-400',
    partial: 'bg-yellow-400',
    failed: 'bg-red-400',
    running: 'bg-purple-400',
  };
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${styles[status] ?? 'bg-white/30'}`}
    />
  );
}

// ============================================================================
// Stat Card
// ============================================================================

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  colorClass: string;
  href: string;
  badge?: boolean;
}

function StatCard({ label, value, icon, colorClass, href, badge }: StatCardProps) {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-4 rounded-xl cursor-pointer hover:bg-white/5 transition-colors"
      onClick={() => navigate(href)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className={`text-3xl font-bold ${colorClass}`}>{value}</span>
          <span className="text-sm text-white/50">{label}</span>
        </div>
        <div className={`p-2 rounded-lg bg-white/5 ${colorClass} flex-shrink-0`}>
          {icon}
        </div>
      </div>
      {badge && value > 0 && (
        <div className="mt-3">
          <span className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-[10px] font-medium border border-red-500/30">
            Needs attention
          </span>
        </div>
      )}
    </motion.div>
  );
}

// ============================================================================
// Recent Executions Row
// ============================================================================

function ExecutionRow({ run }: { run: ExecutionRun }) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-white/5 last:border-0">
      <RunStatusDot status={run.status} />
      <span className="text-sm text-white/70 flex-1">
        Run completed · {run.steps_completed} steps · {run.emails_sent} emails
      </span>
      {run.completed_at && (
        <span className="text-xs text-white/30 flex-shrink-0">{timeAgo(run.completed_at)}</span>
      )}
    </div>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export function DashboardPage() {
  const companyId = useCompanyId();

  const [loading, setLoading] = useState(false);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [leadCount, setLeadCount] = useState(0);
  const [urgentSignalCount, setUrgentSignalCount] = useState(0);
  const [activeSequenceCount, setActiveSequenceCount] = useState(0);
  const [recentRuns, setRecentRuns] = useState<ExecutionRun[]>([]);

  useEffect(() => {
    if (!companyId) return;

    setLoading(true);

    Promise.all([
      apiClient
        .get<{ pending: number }>(`/companies/${companyId}/approvals/count`)
        .then((r) => setPendingApprovals(r.pending))
        .catch(() => setPendingApprovals(0)),

      apiClient
        .get<{ total: number }>(`/companies/${companyId}/leads`)
        .then((r) => setLeadCount(r.total))
        .catch(() => setLeadCount(0)),

      apiClient
        .get<SignalEvent[]>(`/companies/${companyId}/signals`)
        .then((r) => {
          const count = r.filter(
            (s) => !s.is_actioned && (s.urgency === 'immediate' || s.urgency === 'this_week')
          ).length;
          setUrgentSignalCount(count);
        })
        .catch(() => setUrgentSignalCount(0)),

      apiClient
        .get<EnrollmentResponse[]>(
          `/companies/${companyId}/sequences/enrollments?status=active&limit=5`
        )
        .then((r) => setActiveSequenceCount(r.length))
        .catch(() => setActiveSequenceCount(0)),

      apiClient
        .get<ExecutionRun[]>(`/companies/${companyId}/workforce/runs/list`)
        .then((r) => setRecentRuns(r.slice(0, 5)))
        .catch(() => setRecentRuns([])),
    ]).finally(() => setLoading(false));
  }, [companyId]);

  if (!companyId) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
          <h1 className="text-lg font-semibold text-white">Dashboard</h1>
        </div>
        <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center">
          <p className="text-white/40 text-sm">Select a company to see your dashboard</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
          <h1 className="text-lg font-semibold text-white">Dashboard</h1>
        </div>
        <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <h1 className="text-lg font-semibold text-white">Dashboard</h1>
        <p className="text-sm text-white/40 mt-0.5">Overview of your GTM activity</p>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Stat Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Pending Approvals"
            value={pendingApprovals}
            icon={<Bell className="w-4 h-4" />}
            colorClass="text-purple-400"
            href="/approvals"
            badge
          />
          <StatCard
            label="Active Leads"
            value={leadCount}
            icon={<Users className="w-4 h-4" />}
            colorClass="text-blue-400"
            href="/leads"
          />
          <StatCard
            label="Market Signals"
            value={urgentSignalCount}
            icon={<Radio className="w-4 h-4" />}
            colorClass="text-yellow-400"
            href="/signals"
          />
          <StatCard
            label="Active Sequences"
            value={activeSequenceCount}
            icon={<Mail className="w-4 h-4" />}
            colorClass="text-cyan-400"
            href="/sequences"
          />
        </div>

        {/* Recent Executions */}
        <motion.div
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 rounded-xl"
        >
          <h2 className="text-sm font-semibold text-white mb-3">Recent Executions</h2>
          {recentRuns.length === 0 ? (
            <p className="text-sm text-white/30 py-2">
              No executions yet · Design a workforce to get started
            </p>
          ) : (
            <div>
              {recentRuns.map((run) => (
                <ExecutionRow key={run.id} run={run} />
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
