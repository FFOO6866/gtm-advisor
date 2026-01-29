/**
 * Custom React Hooks for API Data Fetching
 *
 * Provides loading states, error handling, and caching for API calls.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface UseApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  isValidating: boolean;
}

export interface UseApiOptions<T> {
  initialData?: T;
  revalidateOnFocus?: boolean;
  revalidateOnReconnect?: boolean;
  refreshInterval?: number;
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
}

export interface UseApiReturn<T> extends UseApiState<T> {
  mutate: (data?: T | ((current: T | null) => T)) => void;
  refresh: () => Promise<void>;
}

// ============================================================================
// Simple Cache
// ============================================================================

const cache = new Map<string, { data: unknown; timestamp: number }>();
const CACHE_TTL = 30000; // 30 seconds

function getCached<T>(key: string): T | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > CACHE_TTL) {
    cache.delete(key);
    return null;
  }
  return entry.data as T;
}

function setCache<T>(key: string, data: T): void {
  cache.set(key, { data, timestamp: Date.now() });
}

export function clearCache(keyPattern?: string): void {
  if (!keyPattern) {
    cache.clear();
    return;
  }
  for (const key of cache.keys()) {
    if (key.includes(keyPattern)) {
      cache.delete(key);
    }
  }
}

// ============================================================================
// useApi Hook
// ============================================================================

export function useApi<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  options: UseApiOptions<T> = {}
): UseApiReturn<T> {
  const {
    initialData,
    revalidateOnFocus = true,
    revalidateOnReconnect = true,
    refreshInterval,
    onSuccess,
    onError,
  } = options;

  const [state, setState] = useState<UseApiState<T>>({
    data: initialData ?? (key ? getCached<T>(key) : null),
    isLoading: !initialData && !getCached<T>(key ?? ''),
    error: null,
    isValidating: false,
  });

  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const fetchData = useCallback(
    async (isValidating = false) => {
      if (!key) return;

      setState((prev) => ({
        ...prev,
        isLoading: !prev.data && !isValidating,
        isValidating,
        error: null,
      }));

      try {
        const data = await fetcherRef.current();

        if (!mountedRef.current) return;

        setCache(key, data);
        setState({
          data,
          isLoading: false,
          error: null,
          isValidating: false,
        });
        onSuccess?.(data);
      } catch (err) {
        if (!mountedRef.current) return;

        const error = err instanceof Error ? err : new Error(String(err));
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error,
          isValidating: false,
        }));
        onError?.(error);
      }
    },
    [key, onSuccess, onError]
  );

  // Initial fetch
  useEffect(() => {
    if (key) {
      fetchData();
    }
  }, [key, fetchData]);

  // Revalidate on focus
  useEffect(() => {
    if (!revalidateOnFocus || !key) return;

    const onFocus = () => {
      fetchData(true);
    };

    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [revalidateOnFocus, key, fetchData]);

  // Revalidate on reconnect
  useEffect(() => {
    if (!revalidateOnReconnect || !key) return;

    const onOnline = () => {
      fetchData(true);
    };

    window.addEventListener('online', onOnline);
    return () => window.removeEventListener('online', onOnline);
  }, [revalidateOnReconnect, key, fetchData]);

  // Refresh interval
  useEffect(() => {
    if (!refreshInterval || !key) return;

    const interval = setInterval(() => {
      fetchData(true);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, key, fetchData]);

  // Cleanup
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const mutate = useCallback(
    (newData?: T | ((current: T | null) => T)) => {
      if (!key) return;

      const data =
        typeof newData === 'function'
          ? (newData as (current: T | null) => T)(state.data)
          : newData;

      if (data !== undefined) {
        setCache(key, data);
        setState((prev) => ({ ...prev, data }));
      } else {
        // Revalidate
        fetchData(true);
      }
    },
    [key, state.data, fetchData]
  );

  const refresh = useCallback(async () => {
    await fetchData(true);
  }, [fetchData]);

  return {
    ...state,
    mutate,
    refresh,
  };
}

// ============================================================================
// useMutation Hook
// ============================================================================

export interface UseMutationState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
}

export interface UseMutationOptions<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
  invalidateKeys?: string[];
}

export interface UseMutationReturn<TData, TVariables> extends UseMutationState<TData> {
  mutate: (variables: TVariables) => Promise<TData | undefined>;
  reset: () => void;
}

export function useMutation<TData, TVariables>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options: UseMutationOptions<TData> = {}
): UseMutationReturn<TData, TVariables> {
  const { onSuccess, onError, invalidateKeys } = options;

  const [state, setState] = useState<UseMutationState<TData>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: TVariables): Promise<TData | undefined> => {
      setState({ data: null, isLoading: true, error: null });

      try {
        const data = await mutationFn(variables);
        setState({ data, isLoading: false, error: null });

        // Invalidate cache
        if (invalidateKeys) {
          invalidateKeys.forEach((key) => clearCache(key));
        }

        onSuccess?.(data);
        return data;
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        setState({ data: null, isLoading: false, error });
        onError?.(error);
        return undefined;
      }
    },
    [mutationFn, onSuccess, onError, invalidateKeys]
  );

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return {
    ...state,
    mutate,
    reset,
  };
}

// ============================================================================
// Workspace-specific hooks
// ============================================================================

import * as api from '../api/workspaces';

// Competitors
export function useCompetitors(companyId: string | null) {
  return useApi(
    companyId ? `competitors-${companyId}` : null,
    () => api.listCompetitors(companyId!),
    { revalidateOnFocus: true }
  );
}

export function useCompetitor(companyId: string | null, competitorId: string | null) {
  return useApi(
    companyId && competitorId ? `competitor-${competitorId}` : null,
    () => api.getCompetitor(companyId!, competitorId!)
  );
}

export function useBattleCard(companyId: string | null, competitorId: string | null) {
  return useApi(
    companyId && competitorId ? `battlecard-${competitorId}` : null,
    () => api.getBattleCard(companyId!, competitorId!)
  );
}

// ICPs
export function useICPs(companyId: string | null) {
  return useApi(
    companyId ? `icps-${companyId}` : null,
    () => api.listICPs(companyId!),
    { revalidateOnFocus: true }
  );
}

export function useICP(companyId: string | null, icpId: string | null) {
  return useApi(
    companyId && icpId ? `icp-${icpId}` : null,
    () => api.getICP(companyId!, icpId!)
  );
}

// Leads
export function useLeads(
  companyId: string | null,
  options?: Parameters<typeof api.listLeads>[1]
) {
  const key = companyId
    ? `leads-${companyId}-${JSON.stringify(options || {})}`
    : null;
  return useApi(key, () => api.listLeads(companyId!, options), {
    revalidateOnFocus: true,
  });
}

export function useLead(companyId: string | null, leadId: string | null) {
  return useApi(
    companyId && leadId ? `lead-${leadId}` : null,
    () => api.getLead(companyId!, leadId!)
  );
}

// Campaigns
export function useCampaigns(
  companyId: string | null,
  options?: Parameters<typeof api.listCampaigns>[1]
) {
  const key = companyId
    ? `campaigns-${companyId}-${JSON.stringify(options || {})}`
    : null;
  return useApi(key, () => api.listCampaigns(companyId!, options), {
    revalidateOnFocus: true,
  });
}

export function useCampaign(companyId: string | null, campaignId: string | null) {
  return useApi(
    companyId && campaignId ? `campaign-${campaignId}` : null,
    () => api.getCampaign(companyId!, campaignId!)
  );
}

// Insights
export function useInsights(
  companyId: string | null,
  options?: Parameters<typeof api.listInsights>[1]
) {
  const key = companyId
    ? `insights-${companyId}-${JSON.stringify(options || {})}`
    : null;
  return useApi(key, () => api.listInsights(companyId!, options), {
    revalidateOnFocus: true,
    refreshInterval: 60000, // Refresh every minute
  });
}

export function useInsightsSummary(companyId: string | null) {
  return useApi(
    companyId ? `insights-summary-${companyId}` : null,
    () => api.getInsightsSummary(companyId!),
    { refreshInterval: 60000 }
  );
}

// Settings
export function useUserSettings(userId: string | null) {
  return useApi(
    userId ? `settings-${userId}` : null,
    () => api.getUserSettings(userId!)
  );
}

export function useUsageStats(userId: string | null) {
  return useApi(
    userId ? `usage-${userId}` : null,
    () => api.getUsageStats(userId!),
    { refreshInterval: 30000 }
  );
}
