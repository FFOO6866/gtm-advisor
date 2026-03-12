import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Zap } from 'lucide-react';
import { AuroraBackground } from '../components/AuroraBackground';

export function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, full_name: fullName, company_name: companyName, password }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.detail || 'Registration failed. Please try again.');
        return;
      }
      navigate('/login', { state: { message: 'Account created! Please sign in.' } });
    } catch {
      setError('Registration failed. Please try again.');
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

          <h1 className="text-2xl font-semibold text-white text-center mb-2">Create your account</h1>
          <p className="text-white/50 text-sm text-center mb-8">Start your GTM journey today</p>

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
              <label className="block text-sm text-white/70 mb-1.5" htmlFor="fullName">
                Full Name
              </label>
              <input
                id="fullName"
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Jane Doe"
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/60 focus:bg-white/8 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm text-white/70 mb-1.5" htmlFor="companyName">
                Company Name
              </label>
              <input
                id="companyName"
                type="text"
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Pte. Ltd."
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
              {isLoading ? 'Creating account...' : 'Create Account'}
            </motion.button>
          </form>

          <p className="text-center text-sm text-white/50 mt-6">
            Already have an account?{' '}
            <button
              onClick={() => navigate('/login')}
              className="text-purple-400 hover:text-purple-300 transition-colors font-medium"
            >
              Sign in
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
