import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, Send, X } from 'lucide-react';
import { Card } from './Card';
import { Badge } from './Badge';
import { Button } from './Button';
import type { Insight } from '../../types';

interface InsightCardProps {
  insight: Insight;
  expanded?: boolean;
  onSendToAgent?: (agentId: string) => void;
  onDismiss?: () => void;
}

export function InsightCard({
  insight,
  expanded = false,
  onSendToAgent,
  onDismiss,
}: InsightCardProps) {
  const [isExpanded, setIsExpanded] = useState(expanded);

  const priorityConfig = {
    high: { color: 'border-l-red-500', badge: 'danger' as const, label: 'HIGH PRIORITY' },
    medium: { color: 'border-l-amber-500', badge: 'warning' as const, label: 'MEDIUM' },
    low: { color: 'border-l-blue-500', badge: 'info' as const, label: 'LOW' },
    opportunity: { color: 'border-l-green-500', badge: 'success' as const, label: 'OPPORTUNITY' },
  };

  const config = priorityConfig[insight.priority] || priorityConfig.low;

  const formatTimeAgo = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - new Date(date).getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    return 'Just now';
  };

  return (
    <Card className={`border-l-4 ${config.color}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={config.badge}>{config.label}</Badge>
          {insight.isNew && (
            <span className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
          )}
        </div>
        <span className="text-xs text-white/50">{formatTimeAgo(insight.createdAt)}</span>
      </div>

      {/* Title & Summary */}
      <h3 className="text-lg font-semibold text-white mt-3">{insight.title}</h3>
      <p className="text-white/70 mt-1 text-sm">{insight.summary}</p>

      {/* Expandable Details */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 space-y-3 overflow-hidden"
          >
            {/* Evidence */}
            {insight.evidence && (
              <div className="flex items-start gap-2 p-3 bg-white/5 rounded-lg">
                <span className="text-lg">📊</span>
                <div>
                  <span className="text-xs font-medium text-white/50 uppercase">Evidence</span>
                  <p className="text-sm text-white/80 mt-0.5">{insight.evidence}</p>
                </div>
              </div>
            )}

            {/* Implication */}
            {insight.implication && (
              <div className="flex items-start gap-2 p-3 bg-white/5 rounded-lg">
                <span className="text-lg">💡</span>
                <div>
                  <span className="text-xs font-medium text-white/50 uppercase">Implication</span>
                  <p className="text-sm text-white/80 mt-0.5">{insight.implication}</p>
                </div>
              </div>
            )}

            {/* Recommended Action */}
            {insight.recommendedAction && (
              <div className="flex items-start gap-2 p-3 bg-purple-500/10 rounded-lg border border-purple-500/20">
                <span className="text-lg">✅</span>
                <div>
                  <span className="text-xs font-medium text-purple-400 uppercase">
                    Recommended Action
                  </span>
                  <p className="text-sm text-white/80 mt-0.5">{insight.recommendedAction}</p>
                </div>
              </div>
            )}

            {/* Sources */}
            {insight.sources && insight.sources.length > 0 && (
              <div className="text-xs text-white/40">
                Sources: {insight.sources.join(', ')}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-white/10">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          rightIcon={isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        >
          {isExpanded ? 'Collapse' : 'View Full Analysis'}
        </Button>

        <div className="flex-1" />

        {onSendToAgent && (
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<Send className="w-3 h-3" />}
            onClick={() => onSendToAgent('campaign-architect')}
          >
            Send to Campaign
          </Button>
        )}

        {onDismiss && (
          <Button variant="ghost" size="sm" onClick={onDismiss}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
    </Card>
  );
}
