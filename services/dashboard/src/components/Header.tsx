import { motion } from 'framer-motion';
import { Zap, Settings, HelpCircle } from 'lucide-react';

interface HeaderProps {
  companyName?: string;
}

export function Header({ companyName }: HeaderProps) {
  return (
    <header className="flex-shrink-0 h-16 border-b border-white/10 bg-surface/30 backdrop-blur-xl">
      <div className="h-full px-6 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <motion.div
            className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 via-blue-500 to-cyan-500 flex items-center justify-center"
            whileHover={{ scale: 1.05, rotate: 5 }}
            whileTap={{ scale: 0.95 }}
          >
            <Zap className="w-5 h-5 text-white" />
          </motion.div>
          <div>
            <h1 className="font-semibold text-white flex items-center gap-2">
              GTM Advisor
              <span className="px-2 py-0.5 text-[10px] rounded-full bg-purple-500/20 text-purple-300 font-medium">
                BETA
              </span>
            </h1>
            <p className="text-xs text-white/40">
              {companyName ? `Analyzing: ${companyName}` : 'AI-Powered Go-To-Market'}
            </p>
          </div>
        </div>

        {/* Center: Status Pills */}
        <div className="hidden md:flex items-center gap-2">
          <StatusPill label="6 Agents" status="ready" />
          <StatusPill label="Perplexity" status="connected" />
          <StatusPill label="NewsAPI" status="connected" />
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          <button className="btn-ghost p-2">
            <HelpCircle className="w-5 h-5" />
          </button>
          <button className="btn-ghost p-2">
            <Settings className="w-5 h-5" />
          </button>
          <button className="btn-primary">
            <span>Upgrade</span>
          </button>
        </div>
      </div>
    </header>
  );
}

function StatusPill({ label, status }: { label: string; status: 'ready' | 'connected' | 'error' }) {
  const statusColors = {
    ready: 'bg-green-500/20 text-green-400 border-green-500/30',
    connected: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  return (
    <div className={`px-3 py-1 rounded-full text-xs font-medium border ${statusColors[status]}`}>
      <span className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${
          status === 'ready' ? 'bg-green-400' :
          status === 'connected' ? 'bg-blue-400' :
          'bg-red-400'
        }`} />
        {label}
      </span>
    </div>
  );
}
