import { useCallback, useEffect, useRef, useState } from 'react';
import { marketApi, type MarketOverview, type OverviewChart, type OverviewRange, type TechnicalAnalysis } from '../api/market';

// Data hooks for the Market Overview card. All data comes from Django (/api/market/overview/...).

const OPEN_POLL_MS = 60_000;        // while the session is open
const CLOSED_POLL_MS = 5 * 60_000;  // otherwise, slowly, so the card notices the session opening

type State<T> = { data: T | null; loading: boolean; error: boolean };

function useRequest<T>(load: () => Promise<T>, enabled = true) {
  const [state, setState] = useState<State<T>>({ data: null, loading: enabled, error: false });
  const latest = useRef(0);

  const run = useCallback((quiet = false) => {
    const id = ++latest.current;
    if (!quiet) setState((s) => ({ ...s, loading: true, error: false }));
    load()
      .then((data) => { if (id === latest.current) setState({ data, loading: false, error: false }); })
      .catch(() => { if (id === latest.current) setState((s) => ({ ...s, loading: false, error: true })); });
  }, [load]);

  useEffect(() => { if (enabled) run(); }, [enabled, run]);
  return { ...state, reload: run };
}

/** Header quote + tracked-company stats, polled every 60s while the market is open. */
export function useMarketOverview(symbol: string) {
  const load = useCallback(() => marketApi.overview(symbol), [symbol]);
  const request = useRequest<MarketOverview>(load);
  const { reload } = request;
  const status = request.data?.status;

  useEffect(() => {
    const timer = window.setInterval(() => reload(true), status === 'OPEN' ? OPEN_POLL_MS : CLOSED_POLL_MS);
    return () => window.clearInterval(timer);
  }, [reload, status]);

  return request;
}

/** Chart points for the picked instrument and range. */
export function useMarketChart(symbol: string, range: OverviewRange) {
  const load = useCallback(() => marketApi.overviewChart(symbol, range), [symbol, range]);
  return useRequest<OverviewChart>(load);
}

/** Technical summary; nothing is requested until ``enabled`` is first true for this symbol. */
export function useMarketTechnical(symbol: string, enabled: boolean) {
  const load = useCallback(() => marketApi.overviewTechnical(symbol), [symbol]);
  const [requested, setRequested] = useState<string | null>(null);
  useEffect(() => { if (enabled) setRequested(symbol); }, [enabled, symbol]);
  return useRequest<TechnicalAnalysis>(load, requested === symbol);
}
