import { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, ArrowRight, Building2, Target, Users, Zap } from 'lucide-react';
import { CompanyInfo, AGENTS } from '../types';

interface OnboardingModalProps {
  onSubmit: (company: CompanyInfo) => void;
}

const INDUSTRIES = [
  'Fintech',
  'SaaS',
  'E-commerce',
  'Healthtech',
  'Edtech',
  'Proptech',
  'Logistics',
  'Professional Services',
  'Other',
];

export function OnboardingModal({ onSubmit }: OnboardingModalProps) {
  const [step, setStep] = useState(0);
  const [formData, setFormData] = useState<Partial<CompanyInfo>>({
    name: '',
    description: '',
    industry: '',
    goals: [],
    competitors: [],
  });

  const handleSubmit = () => {
    onSubmit(formData as CompanyInfo);
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
                    <Target className="w-4 h-4 inline mr-2" />
                    Industry
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {INDUSTRIES.map((industry) => (
                      <button
                        key={industry}
                        onClick={() => setFormData({ ...formData, industry })}
                        className={`
                          px-4 py-2 rounded-xl text-sm font-medium transition-all
                          ${formData.industry === industry
                            ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                            : 'bg-white/5 text-white/70 hover:bg-white/10 border border-white/10'
                          }
                        `}
                      >
                        {industry}
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
                    className="input-glass min-h-[120px] resize-none"
                    autoFocus
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
                  disabled={!canProceed()}
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
