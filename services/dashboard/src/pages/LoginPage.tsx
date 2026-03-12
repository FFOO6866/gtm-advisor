import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Zap } from 'lucide-react';
import { AuroraBackground } from '../components/AuroraBackground';
import { storeAuthTokens } from '../api/client';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        setError('Invalid email or password');
        return;
      }
      const token = await response.json();
      storeAuthTokens(token.access_token, token.refresh_token);
      // Clear all teaser state so paid app starts clean.
      sessionStorage.removeItem('gtm_has_onboarded');
      sessionStorage.removeItem('gtm_company_info');
      sessionStorage.removeItem('gtm_analysis_id');
      sessionStorage.removeItem('gtm_navigated_back');
      sessionStorage.removeItem('gtm_current_company');
      sessionStorage.removeItem('gtm_agent_back');

      // Auto-resolve user's primary company so AppShell can hydrate immediately.
      // Only set if not already present (teaser-to-paid flow already sets it).
      if (!localStorage.getItem('gtm_company_id')) {
        try {
          const companiesRes = await fetch(`${apiBase}/api/v1/companies?page_size=20`, {
            headers: { Authorization: `Bearer ${token.access_token}` },
          });
          if (companiesRes.ok) {
            const companiesData = await companiesRes.json();
            // Prefer the first owned company (owner_id != null) over anonymous ones.
            const ownedCompany = (companiesData.companies ?? []).find(
              (c: { id: string; owner_id: string | null }) => c.owner_id !== null
            );
            const firstCompany = ownedCompany ?? companiesData.companies?.[0];
            if (firstCompany?.id) {
              localStorage.setItem('gtm_company_id', firstCompany.id);
            }
          }
        } catch {
          // Non-fatal — AppShell will show "run first analysis" state
        }
      }

      const params = new URLSearchParams(window.location.search);
      const next = params.get('next');
      navigate((next && next.startsWith('/') && !next.startsWith('//')) ? next : '/today');
    } catch {
      setError('Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <AuroraBackground />
      <motion.div
        className="relative z-10 w-full max-w-md px-6"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="glass-card rounded-2xl p-8 border border-white/10 bg-surface/60 backdrop-blur-xl">
          {/* Logo */}
          <div className="flex items-center justify-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              GTM Advisor
            </span>
          </div>

          <h1 className="text-2xl font-semibold text-white text-center mb-2">Sign in to your account</h1>
          <p className="text-white/50 text-sm text-center mb-8">AI-powered go-to-market advisory</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-white/70 mb-1.5" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/60 focus:bg-white/8 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm text-white/70 mb-1.5" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/60 focus:bg-white/8 transition-colors"
              />
            </div>

            {error && (
              <motion.p
                className="text-red-400 text-sm text-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                {error}
              </motion.p>
            )}

            <motion.button
              type="submit"
              disabled={isLoading}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-500 to-blue-600 text-white font-semibold hover:from-purple-600 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {isLoading ? 'Signing in...' : 'Sign In'}
            </motion.button>
          </form>

          <p className="text-center text-sm text-white/50 mt-6">
            Don&apos;t have an account?{' '}
            <button
              onClick={() => navigate('/register')}
              className="text-purple-400 hover:text-purple-300 transition-colors font-medium"
            >
              Register
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
