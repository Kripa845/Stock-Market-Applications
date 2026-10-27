import { useCallback, useEffect, useRef, useState } from 'react';
import { accDistApi, type AccDistPeriod, type AccDistSnapshot } from '../api/accDist';
import { marketApi } from '../api/market';

// Both acc / dist tables for one period, loaded together.  A response for an older period
// is dropped so fast clicking through the period buttons can't show stale rows.

export function useAccDist(period: AccDistPeriod) {
  const [data, setData] = useState<AccDistSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const latest = useRef(0);

  const load = useCallback(() => {
    const id = ++latest.current;
    setLoading(true);
    setError('');
    accDistApi.snapshot(period)
      .then((snapshot) => { if (id === latest.current) setData(snapshot); })
      .catch((err: unknown) => {
        if (id !== latest.current) return;
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(detail ?? 'Unable to load accumulation / distribution data.');
      })
      .finally(() => { if (id === latest.current) setLoading(false); });
  }, [period]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

/** Symbols on the user's default watchlist, for the Watchlist filter.  Empty until loaded. */
export function useWatchlistSymbols() {
  const [symbols, setSymbols] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    let active = true;
    marketApi.watchlist()
      .then((data) => { if (active) setSymbols(new Set(data.rows.map((row) => row.symbol))); })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  return symbols;
}
