/**
 * Onboarding Modal — collects company context before analysis.
 *
 * Step 0: Company name + industry + EITHER website URL or document upload.
 *         Document upload calls POST /api/v1/documents/parse which uses GPT
 *         to extract structured fields — auto-fills step 1.
 * Step 1: Review / edit description, goals, challenges, competitors, markets.
 */

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles, ArrowRight, Building2, Target, Users, Zap,
  AlertTriangle, Globe, Upload, FileText, X, CheckCircle,
} from 'lucide-react';
import { CompanyInfo, AGENTS, INDUSTRIES } from '../types';
import { uploadFile } from '../api/client';

interface ParsedProfile {
  company_name: string | null;
  description: string | null;
  industry: string | null;
  value_proposition: string | null;
  goals: string[];
  challenges: string[];
  competitors: string[];
  target_markets: string[];
  extracted_text: string | null;
  warning: string | null;
}

interface OnboardingModalProps {
  onSubmit: (company: CompanyInfo) => void;
  isBackendAvailable?: boolean;
}

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB

export function OnboardingModal({ onSubmit, isBackendAvailable = true }: OnboardingModalProps) {
  const [step, setStep] = useState(0);
  const [inputMode, setInputMode] = useState<'website' | 'document'>('website');
  const [formData, setFormData] = useState<Partial<CompanyInfo>>({
    name: '', website: '', description: '', industry: '',
    goals: [], challenges: [], competitors: [],
    targetMarkets: ['Singapore'], valueProposition: '',
  });

  // Document upload state — supports multiple files
  interface UploadedDoc { name: string; text: string; chars: number; }
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadPhase, setUploadPhase] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [extractWarning, setExtractWarning] = useState<string | null>(null);
  const [extractedFields, setExtractedFields] = useState<Set<string>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadPhaseTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const buildDocumentContext = () =>
    uploadedDocs.map(d => `=== ${d.name} ===\n${d.text}`).join('\n\n') || undefined;

  const UPLOAD_PHASES = [
    'Uploading file…',
    'Extracting text…',
    'AI reading document…',
    'Structuring fields…',
  ];

  useEffect(() => {
    if (uploading) {
      setUploadPhase(0);
      uploadPhaseTimerRef.current = setInterval(() => {
        setUploadPhase(p => Math.min(p + 1, UPLOAD_PHASES.length - 1));
      }, 1400);
    } else {
      if (uploadPhaseTimerRef.current) clearInterval(uploadPhaseTimerRef.current);
    }
    return () => { if (uploadPhaseTimerRef.current) clearInterval(uploadPhaseTimerRef.current); };
  }, [uploading]);

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
      documentContext: inputMode === 'document' ? buildDocumentContext() : undefined,
    });
  };

  const canProceed = () => {
    if (step === 0) {
      if (!formData.name || !formData.industry) return false;
      if (uploading) return false;
      if (inputMode === 'document') return uploadedDocs.length > 0;
      if (inputMode === 'website') return !!formData.website?.trim();
      return true;
    }
    if (step === 1) return !!formData.description;
    return true;
  };

  // ── Document upload handler ────────────────────────────────────────────
  const handleFileSelect = async (file: File) => {
    setUploadError(null);
    setExtractWarning(null);

    const resetInput = () => { if (fileInputRef.current) fileInputRef.current.value = ''; };

    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadError('File too large. Maximum size is 10 MB.');
      resetInput();
      return;
    }
    const ext = file.name.toLowerCase();
    if (!ext.endsWith('.pdf') && !ext.endsWith('.docx') && !ext.endsWith('.txt')) {
      setUploadError('Unsupported file type. Please upload a PDF, DOCX, or TXT file.');
      resetInput();
      return;
    }
    if (uploadedDocs.some(d => d.name === file.name)) {
      setUploadError(`"${file.name}" is already added.`);
      resetInput();
      return;
    }

    setUploading(true);

    try {
      const parsed = await uploadFile<ParsedProfile>('/api/v1/documents/parse', file);

      // Auto-fill form fields only from the FIRST document upload
      if (uploadedDocs.length === 0) {
        const filled = new Set<string>();
        const updates: Partial<CompanyInfo> = {};
        if (parsed.company_name) { updates.name = parsed.company_name; filled.add('name'); }
        if (parsed.industry)     { updates.industry = parsed.industry;  filled.add('industry'); }
        if (parsed.description)  { updates.description = parsed.description; filled.add('description'); }
        if (parsed.value_proposition) { updates.valueProposition = parsed.value_proposition; filled.add('valueProposition'); }
        if (parsed.goals?.length)      { updates.goals = parsed.goals; filled.add('goals'); }
        if (parsed.challenges?.length) { updates.challenges = parsed.challenges; filled.add('challenges'); }
        if (parsed.competitors?.length){ updates.competitors = parsed.competitors; filled.add('competitors'); }
        if (parsed.target_markets?.length) { updates.targetMarkets = parsed.target_markets; filled.add('targetMarkets'); }
        setFormData(prev => ({ ...prev, ...updates }));
        setExtractedFields(filled);
      }

      if (parsed.extracted_text) {
        setUploadedDocs(prev => [...prev, { name: file.name, text: parsed.extracted_text!, chars: parsed.extracted_text!.length }]);
      }
      if (parsed.warning) setExtractWarning(parsed.warning);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Document parsing failed. Please fill in the details manually.';
      setUploadError(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const removeDoc = (index: number) => {
    setUploadedDocs(prev => prev.filter((_, i) => i !== index));
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="absolute inset-0 bg-surface/80 backdrop-blur-xl" />

      <motion.div
        className="relative w-full max-w-2xl"
        initial={{ scale: 0.95, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: 20 }}
      >
        <div className="glass-card p-8 rounded-3xl max-h-[90vh] overflow-y-auto">

          {/* Backend warning */}
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
                    Start the gateway server:{' '}
                    <code className="bg-black/30 px-2 py-0.5 rounded text-xs">
                      uv run uvicorn services.gateway.src.main:app --reload --port 8000
                    </code>
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Header */}
          <div className="text-center mb-6">
            <motion.div
              className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-purple-500 via-blue-500 to-cyan-500 flex items-center justify-center"
              animate={{
                boxShadow: [
                  '0 0 30px rgba(139,92,246,0.3)',
                  '0 0 60px rgba(139,92,246,0.5)',
                  '0 0 30px rgba(139,92,246,0.3)',
                ],
              }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Sparkles className="w-8 h-8 text-white" />
            </motion.div>
            <h1 className="text-xl font-bold text-white mb-1">Welcome to GTM Advisor</h1>
            <p className="text-white/50 text-sm">Tell us about your company to get started</p>
          </div>

          {/* Agent row */}
          <div className="flex justify-center gap-2 mb-6">
            {AGENTS.map((agent, i) => (
              <motion.div
                key={agent.id}
                className="w-10 h-10 rounded-full flex items-center justify-center text-base"
                style={{
                  background: `linear-gradient(135deg, rgba(${agent.color},0.2), rgba(${agent.color},0.05))`,
                  border: `1px solid rgba(${agent.color},0.3)`,
                }}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: i * 0.07 }}
                whileHover={{ scale: 1.1, y: -4 }}
                title={agent.name}
              >
                {agent.avatar}
              </motion.div>
            ))}
          </div>

          {/* Steps */}
          <div className="space-y-5">

            {/* ── Step 0 ── */}
            {step === 0 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-4"
              >
                {/* Company name */}
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Building2 className="w-4 h-4 inline mr-1.5" />
                    Company Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g. TechStartup SG"
                    className="input-glass"
                    autoFocus
                  />
                </div>

                {/* Industry */}
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Target className="w-4 h-4 inline mr-1.5" />
                    Industry *
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {INDUSTRIES.map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => setFormData({ ...formData, industry: value })}
                        className={`px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                          formData.industry === value
                            ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                            : 'bg-white/5 text-white/60 hover:bg-white/10 border border-white/10'
                        }`}
                      >
                        {extractedFields.has('industry') && formData.industry === value && (
                          <CheckCircle className="w-3 h-3 inline mr-1 text-green-400" />
                        )}
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Input mode toggle */}
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    Company Information Source
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => {
                        setInputMode('website');
                        setUploadedDocs([]);
                        setUploadError(null);
                        setExtractWarning(null);
                      }}
                      className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all ${
                        inputMode === 'website'
                          ? 'border-purple-500/50 bg-purple-500/10 text-white'
                          : 'border-white/10 bg-white/5 text-white/50 hover:border-white/20'
                      }`}
                    >
                      <Globe className="w-5 h-5" />
                      <span className="text-sm font-medium">Website URL</span>
                      <span className="text-xs text-white/40 text-center">We'll scrape & auto-enrich</span>
                    </button>
                    <button
                      onClick={() => setInputMode('document')}
                      className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all ${
                        inputMode === 'document'
                          ? 'border-purple-500/50 bg-purple-500/10 text-white'
                          : 'border-white/10 bg-white/5 text-white/50 hover:border-white/20'
                      }`}
                    >
                      <Upload className="w-5 h-5" />
                      <span className="text-sm font-medium">Upload Documents</span>
                      <span className="text-xs text-white/40 text-center">Pitch deck, biz plan, profile (multiple)</span>
                    </button>
                  </div>
                </div>

                {/* Website input */}
                <AnimatePresence mode="wait">
                  {inputMode === 'website' && (
                    <motion.div
                      key="website"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden"
                    >
                      <input
                        type="url"
                        value={formData.website}
                        onChange={e => setFormData({ ...formData, website: e.target.value })}
                        placeholder="https://yourcompany.com"
                        className="input-glass"
                      />
                      {formData.website?.trim() ? (
                        <motion.p
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          className="flex items-center gap-1.5 text-xs text-green-400 mt-1.5"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          URL saved — the Company Enricher agent will scrape it during analysis
                        </motion.p>
                      ) : (
                        <p className="text-xs text-white/35 mt-1">
                          Enter your URL to enable Continue
                        </p>
                      )}
                    </motion.div>
                  )}

                  {/* Document upload */}
                  {inputMode === 'document' && (
                    <motion.div
                      key="document"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden"
                    >
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.docx,.txt"
                        className="hidden"
                        onChange={e => {
                          const f = e.target.files?.[0];
                          if (f) handleFileSelect(f);
                        }}
                      />

                      {/* Uploaded docs list */}
                      {uploadedDocs.length > 0 && (
                        <div className="space-y-2 mb-2">
                          {uploadedDocs.map((doc, i) => (
                            <div key={i} className="p-3 rounded-xl bg-green-500/10 border border-green-500/25 flex items-center justify-between">
                              <div className="flex items-center gap-2.5">
                                <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                                <div>
                                  <p className="text-sm font-medium text-white">{doc.name}</p>
                                  <p className="text-xs text-white/40">{(doc.chars / 1000).toFixed(0)}k chars</p>
                                </div>
                              </div>
                              <button onClick={() => removeDoc(i)} className="p-1.5 rounded-lg hover:bg-white/10 text-white/40 hover:text-white/70 transition-colors">
                                <X className="w-4 h-4" />
                              </button>
                            </div>
                          ))}
                          {extractedFields.size > 0 && (
                            <p className="text-xs text-green-400/70 px-1">
                              {extractedFields.size} field{extractedFields.size !== 1 ? 's' : ''} auto-filled from first document
                            </p>
                          )}
                          {extractWarning && (
                            <p className="text-xs text-amber-400/80 px-1 leading-relaxed">{extractWarning}</p>
                          )}
                        </div>
                      )}

                      {/* Drop zone — always visible so user can add more files */}
                      {!uploading && (
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="w-full flex items-center justify-center gap-3 p-4 rounded-xl border-2 border-dashed border-white/15 hover:border-purple-500/40 hover:bg-purple-500/5 transition-all text-white/40 hover:text-white/70"
                        >
                          <FileText className="w-5 h-5" />
                          <span className="text-sm font-medium">
                            {uploadedDocs.length === 0 ? 'Click to upload' : 'Add another document'}
                          </span>
                          <span className="text-xs text-white/30">PDF, DOCX or TXT · Max 10 MB each</span>
                        </button>
                      )}

                      {uploading && (
                        <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                          <div className="flex items-center gap-3 mb-3">
                            <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                            <motion.span
                              key={uploadPhase}
                              initial={{ opacity: 0, y: 4 }}
                              animate={{ opacity: 1, y: 0 }}
                              className="text-sm text-white/70"
                            >
                              {UPLOAD_PHASES[uploadPhase]}
                            </motion.span>
                          </div>
                          <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                            <motion.div
                              className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full"
                              animate={{ width: `${((uploadPhase + 1) / UPLOAD_PHASES.length) * 85}%` }}
                              transition={{ duration: 0.6, ease: 'easeOut' }}
                            />
                          </div>
                        </div>
                      )}

                      {uploadError && (
                        <motion.div
                          initial={{ opacity: 0, y: -4 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="flex items-start gap-2.5 p-3 rounded-xl bg-red-500/10 border border-red-500/25 mt-2"
                        >
                          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                          <p className="text-xs text-red-300 leading-relaxed">{uploadError}</p>
                        </motion.div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* ── Step 1 ── */}
            {step === 1 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-4"
              >
                {extractedFields.size > 0 && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-green-500/10 border border-green-500/20 text-xs text-green-300">
                    <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                    Fields marked with ✦ were extracted from your document. Review and edit as needed.
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Zap className="w-4 h-4 inline mr-1.5" />
                    What does your company do? *
                    {extractedFields.has('description') && <span className="ml-1.5 text-green-400 text-xs">✦ auto-filled</span>}
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Describe your product/service, target customers, and unique value proposition..."
                    className="input-glass min-h-[90px] resize-none"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Target className="w-4 h-4 inline mr-1.5" />
                    Value Proposition
                    {extractedFields.has('valueProposition') && <span className="ml-1.5 text-green-400 text-xs">✦ auto-filled</span>}
                  </label>
                  <input
                    type="text"
                    value={formData.valueProposition}
                    onChange={e => setFormData({ ...formData, valueProposition: e.target.value })}
                    placeholder="e.g., We help SMEs reduce costs by 40% through automation"
                    className="input-glass"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Target className="w-4 h-4 inline mr-1.5" />
                    Primary Goals
                    {extractedFields.has('goals') && <span className="ml-1.5 text-green-400 text-xs">✦ auto-filled</span>}
                  </label>
                  <textarea
                    value={formData.goals?.join('\n')}
                    onChange={e => setFormData({
                      ...formData,
                      goals: e.target.value.split('\n').map(s => s.trim()).filter(Boolean),
                    })}
                    placeholder="One goal per line, e.g.: Enter Singapore market"
                    className="input-glass min-h-[70px] resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Zap className="w-4 h-4 inline mr-1.5" />
                    Key Challenges
                    {extractedFields.has('challenges') && <span className="ml-1.5 text-green-400 text-xs">✦ auto-filled</span>}
                  </label>
                  <textarea
                    value={formData.challenges?.join('\n')}
                    onChange={e => setFormData({
                      ...formData,
                      challenges: e.target.value.split('\n').map(s => s.trim()).filter(Boolean),
                    })}
                    placeholder="One challenge per line"
                    className="input-glass min-h-[70px] resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Users className="w-4 h-4 inline mr-1.5" />
                    Known Competitors
                    {extractedFields.has('competitors') && <span className="ml-1.5 text-green-400 text-xs">✦ auto-filled</span>}
                  </label>
                  <input
                    type="text"
                    value={formData.competitors?.join(', ')}
                    onChange={e => setFormData({
                      ...formData,
                      competitors: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                    })}
                    placeholder="Competitor A, Competitor B"
                    className="input-glass"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">
                    <Globe className="w-4 h-4 inline mr-1.5" />
                    Target Markets
                    {extractedFields.has('targetMarkets') && <span className="ml-1.5 text-green-400 text-xs">✦ auto-filled</span>}
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {['Singapore', 'Malaysia', 'Indonesia', 'Thailand', 'Vietnam', 'Philippines'].map(market => (
                      <button
                        key={market}
                        onClick={() => {
                          const current = formData.targetMarkets || [];
                          const updated = current.includes(market)
                            ? current.filter(m => m !== market)
                            : [...current, market];
                          setFormData({ ...formData, targetMarkets: updated });
                        }}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                          formData.targetMarkets?.includes(market)
                            ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                            : 'bg-white/5 text-white/60 hover:bg-white/10 border border-white/10'
                        }`}
                      >
                        {market}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </div>

          {/* Progress & navigation */}
          <div className="mt-6 flex items-center justify-between">
            <div className="flex gap-2">
              {[0, 1].map(i => (
                <div
                  key={i}
                  className={`h-2 rounded-full transition-all ${
                    i === step ? 'w-8 bg-gradient-to-r from-purple-500 to-blue-500'
                      : i < step ? 'w-2 bg-purple-500'
                      : 'w-2 bg-white/20'
                  }`}
                />
              ))}
            </div>

            <div className="flex gap-3">
              {step > 0 && (
                <button onClick={() => setStep(s => s - 1)} className="btn-ghost">Back</button>
              )}
              {step < 1 ? (
                <button
                  onClick={() => setStep(1)}
                  disabled={!canProceed()}
                  className="btn-primary flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                      Processing…
                    </>
                  ) : (
                    <>Continue <ArrowRight className="w-4 h-4" /></>
                  )}
                </button>
              ) : (
                <button
                  onClick={handleSubmit}
                  disabled={!canProceed() || !isBackendAvailable}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" />
                  Start Analysis
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="absolute -top-20 -right-20 w-40 h-40 rounded-full bg-purple-500/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-40 h-40 rounded-full bg-blue-500/10 blur-3xl pointer-events-none" />
      </motion.div>
    </motion.div>
  );
}
