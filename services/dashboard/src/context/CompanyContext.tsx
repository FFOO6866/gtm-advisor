/**
 * Company Context
 *
 * Provides the current company context to all workspace pages.
 * Manages company selection and persists to session storage.
 */

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface Company {
  id: string;
  name: string;
  website: string | null;
  description: string | null;
  industry: string | null;
  goals: string[];
  challenges: string[];
  competitors: string[];
  target_markets: string[];
  value_proposition: string | null;
  // Enriched data
  founded_year: string | null;
  headquarters: string | null;
  employee_count: string | null;
  funding_stage: string | null;
  tech_stack: string[];
  products: Array<{ name: string; description: string; type: string }>;
  enrichment_confidence: number;
  last_enriched_at: string | null;
}

interface CompanyContextValue {
  company: Company | null;
  companyId: string | null;
  isLoading: boolean;
  error: Error | null;
  setCompany: (company: Company) => void;
  clearCompany: () => void;
  refreshCompany: () => Promise<void>;
}

// ============================================================================
// Context
// ============================================================================

const CompanyContext = createContext<CompanyContextValue | null>(null);

const STORAGE_KEY = 'gtm_current_company';

export function useCompany() {
  const context = useContext(CompanyContext);
  if (!context) {
    throw new Error('useCompany must be used within a CompanyProvider');
  }
  return context;
}

// Hook that returns just the company ID (for API calls)
export function useCompanyId(): string | null {
  const { companyId } = useCompany();
  return companyId;
}

// ============================================================================
// Provider
// ============================================================================

interface CompanyProviderProps {
  children: ReactNode;
}

export function CompanyProvider({ children }: CompanyProviderProps) {
  const [company, setCompanyState] = useState<Company | null>(() => {
    // Initialize from session storage
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {
        return null;
      }
    }
    return null;
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Persist to session storage
  useEffect(() => {
    if (company) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(company));
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, [company]);

  const setCompany = useCallback((newCompany: Company) => {
    setCompanyState(newCompany);
    setError(null);
  }, []);

  const clearCompany = useCallback(() => {
    setCompanyState(null);
    sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const refreshCompany = useCallback(async () => {
    if (!company?.id) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/companies/${company.id}`
      );

      if (!response.ok) {
        throw new Error('Failed to refresh company data');
      }

      const data = await response.json();
      setCompanyState(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to refresh company'));
    } finally {
      setIsLoading(false);
    }
  }, [company?.id]);

  const companyId = company?.id || null;

  return (
    <CompanyContext.Provider
      value={{
        company,
        companyId,
        isLoading,
        error,
        setCompany,
        clearCompany,
        refreshCompany,
      }}
    >
      {children}
    </CompanyContext.Provider>
  );
}

// ============================================================================
// Helper: Create company from onboarding form
// ============================================================================

export interface OnboardingFormData {
  name: string;
  website?: string;
  description: string;
  industry: string;
  goals: string[];
  challenges?: string[];
  competitors: string[];
  targetMarkets?: string[];
  valueProposition?: string;
}

export function createCompanyFromForm(formData: OnboardingFormData, id: string): Company {
  return {
    id,
    name: formData.name,
    website: formData.website || null,
    description: formData.description,
    industry: formData.industry,
    goals: formData.goals,
    challenges: formData.challenges || [],
    competitors: formData.competitors,
    target_markets: formData.targetMarkets || ['Singapore'],
    value_proposition: formData.valueProposition || null,
    // Enriched data (to be populated by Company Enricher agent)
    founded_year: null,
    headquarters: null,
    employee_count: null,
    funding_stage: null,
    tech_stack: [],
    products: [],
    enrichment_confidence: 0,
    last_enriched_at: null,
  };
}
