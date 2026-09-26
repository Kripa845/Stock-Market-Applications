import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, ComposedChart, Line,
  XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell, Customized, useXAxisScale, useYAxisScale,
} from 'recharts';
import {
  Activity, AlertTriangle,
  BarChart3, Loader2, Newspaper,
  RefreshCw, TrendingUp, Zap,
} from 'lucide-react';
import clsx from 'clsx';

import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import NewsMarketReaction from '../components/analysis/NewsMarketReaction';
import { getCompanies } from '../api/companies';
import {
  analysisApi,
  type BehaviorSummary,
  type CategorizedCompanyNews,
  type NewsPriceCorrelation,
  type PricePoint,
} from '../api/analysis';
import type { Company } from '../types/company';

// ─── Shared chart style ───────────────────────────────────────────────────────
const TT_STYLE = {
  background: 'var(--trading-panel)',
  border: '1px solid var(--trading-divider)',
  borderRadius: 3,
  fontSize: 12,
  color: 'var(--trading-text-primary)',
};

const COLORS = {
  volume:  'var(--trading-up)',
  anomaly: 'var(--trading-down)',
  buy:     'var(--trading-up)',
  sell:    'var(--trading-down)',
  neutral: 'var(--trading-muted)',
};

function fmt(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatPill({
  label, value, sub, color = 'text-text-primary',
}: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-[90px]">
      <span className="text-[10px] uppercase tracking-widest text-text-muted">{label}</span>
      <span className={clsx('text-base font-bold font-mono', color)}>{value}</span>
      {sub && <span className="text-[11px] text-text-muted">{sub}</span>}
    </div>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={15} className="text-accent-light shrink-0" />
      <h3 className="text-sm font-semibold text-text-primary">{children}</h3>
    </div>
  );
}

// ─── Pressure gauge (numeric arc visual) ─────────────────────────────────────
// ─── Volume chart with anomaly highlighting ───────────────────────────────────
function VolumeChart({
  data, avgVol, threshold,
}: {
  data: { date: string; volume: number }[];
  avgVol: number;
  threshold: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={130}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--trading-grid)" strokeOpacity={0.65} vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 9, fill: 'var(--trading-muted)' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 9, fill: 'var(--trading-muted)' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={fmt}
          width={38}
        />
        <Tooltip
          contentStyle={TT_STYLE}
          cursor={{ stroke: 'var(--trading-grid)', strokeDasharray: '2 4' }}
          formatter={(v: unknown) => [fmt(Number(v ?? 0)), 'Volume']}
        />
        <ReferenceLine
          y={avgVol}
          stroke="var(--trading-muted)"
          strokeDasharray="4 2"
          label={{ value: 'avg', position: 'right', fill: 'var(--trading-muted)', fontSize: 9 }}
        />
        <ReferenceLine
          y={threshold}
          stroke={COLORS.anomaly}
          strokeDasharray="4 2"
          label={{ value: '×1.5σ', position: 'right', fill: COLORS.anomaly, fontSize: 9 }}
        />
        <Bar dataKey="volume" radius={[2, 2, 0, 0]} maxBarSize={8}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.volume >= threshold ? COLORS.anomaly : COLORS.volume} opacity={0.75} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Price + VWAP combined chart ──────────────────────────────────────────────
function CandleLayer({ data }: { data: PricePoint[] }) {
  const xScale = useXAxisScale('date');
  const yScale = useYAxisScale('price');
  if (!xScale || !yScale || data.length === 0) return null;
  const centers = data.map(d => xScale(d.date, { position: 'middle' }));
  const pitches = centers.slice(1).flatMap((x, i) => x !== undefined && centers[i] !== undefined ? [Math.abs(x - centers[i])] : []);
  const bodyWidth = Math.max(2, Math.min(12, (pitches.length ? Math.min(...pitches) : 10) * 0.62));
  const vwapPoints = data.flatMap((point, i) => {
    const x = centers[i];
    const value = point.volume > 0 ? Number(point.turnover) / point.volume : Number(point.close);
    const y = yScale(value);
    return x !== undefined && y !== undefined ? [`${x},${y}`] : [];
  }).join(' ');
  return <g aria-hidden="true"><polyline points={vwapPoints} fill="none" stroke="var(--trading-accent)" strokeWidth={1.7} strokeLinejoin="round" strokeLinecap="round" />{data.map((point, i) => {
    const x = centers[i];
    const open = yScale(Number(point.open));
    const close = yScale(Number(point.close));
    const high = yScale(Number(point.high));
    const low = yScale(Number(point.low));
    if (x === undefined || open === undefined || close === undefined || high === undefined || low === undefined) return null;
    const up = Number(point.close) >= Number(point.open);
    const color = up ? COLORS.buy : COLORS.sell;
    return <g key={point.id}><line x1={x} x2={x} y1={high} y2={low} stroke={color} strokeWidth={1} /><rect x={x - bodyWidth / 2} y={Math.min(open, close)} width={bodyWidth} height={Math.max(1, Math.abs(close - open))} fill={color} /></g>;
  })}</g>;
}

function OhlcTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload?: PricePoint }>; label?: string }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  const up = Number(point.close) >= Number(point.open);
  return <div className="rounded-sm border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-lg">
    <p className="mb-1 text-text-muted">{label}</p>
    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono tabular-nums">
      <span className="text-text-muted">O</span><span>{Number(point.open).toFixed(2)}</span>
      <span className="text-text-muted">H</span><span>{Number(point.high).toFixed(2)}</span>
      <span className="text-text-muted">L</span><span>{Number(point.low).toFixed(2)}</span>
      <span className="text-text-muted">C</span><span style={{ color: up ? COLORS.buy : COLORS.sell }}>{Number(point.close).toFixed(2)}</span>
      <span className="text-text-muted">VWAP</span><span className="text-accent-light">{(point.volume > 0 ? Number(point.turnover) / point.volume : Number(point.close)).toFixed(2)}</span>
      <span className="text-text-muted">Vol</span><span>{fmt(point.volume)}</span>
    </div>
  </div>;
}

function buildIndicatorData(data: PricePoint[]) {
  const raw = data.map(point => {
    const high = Number(point.high);
    const low = Number(point.low);
    const close = Number(point.close);
    const range = high - low;
    return {
      date: point.date,
      close,
      vwap: point.volume > 0 ? Number(point.turnover) / point.volume : close,
      volume: point.volume,
      buyShare: range > 0 ? Math.max(0, Math.min(1, (close - low) / range)) : 0.5,
    };
  });
  return raw.map((point, index) => {
    const window = raw.slice(Math.max(0, index - 13), index + 1);
    const totalVolume = window.reduce((sum, row) => sum + row.volume, 0);
    const buyingVolume = window.reduce((sum, row) => sum + row.volume * row.buyShare, 0);
    const buyPressure = totalVolume > 0 ? buyingVolume / totalVolume : 0.5;
    return { ...point, buyPressure, sellPressure: 1 - buyPressure };
  });
}

function TradingViewChart({ data }: { data: PricePoint[] }) {
  const indicators = buildIndicatorData(data);
  const latestIndicator = indicators[indicators.length - 1];
  const lowest = data.length ? Math.min(...data.map(p => Number(p.low))) : 0;
  const highest = data.length ? Math.max(...data.map(p => Number(p.high))) : 1;
  const pad = (highest - lowest) * 0.04 || 1;
  return <div className="space-y-0.5">
    <div className="flex items-center gap-2 px-1 pb-1 text-[11px]"><span className="text-text-muted">O H L C</span>{data.length > 0 && <span className="font-mono tabular-nums text-text-primary">{Number(data[data.length - 1].close).toFixed(2)}</span>}<span className="ml-auto text-text-muted">VWAP <span className="font-mono tabular-nums text-accent-light">{latestIndicator?.vwap.toFixed(2) ?? '?'}</span></span></div>
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.65} vertical />
        <XAxis xAxisId="date" dataKey="date" hide />
        <YAxis yAxisId="price" domain={[lowest - pad, highest + pad]} orientation="right" tick={{ fontSize: 10, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={52} tickFormatter={v => Number(v).toFixed(2)} />
        <Tooltip content={<OhlcTooltip />} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '2 4', strokeWidth: 1 }} />
        <Bar xAxisId="date" yAxisId="price" dataKey="close" fill="transparent" stroke="transparent" isAnimationActive={false} />
        <Customized component={<CandleLayer data={data} />} />
      </ComposedChart>
    </ResponsiveContainer>
    <div className="flex items-center gap-2 px-1 pt-1 text-[11px]"><span className="text-text-muted">Volume</span>{data.length > 0 && <span className="font-mono tabular-nums text-up">{fmt(data[data.length - 1].volume)}</span>}</div>
    <ResponsiveContainer width="100%" height={90}>
      <BarChart data={data} margin={{ top: 0, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.5} vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis orientation="right" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={52} tickFormatter={fmt} />
        <Tooltip contentStyle={TT_STYLE} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '2 4' }} formatter={(v: unknown) => [fmt(Number(v ?? 0)), 'Volume']} />
        <Bar dataKey="volume" maxBarSize={10} isAnimationActive={false}>{data.map(point => <Cell key={point.id} fill={Number(point.close) >= Number(point.open) ? COLORS.buy : COLORS.sell} opacity={0.8} />)}</Bar>
      </BarChart>
    </ResponsiveContainer>

    <div className="flex items-center gap-3 border-t border-bg-border px-1 pt-2 text-[11px]">
      <span className="text-text-muted">Buy / Sell Pressure</span>
      <span className="font-mono tabular-nums text-up">Buy {latestIndicator ? (latestIndicator.buyPressure * 100).toFixed(0) : '—'}%</span>
      <span className="font-mono tabular-nums text-down">Sell {latestIndicator ? (latestIndicator.sellPressure * 100).toFixed(0) : '—'}%</span>
      <span className="ml-auto text-[10px] text-text-muted">14-bar OHLCV estimate</span>
    </div>
    <ResponsiveContainer width="100%" height={120}>
      <ComposedChart data={indicators} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.55} vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis orientation="right" domain={[0, 1]} ticks={[0, 0.5, 1]} tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={52} tickFormatter={v => `${Math.round(Number(v) * 100)}%`} />
        <Tooltip contentStyle={TT_STYLE} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '2 4' }} formatter={(v: unknown, name: unknown) => [`${(Number(v ?? 0) * 100).toFixed(1)}%`, String(name)]} />
        <Line type="monotone" dataKey="buyPressure" name="Buy pressure" stroke="var(--trading-up)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey="sellPressure" name="Sell pressure" stroke="var(--trading-down)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  </div>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function computeVolumeStats(prices: PricePoint[]) {
  if (!prices.length) return { avg: 0, std: 0, threshold: 0 };
  const vols = prices.map(p => p.volume);
  const avg  = vols.reduce((s, v) => s + v, 0) / vols.length;
  const std  = Math.sqrt(vols.reduce((s, v) => s + (v - avg) ** 2, 0) / vols.length);
  return { avg, std, threshold: avg + 1.5 * std };
}

function computeVwap(prices: PricePoint[]) {
  const totalTurnover = prices.reduce((s, p) => s + parseFloat(p.turnover), 0);
  const totalVolume   = prices.reduce((s, p) => s + p.volume, 0);
  return totalVolume ? totalTurnover / totalVolume : 0;
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CompanyAnalysisDashboard() {
  const [companies,   setCompanies]   = useState<Company[]>([]);
  const [selectedId,  setSelectedId]  = useState<number | null>(null);
  const [prices,      setPrices]      = useState<PricePoint[]>([]);
  const [behavior,    setBehavior]    = useState<BehaviorSummary | null>(null);
  const [correlation, setCorrelation] = useState<NewsPriceCorrelation | null>(null);
  const [categorizedNews, setCategorizedNews] = useState<CategorizedCompanyNews[] | null>(null);
  const [priceRange,  setPriceRange]  = useState<'7d' | '30d' | '90d'>('30d');
  const [loading,     setLoading]     = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error,       setError]       = useState('');

  // Load company list once
  useEffect(() => {
    getCompanies({ status: 'active' })
      .then(r => {
        setCompanies(r.results);
        setSelectedId(r.results[0]?.id ?? null);
      })
      .catch(() => setError('Unable to load companies.'))
      .finally(() => setLoading(false));
  }, []);

  // Load all per-company data when selection or range changes
  const loadData = useCallback(() => {
    if (!selectedId) return;
    setLoadingData(true);
    setError('');
    setCategorizedNews(null);
    Promise.allSettled([
      analysisApi.getPrices(selectedId, priceRange),
      analysisApi.getBehavior(selectedId),
      analysisApi.getNewsCorrelation(selectedId),
      analysisApi.getCategorizedCompanyNews(selectedId),
    ]).then(([prRes, bhRes, corrRes, newsRes]) => {
      if (prRes.status   === 'fulfilled') setPrices(prRes.value.prices);
      if (bhRes.status   === 'fulfilled') setBehavior(bhRes.value);
      if (corrRes.status === 'fulfilled') setCorrelation(corrRes.value);
      if (newsRes.status === 'fulfilled') setCategorizedNews(newsRes.value.results);
      // surface any hard errors
      const failed = [prRes, bhRes, corrRes, newsRes].filter(r => r.status === 'rejected');
      if (failed.length === 4) setError('Unable to load company data. Check your permissions.');
    }).finally(() => setLoadingData(false));
  }, [selectedId, priceRange]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Derived values ──────────────────────────────────────────────────────────
  const company  = companies.find(c => c.id === selectedId);
  const { avg: avgVol, threshold } = useMemo(() => computeVolumeStats(prices), [prices]);
  const vwap30   = useMemo(() => computeVwap(prices), [prices]);

  const anomalyDays = useMemo(
    () => prices.filter(p => p.volume >= threshold),
    [prices, threshold],
  );

  const volumeChartData = useMemo(
    () => prices.map(p => ({ date: p.date.slice(5), volume: p.volume })),
    [prices],
  );

  const latestClose = prices.length ? parseFloat(prices[prices.length - 1].close) : 0;
  const firstClose  = prices.length ? parseFloat(prices[0].close) : 0;
  const positive    = latestClose >= firstClose;
  const spreadPct   = vwap30 ? ((latestClose - vwap30) / vwap30 * 100) : 0;

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={28} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="trading-terminal-page space-y-6">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <PageHeader
        title="Company Behavior Analysis"
        subtitle="Price / volume trends, VWAP, broker activity, and categorized news market reaction."
        actions={
          <button
            onClick={loadData}
            disabled={loadingData}
            className="btn-ghost flex items-center gap-2 text-xs"
          >
            <RefreshCw size={13} className={loadingData ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="flex items-center gap-2 text-sm text-down">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* ── Company selector ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        {companies.map(c => (
          <button
            key={c.id}
            onClick={() => setSelectedId(c.id)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all',
              c.id === selectedId
                ? 'bg-accent text-white shadow-md'
                : 'bg-bg-elevated text-text-secondary hover:text-text-primary hover:bg-bg-card',
            )}
          >
            {c.symbol}
          </button>
        ))}
      </div>

      {/* ── Company header card ───────────────────────────────────────────── */}
      {company && (
        <div className="card flex flex-wrap items-center gap-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-accent/20 flex items-center justify-center font-bold font-mono text-accent-light text-sm">
              {company.symbol.slice(0, 3)}
            </div>
            <div>
              <p className="font-semibold text-text-primary text-base">{company.symbol}</p>
              <p className="text-xs text-text-muted">{company.name}</p>
            </div>
          </div>

          <Badge variant="gray">{company.sector}</Badge>

          <div className="flex flex-wrap gap-5 ml-auto">
            <StatPill
              label="Latest close"
              value={`Rs. ${latestClose.toFixed(2)}`}
              color={positive ? 'text-up' : 'text-down'}
            />
            <StatPill
              label={`${priceRange} change`}
              value={`${positive ? '+' : ''}${firstClose ? ((latestClose - firstClose) / firstClose * 100).toFixed(2) : 0}%`}
              color={positive ? 'text-up' : 'text-down'}
            />
            <StatPill
              label="VWAP 30d"
              value={`Rs. ${vwap30.toFixed(2)}`}
              color="text-yellow-400"
            />
            <StatPill
              label="vs VWAP"
              value={`${spreadPct >= 0 ? '+' : ''}${spreadPct.toFixed(2)}%`}
              color={spreadPct >= 0 ? 'text-up' : 'text-down'}
              sub={spreadPct >= 0 ? 'Above VWAP' : 'Below VWAP'}
            />
            <StatPill
              label="Anomaly days"
              value={anomalyDays.length}
              color={anomalyDays.length > 0 ? 'text-down' : 'text-text-primary'}
              sub="vol > avg+1.5σ"
            />
          </div>
        </div>
      )}

      {loadingData && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Loader2 size={12} className="animate-spin" /> Loading data…
        </div>
      )}

      {/* ── Range selector ───────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 bg-bg-elevated rounded-lg p-0.5 w-fit">
        {(['7d', '30d', '90d'] as const).map(r => (
          <button
            key={r}
            onClick={() => setPriceRange(r)}
            className={clsx(
              'px-4 py-1.5 rounded text-xs font-medium transition-all',
              priceRange === r
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {r === '7d' ? '1W' : r === '30d' ? '1M' : '3M'}
          </button>
        ))}
      </div>

      {prices.length === 0 && !loadingData ? (
        <div className="card py-16 text-center">
          <p className="text-sm text-text-muted">No price data available for this company.</p>
        </div>
      ) : (
        <>
          {/* TradingView-style price and volume chart */}
          <div className="card space-y-2">
            <SectionTitle icon={TrendingUp}>Price Action</SectionTitle>
            <TradingViewChart data={prices} />
          </div>

          {/* ── Row 2: Volume chart with anomalies ─────────────────────── */}
          <div className="card">
            <div className="flex items-start justify-between mb-3 flex-wrap gap-3">
              <SectionTitle icon={BarChart3}>Daily Volume with Anomaly Detection</SectionTitle>
              <div className="flex items-center gap-4 text-xs text-text-muted flex-wrap">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS.volume, opacity: 0.75 }} />
                  Normal
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS.anomaly, opacity: 0.75 }} />
                  Anomaly (&gt; avg + 1.5σ)
                </span>
                <span className="text-[10px] text-text-muted border border-bg-border rounded px-1.5 py-0.5">
                  Threshold: {fmt(Math.round(threshold))}
                </span>
                <span className="text-[10px] text-text-muted border border-bg-border rounded px-1.5 py-0.5">
                  Avg: {fmt(Math.round(avgVol))}
                </span>
              </div>
            </div>

            <VolumeChart data={volumeChartData} avgVol={avgVol} threshold={threshold} />

            {/* Anomaly list */}
            {anomalyDays.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {anomalyDays.map(d => (
                  <span
                    key={d.date}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md bg-down/10 text-down border border-down/20 font-mono"
                  >
                    <Zap size={10} />
                    {d.date} — {fmt(d.volume)}
                    {' '}({(d.volume / avgVol).toFixed(1)}×)
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* ── Row 3: Behavior AI summary ───────────────────────────────── */}
          {behavior && (
            <div className="card">
              <SectionTitle icon={Activity}>Behavior Analysis Summary</SectionTitle>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Pressure</p>
                  <p className={clsx('text-sm font-semibold capitalize',
                    behavior.pressure === 'buying' ? 'text-up'
                    : behavior.pressure === 'selling' ? 'text-down'
                    : 'text-text-secondary')}>
                    {behavior.pressure === 'buying' ? '▲ ' : behavior.pressure === 'selling' ? '▼ ' : '— '}
                    {behavior.pressure}
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Volume Anomaly</p>
                  <p className={clsx('text-sm font-semibold', behavior.volume_anomaly ? 'text-down' : 'text-up')}>
                    {behavior.volume_anomaly ? `⚡ Yes (${behavior.volume_ratio !== null ? Number(behavior.volume_ratio).toFixed(2) : '?'}×)` : '✓ Normal'}
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">News Sentiment</p>
                  <p className={clsx('text-sm font-semibold',
                    behavior.news_sentiment_score > 0.1 ? 'text-up'
                    : behavior.news_sentiment_score < -0.1 ? 'text-down'
                    : 'text-text-secondary')}>
                    {behavior.news_sentiment_score.toFixed(3)} ({behavior.news_count_30d} articles)
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Spread vs VWAP</p>
                  <p className={clsx('text-sm font-semibold',
                    behavior.price_to_vwap_spread_pct === null ? 'text-text-secondary'
                    : behavior.price_to_vwap_spread_pct >= 0 ? 'text-up' : 'text-down')}>
                    {behavior.price_to_vwap_spread_pct !== null
                      ? `${behavior.price_to_vwap_spread_pct >= 0 ? '+' : ''}${behavior.price_to_vwap_spread_pct.toFixed(2)}%`
                      : '—'}
                  </p>
                </div>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed border-l-2 border-accent-dim pl-3">
                {behavior.summary_text}
              </p>
            </div>
          )}

          <NewsMarketReaction data={correlation?.market_reaction} />

          {/* Categorized articles tagged to the selected company */}
          <div className="card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <SectionTitle icon={Newspaper}>{company?.symbol ?? 'Company'} News</SectionTitle>
              <span className="text-[10px] text-text-muted">{categorizedNews?.length ?? 0} categorized articles</span>
            </div>
            {categorizedNews === null ? (
              <p className="py-4 text-center text-xs text-text-muted">
                {loadingData ? 'Loading categorized company news…' : 'Unable to load categorized news.'}
              </p>
            ) : categorizedNews.length === 0 ? (
              <p className="py-4 text-center text-xs text-text-muted">
                No categorized news is linked to this company yet.
              </p>
            ) : (
              <div className="divide-y divide-bg-border">
                {categorizedNews.map(article => (
                  <article key={article.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1">
                      <a href={article.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-text-primary hover:text-accent-light">
                        {article.headline}
                      </a>
                      <p className="mt-1 text-[10px] text-text-muted">
                        {article.source}{article.published_at ? ` · ${new Date(article.published_at).toLocaleString()}` : ''}
                        {' · '}Company match {Math.round(article.confidence * 100)}%{article.is_manual ? ' · Manually categorized' : ''}
                      </p>
                    </div>
                    <span className={clsx(
                      'rounded px-2 py-1 text-[10px] uppercase',
                      article.sentiment_label === 'positive' ? 'bg-up/10 text-up'
                        : article.sentiment_label === 'negative' ? 'bg-down/10 text-down'
                        : 'bg-bg-elevated text-text-muted',
                    )}>
                      {article.sentiment_label || 'Sentiment unavailable'}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
