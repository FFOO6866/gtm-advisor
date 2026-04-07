/**
 * SettingsPage — Application settings and preferences.
 *
 * v1 launch package: Profile (read-only) + Display Preferences.
 * Integrations status and Danger Zone are gated behind FEATURES flags
 * and only appear in internal builds.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Settings,
  CheckCircle,
  AlertCircle,
  Globe,
  Trash2,
  Save,
  ExternalLink,
} from 'lucide-react';
import { useCompanyId } from '../context/CompanyContext';
import { checkHealth } from '../api/client';
import { FEATURES } from '../config/features';

// ============================================================================
// Types
// ============================================================================

interface DisplayPreferences {
  compactMode: boolean;
  timezone: string;
}

const TIMEZONES = [
  'Asia/Singapore',
  'UTC',
  'America/New_York',
  'Europe/London',
] as const;

const LS_COMPACT = 'gtm_compact_mode';
const LS_TIMEZONE = 'gtm_timezone';

// ============================================================================
// Sub-components
// ============================================================================

function StatusDot({ color }: { color: 'green' | 'red' | 'gray' }) {
  const colorMap = {
    green: 'bg-green-400',
    red: 'bg-red-400',
    gray: 'bg-white/30',
  };
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${colorMap[color]}`}
    />
  );
}

function Toggle({
  enabled,
  onToggle,
}: {
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`relative inline-flex items-center w-10 h-5 rounded-full transition-colors focus:outline-none ${
        enabled ? 'bg-purple-500/40' : 'bg-white/10'
      }`}
      aria-pressed={enabled}
    >
      <span
        className={`inline-block w-3.5 h-3.5 rounded-full transition-transform ${
          enabled
            ? 'translate-x-5 bg-purple-300'
            : 'translate-x-1 bg-white/40'
        }`}
      />
    </button>
  );
}

// ============================================================================
// Main component
// ============================================================================

export function SettingsPage() {
  const companyId = useCompanyId();

  // Backend health
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null);

  // Display preferences
  const [prefs, setPrefs] = useState<DisplayPreferences>({
    compactMode: false,
    timezone: 'Asia/Singapore',
  });
  const [saved, setSaved] = useState(false);

  // Load preferences from localStorage on mount
  useEffect(() => {
    const compact = localStorage.getItem(LS_COMPACT);
    const tz = localStorage.getItem(LS_TIMEZONE);
    setPrefs({
      compactMode: compact === 'true',
      timezone: tz && TIMEZONES.includes(tz as typeof TIMEZONES[number]) ? tz : 'Asia/Singapore',
    });
  }, []);

  // Check backend health on mount
  useEffect(() => {
    checkHealth()
      .then((res) => {
        setBackendHealthy(res.status === 'healthy');
      })
      .catch(() => {
        setBackendHealthy(false);
      });
  }, []);

  function handleSavePrefs() {
    localStorage.setItem(LS_COMPACT, String(prefs.compactMode));
    localStorage.setItem(LS_TIMEZONE, prefs.timezone);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function handleClearLocalData() {
    // Clear all gtm_* keys from sessionStorage
    const ssKeys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (key && key.startsWith('gtm_')) {
        ssKeys.push(key);
      }
    }
    ssKeys.forEach((k) => sessionStorage.removeItem(k));

    // Clear all gtm_* keys from localStorage
    const lsKeys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('gtm_')) {
        lsKeys.push(key);
      }
    }
    lsKeys.forEach((k) => localStorage.removeItem(k));

    window.location.reload();
  }

  // Resolve company name from session storage directly (CompanyContext stores
  // the full company object under 'gtm_current_company')
  const storedCompany = (() => {
    try {
      const raw = sessionStorage.getItem('gtm_current_company');
      if (raw) {
        const parsed = JSON.parse(raw) as { name?: string; id?: string };
        return parsed;
      }
    } catch {
      // ignore
    }
    return null;
  })();

  const companyName = storedCompany?.name ?? null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-2">
          <Settings className="w-5 h-5 text-white/50" />
          <div>
            <h1 className="text-lg font-semibold text-white">Settings</h1>
            <p className="text-xs text-white/40">
              Manage preferences and integration status
            </p>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="max-w-xl"
        >
          {/* ---------------------------------------------------------------- */}
          {/* Section 1: Company Profile                                        */}
          {/* ---------------------------------------------------------------- */}
          <div className="glass-card p-5 rounded-xl mb-4">
            <h2 className="text-sm font-semibold text-white mb-3">
              Company Profile
            </h2>

            {companyId || companyName ? (
              <div className="space-y-2">
                {companyName && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-white/40">Company name</span>
                    <span className="text-sm text-white font-medium">
                      {companyName}
                    </span>
                  </div>
                )}
                {companyId && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-white/40">Company ID</span>
                    <span className="text-xs text-white/60 font-mono">
                      {companyId}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-white/40">No company loaded.</p>
            )}

            <p className="mt-3 text-xs text-white/30 border-t border-white/10 pt-3">
              To change company details, start a new analysis from the home
              screen.
            </p>
          </div>

          {/* ---------------------------------------------------------------- */}
          {/* Section 2: Integrations Status (internal only)                    */}
          {/* ---------------------------------------------------------------- */}
          {FEATURES.settingsApiKeys && (
          <div className="glass-card p-5 rounded-xl mb-4">
            <h2 className="text-sm font-semibold text-white mb-3">
              Integrations
            </h2>

            {/* Backend connection */}
            <div className="flex items-center justify-between py-2 border-b border-white/10">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-white/30" />
                <span className="text-sm text-white">Backend API</span>
              </div>
              <div className="flex items-center gap-2">
                {backendHealthy === null && (
                  <span className="text-xs text-white/30">Checking...</span>
                )}
                {backendHealthy === true && (
                  <>
                    <StatusDot color="green" />
                    <span className="text-xs text-green-400">Connected</span>
                  </>
                )}
                {backendHealthy === false && (
                  <>
                    <StatusDot color="red" />
                    <span className="text-xs text-red-400">Unreachable</span>
                  </>
                )}
              </div>
            </div>

            {/* API key integrations */}
            {[
              { label: 'OpenAI', key: 'OPENAI_API_KEY' },
              { label: 'Perplexity', key: 'PERPLEXITY_API_KEY' },
              { label: 'NewsAPI', key: 'NEWSAPI_API_KEY' },
              { label: 'EODHD', key: 'EODHD_API_KEY' },
            ].map((integration) => (
              <div
                key={integration.key}
                className="flex items-center justify-between py-2.5 border-b border-white/5 last:border-0"
              >
                <div className="flex flex-col">
                  <span className="text-sm text-white">{integration.label}</span>
                  <span className="text-[10px] text-white/30 font-mono">
                    {integration.key}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <StatusDot color="gray" />
                  <span className="text-xs text-white/40">
                    Configured server-side
                  </span>
                </div>
              </div>
            ))}

            <p className="mt-3 text-xs text-white/30 flex items-start gap-1.5">
              <ExternalLink className="w-3 h-3 flex-shrink-0 mt-0.5" />
              API keys are configured server-side via environment variables.
            </p>
          </div>
          )}

          {/* ---------------------------------------------------------------- */}
          {/* Section 3: Display Preferences                                    */}
          {/* ---------------------------------------------------------------- */}
          <div className="glass-card p-5 rounded-xl mb-4">
            <h2 className="text-sm font-semibold text-white mb-4">
              Display Preferences
            </h2>

            <div className="space-y-4">
              {/* Compact mode */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-white">Compact mode</p>
                  <p className="text-xs text-white/30 mt-0.5">
                    Reduce spacing for a denser layout
                  </p>
                </div>
                <Toggle
                  enabled={prefs.compactMode}
                  onToggle={() =>
                    setPrefs((p) => ({ ...p, compactMode: !p.compactMode }))
                  }
                />
              </div>

              {/* Timezone */}
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm text-white">Timezone</p>
                  <p className="text-xs text-white/30 mt-0.5">
                    Used for timestamp display
                  </p>
                </div>
                <select
                  value={prefs.timezone}
                  onChange={(e) =>
                    setPrefs((p) => ({ ...p, timezone: e.target.value }))
                  }
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50 appearance-none cursor-pointer"
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz} value={tz} className="bg-gray-900">
                      {tz}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Save */}
            <div className="flex items-center gap-3 mt-5 pt-4 border-t border-white/10">
              <button
                onClick={handleSavePrefs}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-sm font-medium hover:bg-purple-500/30 transition-colors"
              >
                <Save className="w-4 h-4" />
                Save preferences
              </button>
              {saved && (
                <motion.div
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-1.5 text-green-400 text-sm"
                >
                  <CheckCircle className="w-4 h-4" />
                  Saved
                </motion.div>
              )}
            </div>
          </div>

          {/* ---------------------------------------------------------------- */}
          {/* Section 4: Danger Zone (internal only)                            */}
          {/* ---------------------------------------------------------------- */}
          {FEATURES.settingsDangerZone && (
          <div className="glass-card p-5 rounded-xl mb-4 border border-red-500/30">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="w-4 h-4 text-red-400" />
              <h2 className="text-sm font-semibold text-red-400">
                Danger Zone
              </h2>
            </div>
            <p className="text-xs text-white/40 mb-4">
              Clearing local data will remove your current company session and
              all saved preferences. You will be returned to the home screen and
              will need to start a new analysis.
            </p>
            <button
              onClick={handleClearLocalData}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400 text-sm font-medium hover:bg-red-500/20 transition-colors border border-red-500/20"
            >
              <Trash2 className="w-4 h-4" />
              Clear local data and restart
            </button>
          </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
