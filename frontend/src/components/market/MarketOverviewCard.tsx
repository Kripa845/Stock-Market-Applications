import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, ArrowDown, ArrowUp, CandlestickChart, ChevronLeft, ChevronRight, CircleDollarSign,
  IndianRupee, LineChart as LineChartIcon, Maximize2, MonitorCheck, RotateCcw, TrendingDown, TrendingUp,
} from 'lucide-react';
import type { OverviewRange, OverviewStats } from '../../api/market';
import { useMarketChart, useMarketOverview, useMarketTechnical } from '../../hooks/useMarketOverview';
import { changeTone, formatCount, formatPrice, formatTradeDate } from './format';
import OverviewPriceChart, { type ChartMode } from './OverviewPriceChart';
import TechnicalSummaryView from './TechnicalSummaryView';

// Market Overview card: header for the picked instrument (NEPSE index or a tracked company),
// price chart, and the tracked companies' session stats; the header arrow flips to the
// technical summary of the same instrument.

const RANGES: OverviewRange[] = ['1D', '1W', '1M', '3M', '6M', '1Y', '5Y', 'ALL'];
type View = 'overview' | 'technical';

const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-primary' };
const tonePill = { up: 'bg-up/15 text-up', down: 'bg-down/15 text-down', flat: 'bg-bg-elevated text-text-muted' };

/** "Mon, Oct 12, 03:00:00 PM" in Nepal time. */
const stamp = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString('en-US', {
      timeZone: 'Asia/Kathmandu', weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
    })
    : '—';

function StatBox({ label, value, tone }: { label: string; value: number; tone: 'up' | 'down' | 'blue' }) {
  const styles = {
    up: { box: 'border-up/30 bg-up/10', text: 'text-up', Icon: TrendingUp },
    down: { box: 'border-down/30 bg-down/10', text: 'text-down', Icon: TrendingDown },
    blue: { box: 'border-sky-400/30 bg-sky-400/10', text: 'text-sky-400', Icon: null },
  }[tone];
  const Icon = styles.Icon;
  return (
    <div className={`min-w-0 rounded-lg border px-2.5 py-2 ${styles.box}`}>
      <p className={`truncate text-xs font-semibold ${styles.text}`}>{label}</p>
      <p className={`mt-1 flex items-center gap-1.5 font-mono text-base font-bold ${styles.text}`}>
        {value}{Icon && <Icon size={13} />}
      </p>
    </div>
  );
}

function TotalCard({ icon: Icon, tint, label, value, note }: {
  icon: typeof IndianRupee; tint: string; label: string; value: string; note?: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-lg border border-bg-border bg-bg-elevated px-3 py-3">
      <Icon size={22} className={`shrink-0 ${tint}`} />
      <div className="min-w-0">
        <p className="truncate text-xs text-text-secondary">{label}</p>
        <p className="truncate font-mono text-sm font-bold text-text-primary">{value}</p>
        {note && <p className="truncate text-[10px] text-amber-400">{note}</p>}
      </div>
    </div>
  );
}

function StatsPanel({ stats, label, tradeDate }: { stats: OverviewStats; label: string; tradeDate: string | null }) {
  const partialTrades = stats.transactions_reported < stats.total_scrips_traded;
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-text-muted">{label} · session {formatTradeDate(tradeDate)}</p>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
        <StatBox label="Advanced" value={stats.advanced} tone="up" />
        <StatBox label="Declined" value={stats.declined} tone="down" />
        <StatBox label="Unchanged" value={stats.unchanged} tone="blue" />
        <StatBox label="+ve Circuit" value={stats.positive_circuit} tone="up" />
        <StatBox label="-ve Circuit" value={stats.negative_circuit} tone="down" />
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <TotalCard icon={IndianRupee} tint="text-up" label="Total Turnover Rs:" value={stats.total_turnover_display ?? '—'} />
        <TotalCard icon={MonitorCheck} tint="text-sky-400" label="Total Traded Shares" value={formatCount(stats.total_traded_shares)} />
        <TotalCard icon={CircleDollarSign} tint="text-sky-400" label="Total Transactions" value={formatCount(stats.total_transactions)}
          note={partialTrades ? `${stats.transactions_reported} of ${stats.total_scrips_traded} companies reported` : undefined} />
        <TotalCard icon={LineChartIcon} tint="text-amber-400" label="Total Scrips Traded"
          value={`${stats.total_scrips_traded}`} />
      </div>
    </div>
  );
}

export default function MarketOverviewCard() {
  const [symbol, setSymbol] = useState('NEPSE');
  const [range, setRange] = useState<OverviewRange>('1D');
  const [mode, setMode] = useState<ChartMode>('area');
  const [view, setView] = useState<View>('overview');
  const chartBox = useRef<HTMLDivElement>(null);

  const overview = useMarketOverview(symbol);
  const chart = useMarketChart(symbol, range);
  const technical = useMarketTechnical(symbol, view === 'technical');

  // Refresh the intraday chart together with the 60s summary poll while the session is open.
  const { reload: reloadChart } = chart;
  const asOf = overview.data?.instrument.as_of;
  const seenAsOf = useRef(asOf);
  useEffect(() => {
    const changed = seenAsOf.current !== undefined && seenAsOf.current !== asOf;
    seenAsOf.current = asOf;
    if (changed && range === '1D') reloadChart(true);
  }, [asOf, range, reloadChart]);

  const data = overview.data;
  const quote = data?.instrument;
  const tone = changeTone(quote?.change_pct);
  const Arrow = tone === 'down' ? ArrowDown : ArrowUp;
  const available = chart.data?.available_ranges;
  const intraday = chart.data?.interval === 'intraday';
  const previousClose = quote?.value != null && quote.change != null ? Number(quote.value) - Number(quote.change) : null;
  const canCandle = !!chart.data?.points.length && chart.data.points.every((p) => p.open != null);

  const refresh = () => { overview.reload(); chart.reload(); if (view === 'technical') technical.reload(); };
  const fullscreen = () => { chartBox.current?.requestFullscreen?.().catch(() => undefined); };

  return (
    <section className="card h-full space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)} aria-label="Instrument"
            className="max-w-[9rem] cursor-pointer appearance-none rounded-md bg-transparent pr-1 text-lg font-bold text-text-primary hover:bg-bg-elevated focus:outline-none">
            {(data?.instruments ?? [{ symbol: 'NEPSE', name: 'NEPSE Index', kind: 'index' as const }]).map((item) => (
              <option key={item.symbol} value={item.symbol} className="bg-bg-card text-sm">{item.symbol}</option>
            ))}
          </select>
          <button onClick={() => setView(view === 'overview' ? 'technical' : 'overview')}
            aria-label={view === 'overview' ? 'Show technical analysis' : 'Back to overview'}
            title={view === 'overview' ? 'Technical analysis' : 'Overview'}
            className="flex h-6 w-6 items-center justify-center rounded-md bg-bg-elevated text-text-primary hover:bg-accent/20 hover:text-accent-light">
            {view === 'overview' ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
          </button>
        </div>
        <span className="pt-1 text-right text-xs text-sky-400">{stamp(data?.timestamp ?? null)}</span>
      </div>

      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className={`font-mono text-2xl font-bold ${toneText[tone]}`}>{quote?.value == null ? '—' : formatPrice(quote.value)}</span>
          {quote?.change != null && (
            <span className={`font-mono text-sm ${toneText[tone]}`}>
              {Number(quote.change) > 0 ? '+ ' : Number(quote.change) < 0 ? '- ' : ''}{formatPrice(Math.abs(Number(quote.change)))}
            </span>
          )}
          {quote?.change_pct != null && (
            <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-xs ${tonePill[tone]}`}>
              {tone !== 'flat' && <Arrow size={11} />}{Math.abs(Number(quote.change_pct)).toFixed(2)}%
            </span>
          )}
        </div>
        {data && (
          <span className={`rounded px-2 py-0.5 text-xs font-bold ${data.status === 'OPEN' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'}`}>
            {data.status}
          </span>
        )}
      </div>

      {overview.error && !data && (
        <p className="flex items-center gap-1.5 text-xs text-down">
          <AlertTriangle size={13} /> Could not load the market overview.
          <button onClick={() => overview.reload()} className="underline">Retry</button>
        </p>
      )}

      {view === 'overview' ? (
        <div key={`overview-${symbol}`} className="overview-slide-back space-y-3">
          {/* Chart controls */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex flex-wrap gap-0.5 text-xs">
              {RANGES.map((r) => {
                const disabled = !!available && !available.includes(r);
                return (
                  <button key={r} onClick={() => setRange(r)} disabled={disabled}
                    title={disabled ? 'Not enough stored data for this range' : undefined}
                    className={`rounded px-1.5 py-1 font-medium ${range === r ? 'text-text-primary underline decoration-2 underline-offset-4' : 'text-text-secondary hover:text-text-primary'} disabled:cursor-not-allowed disabled:opacity-35`}>
                    {r}
                  </button>
                );
              })}
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <div className="flex rounded-full border border-bg-border p-0.5">
                <button onClick={() => setMode('area')} aria-label="Area chart"
                  className={`rounded-full px-2 py-0.5 ${mode === 'area' ? 'bg-up/30 text-up' : 'text-text-secondary'}`}>
                  <LineChartIcon size={13} />
                </button>
                <button onClick={() => setMode('candle')} aria-label="Candlestick chart" disabled={!canCandle}
                  title={canCandle ? undefined : 'No open / high / low for these points'}
                  className={`rounded-full px-2 py-0.5 ${mode === 'candle' ? 'bg-up/30 text-up' : 'text-text-secondary'} disabled:opacity-35`}>
                  <CandlestickChart size={13} />
                </button>
              </div>
              <button onClick={refresh} aria-label="Refresh" className="rounded-full border border-bg-border p-1.5 text-text-secondary hover:text-text-primary">
                <RotateCcw size={12} />
              </button>
              <button onClick={fullscreen} aria-label="Full screen" className="rounded-full border border-bg-border p-1.5 text-text-secondary hover:text-text-primary">
                <Maximize2 size={12} />
              </button>
            </div>
          </div>

          <div ref={chartBox} className="h-56 bg-bg-card">
            {chart.loading && !chart.data ? (
              <p className="flex h-full items-center justify-center text-xs text-text-muted">Loading chart…</p>
            ) : chart.error ? (
              <p className="flex h-full items-center justify-center text-xs text-down">Could not load the chart.</p>
            ) : chart.data && chart.data.points.length > 0 ? (
              <OverviewPriceChart points={chart.data.points} intraday={intraday} mode={mode} previousClose={previousClose} />
            ) : (
              <p className="flex h-full items-center justify-center px-6 text-center text-xs text-text-muted">
                {chart.data?.reason ?? 'No chart data.'}
              </p>
            )}
          </div>

          {data?.stats ? (
            <StatsPanel stats={data.stats} label={data.stats_label} tradeDate={data.trade_date} />
          ) : data?.reason ? (
            <p className="text-xs text-text-muted">{data.reason}</p>
          ) : overview.loading ? (
            <p className="text-xs text-text-muted">Loading stats…</p>
          ) : null}
        </div>
      ) : (
        <div key={`technical-${symbol}`} className="overview-slide-next">
          {technical.error ? (
            <p className="flex items-center gap-1.5 text-xs text-down">
              <AlertTriangle size={13} /> Could not load the technical analysis.
              <button onClick={() => technical.reload()} className="underline">Retry</button>
            </p>
          ) : technical.data && technical.data.symbol === symbol ? (
            <TechnicalSummaryView data={technical.data} />
          ) : (
            <p className="py-10 text-center text-xs text-text-muted">Loading technical analysis…</p>
          )}
        </div>
      )}
    </section>
  );
}
