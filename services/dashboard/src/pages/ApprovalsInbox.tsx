/**
 * ApprovalsInbox — Human approval gate for outreach queue.
 *
 * EVERY outreach email goes through this page before sending.
 * Users can: preview, edit, approve, reject, or bulk approve.
 *
 * This is the "human in the loop" that makes GTM Advisor trustworthy.
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, X, Edit3, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { useCompanyId } from '../context/CompanyContext';
import { approvalsApi, ApprovalItem } from '../api/approvals';

function ApprovalCard({
  item,
  onApprove,
  onReject,
  selected,
  onSelect,
}: {
  item: ApprovalItem;
  onApprove: (id: string, editedSubject?: string, editedBody?: string) => void;
  onReject: (id: string) => void;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editSubject, setEditSubject] = useState(item.proposed_subject);
  const [editBody, setEditBody] = useState(item.proposed_body);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      className={`glass-card rounded-xl overflow-hidden border transition-colors ${
        selected ? 'border-purple-500/40' : 'border-white/10'
      }`}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onSelect(item.id)}
            className="mt-1 w-4 h-4 rounded accent-purple-500"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-white">{item.to_name || item.to_email}</span>
              <span className="text-xs text-white/40">{item.to_email}</span>
              {item.sequence_name && (
                <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 text-[10px]">
                  {item.sequence_name} · Step {item.step_number + 1}
                </span>
              )}
            </div>
            <p className="text-sm text-white/70 mt-1 truncate">
              <span className="text-white/30 text-xs">Subject: </span>
              {item.proposed_subject}
            </p>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => setExpanded(e => !e)}
              className="p-1.5 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/5 transition-colors"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-3 pt-3 border-t border-white/10"
            >
              {editing ? (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-white/40 mb-1 block">Subject</label>
                    <input
                      value={editSubject}
                      onChange={e => setEditSubject(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-white/40 mb-1 block">Body</label>
                    <textarea
                      value={editBody}
                      onChange={e => setEditBody(e.target.value)}
                      rows={6}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50 resize-none font-mono"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { onApprove(item.id, editSubject, editBody); setEditing(false); }}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-500/20 text-green-400 text-sm hover:bg-green-500/30 transition-colors"
                    >
                      <CheckCircle className="w-4 h-4" />
                      Save & Approve
                    </button>
                    <button onClick={() => setEditing(false)} className="px-4 py-2 rounded-lg bg-white/5 text-white/50 text-sm hover:bg-white/10 transition-colors">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <pre className="text-sm text-white/70 whitespace-pre-wrap font-sans leading-relaxed bg-white/3 rounded-lg p-3">
                    {item.proposed_body}
                  </pre>
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => onApprove(item.id)}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-500/20 text-green-400 text-sm hover:bg-green-500/30 transition-colors"
                    >
                      <CheckCircle className="w-4 h-4" />
                      Approve & Send
                    </button>
                    <button
                      onClick={() => setEditing(true)}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-sm hover:bg-blue-500/30 transition-colors"
                    >
                      <Edit3 className="w-4 h-4" />
                      Edit
                    </button>
                    <button
                      onClick={() => onReject(item.id)}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 text-sm hover:bg-red-500/30 transition-colors"
                    >
                      <X className="w-4 h-4" />
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export function ApprovalsInbox() {
  const companyId = useCompanyId() ?? '';
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  const load = async () => {
    if (!companyId) return;
    try {
      const data = await approvalsApi.list(companyId);
      setItems(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [companyId]);

  const handleApprove = async (id: string, editedSubject?: string, editedBody?: string) => {
    await approvalsApi.approve(companyId, id, editedSubject, editedBody);
    setItems(prev => prev.filter(i => i.id !== id));
    setSelected(prev => { const next = new Set(prev); next.delete(id); return next; });
  };

  const handleReject = async (id: string) => {
    await approvalsApi.reject(companyId, id);
    setItems(prev => prev.filter(i => i.id !== id));
    setSelected(prev => { const next = new Set(prev); next.delete(id); return next; });
  };

  const handleBulkApprove = async () => {
    setBulkLoading(true);
    await approvalsApi.bulkApprove(companyId, Array.from(selected));
    setItems(prev => prev.filter(i => !selected.has(i.id)));
    setSelected(new Set());
    setBulkLoading(false);
  };

  const toggleSelect = (id: string) => {
    setSelected(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  };

  const selectAll = () => {
    if (selected.size === items.length) setSelected(new Set());
    else setSelected(new Set(items.map(i => i.id)));
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white">Approvals Inbox</h1>
            <p className="text-xs text-white/40">Review and approve outreach before it sends</p>
          </div>
          <div className="flex items-center gap-3">
            {items.length > 0 && (
              <>
                <button onClick={selectAll} className="text-xs text-white/40 hover:text-white/70">
                  {selected.size === items.length ? 'Deselect all' : 'Select all'}
                </button>
                {selected.size > 0 && (
                  <motion.button
                    onClick={handleBulkApprove}
                    disabled={bulkLoading}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-green-500/20 text-green-400 text-sm font-medium hover:bg-green-500/30 transition-colors disabled:opacity-50"
                  >
                    <Zap className="w-4 h-4" />
                    {bulkLoading ? 'Sending...' : `Approve ${selected.size} selected`}
                  </motion.button>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16">
            <CheckCircle className="w-12 h-12 text-green-400/30 mx-auto mb-3" />
            <p className="text-white/50">All caught up! No pending approvals.</p>
            <p className="text-white/30 text-sm mt-1">New outreach steps will appear here for review.</p>
          </div>
        ) : (
          <AnimatePresence>
            {items.map(item => (
              <ApprovalCard
                key={item.id}
                item={item}
                onApprove={handleApprove}
                onReject={handleReject}
                selected={selected.has(item.id)}
                onSelect={toggleSelect}
              />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
