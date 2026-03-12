/**
 * WhyUsPage — Full-page "Why GTM Advisor vs ChatGPT" comparison.
 *
 * Accessible via sidebar nav so users can share/bookmark the differentiator.
 */

import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { WhyUsPanel } from '../components/WhyUsPanel';

export function WhyUsPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="text-white/40 hover:text-white/70 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-lg font-semibold text-white">Why GTM Advisor?</h1>
            <p className="text-xs text-white/40">Not a chatbot. An always-on AI workforce.</p>
          </div>
        </div>
      </div>

      <motion.div
        className="flex-1 overflow-y-auto p-6 max-w-2xl mx-auto w-full"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <WhyUsPanel />
      </motion.div>
    </div>
  );
}
