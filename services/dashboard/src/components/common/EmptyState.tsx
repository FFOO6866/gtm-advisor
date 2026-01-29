import { motion } from 'framer-motion';
import { Card } from './Card';
import { Button } from './Button';

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon = '📭', title, description, action }: EmptyStateProps) {
  return (
    <Card className="py-12">
      <motion.div
        className="flex flex-col items-center justify-center text-center"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <span className="text-5xl mb-4">{icon}</span>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        {description && <p className="text-white/60 mt-1 max-w-sm">{description}</p>}
        {action && (
          <Button variant="primary" className="mt-4" onClick={action.onClick}>
            {action.label}
          </Button>
        )}
      </motion.div>
    </Card>
  );
}
