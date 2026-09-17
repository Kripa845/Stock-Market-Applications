import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Area, BarChart, Bar, ComposedChart, Line,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell, Legend,
} from 'recharts';
import {
  Activity, AlertTriangle, ArrowDown, ArrowUp,
  BarChart3, Building2, Loader2, Minus, Newspaper,
  RefreshCw, TrendingDown, TrendingUp, Zap,
} from 'lucide-react';
import clsx from 'clsx';

import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import { getCompanies } from '../api/companies';
import {
  analysisApi,
  type BehaviorSummary,
  type NewsPriceCorrelation,
  type PricePoint,
  type FloorsheetTx,
} from '../api/analysis';
import type { Company } from '../types/company';

// ─── Shared chart style ───────────────────────────────────────────────────────
const TT_STYLE = {
  background: '#161B2E',
  border: '1px solid #1E2538',
  borderRadius: 10,
  fontSize: 12,
  color: '#CBD5E1',
};

const COLORS = {
  price:   '#22C55E',
  volume:  '#7C3AED',
  vwap:    '#F59E0B',
  anomaly: '#EF4444',
  buy:     '#22C55E',
  sell:    '#EF4444',
  neutral: '#64748B',
  news:    '#38BDF8',
  sentiment: '#F472B6',
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
function PressureGauge({ score, pressure }: { score: number; pressure: string }) {
  const pct  = Math.max(0, Math.min(100, score));
  const color = pressure === 'buying' ? COLORS.buy : pressure === 'selling' ? COLORS.sell : COLORS.neutral;
  const label = pressure === 'buying' ? 'Buying' : pressure === 'selling' ? 'Selling' : 'Neutral';
  const Icon  = pressure === 'buying' ? TrendingUp : pressure === 'selling' ? TrendingDown : Minus;

  return (
    <div className="flex flex-col items-center gap-2 py-2">
      {/* Arc bar */}
      <div className="relative w-32 h-16 overflow-hidden">
        <div className="absolute inset-0 bottom-0 rounded-t-full border-[10px] border-bg-elevated" />
        <div
          className="absolute inset-0 bottom-0 rounded-t-full border-[10px] transition-all duration-700"
          style={{
            borderColor: color,
            clipPath: `inset(0 ${100 - pct}% 0 0)`,
          }}
        />
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
          <p className="text-xl font-bold font-mono" style={{ color }}>{Math.round(pct)}</p>
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <Icon size={14} style={{ color }} />
        <span className="text-sm font-semibold" style={{ color }}>{label} Pressure</span>
      </div>
    </div>
  );
}

// ─── Net broker bar chart ─────────────────────────────────────────────────────
function NetBrokerChart({ txs }: { txs: FloorsheetTx[] }) {
  const net = useMemo(() => {
    const bought = new Map<string, number>();
    const sold   = new Map<string, number>();
    txs.forEach(t => {
      bought.set(t.buyer_broker,  (bought.get(t.buyer_broker)  ?? 0) + t.quantity);
      sold.set(  t.seller_broker, (sold.get(  t.seller_broker) ?? 0) + t.quantity);
    });
    const brokers = new Set([...bought.keys(), ...sold.keys()]);
    const rows = [...brokers].map(b => ({
      broker: b,
      net: (bought.get(b) ?? 0) - (sold.get(b) ?? 0),
    }));
    rows.sort((a, b) => Math.abs(b.net) - Math.abs(a.net));
    return rows.slice(0, 10);
  }, [txs]);

  if (!net.length) {
    return <p className="text-xs text-text-muted py-4 text-center">No floorsheet data for this date.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart
        data={net}
        layout="vertical"
        margin={{ top: 4, right: 16, left: 48, bottom: 4 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 10, fill: '#475569' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={fmt}
        />
        <YAxis
          type="category"
          dataKey="broker"
          tick={{ fontSize: 10, fill: '#94A3B8' }}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip
          contentStyle={TT_STYLE}
          formatter={(v: unknown) => {
            const n = Number(v ?? 0);
            return [`${n > 0 ? '+' : ''}${fmt(Math.abs(n))}`, 'Net qty'];
          }}
          labelFormatter={(l) => `Broker ${l}`}
        />
        <ReferenceLine x={0} stroke="#1E2538" />
        <Bar dataKey="net" radius={[0, 3, 3, 0]} maxBarSize={18}>
          {net.map((row, i) => (
            <Cell key={i} fill={row.net >= 0 ? COLORS.buy : COLORS.sell} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Top broker tables (buy / sell) ──────────────────────────────────────────
function BrokerTable({
  rows, title, color,
}: {
  rows: { broker: string; qty: number; trades: number }[];
  title: string;
  color: string;
}) {
  return (
    <div>
      <p className={clsx('text-xs font-semibold mb-2', color)}>{title}</p>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-bg-border text-text-muted">
            <th className="text-left py-1 font-medium">Broker</th>
            <th className="text-right py-1 font-medium">Qty</th>
            <th className="text-right py-1 font-medium">Txns</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="table-row">
              <td className="py-1.5 text-text-secondary">{r.broker}</td>
              <td className={clsx('py-1.5 text-right font-mono font-medium', color)}>
                {fmt(r.qty)}
              </td>
              <td className="py-1.5 text-right text-text-muted">{r.trades}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
        <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 9, fill: '#475569' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 9, fill: '#475569' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={fmt}
          width={38}
        />
        <Tooltip
          contentStyle={TT_STYLE}
          formatter={(v: unknown) => [fmt(Number(v ?? 0)), 'Volume']}
        />
        <ReferenceLine
          y={avgVol}
          stroke="#475569"
          strokeDasharray="4 2"
          label={{ value: 'avg', position: 'right', fill: '#475569', fontSize: 9 }}
        />
        <ReferenceLine
          y={threshold}
          stroke={COLORS.anomaly}
          strokeDasharray="4 2"
          label={{ value: '×1.5σ', position: 'right', fill: COLORS.anomaly, fontSize: 9 }}
        />
        <Bar dataKey="volume" radius={[2, 2, 0, 0]} maxBarSize={14}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.volume >= threshold ? COLORS.anomaly : COLORS.volume} opacity={0.75} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Price + VWAP combined chart ──────────────────────────────────────────────
function PriceChart({
  data, vwap30, positive,
}: {
  data: { date: string; price: number }[];
  vwap30: number;
  positive: boolean;
}) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <ComposedChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={positive ? COLORS.price : COLORS.sell} stopOpacity={0.25} />
            <stop offset="95%" stopColor={positive ? COLORS.price : COLORS.sell} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 9, fill: '#475569' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={['auto', 'auto']}
          tick={{ fontSize: 9, fill: '#475569' }}
          tickLine={false}
          axisLine={false}
          width={50}
        />
        <Tooltip
          contentStyle={TT_STYLE}
          formatter={(v: unknown, name: unknown) => [
            `Rs. ${Number(v ?? 0).toFixed(2)}`,
            name === 'price' ? 'Close' : 'VWAP',
          ]}
        />
        <ReferenceLine
          y={vwap30}
          stroke={COLORS.vwap}
          strokeDasharray="5 3"
          label={{
            value: `VWAP ${vwap30.toFixed(0)}`,
            position: 'insideTopRight',
            fill: COLORS.vwap,
            fontSize: 9,
          }}
        />
        <Area
          type="monotone"
          dataKey="price"
          stroke={positive ? COLORS.price : COLORS.sell}
          strokeWidth={1.5}
          fill="url(#priceGrad)"
          dot={false}
        />
        <Legend
          wrapperStyle={{ fontSize: 10, paddingTop: 4 }}
          formatter={(v) => (v === 'price' ? 'Close Price' : 'VWAP (30d)')}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ─── News sentiment vs price change scatter ───────────────────────────────────
function NewsPriceScatter({ points }: { points: { sentiment_score: number; price_change_pct: number; date: string; news_count: number }[] }) {
  const withNews = points.filter(p => p.news_count > 0);
  if (!withNews.length) {
    return <p className="text-xs text-text-muted py-4 text-center">No news-tagged trading days in this window.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={160}>
      <ScatterChart margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" />
        <XAxis
          type="number"
          dataKey="sentiment_score"
          name="Sentiment"
          domain={[-1, 1]}
          tick={{ fontSize: 9, fill: '#475569' }}
          tickLine={false}
          axisLine={false}
          label={{ value: 'Sentiment (prev day)', position: 'insideBottom', offset: -2, fill: '#475569', fontSize: 9 }}
        />
        <YAxis
          type="number"
          dataKey="price_change_pct"
          name="Next-day Δ%"
          tick={{ fontSize: 9, fill: '#475569' }}
          tickLine={false}
          axisLine={false}
          width={40}
          tickFormatter={(v) => `${v.toFixed(1)}%`}
        />
        <ReferenceLine x={0} stroke="#1E2538" />
        <ReferenceLine y={0} stroke="#1E2538" />
        <Tooltip
          contentStyle={TT_STYLE}
          cursor={{ strokeDasharray: '3 3' }}
          formatter={(v: unknown, name: unknown) => [
            name === 'Next-day Δ%'
              ? `${Number(v ?? 0).toFixed(2)}%`
              : Number(v ?? 0).toFixed(3),
            String(name),
          ]}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
        />
        <Scatter
          data={withNews}
          fill={COLORS.news}
          fillOpacity={0.8}
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

// ─── News volume vs price change bar chart ────────────────────────────────────
function NewsVolumeChart({ points }: { points: { date: string; news_count: number; price_change_pct: number }[] }) {
  const withNews = points.filter(p => p.news_count > 0);
  if (!withNews.length) return null;
  return (
    <ResponsiveContainer width="100%" height={140}>
      <ComposedChart data={withNews} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} />
        <YAxis yAxisId="left"  tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} width={28} />
        <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} width={36} tickFormatter={(v) => `${v.toFixed(1)}%`} />
        <Tooltip contentStyle={TT_STYLE} />
        <Bar     yAxisId="left"  dataKey="news_count"     fill={COLORS.news}    opacity={0.5} name="Articles" radius={[2,2,0,0]} maxBarSize={20} />
        <Line   yAxisId="right" dataKey="price_change_pct" stroke={COLORS.sentiment} strokeWidth={1.5} dot={{ r: 3 }} name="Next-day Δ%" />
      </ComposedChart>
    </ResponsiveContainer>
  );
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

function computePressureRatio(prices: PricePoint[]) {
  let risingConfirmed = 0, risingWeak = 0;
  for (let i = 1; i < prices.length; i++) {
    const priceUp  = parseFloat(prices[i].close) > parseFloat(prices[i - 1].close);
    const volumeUp = prices[i].volume > prices[i - 1].volume;
    if (priceUp && volumeUp)  risingConfirmed++;
    if (priceUp && !volumeUp) risingWeak++;
  }
  return { risingConfirmed, risingWeak };
}

function aggregateFloorsheet(txs: FloorsheetTx[], side: 'buyer_broker' | 'seller_broker') {
  const m = new Map<string, { qty: number; trades: number }>();
  txs.forEach(t => {
    const key = t[side];
    const cur = m.get(key) ?? { qty: 0, trades: 0 };
    cur.qty    += t.quantity;
    cur.trades += 1;
    m.set(key, cur);
  });
  return [...m.entries()]
    .map(([broker, v]) => ({ broker, ...v }))
    .sort((a, b) => b.qty - a.qty)
    .slice(0, 7);
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CompanyAnalysisDashboard() {
  const [companies,   setCompanies]   = useState<Company[]>([]);
  const [selectedId,  setSelectedId]  = useState<number | null>(null);
  const [prices,      setPrices]      = useState<PricePoint[]>([]);
  const [behavior,    setBehavior]    = useState<BehaviorSummary | null>(null);
  const [correlation, setCorrelation] = useState<NewsPriceCorrelation | null>(null);
  const [floorsheet,  setFloorsheet]  = useState<FloorsheetTx[]>([]);
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
    Promise.allSettled([
      analysisApi.getPrices(selectedId, priceRange),
      analysisApi.getBehavior(selectedId),
      analysisApi.getNewsCorrelation(selectedId),
      analysisApi.getFloorsheet(selectedId),
    ]).then(([prRes, bhRes, corrRes, flRes]) => {
      if (prRes.status   === 'fulfilled') setPrices(prRes.value.prices);
      if (bhRes.status   === 'fulfilled') setBehavior(bhRes.value);
      if (corrRes.status === 'fulfilled') setCorrelation(corrRes.value);
      if (flRes.status   === 'fulfilled') setFloorsheet(flRes.value.transactions);
      // surface any hard errors
      const failed = [prRes, bhRes, corrRes, flRes].filter(r => r.status === 'rejected');
      if (failed.length === 4) setError('Unable to load company data. Check your permissions.');
    }).finally(() => setLoadingData(false));
  }, [selectedId, priceRange]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Derived values ──────────────────────────────────────────────────────────
  const company  = companies.find(c => c.id === selectedId);
  const { avg: avgVol, threshold } = useMemo(() => computeVolumeStats(prices), [prices]);
  const vwap30   = useMemo(() => computeVwap(prices), [prices]);
  const { risingConfirmed, risingWeak } = useMemo(() => computePressureRatio(prices), [prices]);

  const anomalyDays = useMemo(
    () => prices.filter(p => p.volume >= threshold),
    [prices, threshold],
  );

  const priceChartData = useMemo(
    () => prices.map(p => ({ date: p.date.slice(5), price: parseFloat(p.close) })),
    [prices],
  );

  const volumeChartData = useMemo(
    () => prices.map(p => ({ date: p.date.slice(5), volume: p.volume })),
    [prices],
  );

  const latestClose = prices.length ? parseFloat(prices[prices.length - 1].close) : 0;
  const firstClose  = prices.length ? parseFloat(prices[0].close) : 0;
  const positive    = latestClose >= firstClose;
  const spreadPct   = vwap30 ? ((latestClose - vwap30) / vwap30 * 100) : 0;

  const buyers  = useMemo(() => aggregateFloorsheet(floorsheet, 'buyer_broker'),  [floorsheet]);
  const sellers = useMemo(() => aggregateFloorsheet(floorsheet, 'seller_broker'), [floorsheet]);

  const corrPoints = useMemo(
    () => (correlation?.data_points ?? []).map(d => ({
      date:            d.date,
      sentiment_score: d.sentiment_score,
      price_change_pct:d.price_change_pct,
      news_count:      d.news_count,
      volume:          d.volume,
    })),
    [correlation],
  );

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={28} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <PageHeader
        title="Company Behavior Analysis"
        subtitle="Price / volume trends, VWAP, buy-sell pressure, broker activity, and news-price correlation."
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
          {/* ── Row 1: Price chart + Pressure card ─────────────────────── */}
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-4">

            {/* Price chart */}
            <div className="card space-y-3">
              <SectionTitle icon={TrendingUp}>Daily Close Price vs VWAP</SectionTitle>
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-1.5 text-xs text-text-muted">
                  <span className="inline-block w-3 h-0.5" style={{ background: positive ? COLORS.price : COLORS.sell }} />
                  Close price
                </div>
                <div className="flex items-center gap-1.5 text-xs text-text-muted">
                  <span className="inline-block w-3 h-0.5 border-t-2 border-dashed" style={{ borderColor: COLORS.vwap }} />
                  30-day VWAP
                </div>
              </div>
              <PriceChart data={priceChartData} vwap30={vwap30} positive={positive} />
            </div>

            {/* Pressure card */}
            <div className="card flex flex-col gap-4">
              <SectionTitle icon={Activity}>Buy / Sell Pressure</SectionTitle>

              {behavior ? (
                <>
                  <PressureGauge
                    score={behavior.pressure_score}
                    pressure={behavior.pressure}
                  />
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-bg-elevated rounded-lg p-2 text-center">
                      <p className="text-text-muted text-[10px] mb-0.5">Price above VWAP</p>
                      <p className={clsx('font-semibold', spreadPct >= 0 ? 'text-up' : 'text-down')}>
                        {spreadPct >= 0 ? '+' : ''}{spreadPct.toFixed(2)}%
                      </p>
                    </div>
                    <div className="bg-bg-elevated rounded-lg p-2 text-center">
                      <p className="text-text-muted text-[10px] mb-0.5">Vol anomaly ratio</p>
                      <p className={clsx('font-semibold', behavior.volume_anomaly ? 'text-down' : 'text-text-primary')}>
                        {behavior.volume_ratio.toFixed(2)}×
                      </p>
                    </div>
                    <div className="bg-bg-elevated rounded-lg p-2 text-center col-span-2">
                      <p className="text-text-muted text-[10px] mb-0.5">Rising price + rising volume</p>
                      <p className="font-semibold text-text-primary">{risingConfirmed} days</p>
                    </div>
                    <div className="bg-bg-elevated rounded-lg p-2 text-center col-span-2">
                      <p className="text-text-muted text-[10px] mb-0.5">Rising price + falling volume</p>
                      <p className="font-semibold text-yellow-400">{risingWeak} days</p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="space-y-3">
                  {/* Computed from price data only */}
                  <PressureGauge
                    score={50 + (spreadPct * 2)}
                    pressure={spreadPct > 1 ? 'buying' : spreadPct < -1 ? 'selling' : 'neutral'}
                  />
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-bg-elevated rounded-lg p-2 text-center col-span-2">
                      <p className="text-text-muted text-[10px] mb-0.5">Rising price + rising volume</p>
                      <p className="font-semibold text-text-primary">{risingConfirmed} days</p>
                    </div>
                    <div className="bg-bg-elevated rounded-lg p-2 text-center col-span-2">
                      <p className="text-text-muted text-[10px] mb-0.5">Rising price + falling volume</p>
                      <p className="font-semibold text-yellow-400">{risingWeak} days</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
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
                    {behavior.volume_anomaly ? `⚡ Yes (${behavior.volume_ratio.toFixed(2)}×)` : '✓ Normal'}
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
                  <p className={clsx('text-sm font-semibold', behavior.price_to_vwap_spread_pct >= 0 ? 'text-up' : 'text-down')}>
                    {behavior.price_to_vwap_spread_pct >= 0 ? '+' : ''}
                    {behavior.price_to_vwap_spread_pct.toFixed(2)}%
                  </p>
                </div>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed border-l-2 border-accent-dim pl-3">
                {behavior.summary_text}
              </p>
            </div>
          )}

          {/* ── Row 4: Floorsheet broker analysis ───────────────────────── */}
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-4">

            {/* Net buy/sell chart */}
            <div className="card">
              <SectionTitle icon={Building2}>Broker Net Buy / Sell (Latest Floorsheet)</SectionTitle>
              {floorsheet.length === 0 ? (
                <p className="text-xs text-text-muted py-4 text-center">No floorsheet data available.</p>
              ) : (
                <>
                  <p className="text-xs text-text-muted mb-3">
                    Net position per broker (bought − sold).{' '}
                    <span className="text-up">Green = net buyer</span>,{' '}
                    <span className="text-down">red = net seller</span>.
                    Top 10 by absolute net quantity.
                  </p>
                  <NetBrokerChart txs={floorsheet} />
                </>
              )}
            </div>

            {/* Top buyers / sellers tables */}
            <div className="card space-y-5">
              <SectionTitle icon={Activity}>Most Active Brokers</SectionTitle>
              {floorsheet.length === 0 ? (
                <p className="text-xs text-text-muted text-center py-4">No data.</p>
              ) : (
                <>
                  <BrokerTable
                    rows={buyers}
                    title="Top Buyers"
                    color="text-up"
                  />
                  <div className="h-px bg-bg-border" />
                  <BrokerTable
                    rows={sellers}
                    title="Top Sellers"
                    color="text-down"
                  />
                </>
              )}
            </div>
          </div>

          {/* ── Row 5: News-price correlation ───────────────────────────── */}
          <div className="card">
            <div className="flex items-start justify-between flex-wrap gap-3 mb-1">
              <SectionTitle icon={Newspaper}>News Volume & Sentiment vs Next-Day Price Change</SectionTitle>
              {correlation && correlation.correlation_coefficient !== null && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-muted">Pearson r =</span>
                  <span className={clsx(
                    'text-sm font-bold font-mono',
                    Math.abs(correlation.correlation_coefficient) > 0.4 ? 'text-up' : 'text-text-secondary',
                  )}>
                    {correlation.correlation_coefficient.toFixed(3)}
                  </span>
                  <Badge variant={Math.abs(correlation.correlation_coefficient) > 0.4 ? 'green' : 'gray'}>
                    {correlation.correlation_label}
                  </Badge>
                </div>
              )}
            </div>

            {correlation?.analysis_note && (
              <p className="text-xs text-text-muted mb-3 italic">{correlation.analysis_note}</p>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-text-muted mb-2">
                  Scatter — sentiment score (day N) vs price change % (day N+1)
                </p>
                <NewsPriceScatter points={corrPoints} />
              </div>
              <div>
                <p className="text-xs text-text-muted mb-2">
                  Bar — article count and next-day price change for days with news
                </p>
                <NewsVolumeChart points={corrPoints} />
              </div>
            </div>

            {/* Data table of news days */}
            {corrPoints.filter(p => p.news_count > 0).length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-xs min-w-[460px]">
                  <thead>
                    <tr className="border-b border-bg-border text-text-muted">
                      <th className="text-left py-1.5 font-medium">Date</th>
                      <th className="text-right py-1.5 font-medium">Articles</th>
                      <th className="text-right py-1.5 font-medium">Avg Sentiment</th>
                      <th className="text-right py-1.5 font-medium">Close</th>
                      <th className="text-right py-1.5 font-medium">Next-day Δ%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {corrPoints
                      .filter(p => p.news_count > 0)
                      .map((p, i) => {
                        const sent    = p.sentiment_score;
                        const change  = p.price_change_pct;
                        const aligned = (sent > 0 && change > 0) || (sent < 0 && change < 0);
                        return (
                          <tr key={i} className="table-row">
                            <td className="py-2 font-mono text-text-secondary">{p.date}</td>
                            <td className="py-2 text-right">
                              <Badge variant="blue">{p.news_count}</Badge>
                            </td>
                            <td className={clsx(
                              'py-2 text-right font-mono',
                              sent > 0.1 ? 'text-up' : sent < -0.1 ? 'text-down' : 'text-text-secondary',
                            )}>
                              {sent >= 0 ? '+' : ''}{sent.toFixed(3)}
                            </td>
                            <td className="py-2 text-right font-mono text-text-secondary">
                              Rs. {p.volume > 0 ? '—' : '—'}
                            </td>
                            <td className={clsx('py-2 text-right font-mono font-medium',
                              change > 0 ? 'text-up' : change < 0 ? 'text-down' : 'text-text-secondary',
                            )}>
                              <span className="flex items-center justify-end gap-1">
                                {change > 0
                                  ? <ArrowUp size={10} />
                                  : change < 0
                                  ? <ArrowDown size={10} />
                                  : null}
                                {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                                {aligned && (
                                  <span className="ml-1 text-up text-[9px]">✓</span>
                                )}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
                <p className="text-[10px] text-text-muted mt-1.5">
                  ✓ indicates sentiment direction aligned with next-day price movement.
                  This is an observational signal only, not a validated trading indicator.
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
