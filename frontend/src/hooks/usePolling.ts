import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

interface PollResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Poll an endpoint until a condition is met.
 */
export function usePolling<T>(
  url: string,
  intervalMs: number,
  shouldStop: (data: T) => boolean,
  enabled: boolean = true
): PollResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let active = true;

    const poll = async () => {
      try {
        const result = await api.get<T>(url);
        if (!active) return;
        setData(result);
        setLoading(false);

        if (shouldStop(result)) return;

        // Schedule next poll
        setTimeout(() => {
          if (active) poll();
        }, intervalMs);
      } catch (err: any) {
        if (!active) return;
        setError(err.message);
        setLoading(false);
      }
    };

    poll();
    return () => { active = false; };
  }, [url, enabled, intervalMs]);

  return { data, loading, error };
}

/**
 * Poll paper status until processing is complete.
 */
export function usePaperStatus(paperId: string, initialStatus: string) {
  const shouldPoll = ['pending', 'processing'].includes(initialStatus);

  return usePolling(
    `/api/papers/${paperId}/status`,
    3000,
    (data: { processing_status: string }) =>
      !['pending', 'processing'].includes(data.processing_status),
    shouldPoll
  );
}
