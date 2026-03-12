/**
 * AppShell — Shared layout for the authenticated paid application.
 *
 * Wraps all paid routes with AuroraBackground + Header + SidebarNav.
 * Unauthenticated users are redirected to /login?next={currentPath}.
 * Used via React Router's nested <Outlet> pattern.
 */

import { useEffect, useRef, useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AuroraBackground } from './AuroraBackground';
import { Header } from './Header';
import { SidebarNav } from './SidebarNav';
import { useCompany, useCompanyId } from '../context/CompanyContext';
import { fetchCompanyById } from '../api/companies';

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { company, setCompany } = useCompany();
  const companyId = useCompanyId();

  // Determine upfront whether we need to hydrate so we can set the initial state
  // to true and avoid a flash of "no company" content before data loads.
  const needsHydration =
    !companyId &&
    !!localStorage.getItem('gtm_access_token') &&
    !!(localStorage.getItem('gtm_company_id') || sessionStorage.getItem('gtm_company_id'));

  const [isHydrating, setIsHydrating] = useState(needsHydration);
  const didHydrate = useRef(false);

  // On mount: if we have no company in context, try to restore it from
  // the stored company_id (set during teaser analysis). This covers the case
  // where a user ran the teaser, registered, logged in, and landed here fresh.
  useEffect(() => {
    if (companyId || didHydrate.current) return;
    // Guard: only attempt hydration for authenticated sessions
    if (!localStorage.getItem('gtm_access_token')) return;
    didHydrate.current = true;

    const storedId =
      localStorage.getItem('gtm_company_id') ||
      sessionStorage.getItem('gtm_company_id');

    if (!storedId) {
      setIsHydrating(false);
      return;
    }

    setIsHydrating(true);
    fetchCompanyById(storedId)
      .then(setCompany)
      .catch((err) => {
        console.error('[AppShell] Failed to hydrate company context:', err);
        // Stale / inaccessible company_id — remove so we don't retry
        localStorage.removeItem('gtm_company_id');
      })
      .finally(() => setIsHydrating(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!localStorage.getItem('gtm_access_token')) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (isHydrating) {
    return (
      <div className="relative min-h-screen overflow-hidden">
        <AuroraBackground />
        <div className="relative z-10 flex items-center justify-center h-screen">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-white/50 text-sm">Loading your workspace…</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <AuroraBackground />
      <div className="relative z-10 flex flex-col h-screen">
        <Header
          companyName={company?.name}
          onNewAnalysis={() => navigate('/')}
        />
        <main className="flex-1 flex overflow-hidden pb-16 md:pb-0">
          <SidebarNav companyId={companyId ?? ''} companyName={company?.name} />
          <div className="flex-1 overflow-hidden">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
