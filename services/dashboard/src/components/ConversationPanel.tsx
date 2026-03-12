import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Sparkles } from 'lucide-react';
import { Message, AgentActivity, AGENTS } from '../types';

interface ConversationPanelProps {
  messages: Message[];
  onSendMessage: (content: string) => void;
  isAnalyzing: boolean;
  agentActivities: AgentActivity[];
  onStart?: () => void;
}

export function ConversationPanel({
  messages,
  onSendMessage,
  isAnalyzing,
  agentActivities,
  onStart,
}: ConversationPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isAnalyzing) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const getAgentInfo = (agentId?: string) => {
    return AGENTS.find(a => a.id === agentId);
  };

  const activeThinkingAgents = agentActivities.filter(
    a => a.status === 'thinking' || a.status === 'active'
  );

  return (
    <div className="w-96 flex flex-col border-r border-white/10 bg-surface/50 backdrop-blur-xl">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-white/10">
        <h2 className="text-sm font-semibold text-white">Agent Activity</h2>
        <p className="text-xs text-white/40">6 specialists collaborating</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 mask-fade-y">
        {messages.length === 0 && (
          <button
            onClick={onStart}
            className="w-full text-center py-8 rounded-xl hover:bg-white/5 transition-colors group"
          >
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-purple-500/20 transition-colors">
              <Sparkles className="w-8 h-8 text-white/30 group-hover:text-purple-400 transition-colors" />
            </div>
            <p className="text-white/50 text-sm group-hover:text-white/80 transition-colors">
              Start by entering your company details
            </p>
          </button>
        )}

        <AnimatePresence initial={false}>
          {messages.map((message) => {
            const agent = getAgentInfo(message.agentId);

            return (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.3 }}
                className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                {/* Avatar */}
                {message.role === 'agent' && agent && (
                  <div
                    className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm"
                    style={{
                      background: `linear-gradient(135deg, rgba(${agent.color}, 0.3), rgba(${agent.color}, 0.1))`,
                      border: `1px solid rgba(${agent.color}, 0.5)`,
                    }}
                  >
                    {agent.avatar}
                  </div>
                )}

                {/* Message bubble */}
                <div
                  className={`
                    max-w-[80%] px-4 py-3 rounded-2xl
                    ${message.role === 'user'
                      ? 'bg-gradient-to-br from-blue-500 to-purple-600 rounded-br-md'
                      : 'glass-card rounded-bl-md'
                    }
                  `}
                >
                  {message.role === 'agent' && agent && (
                    <p
                      className="text-xs font-medium mb-1"
                      style={{ color: `rgba(${agent.color}, 1)` }}
                    >
                      {agent.name}
                    </p>
                  )}
                  <p className="text-sm text-white/90 leading-relaxed">
                    {message.content}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Typing indicator */}
        <AnimatePresence>
          {activeThinkingAgents.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex gap-3"
            >
              <div className="flex -space-x-2">
                {activeThinkingAgents.slice(0, 3).map(activity => {
                  const agent = getAgentInfo(activity.agentId);
                  if (!agent) return null;
                  return (
                    <div
                      key={activity.agentId}
                      className="w-8 h-8 rounded-full flex items-center justify-center text-sm border-2 border-surface"
                      style={{
                        background: `linear-gradient(135deg, rgba(${agent.color}, 0.3), rgba(${agent.color}, 0.1))`,
                      }}
                    >
                      {agent.avatar}
                    </div>
                  );
                })}
              </div>
              <div className="glass-card px-4 py-3 rounded-2xl rounded-bl-md">
                <div className="thinking-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex-shrink-0 p-4 border-t border-white/10">
        <div className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isAnalyzing ? 'Analysis in progress...' : 'Ask a follow-up question...'}
            disabled={isAnalyzing}
            className="input-glass pr-12"
          />
          <button
            type="submit"
            disabled={!input.trim() || isAnalyzing}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
      </form>
    </div>
  );
}
