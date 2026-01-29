import { motion } from 'framer-motion';
import { clsx } from 'clsx';

export interface TabItem {
  id: string;
  label: string;
  badge?: number;
  icon?: string;
}

interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

export function Tabs({ tabs, activeTab, onChange }: TabsProps) {
  return (
    <div className="flex gap-1 p-1 bg-white/5 rounded-lg border border-white/10">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={clsx(
              'relative px-4 py-2 rounded-md text-sm font-medium transition-colors',
              'flex items-center gap-2',
              isActive ? 'text-white' : 'text-white/60 hover:text-white/80'
            )}
          >
            {isActive && (
              <motion.div
                layoutId="activeTab"
                className="absolute inset-0 bg-white/10 rounded-md"
                transition={{ type: 'spring', duration: 0.3 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-2">
              {tab.icon && <span>{tab.icon}</span>}
              {tab.label}
              {tab.badge !== undefined && tab.badge > 0 && (
                <span className="px-1.5 py-0.5 text-xs bg-purple-500 rounded-full">
                  {tab.badge}
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
