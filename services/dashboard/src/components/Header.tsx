import { motion } from 'framer-motion';
import { Zap, Settings, HelpCircle, LogOut } from 'lucide-react';

interface HeaderProps {
  companyName?: string;
  onNewAnalysis?: () => void;
  teaser?: boolean;
}

export function Header({ companyName, teaser = false }: HeaderProps) {
  const isAuthenticated = !teaser && !!localStorage.getItem('gtm_access_token');

  return (
    <header className="flex-shrink-0 h-16 border-b border-white/10 bg-surface/30 backdrop-blur-xl">
      <div className="h-full px-6 flex items-center justify-between">
        {/* Logo — only shown on unauthenticated (teaser) pages */}
        {!isAuthenticated && (
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
              <p className="hidden sm:block text-xs text-white/40">AI-Powered Go-To-Market</p>
            </div>
          </div>
        )}
        {isAuthenticated && <div />}

        {/* Center — teaser only: show company being analysed */}
        {!isAuthenticated && companyName && (
          <div className="hidden md:flex items-center">
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2 px-4 py-2 rounded-2xl bg-white/5 border border-white/10"
            >
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="text-sm font-medium text-white/70 truncate max-w-[200px]">{companyName}</span>
            </motion.div>
          </div>
        )}

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          <button className="hidden sm:inline-flex btn-ghost p-2" title="Help">
            <HelpCircle className="w-5 h-5" />
          </button>
          <button className="hidden sm:inline-flex btn-ghost p-2" title="Settings">
            <Settings className="w-5 h-5" />
          </button>
          {isAuthenticated ? (
            <button
              onClick={() => {
                localStorage.removeItem('gtm_access_token');
                localStorage.removeItem('gtm_refresh_token');
                localStorage.removeItem('gtm_company_id');
                sessionStorage.removeItem('gtm_company_info');
                sessionStorage.removeItem('gtm_analysis_id');
                sessionStorage.removeItem('gtm_current_company');
                sessionStorage.removeItem('gtm_agent_back');
                window.location.href = '/';
              }}
              className="btn-ghost flex items-center gap-1.5 text-sm px-3 py-1.5 text-white/50 hover:text-white/80"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          ) : (
            <button
              onClick={() => { window.location.href = '/register'; }}
              className="btn-primary"
            >
              <span>Upgrade</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
