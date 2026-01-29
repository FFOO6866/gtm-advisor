import { motion, HTMLMotionProps } from 'framer-motion';
import { clsx } from 'clsx';

interface CardProps extends HTMLMotionProps<'div'> {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'glass' | 'outlined';
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export function Card({
  children,
  className,
  variant = 'glass',
  padding = 'md',
  ...props
}: CardProps) {
  return (
    <motion.div
      className={clsx(
        'rounded-xl',
        {
          'bg-white/5 backdrop-blur-xl border border-white/10': variant === 'glass',
          'bg-surface border border-white/10': variant === 'default',
          'border border-white/20 bg-transparent': variant === 'outlined',
        },
        {
          'p-0': padding === 'none',
          'p-3': padding === 'sm',
          'p-4': padding === 'md',
          'p-6': padding === 'lg',
        },
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
