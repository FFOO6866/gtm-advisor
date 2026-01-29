/**
 * Error State Components
 *
 * Error display and retry functionality for workspace data.
 */

import { motion } from 'framer-motion';
import { Button } from './Button';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  className = '',
}: ErrorStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center ${className}`}
    >
      <div className="text-4xl mb-4">⚠️</div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-white/70 mb-4">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </motion.div>
  );
}

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="bg-red-500/90 text-white px-4 py-3 rounded-lg flex items-center justify-between"
    >
      <div className="flex items-center gap-2">
        <span>⚠️</span>
        <span>{message}</span>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-white/70 hover:text-white transition-colors"
        >
          ✕
        </button>
      )}
    </motion.div>
  );
}

interface APIErrorProps {
  error: Error;
  onRetry?: () => void;
}

export function APIError({ error, onRetry }: APIErrorProps) {
  // Parse error message
  let title = 'Error';
  let message = error.message;

  if (error.message.includes('404')) {
    title = 'Not Found';
    message = 'The requested resource could not be found.';
  } else if (error.message.includes('401') || error.message.includes('403')) {
    title = 'Access Denied';
    message = 'You do not have permission to access this resource.';
  } else if (error.message.includes('500')) {
    title = 'Server Error';
    message = 'An internal server error occurred. Please try again later.';
  } else if (error.message.includes('Network') || error.message.includes('fetch')) {
    title = 'Connection Error';
    message = 'Unable to connect to the server. Please check your internet connection.';
  }

  return <ErrorState title={title} message={message} onRetry={onRetry} />;
}

interface InlineErrorProps {
  message: string;
}

export function InlineError({ message }: InlineErrorProps) {
  return (
    <div className="text-red-400 text-sm flex items-center gap-1">
      <span>⚠️</span>
      <span>{message}</span>
    </div>
  );
}

interface FormErrorProps {
  errors: Record<string, string>;
}

export function FormErrors({ errors }: FormErrorProps) {
  const errorList = Object.entries(errors);
  if (errorList.length === 0) return null;

  return (
    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 space-y-1">
      {errorList.map(([field, message]) => (
        <div key={field} className="text-red-400 text-sm">
          <span className="font-medium capitalize">{field.replace(/_/g, ' ')}:</span>{' '}
          {message}
        </div>
      ))}
    </div>
  );
}
