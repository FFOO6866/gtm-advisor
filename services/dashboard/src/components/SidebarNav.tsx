/**
 * SidebarNav — persistent product navigation.
 *
 * Unlocks after a company workspace exists (companyId is set).
 * Before that, the app shows the onboarding/analysis flow full-width.
 *
 * Primary nav: Today, Campaigns, Prospects, Content, Insights, Results
 * Secondary nav: Approvals (badge), Sequences, Workforce
 * Bottom: Why Us, Settings
 */

import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Sun, Megaphone, Users, FileText, Lightbulb, TrendingUp,
  Bell, Mail, Bot, Search, Settings, ChevronRight, HelpCircle, Zap
} from 'lucide-react';
import { approvalsApi } from '../api/approvals';

interface SidebarNavProps {
  companyId: string;
  companyName?: string;
}

const PRIMARY_NAV = [
  { path: '/today', icon: Sun, label: 'Today', color: 'text-amber-400' },
  { path: '/campaigns', icon: Megaphone, label: 'Campaigns', color: 'text-purple-400' },
  { path: '/prospects', icon: Users, label: 'Prospects', color: 'text-blue-400' },
  { path: '/content', icon: FileText, label: 'Content', color: 'text-cyan-400' },
  { path: '/insights', icon: Lightbulb, label: 'Insights', color: 'text-yellow-400' },
  { path: '/results', icon: TrendingUp, label: 'Results', color: 'text-emerald-400' },
];

const SECONDARY_NAV = [
  { path: '/approvals', icon: Bell, label: 'Approvals', color: 'text-red-400', badge: true },
  { path: '/sequences', icon: Mail, label: 'Sequences', color: 'text-cyan-400' },
  { path: '/workforce', icon: Bot, label: 'Workforce', color: 'text-pink-400' },
  { path: '/', icon: Search, label: 'Analysis', color: 'text-white/60' },
];

export function SidebarNav({ companyId, companyName }: SidebarNavProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(0);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    approvalsApi.count(companyId)
      .then(r => setPendingCount(r.pending))
      .catch(() => {});
    // Refresh every 60s
    const interval = setInterval(() => {
      approvalsApi.count(companyId)
        .then(r => setPendingCount(r.pending))
        .catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [companyId]);

  return (
    <>
    <motion.aside
      className={`hidden md:flex flex-shrink-0 flex-col h-full bg-surface/60 backdrop-blur-xl border-r border-white/10 transition-all duration-300 ${collapsed ? 'w-16' : 'w-56'}`}
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Workspace header */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-white/10">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center flex-shrink-0">
          <Zap className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-xs font-semibold text-white truncate">{companyName || 'Workspace'}</p>
            <p className="text-[10px] text-white/40">GTM Dashboard</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="ml-auto text-white/30 hover:text-white/60 transition-colors"
        >
          <ChevronRight className={`w-4 h-4 transition-transform ${collapsed ? '' : 'rotate-180'}`} />
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        {/* Primary — outcome-oriented */}
        <div className="space-y-1">
          {PRIMARY_NAV.map(({ path, icon: Icon, label, color }) => {
            const isActive = location.pathname === path;
            return (
              <motion.button
                key={path}
                onClick={() => navigate(path)}
                whileHover={{ x: 2 }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white/80 hover:bg-white/5'
                }`}
              >
                <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? color : ''}`} />
                {!collapsed && <span>{label}</span>}
              </motion.button>
            );
          })}
        </div>

        {/* Divider */}
        {!collapsed && (
          <p className="px-3 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-wider text-white/20">
            Operations
          </p>
        )}
        {collapsed && <div className="my-3 border-t border-white/10" />}

        {/* Secondary — operational */}
        <div className="space-y-1">
          {SECONDARY_NAV.map(({ path, icon: Icon, label, color, badge }) => {
            const isActive = location.pathname === path || (path !== '/' && location.pathname.startsWith(path));
            return (
              <motion.button
                key={path}
                onClick={() => navigate(path)}
                whileHover={{ x: 2 }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors relative ${
                  isActive ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white/80 hover:bg-white/5'
                }`}
              >
                <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? color : ''}`} />
                {!collapsed && <span>{label}</span>}
                {badge && pendingCount > 0 && (
                  <span className={`${collapsed ? 'absolute top-1 right-1' : 'ml-auto'} w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center`}>
                    {pendingCount > 9 ? '9+' : pendingCount}
                  </span>
                )}
              </motion.button>
            );
          })}
        </div>
      </nav>

      {/* Bottom: Why Us + Settings */}
      <div className="px-2 py-3 border-t border-white/10 space-y-1">
        <motion.button
          onClick={() => navigate('/why-us')}
          whileHover={{ x: 2 }}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${location.pathname === '/why-us' ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white/80 hover:bg-white/5'}`}
        >
          <HelpCircle className="w-4 h-4 flex-shrink-0" />
          {!collapsed && <span>Why Us?</span>}
        </motion.button>
        <motion.button
          onClick={() => navigate('/settings')}
          whileHover={{ x: 2 }}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white/50 hover:text-white/80 hover:bg-white/5 transition-colors"
        >
          <Settings className="w-4 h-4 flex-shrink-0" />
          {!collapsed && <span>Settings</span>}
        </motion.button>
      </div>
    </motion.aside>

    {/* Mobile bottom nav */}
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-surface/90 backdrop-blur-xl border-t border-white/10 flex items-center justify-around px-2 py-1 safe-area-bottom">
      {PRIMARY_NAV.map(({ path, icon: Icon, label, color }) => {
        const isActive = location.pathname === path;
        return (
          <button
            key={path}
            onClick={() => navigate(path)}
            className={`flex flex-col items-center gap-0.5 px-3 py-2 rounded-xl transition-colors min-w-0 ${
              isActive ? 'text-white' : 'text-white/40'
            }`}
          >
            <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? color : ''}`} />
            <span className="text-[9px] font-medium truncate">{label}</span>
          </button>
        );
      })}
      {/* Approvals with badge */}
      <button
        onClick={() => navigate('/approvals')}
        className={`flex flex-col items-center gap-0.5 px-3 py-2 rounded-xl transition-colors relative ${location.pathname === '/approvals' ? 'text-white' : 'text-white/40'}`}
      >
        <Bell className="w-5 h-5 flex-shrink-0" />
        <span className="text-[9px] font-medium">Approvals</span>
        {pendingCount > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[8px] font-bold flex items-center justify-center">
            {pendingCount > 9 ? '9+' : pendingCount}
          </span>
        )}
      </button>
    </nav>
    </>
  );
}
