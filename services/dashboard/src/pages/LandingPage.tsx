/**
 * LandingPage — Hi Meet.AI marketing homepage (v4 — Brand-Led Rebuild).
 *
 * 5 sections: Hero → The Shift → The Platform → How It Works → CTA + Footer
 * Uses existing design system: glass-card, border-gradient, text-gradient, AuroraBackground.
 * Images load from /images/*.jpg with CSS gradient fallbacks.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import {
  ArrowRight, ChevronDown,
  Clock, Shuffle, UserPlus,
  Radio, Compass, Play, RefreshCw,
  Target, Search, Megaphone, Cog, BarChart3,
  UserCheck, Zap, Shield, Globe, Users, TrendingUp, Brain, Activity,
  CheckCircle,
} from 'lucide-react';
import { AuroraBackground } from '../components/AuroraBackground';

// ── Condensed Stories ───────────────────────────────────────────────

const STORIES = [
  {
    category: 'Speed',
    icon: Zap,
    color: 'from-red-500 to-orange-500',
    tension: 'Competitor raised $5M. You need a response in days.',
    insight: 'The company that maps the landscape first sets the terms.',
    result: 'Competitive response campaigns delivered in hours, not months.',
  },
  {
    category: 'Intelligence',
    icon: Radio,
    color: 'from-blue-500 to-cyan-500',
    tension: "Marketing spend is up but you can't tell which signals matter.",
    insight: "The problem isn't lack of data — it's lack of synthesis.",
    result: 'One system identifies what matters and recommends what to do.',
  },
  {
    category: 'Execution',
    icon: Play,
    color: 'from-purple-500 to-pink-500',
    tension: 'Great strategy built. Three-month gap before anything executes.',
    insight: 'The bottleneck is sequential delivery, not capability.',
    result: 'Strategy flows into campaigns and outreach the same week.',
  },
  {
    category: 'Scale',
    icon: TrendingUp,
    color: 'from-emerald-500 to-teal-500',
    tension: 'Next million in revenue means doubling the team.',
    insight: 'Growth scales through intelligence, not headcount.',
    result: 'Full strategic bench without the proportional cost.',
  },
];

// ── Model Steps ─────────────────────────────────────────────────────

const PIPELINE = [
  { icon: Radio, title: 'Intelligence', color: 'from-blue-500 to-cyan-500', line: 'Live market data, competitive signals, benchmarks.' },
  { icon: Compass, title: 'Strategy', color: 'from-indigo-500 to-purple-500', line: 'Positioning, targeting, campaign architecture.' },
  { icon: Play, title: 'Execution', color: 'from-purple-500 to-pink-500', line: 'Campaigns and outreach with human approval.' },
  { icon: RefreshCw, title: 'Optimization', color: 'from-emerald-500 to-teal-500', line: "Attribution closes the loop." },
];

// ── Animated Counter ────────────────────────────────────────────────

function Counter({ target, suffix = '' }: { target: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!isInView) return;
    let frame: number;
    const duration = 1500;
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setCount(Math.round(eased * target));
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [isInView, target]);

  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

// ── FadeIn ──────────────────────────────────────────────────────────

function FadeIn({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.6, delay }} className={className}>
      {children}
    </motion.div>
  );
}

// ── Image with fallback ─────────────────────────────────────────────

function BrandImage({ src, alt, fallbackClass, className }: { src: string; alt: string; fallbackClass: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <div className={`${fallbackClass} ${className}`} />;
  return <img src={src} alt={alt} className={className} onError={() => setFailed(true)} loading="lazy" />;
}

// ── Main Component ──────────────────────────────────────────────────

export function LandingPage() {
  const navigate = useNavigate();
  const [activeStory, setActiveStory] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  const nextStory = useCallback(() => {
    setActiveStory((prev) => (prev + 1) % STORIES.length);
  }, []);

  useEffect(() => {
    if (isPaused) return;
    const timer = setInterval(nextStory, 8000);
    return () => clearInterval(timer);
  }, [isPaused, nextStory]);

  return (
    <div className="relative min-h-screen bg-surface overflow-hidden">
      <AuroraBackground />

      <div className="relative z-10">

        {/* ═══════════════════════════════════════════════════════
            NAVIGATION
        ═══════════════════════════════════════════════════════ */}
        <nav className="fixed top-0 left-0 right-0 z-50 bg-surface/70 backdrop-blur-xl border-b border-white/[0.06]">
          <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500 via-blue-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-bold text-white tracking-tight">Hi Meet.AI</span>
            </div>
            {/* Nav links */}
            <div className="hidden sm:flex items-center gap-5">
              {[
                { label: 'Platform', href: '#platform' },
                { label: 'Why Us', href: '#why-us' },
                { label: 'How It Works', href: '#how-it-works' },
              ].map(({ label, href }) => (
                <a key={label} href={href} className="text-sm text-white/60 hover:text-white transition-colors">
                  {label}
                </a>
              ))}
            </div>

            <button onClick={() => navigate('/register')} className="btn-primary text-xs sm:text-sm">
              <span>Get Started</span>
            </button>
          </div>
        </nav>

        {/* ═══════════════════════════════════════════════════════
            SECTION 1 — HERO
        ═══════════════════════════════════════════════════════ */}
        <section className="relative min-h-[90vh] sm:min-h-screen flex items-center overflow-hidden">
          {/* Hero image / fallback */}
          <div className="absolute inset-0">
            <BrandImage src="/images/hero.jpg" alt="" fallbackClass="img-fallback-hero" className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-b from-surface/50 via-surface/60 to-surface" />
            <div className="absolute inset-0 bg-gradient-to-br from-purple-900/20 via-transparent to-blue-900/10" />
          </div>

          <div className="relative z-10 w-full max-w-6xl mx-auto px-6 pt-28 sm:pt-36 pb-20">
            <div className="max-w-3xl">
              {/* Badge */}
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/[0.06] border border-white/10 text-sm text-white/50 mb-8 backdrop-blur-sm"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Human-Led · Agent-Driven
              </motion.div>

              {/* Headline */}
              <motion.h1
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
                className="text-5xl sm:text-6xl lg:text-7xl font-bold text-white leading-[1.05] mb-6 tracking-tight"
              >
                Your Full Strategic Bench.{' '}
                <span className="text-gradient">Always On.</span>
              </motion.h1>

              {/* Subtitle */}
              <motion.p
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className="text-lg sm:text-xl text-white/50 leading-relaxed mb-10 max-w-xl"
              >
                Human-led, agent-driven growth from intelligence to campaign
                execution — without the lag.
              </motion.p>

              {/* CTAs */}
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="flex flex-col sm:flex-row gap-4 mb-16"
              >
                <button onClick={() => navigate('/register')} className="btn-primary flex items-center justify-center gap-2 text-base px-8 py-4">
                  <span>Get Started</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
                <a
                  href="mailto:hello@himeet.ai?subject=Walkthrough%20Request"
                  className="btn-ghost text-base px-8 py-4 text-center"
                >
                  Request a Walkthrough
                </a>
              </motion.div>

              {/* Stats */}
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.45 }}
                className="grid grid-cols-3 gap-4 max-w-md"
              >
                {[
                  { icon: Brain, value: 12, suffix: '', label: 'AI Agents', color: 'text-purple-400' },
                  { icon: Activity, value: 1100, suffix: '+', label: 'Companies Benchmarked', color: 'text-blue-400' },
                  { icon: Shield, value: 100, suffix: '%', label: 'Human Approved', color: 'text-emerald-400' },
                ].map(({ icon: Icon, value, suffix, label, color }) => (
                  <div key={label} className="text-left">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Icon className={`w-3.5 h-3.5 ${color}`} />
                      <p className="text-2xl font-bold text-white"><Counter target={value} suffix={suffix} /></p>
                    </div>
                    <p className="text-[11px] text-white/30 uppercase tracking-wider">{label}</p>
                  </div>
                ))}
              </motion.div>
            </div>
          </div>

          <motion.div className="absolute bottom-6 left-1/2 -translate-x-1/2" animate={{ y: [0, 8, 0] }} transition={{ duration: 2, repeat: Infinity }}>
            <ChevronDown className="w-5 h-5 text-white/15" />
          </motion.div>
        </section>

        {/* ═══════════════════════════════════════════════════════
            SECTION 2 — THE SHIFT (Problem → Solution)
        ═══════════════════════════════════════════════════════ */}
        <section id="why-us" className="relative py-20 sm:py-32 px-6 dot-grid scroll-mt-20">
          <div className="max-w-6xl mx-auto">
            <FadeIn className="text-center mb-12 sm:mb-20">
              <h2 className="text-3xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
                The Old Model Is <span className="text-gradient">Broken</span>
              </h2>
              <p className="text-lg text-white/40 max-w-xl mx-auto">
                Traditional growth is sequential, siloed, and headcount-bound. We replaced it.
              </p>
            </FadeIn>

            <div className="grid lg:grid-cols-11 gap-6 lg:gap-0 items-stretch">
              {/* BEFORE — left side */}
              <div className="lg:col-span-5 space-y-4">
                <p className="text-xs font-semibold uppercase tracking-widest text-white/20 mb-5 text-center lg:text-left">Before</p>
                {[
                  { icon: Clock, text: 'Strategy takes weeks. Execution takes months.', stat: '6-12 wks' },
                  { icon: Shuffle, text: 'Every handoff loses context and momentum.', stat: '4-5 handoffs' },
                  { icon: UserPlus, text: 'Scaling growth means scaling headcount.', stat: '3-5 hires' },
                ].map(({ icon: Icon, text, stat }, i) => (
                  <FadeIn key={text} delay={i * 0.08}>
                    <div className="glass-card rounded-xl p-5 flex items-start gap-4">
                      <div className="w-9 h-9 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
                        <Icon className="w-4 h-4 text-red-400/70" />
                      </div>
                      <p className="text-sm text-white/55 font-medium flex-1">{text}</p>
                      <span className="text-xs font-bold text-red-400/50 bg-red-500/10 px-2 py-1 rounded-md flex-shrink-0">{stat}</span>
                    </div>
                  </FadeIn>
                ))}
              </div>

              {/* CENTER DIVIDER — shift image or gradient */}
              <div className="lg:col-span-1 flex items-center justify-center py-4 lg:py-0">
                <div className="hidden lg:block w-px h-full bg-gradient-to-b from-transparent via-purple-500/30 to-transparent" />
                <div className="lg:hidden w-full h-px bg-gradient-to-r from-transparent via-purple-500/30 to-transparent" />
              </div>

              {/* AFTER — right side */}
              <div className="lg:col-span-5 space-y-4">
                <p className="text-xs font-semibold uppercase tracking-widest text-purple-400/40 mb-5 text-center lg:text-left">With Hi Meet.AI</p>
                {[
                  { icon: Zap, text: 'Strategy to campaign in the same week.', label: 'Hours', color: 'text-purple-400', bg: 'bg-purple-500/10' },
                  { icon: Globe, text: 'One system. No handoffs. No context loss.', label: '1 system', color: 'text-blue-400', bg: 'bg-blue-500/10' },
                  { icon: Users, text: '12 agents, not 12 new hires.', label: '12 agents', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
                ].map(({ icon: Icon, text, label, color, bg }, i) => (
                  <FadeIn key={text} delay={i * 0.08}>
                    <div className="border-gradient rounded-xl p-5 flex items-start gap-4">
                      <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center flex-shrink-0`}>
                        <Icon className={`w-4 h-4 ${color}`} />
                      </div>
                      <p className="text-sm text-white/70 font-medium flex-1">{text}</p>
                      <span className={`text-xs font-bold ${color}/70 ${bg} px-2 py-1 rounded-md flex-shrink-0`}>{label}</span>
                    </div>
                  </FadeIn>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════
            SECTION 3 — THE PLATFORM (Product Evidence)
        ═══════════════════════════════════════════════════════ */}
        <section id="platform" className="relative py-20 sm:py-32 px-6 overflow-hidden scroll-mt-20">
          <div className="max-w-6xl mx-auto">
            <FadeIn className="text-center mb-12 sm:mb-16">
              <h2 className="text-3xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
                What You <span className="text-gradient">Actually Get</span>
              </h2>
              <p className="text-lg text-white/40 max-w-xl mx-auto">
                Not features. An integrated growth function — from intelligence to attribution.
              </p>
            </FadeIn>

            {/* Deliverables grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4 mb-16 sm:mb-20">
              {[
                { icon: Radio, title: 'Market Intelligence', color: 'text-blue-400', bg: 'from-blue-500/20 to-blue-500/5' },
                { icon: Target, title: 'Strategy & Positioning', color: 'text-indigo-400', bg: 'from-indigo-500/20 to-indigo-500/5' },
                { icon: Search, title: 'Lead Identification', color: 'text-purple-400', bg: 'from-purple-500/20 to-purple-500/5' },
                { icon: Megaphone, title: 'Campaign Architecture', color: 'text-pink-400', bg: 'from-pink-500/20 to-pink-500/5' },
                { icon: Cog, title: 'Coordinated Execution', color: 'text-amber-400', bg: 'from-amber-500/20 to-amber-500/5' },
                { icon: BarChart3, title: 'ROI Attribution', color: 'text-emerald-400', bg: 'from-emerald-500/20 to-emerald-500/5' },
              ].map(({ icon: Icon, title, color, bg }, i) => (
                <FadeIn key={title} delay={i * 0.05}>
                  <motion.div
                    whileHover={{ y: -3 }}
                    transition={{ duration: 0.2 }}
                    className={`glass-card rounded-xl p-4 text-center bg-gradient-to-b ${bg} group cursor-default h-full`}
                  >
                    <div className={`w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform`}>
                      <Icon className={`w-5 h-5 ${color}`} />
                    </div>
                    <p className="text-xs font-semibold text-white/70 leading-tight">{title}</p>
                  </motion.div>
                </FadeIn>
              ))}
            </div>

            {/* Product screenshot in glass frame — proves deliverables are real */}
            <FadeIn delay={0.1}>
              <div className="relative max-w-5xl mx-auto">
                {/* Glow behind frame */}
                <div className="absolute -inset-4 sm:-inset-8 rounded-3xl img-glow opacity-50" />

                <div className="relative glass-card rounded-2xl overflow-hidden">
                  {/* Browser chrome */}
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06] bg-surface-50/50">
                    <div className="flex gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-white/10" />
                      <div className="w-3 h-3 rounded-full bg-white/10" />
                      <div className="w-3 h-3 rounded-full bg-white/10" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-4 py-1 rounded-md bg-white/[0.04] text-xs text-white/25 font-mono">
                        app.himeet.ai
                      </div>
                    </div>
                  </div>
                  {/* Screenshot or fallback */}
                  <div className="relative aspect-[16/9] bg-surface-100">
                    <BrandImage
                      src="/images/platform.jpg"
                      alt="Hi Meet.AI platform — TodayPage with market intelligence"
                      fallbackClass="img-fallback-hero"
                      className="w-full h-full object-cover object-top"
                    />
                  </div>
                </div>

                {/* Floating callout cards */}
                <div className="hidden md:block">
                  {[
                    { label: 'Live Market Signals', value: 'EODHD + NewsAPI + ACRA', position: 'absolute -left-4 lg:-left-12 top-1/4', color: 'text-blue-400' },
                    { label: 'Qualified Leads', value: 'Enriched + BANT Scored', position: 'absolute -right-4 lg:-right-12 top-1/3', color: 'text-purple-400' },
                    { label: 'ROI Attribution', value: 'Outreach → Deal Tracked', position: 'absolute -right-4 lg:-right-12 bottom-1/4', color: 'text-emerald-400' },
                  ].map(({ label, value, position, color }, i) => (
                    <motion.div
                      key={label}
                      className={`${position} glass-card rounded-xl p-3 shadow-glow-sm max-w-[180px]`}
                      initial={{ opacity: 0, x: i === 0 ? -20 : 20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.4 + i * 0.15 }}
                    >
                      <p className={`text-xs font-semibold ${color} mb-0.5`}>{label}</p>
                      <p className="text-[10px] text-white/35">{value}</p>
                    </motion.div>
                  ))}
                </div>
              </div>
            </FadeIn>

            {/* Mobile feature strip — visible below screenshot on small screens */}
            <div className="md:hidden grid grid-cols-3 gap-3 mt-6">
              {[
                { label: 'Live Signals', color: 'text-blue-400', icon: Radio },
                { label: 'Scored Leads', color: 'text-purple-400', icon: Users },
                { label: 'ROI Tracked', color: 'text-emerald-400', icon: TrendingUp },
              ].map(({ label, color, icon: Icon }) => (
                <div key={label} className="glass-card rounded-xl p-3 text-center">
                  <Icon className={`w-4 h-4 ${color} mx-auto mb-1`} />
                  <p className="text-[10px] text-white/40 font-medium">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════
            SECTION 4 — HOW IT WORKS (Pipeline + Stories)
        ═══════════════════════════════════════════════════════ */}
        <section id="how-it-works" className="relative py-20 sm:py-32 px-6 dot-grid scroll-mt-20">
          <div className="max-w-5xl mx-auto">
            <FadeIn className="text-center mb-12 sm:mb-16">
              <h2 className="text-3xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
                How It <span className="text-gradient">Works</span>
              </h2>
            </FadeIn>

            {/* Pipeline */}
            <div className="relative mb-20 sm:mb-28">
              {/* Connection line (desktop) */}
              <div className="hidden lg:block absolute top-7 left-[12.5%] right-[12.5%] h-px bg-white/10">
                <motion.div
                  className="h-full bg-gradient-to-r from-blue-400 via-purple-400 to-emerald-400"
                  initial={{ width: 0 }}
                  whileInView={{ width: '100%' }}
                  viewport={{ once: true }}
                  transition={{ duration: 1.5, delay: 0.3 }}
                />
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                {PIPELINE.map(({ icon: Icon, title, color, line }, i) => (
                  <FadeIn key={title} delay={i * 0.1}>
                    <motion.div whileHover={{ y: -4 }} transition={{ duration: 0.2 }} className="text-center group">
                      <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${color} flex items-center justify-center mx-auto mb-4 shadow-lg group-hover:scale-110 transition-transform`}>
                        <Icon className="w-6 h-6 text-white" />
                      </div>
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-1">{title}</h3>
                      <p className="text-xs text-white/35">{line}</p>
                    </motion.div>
                  </FadeIn>
                ))}
              </div>
            </div>

            {/* Human-Led, Agent-Driven — trust & oversight */}
            <FadeIn className="mb-20 sm:mb-28">
              <div className="relative glass-card rounded-2xl overflow-hidden max-w-4xl mx-auto">
                {/* Background accent */}
                <div className="absolute inset-0">
                  <BrandImage src="/images/intelligence.jpg" alt="" fallbackClass="img-fallback-hero" className="w-full h-full object-cover" />
                  <div className="absolute inset-0 bg-surface/80" />
                  <div className="absolute inset-0 bg-gradient-to-br from-purple-900/20 to-blue-900/10" />
                </div>

                <div className="relative p-6 sm:p-10">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
                      <UserCheck className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h3 className="text-lg sm:text-xl font-bold text-white">Human-Led. Agent-Driven.</h3>
                      <p className="text-xs text-white/40">Every decision is guided by human oversight. Agents handle speed and scale.</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    {[
                      { icon: UserCheck, text: 'Humans approve every outreach', color: 'text-blue-400' },
                      { icon: Zap, text: 'Agents research & execute at speed', color: 'text-purple-400' },
                      { icon: Shield, text: 'PDPA-compliant audit trails', color: 'text-emerald-400' },
                      { icon: Globe, text: 'Built for Singapore context', color: 'text-cyan-400' },
                    ].map(({ icon: Icon, text, color }) => (
                      <div key={text} className="flex items-start gap-2.5 p-3 rounded-lg bg-white/[0.04]">
                        <Icon className={`w-4 h-4 ${color} flex-shrink-0 mt-0.5`} />
                        <p className="text-xs text-white/55 font-medium leading-relaxed">{text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </FadeIn>

            {/* Condensed stories */}
            <FadeIn>
              <div onMouseEnter={() => setIsPaused(true)} onMouseLeave={() => setIsPaused(false)}>
                <p className="text-xs font-semibold uppercase tracking-widest text-white/20 text-center mb-6">In Practice</p>

                {/* Tabs */}
                <div className="flex flex-wrap justify-center gap-2 mb-6">
                  {STORIES.map((story, i) => {
                    const Icon = story.icon;
                    return (
                      <button
                        key={story.category}
                        onClick={() => setActiveStory(i)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          i === activeStory
                            ? `bg-gradient-to-r ${story.color} text-white shadow-md`
                            : 'text-white/25 hover:text-white/45 bg-white/[0.04]'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        {story.category}
                      </button>
                    );
                  })}
                </div>

                {/* Story card — condensed 3-line format */}
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeStory}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.3 }}
                    className="glass-card rounded-2xl overflow-hidden max-w-2xl mx-auto"
                  >
                    <div className={`h-0.5 bg-gradient-to-r ${STORIES[activeStory].color}`} />
                    <div className="p-5 sm:p-6 space-y-4">
                      <div className="flex items-start gap-3">
                        <div className="w-5 h-5 rounded-full bg-red-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
                        </div>
                        <p className="text-sm text-white/65">{STORIES[activeStory].tension}</p>
                      </div>
                      <div className="flex items-start gap-3">
                        <div className="w-5 h-5 rounded-full bg-purple-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <div className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                        </div>
                        <p className="text-sm text-white/50 italic">{STORIES[activeStory].insight}</p>
                      </div>
                      <div className="flex items-start gap-3">
                        <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-emerald-400/80 font-medium">{STORIES[activeStory].result}</p>
                      </div>
                    </div>
                  </motion.div>
                </AnimatePresence>

                {/* Progress */}
                <div className="flex justify-center gap-2 mt-5">
                  {STORIES.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveStory(i)}
                      className={`h-1 rounded-full transition-all ${
                        i === activeStory ? 'w-8 bg-gradient-to-r from-purple-400 to-blue-400' : 'w-1.5 bg-white/15'
                      }`}
                    />
                  ))}
                </div>
              </div>
            </FadeIn>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════
            SECTION 5 — CTA
        ═══════════════════════════════════════════════════════ */}
        <section className="relative py-24 sm:py-36 px-6 overflow-hidden">
          {/* Background */}
          <div className="absolute inset-0">
            <BrandImage src="/images/singapore.jpg" alt="" fallbackClass="img-fallback-cta" className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-surface/60" />
            <div className="absolute inset-0 bg-gradient-to-t from-surface via-transparent to-surface/70" />
          </div>

          <div className="max-w-2xl mx-auto text-center relative z-10">
            <FadeIn>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.06] border border-white/10 text-xs text-white/40 mb-6">
                <Shield className="w-3 h-3 text-emerald-400" />
                PDPA Compliant · Human Oversight · Singapore Context
              </div>

              <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-6 tracking-tight">
                Ready to Move <span className="text-gradient">Faster?</span>
              </h2>
              <p className="text-lg text-white/45 mb-4 leading-relaxed">
                We're onboarding early partners who want to see what growth looks
                like when intelligence and execution run as one system.
              </p>
              <p className="text-sm text-white/25 mb-10">
                Built as a platform, not a service. Singapore-first. APAC-ready.
              </p>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <button onClick={() => navigate('/register')} className="btn-primary w-full sm:w-auto flex items-center justify-center gap-2 text-base px-10 py-4">
                  <span>Get Started</span>
                  <ArrowRight className="w-5 h-5" />
                </button>
                <a
                  href="mailto:hello@himeet.ai?subject=Walkthrough%20Request"
                  className="btn-ghost w-full sm:w-auto text-base px-10 py-4 text-center"
                >
                  Request a Walkthrough
                </a>
              </div>
            </FadeIn>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════
            FOOTER
        ═══════════════════════════════════════════════════════ */}
        <footer className="border-t border-white/[0.06] py-12 sm:py-16 px-6">
          <div className="max-w-5xl mx-auto">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 mb-10">
              <div className="col-span-2 lg:col-span-1">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                    <Zap className="w-3.5 h-3.5 text-white" />
                  </div>
                  <span className="text-sm font-bold text-white">Hi Meet.AI</span>
                </div>
                <p className="text-xs text-white/30 leading-relaxed max-w-[220px]">
                  Human-led, agent-driven growth for companies that move fast.
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/20 mb-4">Platform</p>
                <ul className="space-y-2">
                  {['Market Intelligence', 'Lead Identification', 'Campaign Architecture', 'ROI Attribution'].map(item => (
                    <li key={item}><span className="text-xs text-white/30">{item}</span></li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/20 mb-4">Company</p>
                <ul className="space-y-2">
                  <li><button onClick={() => navigate('/register')} className="text-xs text-white/30 hover:text-white/60 transition-colors">Get Started</button></li>
                  <li><a href="mailto:hello@himeet.ai" className="text-xs text-white/30 hover:text-white/60 transition-colors">Contact</a></li>
                  <li><button onClick={() => navigate('/login')} className="text-xs text-white/30 hover:text-white/60 transition-colors">Sign In</button></li>
                </ul>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/20 mb-4">Singapore</p>
                <ul className="space-y-2">
                  {['PDPA Compliant', 'PSG/EDG Eligible', 'ACRA Integrated'].map(item => (
                    <li key={item}><span className="text-xs text-white/30">{item}</span></li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="border-t border-white/[0.06] pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
              <p className="text-[11px] text-white/20">&copy; {new Date().getFullYear()} Hi Meet.AI Pte. Ltd. All rights reserved.</p>
              <div className="flex gap-6">
                <span className="text-[11px] text-white/20">Privacy Policy</span>
                <span className="text-[11px] text-white/20">Terms of Service</span>
              </div>
            </div>
          </div>
        </footer>

      </div>
    </div>
  );
}
