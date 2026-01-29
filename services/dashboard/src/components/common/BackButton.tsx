import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';

interface BackButtonProps {
  to?: string;
  label?: string;
}

export function BackButton({ to = '/', label = 'Back to Command Center' }: BackButtonProps) {
  const navigate = useNavigate();

  return (
    <motion.button
      onClick={() => navigate(to)}
      className="flex items-center gap-2 text-white/60 hover:text-white transition-colors"
      whileHover={{ x: -2 }}
    >
      <ArrowLeft className="w-4 h-4" />
      <span className="text-sm">{label}</span>
    </motion.button>
  );
}
