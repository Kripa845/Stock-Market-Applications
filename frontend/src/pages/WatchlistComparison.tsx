/**
 * WatchlistComparison.tsx
 *
 * Cross-company watchlist comparison page.
 * All data comes from GET /api/analysis/cross-company/ which returns:
 *   companies[], most_volatile[], most_active_volume[], most_active_turnover[],
 *   most_in_news[], top_gainers[], top_losers[], sectors[], pressure_distribution
 *
 * The endpoint computes:
 *   - latest price from stored DailyPrice (31-day window)
 *   - VWAP, pressure, volume_ratio, volume_anomaly from stored DailyAnalysis
 *   - volatility (std-dev of daily returns in window)
 *   - news_count from ArticleCompanyTag
 *
 * Nothing is hardcoded or recalculated in React.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, RadarChart,
  PolarGrid, PolarAngleAxis, Radar, Legend,
} from 'recharts';
import {
  AlertTriangle, ArrowDown, ArrowUp,
  BarChart3, Loader2, RefreshCw,
  TrendingDown, TrendingUp, Zap,
} from 'lucide-react';
import clsx from 'clsx';

import { analysisApi, type CompanyStat, type CrossCompanyAnalysis, type SectorStat } from '../api/analysis';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';

// ─── Constants ────────────────────────────────────────────────────────────────

const TT = { background: '#161B2E', border: '1px solid #1E2538', borderRadius: 10, fontSize: 12 };

const COLORS = {
  buy:     '#22C55E',
  sell:    '#EF4444',
  neutral: '#64748B',
  volume:  '#7C3AED',
  news:    '#A78BFA',
  vwap:    '#F59E0B',
};

function fmt(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000)     return `${(v / 1_000).toFixed(1)}K`;
  return String(Math.round(v));
}

function pct(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

// ─── Pressure badge ───────────────────────────────────────────────────────────

function PressureBadge({ p }: { p: string }) {
  const variant = p === 'buying' ? 'green' : p === 'selling' ? 'red' : 'gray';
  return <Badge variant={variant}>{p}</Badge>;
}

// ─── Section header ───────────────────────────────────────────────────────────

function SH({ icon: Icon, title, sub }: { icon: React.ElementType; title: string; sub?: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={15} className="text-accent-light shrink-0" />
      <div>
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        {sub && <p className="text-[11px] text-text-muted">{sub}</p>}
      </div>
    </div>
  );
}

// ─── Top-5 bar chart ──────────────────────────────────────────────────────────

function Top5Chart({
  data,
  dataKey,
  label,
  color,
  formatter,
}: {
  data: CompanyStat[];
  dataKey: keyof CompanyStat;
  label: string;
  color: string;
  formatter?: (v: number) => string;
}) {
  const chartData = data.map(c => ({ symbol: c.symbol, value: c[dataKey] as number }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
        <XAxis dataKey="symbol" tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fontSize: 10, fill: '#475569' }} tickLine={false} axisLine={false} width={44} tickFormatter={formatter ?? fmt} />
        <Tooltip contentStyle={TT} formatter={(v: unknown) => [(formatter ?? fmt)(Number(v ?? 0)), label]} />
        <Bar dataKey="value" fill={color} radius={[3, 3, 0, 0]} opacity={0.85} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Full company comparison table ────────────────────────────────────────────

function CompanyTable({
  companies,
  selected,
  onToggle,
}: {
  companies: CompanyStat[];
  selected: Set<number>;
  onToggle: (id: number) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[900px]">
        <thead>
          <tr className="border-b border-bg-border text-text-muted">
            <th className="text-left py-2 font-medium w-6" />
            <th className="text-left py-2 font-medium">Symbol</th>
            <th className="text-left py-2 font-medium">Sector</th>
            <th className="text-right py-2 font-medium">Price</th>
            <th className="text-right py-2 font-medium">Return</th>
            <th className="text-right py-2 font-medium">Volume</th>
            <th className="text-right py-2 font-medium">Turnover</th>
            <th className="text-right py-2 font-medium">VWAP</th>
            <th className="text-right py-2 font-medium">Vol Ratio</th>
            <th className="text-center py-2 font-medium">Anomaly</th>
            <th className="text-center py-2 font-medium">Pressure</th>
            <th className="text-right py-2 font-medium">News</th>
            <th className="text-right py-2 font-medium">Volatility</th>
          </tr>
        </thead>
        <tbody>
          {companies.map(c => (
            <tr
              key={c.id}
              className={clsx(
                'table-row',
                selected.has(c.id) && 'bg-accent/5',
              )}
            >
              <td className="py-2" onClick={e => { e.stopPropagation(); onToggle(c.id); }}>
                <input
                  type="checkbox"
                  checked={selected.has(c.id)}
                  onChange={() => onToggle(c.id)}
                  className="h-3.5 w-3.5 accent-accent"
                />
              </td>
              <td className="py-2 font-mono font-semibold text-accent-light">{c.symbol}</td>
              <td className="py-2 text-text-muted">{c.sector}</td>
              <td className="py-2 text-right font-mono text-text-primary">
                {c.latest_price > 0 ? `Rs. ${c.latest_price.toFixed(2)}` : '—'}
              </td>
              <td className={clsx('py-2 text-right font-mono', c.change_pct >= 0 ? 'text-up' : 'text-down')}>
                <span className="flex items-center justify-end gap-0.5">
                  {c.change_pct >= 0 ? <ArrowUp size={9} /> : <ArrowDown size={9} />}
                  {pct(c.change_pct)}
                </span>
              </td>
              <td className="py-2 text-right font-mono text-text-secondary">{fmt(c.volume_24h)}</td>
              <td className="py-2 text-right font-mono text-text-secondary">{fmt(c.turnover_24h)}</td>
              <td className="py-2 text-right font-mono text-yellow-400">
                {c.vwap !== null ? c.vwap.toFixed(2) : '—'}
              </td>
              <td className={clsx('py-2 text-right font-mono', c.volume_ratio !== null && c.volume_ratio >= 1.5 ? 'text-down' : 'text-text-secondary')}>
                {c.volume_ratio !== null ? `${c.volume_ratio.toFixed(2)}×` : '—'}
              </td>
              <td className="py-2 text-center">
                {c.volume_anomaly
                  ? <span className="text-down flex items-center justify-center gap-0.5"><Zap size={9} /> Yes</span>
                  : <span className="text-text-muted">—</span>}
              </td>
              <td className="py-2 text-center"><PressureBadge p={c.pressure} /></td>
              <td className="py-2 text-right text-text-secondary">{c.news_count}</td>
              <td className="py-2 text-right font-mono text-text-secondary">{c.volatility.toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Side-by-side comparison for selected companies ───────────────────────────

function ComparisonGrid({ companies }: { companies: CompanyStat[] }) {
  if (companies.length === 0) {
    return (
      <p className="text-xs text-text-muted py-4 text-center">
        Select companies in the table above to compare them side by side.
      </p>
    );
  }

  const rows: { label: string; render: (c: CompanyStat) => React.ReactNode }[] = [
    { label: 'Price',      render: c => c.latest_price > 0 ? `Rs. ${c.latest_price.toFixed(2)}` : '—' },
    {
      label: 'Return',
      render: c => (
        <span className={c.change_pct >= 0 ? 'text-up' : 'text-down'}>{pct(c.change_pct)}</span>
      ),
    },
    { label: 'Volume',     render: c => fmt(c.volume_24h) },
    { label: 'Turnover',   render: c => fmt(c.turnover_24h) },
    { label: 'VWAP',       render: c => c.vwap !== null ? <span className="text-yellow-400">{c.vwap.toFixed(2)}</span> : '—' },
    {
      label: 'Vol Ratio',
      render: c => c.volume_ratio !== null
        ? <span className={c.volume_ratio >= 1.5 ? 'text-down' : ''}>{c.volume_ratio.toFixed(2)}×</span>
        : '—',
    },
    {
      label: 'Anomaly',
      render: c => c.volume_anomaly
        ? <span className="text-down flex items-center gap-0.5"><Zap size={10} />Yes</span>
        : <span className="text-text-muted">Normal</span>,
    },
    { label: 'Pressure',   render: c => <PressureBadge p={c.pressure} /> },
    { label: 'News',       render: c => c.news_count },
    { label: 'Volatility', render: c => `${c.volatility.toFixed(2)}%` },
    { label: 'Sector',     render: c => <span className="text-text-muted text-[11px]">{c.sector}</span> },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-bg-border">
            <th className="text-left py-2 font-medium text-text-muted w-28">Metric</th>
            {companies.map(c => (
              <th key={c.id} className="text-right py-2 font-medium text-accent-light font-mono">{c.symbol}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.label} className="border-b border-bg-border/50">
              <td className="py-2 text-text-muted">{row.label}</td>
              {companies.map(c => (
                <td key={c.id} className="py-2 text-right font-mono text-text-primary">
                  {row.render(c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Radar chart for multi-metric comparison ──────────────────────────────────

function ComparisonRadar({ companies, all }: { companies: CompanyStat[]; all: CompanyStat[] }) {
  if (companies.length === 0 || all.length === 0) return null;

  // Normalise each metric to 0-100 relative to the full set
  const norm = (val: number, vals: number[]): number => {
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    return max === min ? 50 : ((val - min) / (max - min)) * 100;
  };

  const metrics = [
    { key: 'change_pct',  label: 'Return' },
    { key: 'volume_24h',  label: 'Volume' },
    { key: 'volatility',  label: 'Volatility' },
    { key: 'news_count',  label: 'News' },
  ] as const;

  const metricAll = metrics.map(m => all.map(c => c[m.key] as number));

  const radarData = metrics.map((m, mi) => {
    const entry: Record<string, number | string> = { metric: m.label };
    companies.forEach(c => {
      entry[c.symbol] = norm(c[m.key] as number, metricAll[mi]);
    });
    return entry;
  });

  const RADAR_COLORS = ['#7C3AED', '#22C55E', '#F59E0B', '#A78BFA', '#F472B6'];

  return (
    <div className="card">
      <SH icon={BarChart3} title="Multi-Metric Comparison (normalised 0–100)" sub="Each axis is scaled relative to all companies in the dataset." />
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <PolarGrid stroke="#1E2538" />
          <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: '#94A3B8' }} />
          {companies.map((c, i) => (
            <Radar
              key={c.id}
              name={c.symbol}
              dataKey={c.symbol}
              stroke={RADAR_COLORS[i % RADAR_COLORS.length]}
              fill={RADAR_COLORS[i % RADAR_COLORS.length]}
              fillOpacity={0.15}
              strokeWidth={1.5}
            />
          ))}
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Tooltip contentStyle={TT} formatter={(v: unknown) => [`${Number(v ?? 0).toFixed(1)}`, '']} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Sector summary ───────────────────────────────────────────────────────────

function SectorSummary({ sectors }: { sectors: SectorStat[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {sectors.map(s => (
        <div key={s.sector} className="card">
          <p className="text-xs font-semibold text-text-primary truncate">{s.sector}</p>
          <p className="text-[11px] text-text-muted mt-0.5">
            {s.companies_count} {s.companies_count === 1 ? 'company' : 'companies'}
          </p>
          <p className={clsx('text-sm font-semibold font-mono mt-1', s.avg_change_pct >= 0 ? 'text-up' : 'text-down')}>
            {pct(s.avg_change_pct)}
          </p>
          <p className="text-[11px] text-text-muted">avg return · turnover {fmt(s.total_turnover)}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function WatchlistComparison() {
  const [data,     setData]     = useState<CrossCompanyAnalysis | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [view,     setView]     = useState<'table' | 'top5' | 'sector'>('table');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await analysisApi.getCrossCompany();
      setData(result);
    } catch {
      setError('Unable to load cross-company analysis. Ensure the analysis task has run after the latest crawl.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleCompany = useCallback((id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const selectedCompanies = useMemo(
    () => (data?.companies ?? []).filter(c => selected.has(c.id)),
    [data, selected],
  );

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="animate-spin text-accent" size={28} />
    </div>
  );

  if (error) return (
    <div className="space-y-4">
      <PageHeader title="Watchlist Comparison" subtitle="Cross-company market analysis." />
      <div className="card flex flex-col items-center gap-3 py-16 text-center">
        <AlertTriangle size={32} className="text-yellow-400" />
        <p className="text-sm text-text-secondary max-w-md">{error}</p>
        <button onClick={load} className="btn-ghost text-xs flex items-center gap-1.5">
          <RefreshCw size={13} /> Retry
        </button>
      </div>
    </div>
  );

  if (!data || data.companies.length === 0) return (
    <div className="space-y-4">
      <PageHeader title="Watchlist Comparison" />
      <EmptyState
        title="No company data available"
        description="Run the trading data crawler and then the analysis task to populate this page."
      />
    </div>
  );

  const { companies, most_volatile, most_active_volume, most_in_news,
          top_gainers, top_losers, sectors } = data;

  return (
    <div className="space-y-6">

      {/* Header */}
      <PageHeader
        title="Watchlist Comparison"
        subtitle={`${data.watchlist_count} active companies · 31-day rolling window`}
        actions={
          <button onClick={load} className="btn-ghost flex items-center gap-2 text-xs">
            <RefreshCw size={13} /> Refresh
          </button>
        }
      />

      {/* View selector */}
      <div className="flex gap-1 bg-bg-elevated rounded-xl p-1 w-fit">
        {([['table', 'All Companies'], ['top5', 'Top 5 Lists'], ['sector', 'Sectors']] as const).map(([k, label]) => (
          <button key={k} onClick={() => setView(k)}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              view === k ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* ── All Companies table ─────────────────────────────────────────────── */}
      {view === 'table' && (
        <div className="space-y-4">
          <div className="card">
            <SH icon={BarChart3} title="All Companies" sub="Check boxes to compare companies." />
            <CompanyTable companies={companies} selected={selected} onToggle={toggleCompany} />
          </div>

          {/* Side-by-side comparison */}
          {selectedCompanies.length >= 2 && (
            <div className="card">
              <SH icon={BarChart3} title={`Comparing: ${selectedCompanies.map(c => c.symbol).join(' · ')}`} />
              <ComparisonGrid companies={selectedCompanies} />
            </div>
          )}

          {selectedCompanies.length >= 2 && (
            <ComparisonRadar companies={selectedCompanies} all={companies} />
          )}

          {selectedCompanies.length === 1 && (
            <p className="text-xs text-text-muted text-center">
              Select one more company to enable side-by-side comparison.
            </p>
          )}
        </div>
      )}

      {/* ── Top 5 lists ─────────────────────────────────────────────────────── */}
      {view === 'top5' && (
        <div className="space-y-6">

          {/* Gainers / Losers */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <SH icon={TrendingUp} title="Top Gainers" sub="By daily return % (31-day window)" />
              <Top5Chart data={top_gainers} dataKey="change_pct" label="Return %" color={COLORS.buy} formatter={v => pct(v)} />
              <table className="w-full text-xs mt-2">
                <tbody>
                  {top_gainers.map(c => (
                    <tr key={c.id} className="table-row">
                      <td className="py-1.5 font-mono text-accent-light">{c.symbol}</td>
                      <td className="py-1.5 text-text-muted">{c.sector}</td>
                      <td className="py-1.5 text-right font-mono text-up font-medium">{pct(c.change_pct)}</td>
                      <td className="py-1.5 text-right"><PressureBadge p={c.pressure} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card">
              <SH icon={TrendingDown} title="Top Losers" sub="By daily return % (31-day window)" />
              <Top5Chart data={[...top_losers].reverse()} dataKey="change_pct" label="Return %" color={COLORS.sell} formatter={v => pct(v)} />
              <table className="w-full text-xs mt-2">
                <tbody>
                  {top_losers.map(c => (
                    <tr key={c.id} className="table-row">
                      <td className="py-1.5 font-mono text-accent-light">{c.symbol}</td>
                      <td className="py-1.5 text-text-muted">{c.sector}</td>
                      <td className="py-1.5 text-right font-mono text-down font-medium">{pct(c.change_pct)}</td>
                      <td className="py-1.5 text-right"><PressureBadge p={c.pressure} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Most volatile */}
          <div className="card">
            <SH icon={Zap} title="Most Volatile" sub="Standard deviation of daily returns over the 31-day window" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Top5Chart data={most_volatile} dataKey="volatility" label="Volatility %" color={COLORS.volume} formatter={v => `${v.toFixed(2)}%`} />
              <table className="w-full text-xs self-center">
                <thead><tr className="border-b border-bg-border text-text-muted">
                  <th className="text-left py-1.5 font-medium">Symbol</th>
                  <th className="text-right py-1.5 font-medium">Volatility</th>
                  <th className="text-right py-1.5 font-medium">Return</th>
                  <th className="text-right py-1.5 font-medium">Pressure</th>
                </tr></thead>
                <tbody>
                  {most_volatile.map(c => (
                    <tr key={c.id} className="table-row">
                      <td className="py-1.5 font-mono text-accent-light">{c.symbol}</td>
                      <td className="py-1.5 text-right font-mono text-text-primary">{c.volatility.toFixed(2)}%</td>
                      <td className={clsx('py-1.5 text-right font-mono', c.change_pct >= 0 ? 'text-up' : 'text-down')}>{pct(c.change_pct)}</td>
                      <td className="py-1.5 text-right"><PressureBadge p={c.pressure} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Most active by volume */}
          <div className="card">
            <SH icon={BarChart3} title="Most Active by Volume" sub="Highest traded volume in the 31-day window" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Top5Chart data={most_active_volume} dataKey="volume_24h" label="Volume" color={COLORS.vwap} />
              <table className="w-full text-xs self-center">
                <thead><tr className="border-b border-bg-border text-text-muted">
                  <th className="text-left py-1.5 font-medium">Symbol</th>
                  <th className="text-right py-1.5 font-medium">Volume</th>
                  <th className="text-right py-1.5 font-medium">Vol Ratio</th>
                  <th className="text-center py-1.5 font-medium">Anomaly</th>
                </tr></thead>
                <tbody>
                  {most_active_volume.map(c => (
                    <tr key={c.id} className="table-row">
                      <td className="py-1.5 font-mono text-accent-light">{c.symbol}</td>
                      <td className="py-1.5 text-right font-mono">{fmt(c.volume_24h)}</td>
                      <td className={clsx('py-1.5 text-right font-mono', c.volume_ratio !== null && c.volume_ratio >= 1.5 ? 'text-down' : '')}>
                        {c.volume_ratio !== null ? `${c.volume_ratio.toFixed(2)}×` : '—'}
                      </td>
                      <td className="py-1.5 text-center">
                        {c.volume_anomaly ? <span className="text-down flex items-center justify-center gap-0.5"><Zap size={9} />Yes</span> : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Most in the news */}
          <div className="card">
            <SH icon={BarChart3} title="Most In The News" sub="Articles tagged to this company over the 31-day window" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Top5Chart data={most_in_news} dataKey="news_count" label="Articles" color={COLORS.news} />
              <table className="w-full text-xs self-center">
                <thead><tr className="border-b border-bg-border text-text-muted">
                  <th className="text-left py-1.5 font-medium">Symbol</th>
                  <th className="text-right py-1.5 font-medium">Articles</th>
                  <th className="text-right py-1.5 font-medium">Return</th>
                  <th className="text-right py-1.5 font-medium">Pressure</th>
                </tr></thead>
                <tbody>
                  {most_in_news.map(c => (
                    <tr key={c.id} className="table-row">
                      <td className="py-1.5 font-mono text-accent-light">{c.symbol}</td>
                      <td className="py-1.5 text-right font-mono text-accent-light">{c.news_count}</td>
                      <td className={clsx('py-1.5 text-right font-mono', c.change_pct >= 0 ? 'text-up' : 'text-down')}>{pct(c.change_pct)}</td>
                      <td className="py-1.5 text-right"><PressureBadge p={c.pressure} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Sector summary ───────────────────────────────────────────────────── */}
      {view === 'sector' && (
        <div className="space-y-4">
          <SectorSummary sectors={sectors} />

          {/* Sector return bar */}
          <div className="card">
            <SH icon={BarChart3} title="Avg Return by Sector" />
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={sectors} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
                <XAxis dataKey="sector" tick={{ fontSize: 9, fill: '#94A3B8' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} width={40} tickFormatter={v => `${v.toFixed(1)}%`} />
                <Tooltip contentStyle={TT} formatter={(v: unknown) => [`${Number(v ?? 0).toFixed(2)}%`, 'Avg Return']} />
                <Bar dataKey="avg_change_pct" radius={[3, 3, 0, 0]} maxBarSize={40}>
                  {sectors.map((s, i) => (
                    <Cell key={i} fill={s.avg_change_pct >= 0 ? COLORS.buy : COLORS.sell} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Sector turnover bar */}
          <div className="card">
            <SH icon={BarChart3} title="Total Turnover by Sector" />
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sectors} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
                <XAxis dataKey="sector" tick={{ fontSize: 9, fill: '#94A3B8' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} width={44} tickFormatter={fmt} />
                <Tooltip contentStyle={TT} formatter={(v: unknown) => [fmt(Number(v ?? 0)), 'Turnover']} />
                <Bar dataKey="total_turnover" fill={COLORS.volume} radius={[3, 3, 0, 0]} maxBarSize={40} opacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

    </div>
  );
}
