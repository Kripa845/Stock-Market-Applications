// Technical Charts: a full-window trading terminal — the candlestick chart (with its
// indicator, interval, drawing and range tools), a tool rail on the right and the panel
// it opens (watchlist, movers, symbol details, sectors, broker activity).
// The full company dashboard (volume anomalies, news sentiment, behaviour summary,
// company news) still lives in CompanyAnalysisDashboard at /company-analysis.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, AlignJustify, Loader2 } from 'lucide-react';

import TerminalHeader from '../components/technical/TerminalHeader';
import KlinePriceChart, { type PriceLine } from '../components/charts/KlinePriceChart';
import { rangeAvailable, rangeStart } from '../components/charts/chartRanges';
import {
  BrokersPanel, DetailsPanel, MoversPanel, NewsPanel, SectorsPanel, ToolRail, WatchlistPanel,
  companyRow, fmt, indexRow,
  type DailyBar, type ListRow, type PanelId, type Week52,
} from '../components/technical/terminal';
import { getCompanies } from '../api/companies';
import { analysisApi, type PricePoint } from '../api/analysis';
import type { Company } from '../types/company';
import {
  getIndexHistory, getIndexIntraday, getIndexSupportResistance, getIndices, getSubIndices,
  type IndexHistory, type IndexRow,
} from '../api/marketIndices';
import { marketIntelligenceApi, type SupportResistance } from '../api/marketIntelligence';

const SR_STORAGE_KEY = 'technical-sr-lines';
const SR_SUPPORT_COLOR = '#22C55E';
const SR_RESISTANCE_COLOR = '#EF4444';

function changeNote(change: number | null, pct: number | null) {
  if (change === null) return undefined;
  return `${fmt(change, true)} (${fmt(pct, true)}%)`;
}

const num = (value: string | number | null | undefined) => {
  if (value == null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

// The companies API pages by 20; the symbol list needs all of them.
async function allActiveCompanies(): Promise<Company[]> {
  const all: Company[] = [];
  for (let page = 1; ; page += 1) {
    const data = await getCompanies({ status: 'active', page });
    all.push(...data.results);
    if (!data.next) return all;
  }
}

export default function TechnicalCharts() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  // Back to the previous in-app page; opened directly (history index 0) → the user's home page.
  // Symbol changes use replace, so they never add entries that Back would step through.
  const goBack = () =>
    ((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0 ? navigate(-1) : navigate('/role-redirect');
  const indexParam = searchParams.get('index')?.toUpperCase() ?? null;
  const symbolParam = searchParams.get('symbol')?.toUpperCase() ?? null;

  const [companies, setCompanies] = useState<Company[]>([]);
  const [mainIndices, setMainIndices] = useState<IndexRow[]>([]);
  const [subIndices, setSubIndices] = useState<IndexRow[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listVersion, setListVersion] = useState(0);
  const [marketOpen, setMarketOpen] = useState<boolean | null>(null);

  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [indexHistory, setIndexHistory] = useState<IndexHistory | null>(null);
  const [anomalyDates, setAnomalyDates] = useState<string[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState('');

  // Which rail panel is open; wide screens start with the watchlist, narrow ones with the chart only.
  const [panel, setPanel] = useState<PanelId | null>(
    () => (typeof window === 'undefined' || window.innerWidth >= 1024 ? 'watchlist' : null),
  );
  const togglePanel = (id: PanelId) => setPanel((current) => (current === id ? null : id));

  // ── Symbol list ────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setListLoading(true);
    Promise.allSettled([allActiveCompanies(), getIndices(), getSubIndices()]).then(([c, main, sub]) => {
      if (cancelled) return;
      if (c.status === 'fulfilled') setCompanies(c.value);
      else setError('Unable to load companies.');
      setMainIndices(main.status === 'fulfilled' ? main.value.rows : []);
      setMarketOpen(main.status === 'fulfilled' ? main.value.market_open : null);
      setMarketOpen(main.status === 'fulfilled' ? main.value.market_open : null);
      setSubIndices(sub.status === 'fulfilled' ? sub.value.rows : []);
      setListLoading(false);
    });
    return () => { cancelled = true; };
  }, [listVersion]);

  const rows = useMemo(() => [
    ...mainIndices.map((r) => indexRow(r, false)),
    ...subIndices.map((r) => indexRow(r, true)),
    ...companies.map(companyRow),
  ], [mainIndices, subIndices, companies]);
  const sectors = useMemo(
    () => Array.from(new Set(companies.map((c) => c.sector).filter(Boolean))).sort(),
    [companies],
  );


  // ── Current selection (kept in the URL: ?index=NEPSE or ?symbol=NABIL) ─────
  const selected: ListRow | null = useMemo(() => {
    const requested = indexParam
      ? rows.find((r) => r.kind === 'index' && r.code === indexParam)
      : symbolParam ? rows.find((r) => r.kind === 'company' && r.code === symbolParam) : undefined;
    // Default (or an unknown code in the URL): the NEPSE index, else the first company.
    return requested ?? rows.find((r) => r.key === 'index:NEPSE') ?? rows.find((r) => r.kind === 'company') ?? null;
  }, [rows, indexParam, symbolParam]);

  const select = (row: ListRow) =>
    setSearchParams(row.kind === 'index' ? { index: row.code } : { symbol: row.code }, { replace: true });

  // ── Chart data for the selection ───────────────────────────────────────────
  const selectedKey = selected?.key ?? '';
  const selectedCompanyId = selected?.company?.id ?? null;

  const loadChart = useCallback(() => {
    if (!selected) return;
    let cancelled = false;
    setLoadingData(true);
    setError('');
    setPrices([]);
    setIndexHistory(null);
    setAnomalyDates([]);
    const request = selected.kind === 'index'
      ? getIndexHistory(selected.code).then((history) => { if (!cancelled) setIndexHistory(history); })
      : analysisApi.getPrices(selected.company!.id, 'all', { source: 'crawled' })
        .then((result) => { if (!cancelled) setPrices(result.prices); });
    request
      .catch(() => { if (!cancelled) setError(`Unable to load ${selected.code} data. Check your permissions.`); })
      .finally(() => { if (!cancelled) setLoadingData(false); });
    return () => { cancelled = true; };
    // selectedKey identifies the selection; the row object changes on every list refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey]);

  useEffect(() => loadChart(), [loadChart]);

  // Volume-anomaly markers on a company's volume bars (last 6 months, or all data if less).
  const priceDates = useMemo(() => [...new Set(prices.map((p) => p.date))].sort(), [prices]);
  const anomalySymbol = selected?.kind === 'company' ? selected.code : null;
  useEffect(() => {
    if (!anomalySymbol) return;
    const startDate = rangeStart(priceDates, rangeAvailable(priceDates, '6M') ? '6M' : 'All');
    if (!startDate) return;
    let cancelled = false;
    analysisApi.getVolumeAnomalies(anomalySymbol, { start_date: startDate, lookback: 20 })
      .then((result) => { if (!cancelled) setAnomalyDates(result.filter((v) => v.is_anomaly).map((v) => v.date)); })
      .catch(() => { /* markers are optional; the chart still renders */ });
    return () => { cancelled = true; };
  }, [anomalySymbol, priceDates]);

  // Intraday: a company's 1-minute bars come from its timestamped floorsheet trades; an index's
  // from the 5-minute values recorded off NEPSE's live feed (main indices only).
  const selectedIndexCode = selected?.kind === 'index' ? selected.code : null;
  const fetchMinuteBars = useCallback(
    (days: number) => (selectedCompanyId ? analysisApi.getIntradayBars(selectedCompanyId, days)
      : selectedIndexCode ? getIndexIntraday(selectedIndexCode, days)
      : Promise.resolve([])),
    [selectedCompanyId, selectedIndexCode],
  );

  const refresh = () => {
    setListVersion((v) => v + 1);
    loadChart();
  };

  // ── Daily bars + 52-week range for the details panel ───────────────────────
  const dailyBars: DailyBar[] = useMemo(() => {
    if (selected?.kind === 'index') {
      return (indexHistory?.prices ?? []).map((p) => ({
        date: p.date, open: num(p.open), high: num(p.high), low: num(p.low), close: Number(p.close),
        volume: p.volume, turnover: num(p.turnover),
      }));
    }
    return prices.map((p) => ({
      date: p.date, open: num(p.open), high: num(p.high), low: num(p.low), close: Number(p.close),
      volume: p.volume, turnover: num(p.turnover),
    }));
  }, [selected?.kind, indexHistory, prices]);

  const week52: Week52 | null = useMemo(() => {
    if (selected?.kind === 'index') {
      const w = indexHistory?.fifty_two_week;
      return w ? { high: num(w.high), highDate: w.high_date, low: num(w.low), lowDate: w.low_date } : null;
    }
    const last = dailyBars[dailyBars.length - 1];
    if (!last) return null;
    // Same window as the backend's index figure: the 365 days up to the latest session.
    const from = new Date(`${last.date}T00:00:00Z`);
    from.setUTCDate(from.getUTCDate() - 365);
    const start = from.toISOString().slice(0, 10);
    let high: DailyBar | null = null;
    let low: DailyBar | null = null;
    for (const bar of dailyBars) {
      if (bar.date < start) continue;
      if (bar.high !== null && (!high || bar.high > high.high!)) high = bar;
      if (bar.low !== null && (!low || bar.low < low.low!)) low = bar;
    }
    return { high: high?.high ?? null, highDate: high?.date ?? null, low: low?.low ?? null, lowDate: low?.date ?? null };
  }, [selected?.kind, indexHistory, dailyBars]);

  // ── Chart ──────────────────────────────────────────────────────────────────
  const indexWeek52 = indexHistory?.fifty_two_week;
  const indexPriceLines = useMemo(() => [
    { label: `52W H ${fmt(indexWeek52?.high)}`, value: num(indexWeek52?.high) },
    { label: `52W L ${fmt(indexWeek52?.low)}`, value: num(indexWeek52?.low) },
  ], [indexWeek52]);

  // ── Support & resistance levels (companies only; computed nightly by the backend) ──
  const [srOn, setSrOn] = useState(() => {
    try { return localStorage.getItem(SR_STORAGE_KEY) !== 'off'; } catch { return true; }
  });
  const [sr, setSr] = useState<SupportResistance | null>(null);
  const [srState, setSrState] = useState<'idle' | 'loading' | 'missing' | 'error'>('idle');
  const toggleSr = () => setSrOn((on) => {
    try { localStorage.setItem(SR_STORAGE_KEY, on ? 'off' : 'on'); } catch { /* not remembered */ }
    return !on;
  });

  useEffect(() => {
    if (!srOn || (!selectedCompanyId && !selectedIndexCode)) { setSr(null); setSrState('idle'); return; }
    let cancelled = false;
    setSr(null);
    setSrState('loading');
    // Companies: levels computed nightly.  Indices: the same algorithm on stored index history, on request.
    const request: Promise<SupportResistance> = selectedCompanyId
      ? marketIntelligenceApi.getSupportResistance(selectedCompanyId)
      : getIndexSupportResistance(selectedIndexCode!);
    request
      .then((data) => { if (!cancelled) { setSr(data); setSrState('idle'); } })
      .catch((err) => { if (!cancelled) setSrState(err?.response?.status === 404 ? 'missing' : 'error'); });
    return () => { cancelled = true; };
  }, [srOn, selectedCompanyId, selectedIndexCode, listVersion]);

  const srLines: PriceLine[] = useMemo(() => (sr?.levels ?? []).map((level) => ({
    label: `${level.kind === 'support' ? 'S' : 'R'} ${fmt(level.price)} · ${level.touches}×`,
    value: Number(level.price),
    color: level.kind === 'support' ? SR_SUPPORT_COLOR : SR_RESISTANCE_COLOR,
    scale: false,          // a far-away level must not squash the candles
  })), [sr]);

  const srTitle = !srOn ? 'Show support & resistance levels'
    : srState === 'loading' ? 'Loading support & resistance…'
    : srState === 'missing' ? 'Support & resistance has not been computed for this company yet'
    : srState === 'error' ? 'Unable to load support & resistance levels'
    : sr?.status === 'insufficient_history'
      ? `Not enough history${sr.adjustment_cut ? ` since the price adjustment on ${sr.adjustment_cut}` : ''} (${sr.sessions_used} sessions)`
    : sr?.status === 'no_levels' ? 'No level was touched twice in the last year'
    : sr ? `${sr.levels.length} levels as of ${sr.as_of}: swing highs/lows (±${sr.params.pivot_window} bars) `
      + `within ${sr.params.tolerance_pct}% of each other, at least ${sr.params.min_touches} touches. Not investment advice.`
    : '';
  const srProblem = srOn && (srState === 'missing' || srState === 'error' || (sr !== null && sr.status !== 'ok'));

  // Shown on every chart so the feature is discoverable; levels exist for companies only.
  const srAvailable = Boolean(selected);
  const srChecked = srAvailable && srOn;
  const srButton = (
    <button
      type="button"
      role="switch"
      onClick={toggleSr}
      disabled={!srAvailable}
      aria-checked={srChecked}
      title={srAvailable ? srTitle : 'Pick a symbol from the Watchlist.'}
      className="flex h-9 items-center gap-2.5 rounded-lg border border-bg-border px-3 text-[13px] font-medium text-text-secondary transition-colors enabled:hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
    >
      <AlignJustify size={15} />
      S&amp;R lines
      {srOn && srState === 'loading' && <Loader2 size={12} className="animate-spin" />}
      {srProblem && <span aria-hidden="true" className="rounded-full bg-amber-500/20 px-1.5 text-[10px] text-amber-400">!</span>}
      <span className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${srChecked ? 'bg-up' : 'bg-bg-elevated ring-1 ring-inset ring-bg-border'}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${srChecked ? 'left-[18px]' : 'left-0.5'}`} />
      </span>
    </button>
  );

  let chart: React.ReactNode = null;
  if (selected?.kind === 'index' && indexHistory && indexHistory.prices.length > 0) {
    const latest = indexHistory.latest;
    chart = (
      <KlinePriceChart
        prices={indexHistory.prices}
        symbol={indexHistory.name}
        indexCode={selected.code}
        fetchMinuteBars={fetchMinuteBars}
        priceLines={srOn ? [...indexPriceLines, ...srLines] : indexPriceLines}
        lastPriceNote={changeNote(num(latest?.change), num(latest?.change_pct))}
        toolbarExtra={srButton}
      />
    );
  } else if (selected?.kind === 'company' && prices.length > 0) {
    const last = dailyBars[dailyBars.length - 1];
    const prev = dailyBars[dailyBars.length - 2];
    const ch = prev ? last.close - prev.close : null;
    const pct = ch !== null && prev?.close ? (ch / prev.close) * 100 : null;
    chart = (
      <KlinePriceChart
        prices={prices}
        symbol={selected.code}
        anomalyDates={anomalyDates}
        fetchMinuteBars={fetchMinuteBars}
        companyId={selected.company!.id}
        lastPriceNote={changeNote(ch, pct)}
        priceLines={srOn ? srLines : undefined}
        toolbarExtra={srButton}
      />
    );
  }

  const emptyMessage = listLoading ? null
    : !selected ? 'Pick a symbol from the watchlist.'
    : loadingData ? null
    : `No stored price data for ${selected.code} yet.`;

  const panelContent = {
    watchlist: (
      <WatchlistPanel rows={rows} sectors={sectors} selectedKey={selected?.key} loading={listLoading} onSelect={select} />
    ),
    movers: <MoversPanel rows={rows} selectedKey={selected?.key} onSelect={select} />,
    details: <DetailsPanel row={selected} bars={dailyBars} week52={week52} loading={loadingData} />,
    sectors: <SectorsPanel rows={rows} selectedKey={selected?.key} onSelect={select} />,
    brokers: <BrokersPanel row={selected} />,
    news: <NewsPanel row={selected} />,
  } satisfies Record<PanelId, React.ReactNode>;

  return (
    // Rendered outside the app Layout: the terminal owns the whole window.
    <div className="flex h-screen min-h-[560px] flex-col overflow-hidden bg-bg-primary">
      {/* ── Top bar: back, the selected symbol and price, search, market status ── */}
      <TerminalHeader
        selected={selected}
        rows={rows}
        marketOpen={marketOpen}
        busy={listLoading || loadingData}
        onBack={goBack}
        onRefresh={refresh}
        onSelect={select}
      />

      <div className="relative flex min-h-0 flex-1">
        {/* ── Chart ───────────────────────────────────────────────────────── */}
        <section className="relative flex min-w-0 flex-1 flex-col" aria-label="Chart">
          {chart ?? (
            <div className="flex flex-1 items-center justify-center text-sm text-text-muted">
              {emptyMessage ?? <Loader2 size={24} className="animate-spin text-accent" />}
            </div>
          )}

          {chart && loadingData && (
            <div className="pointer-events-none absolute right-3 top-12 flex items-center gap-1.5 rounded bg-bg-elevated px-2 py-1 text-[11px] text-text-muted">
              <Loader2 size={11} className="animate-spin" /> Loading…
            </div>
          )}

          {error && (
            <div role="alert" className="absolute left-1/2 top-12 z-10 flex -translate-x-1/2 items-center gap-2 rounded border border-down/30 bg-bg-secondary px-3 py-2 text-xs text-down shadow-lg">
              <AlertTriangle size={13} /> {error}
            </div>
          )}
        </section>

        {/* ── Open panel (overlays the chart on narrow screens) ───────────── */}
        {panel && (
          <aside
            className="absolute inset-y-0 right-[68px] z-20 w-[380px] max-w-[calc(100vw-5rem)] border-l border-bg-border bg-bg-secondary shadow-xl lg:static lg:shadow-none"
            aria-label={panel}
          >
            {panelContent[panel]}
          </aside>
        )}

        {/* ── Tool rail ───────────────────────────────────────────────────── */}
        <ToolRail active={panel} onSelect={togglePanel} />
      </div>
    </div>
  );
}
