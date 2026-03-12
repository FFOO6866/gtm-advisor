/**
 * Company API — fetch and map backend CompanyResponse to the frontend Company type.
 *
 * The backend returns `products` as string[] whereas CompanyContext expects
 * Array<{name, description, type}>. This module bridges that gap.
 */

import { apiClient } from './client';
import type { Company } from '../context/CompanyContext';

interface CompanyApiResponse {
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
  founded_year: string | null;
  headquarters: string | null;
  employee_count: string | null;
  funding_stage: string | null;
  tech_stack: string[];
  products: string[];
  enrichment_confidence: number;
  last_enriched_at: string | null;
}

function toCompany(data: CompanyApiResponse): Company {
  return {
    id: data.id,
    name: data.name,
    website: data.website,
    description: data.description,
    industry: data.industry,
    goals: data.goals ?? [],
    challenges: data.challenges ?? [],
    competitors: data.competitors ?? [],
    target_markets: data.target_markets ?? [],
    value_proposition: data.value_proposition,
    founded_year: data.founded_year,
    headquarters: data.headquarters,
    employee_count: data.employee_count,
    funding_stage: data.funding_stage,
    tech_stack: data.tech_stack ?? [],
    products: (data.products ?? []).map(p => ({ name: p, description: '', type: 'product' })),
    enrichment_confidence: data.enrichment_confidence ?? 0,
    last_enriched_at: data.last_enriched_at,
  };
}

/**
 * Fetch a company by ID from the backend and return as a typed Company.
 * Accessible for both unowned (anonymous teaser) and owned companies.
 */
export async function fetchCompanyById(companyId: string): Promise<Company> {
  const data = await apiClient.get<CompanyApiResponse>(`/companies/${companyId}`);
  return toCompany(data);
}
