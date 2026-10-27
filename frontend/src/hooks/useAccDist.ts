import { useCallback, useEffect, useRef, useState } from 'react';
import { accDistApi, type AccDistPeriod, type AccDistSnapshot } from '../api/accDist';

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
      .catch(() => { if (id === latest.current) setError('Unable to load accumulation / distribution data.'); })
      .finally(() => { if (id === latest.current) setLoading(false); });
  }, [period]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

/** The user's saved symbols, for the Watchlist filter.  Empty until loaded. */
export function useWatchlistSymbols() {
  const [symbols, setSymbols] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    let active = true;
    accDistApi.watchlistSymbols()
      .then((list) => { if (active) setSymbols(new Set(list)); })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  return symbols;
}
