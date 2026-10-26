import { useCallback, useEffect, useRef, useState } from 'react';
import { marketApi, type HeatmapResponse } from '../api/market';

// Data hook for the watchlist heatmap (/api/market/heatmap/).

const OPEN_POLL_MS = 60_000;        // while the session is open
const CLOSED_POLL_MS = 5 * 60_000;  // otherwise, slowly, so the map notices the session opening

export function useHeatmap() {
  const [data, setData] = useState<HeatmapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const latest = useRef(0);

  const load = useCallback((quiet = false) => {
    const id = ++latest.current;
    if (!quiet) setLoading(true);
    marketApi.heatmap()
      .then((response) => { if (id === latest.current) { setData(response); setError(false); } })
      // A failed background refresh keeps the last map on screen.
      .catch(() => { if (id === latest.current && !quiet) setError(true); })
      .finally(() => { if (id === latest.current) setLoading(false); });
  }, []);

  useEffect(() => { load(); }, [load]);

  const open = data?.market_open ?? false;
  useEffect(() => {
    const timer = window.setInterval(() => load(true), open ? OPEN_POLL_MS : CLOSED_POLL_MS);
    return () => window.clearInterval(timer);
  }, [load, open]);

  return { data, loading, error, reload: load };
}
