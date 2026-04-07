import { Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { FEATURES, type FeatureFlag } from '../config/features';

interface FeatureGateProps {
  flag: FeatureFlag;
  children: ReactNode;
  /** Where to redirect when the flag is false. Defaults to /today. */
  redirectTo?: string;
}

/**
 * Route-level feature gate. Silent redirect when the flag is false.
 *
 * Usage:
 *   <Route
 *     path="/workforce"
 *     element={
 *       <FeatureGate flag="workforce">
 *         <WorkforceWorkspace />
 *       </FeatureGate>
 *     }
 *   />
 *
 * Design notes:
 *   - No "upgrade" or "not available" screen — silent redirect keeps UX clean
 *     and avoids implying a paywall that doesn't exist.
 *   - Internal QA bypasses the gate via VITE_LAUNCH_MODE=internal (see features.ts).
 *   - The default redirect target is /today because it's the primary launch
 *     surface and a safe fallback from any gated route.
 */
export function FeatureGate({ flag, children, redirectTo = '/today' }: FeatureGateProps) {
  if (!FEATURES[flag]) {
    return <Navigate to={redirectTo} replace />;
  }
  return <>{children}</>;
}
