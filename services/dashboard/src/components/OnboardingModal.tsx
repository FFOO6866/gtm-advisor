/**
 * Onboarding Modal for GTM Advisor
 *
 * Collects company information for analysis.
 * Backend-aware with proper industry values.
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, ArrowRight, Building2, Target, Users, Zap, AlertTriangle, Globe } from 'lucide-react';
import { CompanyInfo, AGENTS, INDUSTRIES } from '../types';

interface OnboardingModalProps {
  onSubmit: (company: CompanyInfo) => void;
  isBackendAvailable?: boolean;
}

export function OnboardingModal({ onSubmit, isBackendAvailable = true }: OnboardingModalProps) {
  const [step, setStep] = useState(0);
  const [formData, setFormData] = useState<Partial<CompanyInfo>>({
    name: '',
    website: '',
    description: '',
    industry: '',
    goals: [],
    challenges: [],
    competitors: [],
    targetMarkets: ['Singapore'],
    valueProposition: '',
  });

  const handleSubmit = () => {
    onSubmit({
      name: formData.name || '',
      website: formData.website || undefined,
      description: formData.description || '',
      industry: formData.industry || 'other',
      goals: formData.goals || [],
      challenges: formData.challenges || [],
      competitors: formData.competitors || [],
      targetMarkets: formData.targetMarkets || ['Singapore'],
      valueProposition: formData.valueProposition,
    });
  };

  const canProceed = () => {
    if (step === 0) return formData.name && formData.industry;
    if (step === 1) return formData.description;
    return true;
  };

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-surface/80 backdrop-blur-xl" />

      {/* Modal */}
      <motion.div
        className="relative w-full max-w-2xl"
        initial={{ scale: 0.95, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: 20 }}
      >
        <div className="glass-card p-8 rounded-3xl">
          {/* Backend Warning */}
          {!isBackendAvailable && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 p-4 rounded-xl bg-amber-500/20 border border-amber-500/30"
            >
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
                <div>
                  <p className="text-amber-200 font-medium">Backend Not Available</p>
                  <p className="text-amber-200/70 text-sm">
                    Start the gateway server: <code className="bg-black/30 px-2 py-0.5 rounded">uv run uvicorn services.gateway.src.main:app --reload --port 8000</code>
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Header */}
          <div className="text-center mb-8">
            <motion.div
              className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-purple-500 via-blue-500 to-cyan-500 flex items-center justify-center"
              animate={{
                boxShadow: [
                  '0 0 30px rgba(139, 92, 246, 0.3)',
                  '0 0 60px rgba(139, 92, 246, 0.5)',
                  '0 0 30px rgba(139, 92, 246, 0.3)',
                ],
              }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Sparkles className="w-10 h-10 text-white" />
            </motion.div>
            <h1 className="text-2xl font-bold text-white mb-2">
              Welcome to GTM Advisor
            </h1>
            <p className="text-white/60">
              Let our AI team analyze your go-to-market strategy
            </p>
          </div>

          {/* Agent Preview */}
          <div className="flex justify-center gap-2 mb-8">
            {AGENTS.map((agent, i) => (
              <motion.div
                key={agent.id}
                className="w-12 h-12 rounded-full flex items-center justify-center text-lg"
                style={{
                  background: `linear-gradient(135deg, rgba(${agent.color}, 0.2), rgba(${agent.color}, 0.05))`,
                  border: `1px solid rgba(${agent.color}, 0.3)`,
                }}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: i * 0.1 }}
                whileHover={{ scale: 1.1, y: -5 }}
                title={agent.name}
              >
                {agent.avatar}
              </motion.div>
            ))}
          </div>

          {/* Form Steps */}
          <div className="space-y-6">
            {step === 0 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <Building2 className="w-4 h-4 inline mr-2" />
                    Company Name
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., TechStartup SG"
                    className="input-glass"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <Globe className="w-4 h-4 inline mr-2" />
                    Company Website
                  </label>
                  <input
                    type="url"
                    value={formData.website}
                    onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                    placeholder="e.g., https://yourcompany.com"
                    className="input-glass"
                  />
                  <p className="text-xs text-white/40 mt-1">
                    We'll analyze your website to auto-enrich company information
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <Target className="w-4 h-4 inline mr-2" />
                    Industry
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {INDUSTRIES.map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => setFormData({ ...formData, industry: value })}
                        className={`
                          px-4 py-2 rounded-xl text-sm font-medium transition-all
                          ${formData.industry === value
                            ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                            : 'bg-white/5 text-white/70 hover:bg-white/10 border border-white/10'
                          }
                        `}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {step === 1 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <Zap className="w-4 h-4 inline mr-2" />
                    What does your company do?
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Describe your product/service, target customers, and unique value proposition..."
                    className="input-glass min-h-[100px] resize-none"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <Target className="w-4 h-4 inline mr-2" />
                    Value Proposition (optional)
                  </label>
                  <input
                    type="text"
                    value={formData.valueProposition}
                    onChange={(e) => setFormData({ ...formData, valueProposition: e.target.value })}
                    placeholder="e.g., We help SMEs reduce costs by 40% through automation"
                    className="input-glass"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <Users className="w-4 h-4 inline mr-2" />
                    Known Competitors (optional)
                  </label>
                  <input
                    type="text"
                    value={formData.competitors?.join(', ')}
                    onChange={(e) => setFormData({
                      ...formData,
                      competitors: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                    })}
                    placeholder="e.g., Competitor A, Competitor B"
                    className="input-glass"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <Globe className="w-4 h-4 inline mr-2" />
                    Target Markets
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {['Singapore', 'Malaysia', 'Indonesia', 'Thailand', 'Vietnam', 'Philippines'].map((market) => (
                      <button
                        key={market}
                        onClick={() => {
                          const current = formData.targetMarkets || [];
                          const updated = current.includes(market)
                            ? current.filter(m => m !== market)
                            : [...current, market];
                          setFormData({ ...formData, targetMarkets: updated });
                        }}
                        className={`
                          px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                          ${formData.targetMarkets?.includes(market)
                            ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                            : 'bg-white/5 text-white/70 hover:bg-white/10 border border-white/10'
                          }
                        `}
                      >
                        {market}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </div>

          {/* Progress & Actions */}
          <div className="mt-8 flex items-center justify-between">
            {/* Progress dots */}
            <div className="flex gap-2">
              {[0, 1].map((i) => (
                <div
                  key={i}
                  className={`w-2 h-2 rounded-full transition-all ${
                    i === step
                      ? 'w-8 bg-gradient-to-r from-purple-500 to-blue-500'
                      : i < step
                      ? 'bg-purple-500'
                      : 'bg-white/20'
                  }`}
                />
              ))}
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              {step > 0 && (
                <button
                  onClick={() => setStep(step - 1)}
                  className="btn-ghost"
                >
                  Back
                </button>
              )}

              {step < 1 ? (
                <button
                  onClick={() => setStep(step + 1)}
                  disabled={!canProceed()}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                  <span>Continue</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={handleSubmit}
                  disabled={!canProceed() || !isBackendAvailable}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Start Analysis</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Decorative elements */}
        <div className="absolute -top-20 -right-20 w-40 h-40 rounded-full bg-purple-500/10 blur-3xl" />
        <div className="absolute -bottom-20 -left-20 w-40 h-40 rounded-full bg-blue-500/10 blur-3xl" />
      </motion.div>
    </motion.div>
  );
}
