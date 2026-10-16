import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowDown, ArrowRight, ArrowUp, BarChart3, CandlestickChart, ChevronRight, Coins, Gauge, Layers, LineChart as LineChartIcon,
  TrendingDown, TrendingUp, type LucideIcon,
} from 'lucide-react';
import {
  marketApi, type OverviewChart, type OverviewRange, type PublicMarketRow, type PublicMarketSnapshot,
} from '../../api/market';
import type { IndexRow } from '../../api/marketIndices';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../market/format';
import OverviewPriceChart, { type ChartMode } from '../market/OverviewPriceChart';
import WatchlistStrip from '../market/WatchlistStrip';

// "Market overview" on the public landing page: the NEPSE index chart (GET /market/public/chart/),
// NEPSE indices / sub-indices and the top 5 tracked
// gainers, losers, turnover, volume and transactions for the latest crawled session
// (GET /market/public/snapshot/, no login needed). Like LandingNews, the section hides itself when
// the request fails or there is no data, so visitors never see placeholder numbers.

const card = 'flex h-full flex-col overflow-hidden rounded-2xl border border-[color:var(--l-border)] bg-gradient-to-b from-[var(--l-card-from)] to-[var(--l-card-to)]';
const toneText = { up: 'text-up', down: 'text-down', flat: 'text-[color:var(--l-muted)]' };

const signed = (value: number | string | null) => {
  if (value == null) return '—';
  const n = Number(value);
  return `${n > 0 ? '+' : ''}${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
};

// "Banking SubIndex" -> "Banking", "NEPSE Index" -> "NEPSE" (same as NepseIndices).
const shortName = (row: IndexRow) => row.sector || row.name.replace(/ Index$/, '');

const RANGES: OverviewRange[] = ['1D', '1W', '1M', '3M', '6M', '1Y', '5Y', 'ALL'];

function Stat({ label, value, tone }: { label: string; value: number; tone: 'up' | 'down' | 'flat' }) {
  return (
    <div className="min-w-0 rounded-lg border border-[color:var(--l-border)] px-2.5 py-2">
      <p className="truncate text-[11px] text-[color:var(--l-faint)]">{label}</p>
      <p className={`mt-0.5 font-mono text-base font-semibold ${toneText[tone]}`}>{value}</p>
    </div>
  );
}

function NepseChartCard({ data, theme }: { data: PublicMarketSnapshot; theme: 'dark' | 'light' }) {
  const [range, setRange] = useState<OverviewRange>('1D');
  const [mode, setMode] = useState<ChartMode>('area');
  const [chart, setChart] = useState<OverviewChart | null | 'failed'>(null);
  const [available, setAvailable] = useState<OverviewRange[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setChart(null);
    marketApi.publicChart(range)
      .then((series) => {
        if (cancelled) return;
        setAvailable(series.available_ranges);
        // Fewer than two intraday values stored: start on a daily range instead of an empty chart or a lone dot.
        const daily = series.available_ranges.filter((r) => r !== '1D');
        if (series.points.length < 2 && range === '1D' && daily.length) {
          setRange(daily.includes('1M') ? '1M' : daily[0]);
          return;
        }
        setChart(series);
      })
      .catch(() => { if (!cancelled) setChart('failed'); });
    return () => { cancelled = true; };
  }, [range]);

  const quote = data.nepse;
  const tone = changeTone(quote.change_pct);
  const Arrow = tone === 'down' ? ArrowDown : ArrowUp;
  const previousClose = quote.value != null && quote.change != null ? Number(quote.value) - Number(quote.change) : null;
  const series = chart && chart !== 'failed' ? chart : null;
  const canCandle = !!series?.points.length && series.points.every((p) => p.open != null);
  const { stats } = data;

  return (
    <div className={`${card} gap-3 p-5`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-semibold">NEPSE Index</p>
            <Link to="/technical-charts" aria-label="Open technical charts" title="Technical charts"
              className="flex h-6 w-6 items-center justify-center rounded-md border border-[color:var(--l-border)] text-[color:var(--l-muted)] transition hover:text-[color:var(--l-accent)]">
              <ChevronRight size={15} />
            </Link>
          </div>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className={`font-mono text-2xl font-bold ${tone === 'flat' ? '' : toneText[tone]}`}>
              {quote.value == null ? '—' : formatPrice(quote.value)}
            </span>
            {quote.change != null && <span className={`font-mono text-sm ${toneText[tone]}`}>{signed(quote.change)}</span>}
            {quote.change_pct != null && (
              <span className={`inline-flex items-center gap-1 font-mono text-xs ${toneText[tone]}`}>
                {tone !== 'flat' && <Arrow size={11} />}{formatPct(quote.change_pct)}
              </span>
            )}
          </div>
        </div>
        <span className={`rounded px-2 py-0.5 text-xs font-bold ${data.status === 'OPEN' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'}`}>
          {data.status === 'OPEN' ? 'Market open' : 'Market closed'}
        </span>
      </div>

      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-0.5 text-xs">
          {RANGES.map((r) => {
            const disabled = !!available && !available.includes(r);
            return (
              <button key={r} type="button" onClick={() => setRange(r)} disabled={disabled}
                title={disabled ? 'Not enough stored data for this range' : undefined}
                className={`rounded px-1.5 py-1 font-medium transition ${range === r ? 'text-[color:var(--l-accent)] underline decoration-2 underline-offset-4' : 'text-[color:var(--l-muted)] hover:text-[color:var(--l-text)]'} disabled:cursor-not-allowed disabled:opacity-35`}>
                {r}
              </button>
            );
          })}
        </div>
        <div className="flex shrink-0 rounded-full border border-[color:var(--l-border)] p-0.5">
          <button type="button" onClick={() => setMode('area')} aria-label="Area chart"
            className={`rounded-full px-2 py-0.5 ${mode === 'area' ? 'bg-violet-500/20 text-[color:var(--l-accent)]' : 'text-[color:var(--l-muted)]'}`}>
            <LineChartIcon size={13} />
          </button>
          <button type="button" onClick={() => setMode('candle')} aria-label="Candlestick chart" disabled={!canCandle}
            title={canCandle ? undefined : 'No open / high / low for these points'}
            className={`rounded-full px-2 py-0.5 ${mode === 'candle' ? 'bg-violet-500/20 text-[color:var(--l-accent)]' : 'text-[color:var(--l-muted)]'} disabled:opacity-35`}>
            <CandlestickChart size={13} />
          </button>
        </div>
      </div>

      <div className="h-60">
        {chart === null ? (
          <div className="h-full animate-pulse rounded-lg bg-[var(--l-surface)]" aria-hidden />
        ) : chart === 'failed' ? (
          <p className="flex h-full items-center justify-center text-xs text-[color:var(--l-faint)]">Could not load the chart.</p>
        ) : chart.points.length ? (
          <OverviewPriceChart points={chart.points} intraday={chart.interval === 'intraday'}
            mode={canCandle ? mode : 'area'} previousClose={previousClose} sessionDate={chart.session_date}
            gridColor={theme === 'dark' ? '#242832' : '#e7e5ee'} />
        ) : (
          <p className="flex h-full items-center justify-center px-6 text-center text-xs text-[color:var(--l-faint)]">
            {chart.reason ?? 'No chart data.'}
          </p>
        )}
      </div>

      {stats && (
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Advanced" value={stats.advanced} tone="up" />
          <Stat label="Declined" value={stats.declined} tone="down" />
          <Stat label="Unchanged" value={stats.unchanged} tone="flat" />
        </div>
      )}
    </div>
  );
}

const BOARDS = [['indices', 'Index'], ['sub_indices', 'Sub Index']] as const;
type Board = (typeof BOARDS)[number][0];

function IndicesCard({ data }: { data: PublicMarketSnapshot }) {
  const [board, setBoard] = useState<Board>('indices');
  const { rows, as_of: asOf } = data[board];
  return (
    <div className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--l-border)] px-5 py-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Gauge size={15} className="text-[color:var(--l-accent)]" /> NEPSE &amp; Indices
          {asOf && <span className="text-xs font-normal text-[color:var(--l-faint)]">· {formatTradeDate(asOf)}</span>}
        </h3>
        <div className="inline-flex gap-1 rounded-lg border border-[color:var(--l-border)] p-0.5 text-xs font-medium">
          {BOARDS.map(([key, label]) => (
            <button key={key} type="button" onClick={() => setBoard(key)}
              className={`rounded-md px-3 py-1 transition ${board === key ? 'bg-violet-500/20 text-[color:var(--l-accent)]' : 'text-[color:var(--l-muted)] hover:text-[color:var(--l-text)]'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-[color:var(--l-faint)]">No index values stored yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-[color:var(--l-border)] text-[11px] uppercase tracking-wide text-[color:var(--l-faint)]">
                <th className="px-5 py-2 text-left font-medium">Index</th>
                <th className="px-2 py-2 text-right font-medium">Close</th>
                <th className="px-2 py-2 text-right font-medium">Ch</th>
                <th className="px-2 py-2 text-right font-medium">Ch %</th>
                <th className="px-2 py-2 text-right font-medium">Turnover</th>
                <th className="px-5 py-2 text-right font-medium">Trans</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const tone = toneText[changeTone(row.ch)];
                return (
                  <tr key={row.code} className="border-b border-[color:var(--l-border)] last:border-0">
                    <td className="max-w-[200px] truncate px-5 py-2.5 font-medium" title={row.name}>{shortName(row)}</td>
                    <td className="px-2 text-right font-mono">{formatPrice(row.close)}</td>
                    <td className={`px-2 text-right font-mono ${tone}`}>{signed(row.ch)}</td>
                    <td className={`px-2 text-right font-mono ${tone}`}>{formatPct(row.ch_pct)}</td>
                    <td className="px-2 text-right font-mono text-[color:var(--l-text-2)]">{formatNprCompact(row.turnover)}</td>
                    <td className="px-5 text-right font-mono text-[color:var(--l-text-2)]">{formatCount(row.transactions)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface RankSpec {
  key: 'gainers' | 'losers' | 'top_turnover' | 'top_volume' | 'top_transactions';
  title: string;
  icon: LucideIcon;
  tint: string;
  valueLabel: string;
  value: (row: PublicMarketRow) => React.ReactNode;
}

const pctValue = (row: PublicMarketRow) => <span className={toneText[changeTone(row.change_pct)]}>{formatPct(row.change_pct)}</span>;

const RANKS: RankSpec[] = [
  { key: 'gainers', title: 'Top Gainers', icon: TrendingUp, tint: 'text-up', valueLabel: '% Change', value: pctValue },
  { key: 'losers', title: 'Top Losers', icon: TrendingDown, tint: 'text-down', valueLabel: '% Change', value: pctValue },
  { key: 'top_turnover', title: 'Top Turnover', icon: Coins, tint: 'text-amber-400', valueLabel: 'Turnover', value: (row) => formatNprCompact(row.turnover) },
  { key: 'top_volume', title: 'Top Volume', icon: Layers, tint: 'text-sky-400', valueLabel: 'Volume', value: (row) => formatNprCompact(row.volume) },
  { key: 'top_transactions', title: 'Top Transactions', icon: BarChart3, tint: 'text-violet-400', valueLabel: 'Trades', value: (row) => formatCount(row.transactions) },
];

function RankCard({ spec, rows }: { spec: RankSpec; rows: PublicMarketRow[] }) {
  const Icon = spec.icon;
  return (
    <div className={card}>
      <h3 className="flex items-center gap-2 border-b border-[color:var(--l-border)] px-5 py-3 text-sm font-semibold">
        <Icon size={15} className={spec.tint} /> {spec.title}
      </h3>
      {rows.length === 0 ? (
        <p className="flex-1 px-5 py-8 text-center text-xs text-[color:var(--l-faint)]">No rows for this session.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--l-border)] text-[11px] uppercase tracking-wide text-[color:var(--l-faint)]">
              <th className="px-5 py-2 text-left font-medium">Symbol</th>
              <th className="py-2 text-right font-medium">LTP</th>
              <th className="px-5 py-2 text-right font-medium">{spec.valueLabel}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} className="border-b border-[color:var(--l-border)] last:border-0">
                <td className="px-5 py-2.5">
                  <span className="block font-semibold">{row.symbol}</span>
                  <span className="block max-w-[150px] truncate text-[11px] text-[color:var(--l-faint)]" title={row.name}>{row.name}</span>
                </td>
                <td className="py-2.5 text-right font-mono text-[color:var(--l-text-2)]">{formatPrice(row.close)}</td>
                <td className="px-5 py-2.5 text-right font-mono font-semibold">{spec.value(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`${card} animate-pulse ${className}`} aria-hidden><div className="h-full bg-[var(--l-surface)]" /></div>;
}

export default function LandingMarket({ heading, theme }: { heading: React.ReactNode; theme: 'dark' | 'light' }) {
  const [data, setData] = useState<PublicMarketSnapshot | null | 'failed'>(null);

  useEffect(() => {
    let cancelled = false;
    marketApi.publicSnapshot()
      .then((snapshot) => { if (!cancelled) setData(snapshot); })
      .catch(() => { if (!cancelled) setData('failed'); });
    return () => { cancelled = true; };
  }, []);

  if (data === 'failed') return null;
  if (data && !data.as_of && !data.indices.rows.length && !data.sub_indices.rows.length) return null;

  return (
    <section id="market" className="scroll-mt-20 px-4 py-20 sm:px-6">
      {heading}
      <div className="mx-auto mt-12 max-w-6xl space-y-4">
        {data ? (
          <>
            <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
              <NepseChartCard data={data} theme={theme} />
              <IndicesCard data={data} />
            </div>
            <WatchlistStrip variant="landing" />
            {data.as_of && (
              <p className="pt-4 text-xs text-[color:var(--l-faint)]">
                Tracked companies · session {formatTradeDate(data.as_of)} · end of day, not live
              </p>
            )}
            <div className="grid gap-4 md:grid-cols-2">
              {RANKS.slice(0, 2).map((spec) => <RankCard key={spec.key} spec={spec} rows={data[spec.key]} />)}
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {RANKS.slice(2).map((spec) => <RankCard key={spec.key} spec={spec} rows={data[spec.key]} />)}
            </div>
            <div className="pt-4 text-center">
              <Link to="/register" className="inline-flex items-center gap-1 text-sm font-medium text-[color:var(--l-accent)] hover:underline">
                Create a free account for full rankings, charts and history <ArrowRight size={14} />
              </Link>
            </div>
          </>
        ) : (
          <>
            <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
              <Skeleton className="h-96" /><Skeleton className="h-96" />
            </div>
            <div className="grid gap-4 md:grid-cols-2"><Skeleton className="h-64" /><Skeleton className="h-64" /></div>
          </>
        )}
      </div>
    </section>
  );
}
