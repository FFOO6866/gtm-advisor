/**
 * SequencesPage — Email sequence enrollment management and playbook template browser.
 *
 * Tabs:
 * - Enrollments: active/paused/completed outreach sequences with pause/resume controls
 * - Templates: playbook library with step counts, duration, and Singapore-specific tags
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Mail, Pause, Play, CheckCircle, Clock, Users, ChevronRight, Zap } from 'lucide-react';
import { useCompanyId } from '../context/CompanyContext';
import { apiClient } from '../api/client';

interface EnrollmentResponse {
  id: string;
  lead_id: string;
  template_id: string;
  status: 'active' | 'paused' | 'completed' | 'rejected' | 'opted_out';
  current_step: number;
  next_step_due: string | null;
  enrolled_at: string;
  emails_sent: number;
}

interface PlaybookTemplate {
  id: string;
  playbook_type: string;
  name: string;
  description: string;
  steps_count: number;
  duration_days: number;
  success_rate_benchmark?: string;
  is_singapore_specific: boolean;
  best_for: string;
}

type EnrollmentFilter = 'all' | 'active' | 'paused' | 'completed';

const ENROLLMENT_FILTERS: { key: EnrollmentFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'paused', label: 'Paused' },
  { key: 'completed', label: 'Completed' },
];

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400 border-green-500/30',
  paused: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  completed: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  rejected: 'bg-red-500/20 text-red-400 border-red-500/30',
  opted_out: 'bg-white/10 text-white/40 border-white/10',
};

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  paused: 'Paused',
  completed: 'Completed',
  rejected: 'Rejected',
  opted_out: 'Opted Out',
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-SG', { day: 'numeric', month: 'short', year: 'numeric' });
}

function truncateId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

function EnrollmentCard({
  enrollment,
  onPause,
  onResume,
}: {
  enrollment: EnrollmentResponse;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
}) {
  const [actionLoading, setActionLoading] = useState(false);

  const handlePause = async () => {
    setActionLoading(true);
    await onPause(enrollment.id);
    setActionLoading(false);
  };

  const handleResume = async () => {
    setActionLoading(true);
    await onResume(enrollment.id);
    setActionLoading(false);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-4 rounded-xl border border-white/10 hover:border-white/20 transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center flex-shrink-0">
          <Mail className="w-4 h-4 text-cyan-400" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span className="text-sm font-medium text-white">
              Lead <span className="font-mono text-white/60">{truncateId(enrollment.lead_id)}</span>
            </span>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${STATUS_STYLES[enrollment.status] ?? STATUS_STYLES.opted_out}`}
            >
              {STATUS_LABELS[enrollment.status] ?? enrollment.status}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs text-white/40 flex-wrap">
            <span className="flex items-center gap-1">
              <ChevronRight className="w-3 h-3" />
              Step {enrollment.current_step}
            </span>
            <span className="flex items-center gap-1">
              <Mail className="w-3 h-3" />
              {enrollment.emails_sent} sent
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Enrolled {formatDate(enrollment.enrolled_at)}
            </span>
            {enrollment.status === 'active' && enrollment.next_step_due && (
              <span className="flex items-center gap-1 text-cyan-400">
                <Zap className="w-3 h-3" />
                Next: {formatDate(enrollment.next_step_due)}
              </span>
            )}
          </div>
        </div>

        <div className="flex-shrink-0">
          {enrollment.status === 'active' && (
            <button
              onClick={handlePause}
              disabled={actionLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-500/10 text-orange-400 text-xs font-medium hover:bg-orange-500/20 transition-colors disabled:opacity-50"
            >
              <Pause className="w-3 h-3" />
              Pause
            </button>
          )}
          {enrollment.status === 'paused' && (
            <button
              onClick={handleResume}
              disabled={actionLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-500/10 text-green-400 text-xs font-medium hover:bg-green-500/20 transition-colors disabled:opacity-50"
            >
              <Play className="w-3 h-3" />
              Resume
            </button>
          )}
          {enrollment.status === 'completed' && (
            <CheckCircle className="w-4 h-4 text-cyan-400 opacity-60" />
          )}
        </div>
      </div>
    </motion.div>
  );
}

function TemplateCard({ template }: { template: PlaybookTemplate }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-4 rounded-xl border border-white/10 hover:border-purple-500/30 transition-colors flex flex-col gap-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h3 className="text-sm font-semibold text-white truncate">{template.name}</h3>
            {template.is_singapore_specific && (
              <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 text-[10px] font-medium border border-red-500/20 flex-shrink-0">
                SG
              </span>
            )}
          </div>
          <p className="text-xs text-white/50 line-clamp-2 leading-relaxed">{template.description}</p>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-white/40 flex-wrap">
        <span className="flex items-center gap-1">
          <ChevronRight className="w-3 h-3 text-cyan-400" />
          {template.steps_count} steps
        </span>
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-cyan-400" />
          {template.duration_days} days
        </span>
        {template.success_rate_benchmark && (
          <span className="flex items-center gap-1 text-green-400">
            <Zap className="w-3 h-3" />
            {template.success_rate_benchmark}
          </span>
        )}
      </div>

      <div className="pt-2 border-t border-white/5">
        <div className="flex items-center gap-1.5">
          <Users className="w-3 h-3 text-white/30 flex-shrink-0" />
          <span className="text-[10px] text-white/40 truncate">{template.best_for}</span>
        </div>
      </div>
    </motion.div>
  );
}

export function SequencesPage() {
  const companyId = useCompanyId() ?? '';
  const [activeTab, setActiveTab] = useState<'enrollments' | 'templates'>('enrollments');

  const [enrollments, setEnrollments] = useState<EnrollmentResponse[]>([]);
  const [enrollmentsLoading, setEnrollmentsLoading] = useState(true);
  const [enrollmentFilter, setEnrollmentFilter] = useState<EnrollmentFilter>('all');

  const [templates, setTemplates] = useState<PlaybookTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesLoaded, setTemplatesLoaded] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    setEnrollmentsLoading(true);
    const query = enrollmentFilter !== 'all' ? `?status=${enrollmentFilter}` : '';
    apiClient
      .get<EnrollmentResponse[]>(`/companies/${companyId}/sequences/enrollments${query}`)
      .then(data => { setEnrollments(data); setEnrollmentsLoading(false); })
      .catch(() => setEnrollmentsLoading(false));
  }, [companyId, enrollmentFilter]);

  useEffect(() => {
    if (activeTab !== 'templates' || templatesLoaded || !companyId) return;
    setTemplatesLoading(true);
    apiClient
      .get<PlaybookTemplate[]>(`/companies/${companyId}/sequences/templates`)
      .then(data => { setTemplates(data); setTemplatesLoading(false); setTemplatesLoaded(true); })
      .catch(() => setTemplatesLoading(false));
  }, [activeTab, companyId, templatesLoaded]);

  const handlePause = async (enrollmentId: string) => {
    try {
      await apiClient.post(`/companies/${companyId}/sequences/enrollments/${enrollmentId}/pause`);
      setEnrollments(prev =>
        prev.map(e => e.id === enrollmentId ? { ...e, status: 'paused' as const } : e)
      );
    } catch {
      // leave state unchanged on error
    }
  };

  const handleResume = async (enrollmentId: string) => {
    try {
      await apiClient.post(`/companies/${companyId}/sequences/enrollments/${enrollmentId}/resume`);
      setEnrollments(prev =>
        prev.map(e => e.id === enrollmentId ? { ...e, status: 'active' as const } : e)
      );
    } catch {
      // leave state unchanged on error
    }
  };

  const activeCount = enrollments.filter(e => e.status === 'active').length;
  const pausedCount = enrollments.filter(e => e.status === 'paused').length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white flex items-center gap-2">
              <Mail className="w-5 h-5 text-cyan-400" />
              Sequences
            </h1>
            <p className="text-xs text-white/40">
              {activeCount > 0
                ? <span className="text-green-400">{activeCount} active</span>
                : 'No active sequences'
              }
              {pausedCount > 0 && (
                <span className="text-white/30"> · <span className="text-orange-400">{pausedCount} paused</span></span>
              )}
            </p>
          </div>

          {/* Tabs */}
          <div className="flex items-center gap-1 bg-white/5 rounded-xl p-1">
            <button
              onClick={() => setActiveTab('enrollments')}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === 'enrollments'
                  ? 'bg-white/10 text-white'
                  : 'text-white/40 hover:text-white/70'
              }`}
            >
              Enrollments
            </button>
            <button
              onClick={() => setActiveTab('templates')}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === 'templates'
                  ? 'bg-white/10 text-white'
                  : 'text-white/40 hover:text-white/70'
              }`}
            >
              Templates
            </button>
          </div>
        </div>

        {/* Enrollment filter bar */}
        {activeTab === 'enrollments' && (
          <div className="flex gap-1 mt-3">
            {ENROLLMENT_FILTERS.map(f => (
              <button
                key={f.key}
                onClick={() => setEnrollmentFilter(f.key)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  enrollmentFilter === f.key
                    ? 'bg-white/10 text-white'
                    : 'text-white/40 hover:text-white/60'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'enrollments' && (
          <>
            {enrollmentsLoading ? (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : enrollments.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Mail className="w-12 h-12 text-white/10 mb-3" />
                <p className="text-white/50 text-sm">No enrollments yet</p>
                <p className="text-white/30 text-xs mt-1">Activate a playbook to start outreach</p>
              </div>
            ) : (
              <div className="space-y-3">
                {enrollments.map(enrollment => (
                  <EnrollmentCard
                    key={enrollment.id}
                    enrollment={enrollment}
                    onPause={handlePause}
                    onResume={handleResume}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {activeTab === 'templates' && (
          <>
            {templatesLoading ? (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : templates.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Zap className="w-12 h-12 text-white/10 mb-3" />
                <p className="text-white/50 text-sm">No templates available</p>
                <p className="text-white/30 text-xs mt-1">Playbook templates will appear here once configured</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {templates.map(template => (
                  <TemplateCard key={template.id} template={template} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
