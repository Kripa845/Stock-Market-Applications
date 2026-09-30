

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AlertTriangle, ArrowLeft, ArrowUp, ArrowDown,
  Loader2, Newspaper, TrendingUp, TrendingDown, Star,
  Activity, BarChart3, Info,
} from 'lucide-react';
import {
  Bar, ComposedChart, Line,
  ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

import { getCompanies } from '../api/companies';
import { stocksApi } from '../api/stocks';
import { newsApi } from '../api/news';
import {
  analysisApi,
  type BehaviorSummary,
  type NewsPriceCorrelation,
} from '../api/analysis';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';
import KlinePriceChart from '../components/charts/KlinePriceChart';
import type { Company, DailyPrice, FloorsheetTransaction, NewsArticle, SentimentLabel } from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

const TABS = ['Overview', 'Behavior', 'Correlation', 'News', 'Floorsheet'] as const;
type Tab = typeof TABS[number];

const TT = { background: '#161B2E', border: '1px solid #1E2538', borderRadius: 10, fontSize: 12 };

const C = {
  price:   '#22C55E',
  sell:    '#EF4444',
  volume:  '#7C3AED',
  vwap:    '#F59E0B',
  buy:     '#22C55E',
  neutral: '#64748B',
  news:    '#A78BFA',
  sent:    '#F472B6',
};

function n(v: string | number | null | undefined, dp = 2): string {
  if (v === null || v === undefined) return '—';
  return Number(v).toFixed(dp);
}

function fmt(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000)     return `${(v / 1_000).toFixed(1)}K`;
  return String(v);
}

// ─── Small reusable pieces ────────────────────────────────────────────────────

function SentimentBadge({ label }: { label: SentimentLabel }) {
  if (!label) return null;
  const m = { positive: 'green', negative: 'red', neutral: 'gray' } as const;
  return <Badge variant={m[label]}>{label}</Badge>;
}

function Metric({
  label, value, sub, color,
}: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="bg-bg-elevated rounded-lg p-3 flex flex-col gap-0.5">
      <p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p>
      <p className={clsx('text-sm font-semibold font-mono', color ?? 'text-text-primary')}>{value}</p>
      {sub && <p className="text-[10px] text-text-muted">{sub}</p>}
    </div>
  );
}

function SectionHead({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={14} className="text-accent-light shrink-0" />
      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
    </div>
  );
}

// ─── Broker aggregation (from raw floorsheet transactions) ────────────────────

interface BrokerTotals { broker: string; quantity: number; amount: number; transactions: number }

function aggregateBrokers(rows: FloorsheetTransaction[], field: 'buyer_broker' | 'seller_broker'): BrokerTotals[] {
  const m = new Map<string, BrokerTotals>();
  rows.forEach(r => {
    const b = r[field];
    const c = m.get(b) ?? { broker: b, quantity: 0, amount: 0, transactions: 0 };
    c.quantity     += r.quantity;
    c.amount       += Number(r.amount ?? Number(r.rate) * r.quantity);
    c.transactions += 1;
    m.set(b, c);
  });
  return [...m.values()].sort((a, b) => b.quantity - a.quantity).slice(0, 10);
}

function BrokerTable({ rows, title, color }: { rows: BrokerTotals[]; title: string; color: string }) {
  if (!rows.length) return (
    <div className="card">
      <p className={`text-xs font-semibold mb-3 ${color}`}>{title}</p>
      <p className="text-xs text-text-muted py-2 text-center">No floorsheet data.</p>
    </div>
  );
  return (
    <div className="card">
      <p className={`text-xs font-semibold mb-3 ${color}`}>{title}</p>
      <table className="w-full text-xs">
        <thead><tr className="text-text-muted border-b border-bg-border">
          <th className="text-left py-1 font-medium">Broker</th>
          <th className="text-right py-1 font-medium">Qty</th>
          <th className="text-right py-1 font-medium">Txns</th>
        </tr></thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.broker} className="table-row">
              <td className="py-1.5 text-text-secondary">{r.broker}</td>
              <td className={`py-1.5 text-right font-mono font-medium ${color}`}>{fmt(r.quantity)}</td>
              <td className="py-1.5 text-right text-text-muted">{r.transactions}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Behavior summary panel ───────────────────────────────────────────────────

function BehaviorPanel({ b }: { b: BehaviorSummary }) {
  const pressureColor = b.pressure === 'buying' ? 'text-up' : b.pressure === 'selling' ? 'text-down' : 'text-text-secondary';

  return (
    <div className="space-y-5">
      {/* Window metadata */}
      {b.latest_trading_date && (
        <p className="text-xs text-text-muted">
          Analysis window:&nbsp;
          <span className="text-text-secondary font-medium">
            {b.window_start_date} → {b.window_end_date}
          </span>
          &nbsp;({b.unique_trading_dates} trading sessions)
          &nbsp;· Latest date:&nbsp;
          <span className="text-text-secondary font-medium">{b.latest_trading_date}</span>
        </p>
      )}

      {/* Summary narrative */}
      <div className="rounded-lg border border-bg-border bg-bg-elevated px-4 py-3">
        <p className="text-sm text-text-secondary leading-relaxed">{b.summary_text}</p>
      </div>

      {/* Key metrics grid */}
      <div>
        <SectionHead icon={BarChart3} title="Price & VWAP" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          <Metric label="Latest Price"     value={b.latest_price    ? `Rs. ${n(b.latest_price)}`    : '—'} />
          <Metric label="Previous Close"   value={b.previous_close  ? `Rs. ${n(b.previous_close)}`  : '—'} />
          <Metric
            label="Daily Return"
            value={b.daily_return_pct ? `${Number(b.daily_return_pct) >= 0 ? '+' : ''}${n(b.daily_return_pct)}%` : '—'}
            color={b.daily_return_pct ? (Number(b.daily_return_pct) >= 0 ? 'text-up' : 'text-down') : undefined}
          />
          <Metric
            label="Daily VWAP"
            value={b.vwap ? `Rs. ${n(b.vwap)}` : '—'}
            sub="daily turnover / daily volume"
            color="text-yellow-400"
          />
          <Metric
            label="VWAP Spread"
            value={b.price_to_vwap_spread_pct !== null ? `${Number(b.price_to_vwap_spread_pct) >= 0 ? '+' : ''}${n(b.price_to_vwap_spread_pct)}%` : '—'}
            color={b.price_to_vwap_spread_pct !== null ? (Number(b.price_to_vwap_spread_pct) >= 0 ? 'text-up' : 'text-down') : undefined}
            sub="close vs daily VWAP"
          />
        </div>
      </div>

      {/* Pressure */}
      <div>
        <SectionHead icon={Activity} title="Pressure Indicator" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 mb-2">
          <Metric
            label="Pressure"
            value={b.pressure.charAt(0).toUpperCase() + b.pressure.slice(1)}
            color={pressureColor}
          />
          <Metric label="Pressure Score" value={b.pressure_score ? n(b.pressure_score, 1) : '—'} sub="-100 to +100" />
          <Metric label="Method" value={b.pressure_method} />
        </div>
        <div className="flex items-start gap-1.5 text-[11px] text-text-muted rounded-lg border border-bg-border px-3 py-2">
          <Info size={11} className="shrink-0 mt-0.5" />
          <span>
            Pressure is an OHLCV-based analytical proxy ({b.pressure_method}).
            It is not evidence of actual order-book buying or selling pressure.
          </span>
        </div>
      </div>

      {/* Volume */}
      <div>
        <SectionHead icon={BarChart3} title="Volume" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          <Metric label="Current Volume"    value={fmt(b.current_volume)} />
          <Metric
            label="20-Session Avg"
            value={b.volume_avg_20d ? fmt(Math.round(Number(b.volume_avg_20d))) : '—'}
            sub="previous 20 trading sessions"
          />
          <Metric
            label="Volume Ratio"
            value={b.volume_ratio ? `${n(b.volume_ratio)}×` : '—'}
            sub="anomaly threshold ≥ 1.5×"
            color={b.volume_anomaly ? 'text-down' : 'text-text-primary'}
          />
          <Metric
            label="Volume Anomaly"
            value={b.volume_anomaly ? '⚡ Detected' : '✓ Normal'}
            color={b.volume_anomaly ? 'text-down' : 'text-up'}
          />
          <Metric
            label="Baseline Sessions"
            value={`${b.volume_baseline_sessions} sessions`}
            color={b.has_sufficient_history ? 'text-text-primary' : 'text-yellow-400'}
          />
          {!b.has_sufficient_history && (
            <div className="col-span-2 sm:col-span-3 lg:col-span-4 text-[11px] text-yellow-400 flex items-center gap-1">
              <Info size={11} /> Volume baseline is provisional — fewer than 20 sessions available.
            </div>
          )}
        </div>
      </div>

      <div className="card mt-3">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-semibold text-text-primary">Persisted volume anomaly days</h4>
          <Badge variant={b.volume_anomalies.summary_count ? 'red' : 'gray'}>{b.volume_anomalies.summary_count} flagged</Badge>
        </div>
        {b.volume_anomalies.results.length ? <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-text-muted border-b border-bg-border"><th className="text-left py-1">Date</th><th>Reason</th><th>Z-score</th><th>% of average</th></tr></thead><tbody>
          {b.volume_anomalies.results.map(row => <tr key={row.date} className="table-row"><td className="py-1.5">{row.date}</td><td className="text-center">{row.reason}</td><td className="text-center">{row.z_score?.toFixed(2) ?? '—'}</td><td className="text-center">{row.pct_of_avg !== null ? `${(row.pct_of_avg * 100).toFixed(1)}%` : '—'}</td></tr>)}
        </tbody></table></div> : <p className="text-[11px] text-text-muted">No persisted anomaly days in this analysis window.</p>}
        <p className="text-[10px] text-text-muted mt-2">Flagged when volume is at least 2.5× the SMA of the preceding 20 trading sessions. Current day is excluded; incomplete baselines are not scored.</p>
      </div>

      {/* Broker activity */}
      <div>
        <SectionHead icon={Activity} title="Broker Activity (Floorsheet Sample)" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
          <Metric label="Most Active Buyer"  value={b.most_active_buyer  ?? '—'} />
          <Metric label="Most Active Seller" value={b.most_active_seller ?? '—'} />
          <Metric label="Top Net Buyer"      value={b.top_net_buyer      ?? '—'} color="text-up" />
          <Metric label="Top Net Seller"     value={b.top_net_seller     ?? '—'} color="text-down" />
        </div>

        {b.brokers.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[560px]">
              <thead>
                <tr className="border-b border-bg-border text-text-muted">
                  <th className="text-left py-1.5 font-medium">Broker</th>
                  <th className="text-right py-1.5 font-medium">Buy Qty</th>
                  <th className="text-right py-1.5 font-medium">Sell Qty</th>
                  <th className="text-right py-1.5 font-medium">Net Qty</th>
                  <th className="text-right py-1.5 font-medium">Trades</th>
                </tr>
              </thead>
              <tbody>
                {b.brokers.map(br => (
                  <tr key={br.broker} className="table-row">
                    <td className="py-1.5 text-text-secondary font-mono">{br.broker}</td>
                    <td className="py-1.5 text-right font-mono text-up">{fmt(br.buy_quantity)}</td>
                    <td className="py-1.5 text-right font-mono text-down">{fmt(br.sell_quantity)}</td>
                    <td className={clsx(
                      'py-1.5 text-right font-mono font-semibold',
                      br.net_quantity > 0 ? 'text-up' : br.net_quantity < 0 ? 'text-down' : 'text-text-secondary',
                    )}>
                      {br.net_quantity > 0 ? '+' : ''}{fmt(br.net_quantity)}
                    </td>
                    <td className="py-1.5 text-right text-text-muted">{br.trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {b.floorsheet_sampled_dates.length > 0 && (
          <p className="mt-2 text-[10px] text-text-muted">
            Floorsheet coverage: {b.floorsheet_sampled_dates.join(', ')}.
            This is a representative sample — not a continuous series.
          </p>
        )}

        {/* News */}
        <div className="grid grid-cols-2 gap-2 mt-4">
          <Metric
            label="News Sentiment (window)"
            value={b.news_sentiment_score.toFixed(3)}
            color={b.news_sentiment_score > 0.1 ? 'text-up' : b.news_sentiment_score < -0.1 ? 'text-down' : 'text-text-secondary'}
            sub="avg sentiment score"
          />
          <Metric label="Articles in Window" value={b.news_count_30d} />
        </div>
      </div>
    </div>
  );
}

// ─── Correlation panel ────────────────────────────────────────────────────────

function CorrelationPanel({ c }: { c: NewsPriceCorrelation }) {
  const withNews = c.data_points.filter(d => d.news_count > 0);
  const correlationLabels: Record<string, string> = {
    news_intensity_vs_signed_return: 'News intensity vs signed return',
    news_intensity_vs_abs_return: 'News intensity vs absolute return',
    news_intensity_vs_volume_change: 'News intensity vs volume change',
  };

  return (
    <div className="space-y-5">
      {/* Disclaimer */}
      <div className="flex items-start gap-1.5 text-[11px] text-text-muted rounded-lg border border-bg-border px-3 py-2">
        <Info size={11} className="shrink-0 mt-0.5" />
        <span>{c.analysis_note}</span>
      </div>

      <div className="card space-y-3">
        <SectionHead icon={Activity} title="News activity vs subsequent market movement" />
        <p className="text-xs text-yellow-400">{c.caveat ?? 'Exploratory only — small sample size; not a validated trading signal.'}</p>
        <p className="text-[11px] text-text-muted">Pearson r and Spearman rho with p-values; news intensity sums company-tag confidence scores (minimum 0.5).</p>
        {[1, 2].map(lag => <div key={lag} className="overflow-x-auto">
          <h4 className="text-xs font-semibold text-text-secondary mb-1">T+{lag}</h4>
          <table className="w-full text-xs min-w-[620px]"><thead><tr className="text-text-muted border-b border-bg-border"><th className="text-left py-1">Pairing</th><th>Pearson r (p)</th><th>Spearman ρ (p)</th><th>N</th><th>Reliability</th></tr></thead>
            <tbody>{Object.entries(correlationLabels).map(([key, label]) => {
              const value = c.by_lag?.[`${lag}d`]?.[key];
              return <tr key={key} className={clsx('table-row', value && !value.reliable && 'opacity-50')}>
                <td className="py-1.5">{label}</td><td className="text-center">{value?.pearson_r ?? '—'} ({value?.pearson_p ?? '—'})</td>
                <td className="text-center">{value?.spearman_rho ?? '—'} ({value?.spearman_p ?? '—'})</td><td className="text-center">{value?.n ?? 0}</td>
                <td className="text-center">{value ? <Badge variant={value.reliable ? 'green' : 'gray'}>{value.reliable ? 'Reliable (N ≥ 8)' : 'Low N'}</Badge> : 'Pending backfill'}</td>
              </tr>;
            })}</tbody></table>
        </div>)}
      </div>

      {/* Pearson r */}
      <div className="card py-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <p className="text-[10px] text-text-muted uppercase tracking-wider">Pearson r (sentiment → next-day price change)</p>
            <p className={clsx(
              'text-2xl font-bold font-mono mt-1',
              c.correlation_coefficient === null ? 'text-text-muted'
              : Math.abs(c.correlation_coefficient) > 0.4 ? 'text-up'
              : 'text-text-secondary',
            )}>
              {c.correlation_coefficient !== null ? c.correlation_coefficient.toFixed(3) : 'Insufficient data'}
            </p>
          </div>
          {c.correlation_coefficient !== null && (
            <Badge variant={Math.abs(c.correlation_coefficient) > 0.4 ? 'green' : 'gray'}>
              {c.correlation_label}
            </Badge>
          )}
          <p className="text-xs text-text-muted ml-auto">
            {withNews.length} days with news coverage · {c.data_points.length} total trading days in window
          </p>
        </div>
        <p className="text-[11px] text-yellow-400/80 mt-2 flex items-center gap-1">
          <Info size={10} />
          Correlation does not imply causation. This is an observational signal, not a trading indicator.
        </p>
      </div>

      {/* Scatter: sentiment vs next-day price change */}
      {withNews.length >= 2 ? (
        <div className="card">
          <SectionHead icon={Activity} title="Sentiment (day N) vs Price Change (day N+1)" />
          <ResponsiveContainer width="100%" height={200}>
            <ScatterChart margin={{ top: 4, right: 16, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" />
              <XAxis
                type="number" dataKey="sentiment_score" name="Sentiment"
                domain={[-1, 1]} tick={{ fontSize: 9, fill: '#475569' }}
                tickLine={false} axisLine={false}
                label={{ value: 'Sentiment score (day N)', position: 'insideBottom', offset: -10, fill: '#475569', fontSize: 9 }}
              />
              <YAxis
                type="number" dataKey="price_change_pct" name="Next-day Δ%"
                tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false}
                width={40} tickFormatter={v => `${v.toFixed(1)}%`}
              />
              <ReferenceLine x={0} stroke="#1E2538" />
              <ReferenceLine y={0} stroke="#1E2538" />
              <Tooltip
                contentStyle={TT} cursor={{ strokeDasharray: '3 3' }}
                formatter={(v: unknown, nm: unknown) => [
                  nm === 'Next-day Δ%' ? `${Number(v ?? 0).toFixed(2)}%` : Number(v ?? 0).toFixed(3),
                  String(nm),
                ]}
                labelFormatter={(_, pl) => pl?.[0]?.payload?.date ?? ''}
              />
              <Scatter data={withNews} fill={C.news} fillOpacity={0.8} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="card py-8 text-center text-xs text-text-muted">
          Not enough news-tagged trading days for a scatter chart (need ≥ 2, have {withNews.length}).
        </div>
      )}

      {/* Bar + Line: news count vs next-day price change */}
      {withNews.length >= 1 && (
        <div className="card">
          <SectionHead icon={Newspaper} title="Article Count & Next-Day Price Change (days with news)" />
          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={withNews} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} />
              <YAxis yAxisId="l" tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} width={28} />
              <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} width={36} tickFormatter={v => `${v.toFixed(1)}%`} />
              <Tooltip contentStyle={TT} />
              <Bar    yAxisId="l" dataKey="news_count"      fill={C.news}  opacity={0.5} name="Articles"     radius={[2,2,0,0]} maxBarSize={20} />
              <Line   yAxisId="r" dataKey="price_change_pct" stroke={C.sent} strokeWidth={1.5} dot={{ r: 3 }} name="Next-day Δ%" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Data table */}
      {withNews.length > 0 && (
        <div className="card overflow-x-auto">
          <SectionHead icon={Newspaper} title="Days With News Coverage" />
          <table className="w-full text-xs min-w-[480px]">
            <thead>
              <tr className="border-b border-bg-border text-text-muted">
                <th className="text-left py-1.5 font-medium">Date</th>
                <th className="text-right py-1.5 font-medium">Articles</th>
                <th className="text-right py-1.5 font-medium">Avg Sentiment</th>
                <th className="text-right py-1.5 font-medium">Price Chg % (same day)</th>
                <th className="text-right py-1.5 font-medium">Volume</th>
              </tr>
            </thead>
            <tbody>
              {withNews.map((d, i) => (
                <tr key={i} className="table-row">
                  <td className="py-2 font-mono text-text-secondary">{d.date}</td>
                  <td className="py-2 text-right"><Badge variant="purple">{d.news_count}</Badge></td>
                  <td className={clsx('py-2 text-right font-mono',
                    d.sentiment_score > 0.1 ? 'text-up' : d.sentiment_score < -0.1 ? 'text-down' : 'text-text-secondary',
                  )}>
                    {d.sentiment_score >= 0 ? '+' : ''}{d.sentiment_score.toFixed(3)}
                  </td>
                  <td className={clsx('py-2 text-right font-mono',
                    d.price_change_pct > 0 ? 'text-up' : d.price_change_pct < 0 ? 'text-down' : 'text-text-secondary',
                  )}>
                    <span className="flex items-center justify-end gap-1">
                      {d.price_change_pct > 0 ? <ArrowUp size={9} /> : d.price_change_pct < 0 ? <ArrowDown size={9} /> : null}
                      {d.price_change_pct >= 0 ? '+' : ''}{d.price_change_pct.toFixed(2)}%
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono text-text-secondary">{fmt(d.volume)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-text-muted mt-1.5">
            Price change shown is the same-day return.  The correlation
            analysis uses the <em>next</em> trading session's return relative
            to the news publication date.
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function StockDetail() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate   = useNavigate();

  const [tab,        setTab]        = useState<Tab>('Overview');
  const [priceRange, setPriceRange] = useState<7 | 30 | 90>(30);

  const [company,     setCompany]     = useState<Company | null>(null);
  const [prices,      setPrices]      = useState<DailyPrice[]>([]);
  const [floorsheet,  setFloorsheet]  = useState<FloorsheetTransaction[]>([]);
  const [floorDate,   setFloorDate]   = useState<string | null>(null);
  const [relatedNews, setRelatedNews] = useState<NewsArticle[]>([]);
  const [behavior,    setBehavior]    = useState<BehaviorSummary | null>(null);
  const [correlation, setCorrelation] = useState<NewsPriceCorrelation | null>(null);

  const [loading,         setLoading]         = useState(true);
  const [loadingBehavior, setLoadingBehavior] = useState(false);
  const [loadingCorr,     setLoadingCorr]     = useState(false);
  const [error,           setError]           = useState('');
  const [behaviorError,   setBehaviorError]   = useState('');
  const [corrError,       setCorrError]       = useState('');

  // Initial load: company lookup + price + floorsheet + news (all parallel)
  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    setBehavior(null);
    setCorrelation(null);

    (async () => {
      try {
        const companyData = await getCompanies({ search: symbol, status: 'active' });
        const found = companyData.results[0];
        if (!found) throw new Error('Company not found');
        setCompany(found);
        analysisApi.getBehavior(found.id).then(setBehavior).catch(() => undefined);

        const [priceData, floorData, newsData] = await Promise.all([
          stocksApi.getPrices(found.id, `${priceRange}d`),
          stocksApi.getFloorsheet(found.id),
          newsApi.getNews({ company_id: found.id }),
        ]);
        setPrices(priceData.prices);
        setFloorsheet(floorData.transactions);
        setFloorDate(floorData.date);
        setRelatedNews(newsData.results);
      } catch (err: unknown) {
        setError((err as { message?: string })?.message || 'Unable to load company data.');
        setCompany(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [symbol, priceRange]);

  // Lazy-load behavior when tab is selected or company changes
  const loadBehavior = useCallback(async (companyId: number) => {
    setLoadingBehavior(true);
    setBehaviorError('');
    try {
      const data = await analysisApi.getBehavior(companyId);
      setBehavior(data);
    } catch {
      setBehaviorError('Unable to load behavior analysis. Run the trading crawler then the analysis task.');
    } finally {
      setLoadingBehavior(false);
    }
  }, []);

  // Lazy-load correlation when tab is selected or company changes
  const loadCorrelation = useCallback(async (companyId: number) => {
    setLoadingCorr(true);
    setCorrError('');
    try {
      const data = await analysisApi.getNewsCorrelation(companyId);
      setCorrelation(data);
    } catch {
      setCorrError('Unable to load correlation data.');
    } finally {
      setLoadingCorr(false);
    }
  }, []);

  // Trigger lazy loads when tab becomes active
  useEffect(() => {
    if (!company) return;
    if (tab === 'Behavior' && !behavior && !loadingBehavior) {
      loadBehavior(company.id);
    }
    if (tab === 'Correlation' && !correlation && !loadingCorr) {
      loadCorrelation(company.id);
    }
  }, [tab, company, behavior, correlation, loadingBehavior, loadingCorr, loadBehavior, loadCorrelation]);

  // Broker aggregation from raw floorsheet
  const buyers  = useMemo(() => aggregateBrokers(floorsheet, 'buyer_broker'),  [floorsheet]);
  const sellers = useMemo(() => aggregateBrokers(floorsheet, 'seller_broker'), [floorsheet]);

  // Price chart helpers
  const sliced    = useMemo(() => prices.slice(-priceRange), [prices, priceRange]);
  const last      = sliced.length ? +sliced[sliced.length - 1].close : 0;
  const prev      = prices.length >= 2 ? +prices[prices.length - 2].close : last;
  const change    = +(last - prev).toFixed(2);
  const changePct = prev > 0 ? +((change / prev) * 100).toFixed(2) : 0;
  const positive  = changePct >= 0;

  // ── Loading / error screens ──────────────────────────────────────────────

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="animate-spin text-accent" size={28} />
    </div>
  );

  if (error || !company) return (
    <div className="space-y-4">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary">
        <ArrowLeft size={14} /> Back
      </button>
      <div className="card flex flex-col items-center gap-3 py-16 text-center">
        <AlertTriangle size={32} className="text-down" />
        <p className="font-semibold text-text-primary">{error || `Company "${symbol?.toUpperCase()}" not found`}</p>
        <p className="text-sm text-text-muted">Check the symbol or go back to the companies list.</p>
      </div>
    </div>
  );

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">

      {/* Back */}
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors">
        <ArrowLeft size={14} /> Back
      </button>

      {/* Header */}
      <div className="card flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center font-bold font-mono text-white text-sm">
            {company.symbol.slice(0, 3)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-text-primary">{company.symbol}</h1>
              <Badge variant="gray">{company.sector}</Badge>
            </div>
            <p className="text-sm text-text-secondary">{company.name}</p>
          </div>
        </div>
        <div className="text-right">
          {last > 0 ? (
            <>
              <p className="text-3xl font-bold font-mono text-text-primary">Rs.&nbsp;{last.toFixed(2)}</p>
              <p className={`flex items-center justify-end gap-1 text-sm font-medium mt-1 ${positive ? 'text-up' : 'text-down'}`}>
                {positive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {positive ? '+' : ''}{change} ({positive ? '+' : ''}{changePct}%)
              </p>
            </>
          ) : (
            <p className="text-sm text-text-muted">No price data</p>
          )}
        </div>
        <button className="p-2 rounded-lg hover:bg-bg-elevated transition-colors text-text-muted hover:text-yellow-400">
          <Star size={16} />
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1 bg-bg-elevated rounded-xl p-1 w-fit">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === t ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Overview ─────────────────────────────────────────────────────── */}
      {tab === 'Overview' && (
        <div className="space-y-4">
          <div className="flex items-center gap-1 bg-bg-elevated rounded-lg p-0.5 w-fit">
            {([7, 30, 90] as const).map(d => (
              <button key={d} onClick={() => setPriceRange(d)}
                className={`px-3 py-1 rounded text-xs font-medium transition-all ${priceRange === d ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'}`}>
                {d === 7 ? '1W' : d === 30 ? '1M' : '3M'}
              </button>
            ))}
          </div>

          {prices.length === 0 ? (
            <EmptyState title="No price data" description="This company has no crawled prices yet." />
          ) : (
            <>
              {/* KLineChart candlesticks with OHLC price and built-in volume pane */}
              <div className="card h-[420px] p-1">
                <p style={{ color: "red" }}>DEBUG: StockDetail Overview is rendering</p>
                <KlinePriceChart prices={sliced} symbol={company.symbol} />
              </div>

              {/* Period stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Period High', value: `Rs. ${Math.max(...prices.map(p => +p.close)).toFixed(2)}` },
                  { label: 'Period Low',  value: `Rs. ${Math.min(...prices.map(p => +p.close)).toFixed(2)}` },
                  { label: 'Avg Volume',  value: `${((prices.reduce((s, p) => s + p.volume, 0) / prices.length) / 1000).toFixed(0)}K` },
                  { label: 'Sector',      value: company.sector },
                ].map(s => (
                  <div key={s.label} className="card-elevated text-center">
                    <p className="text-xs text-text-muted">{s.label}</p>
                    <p className="text-sm font-semibold text-text-primary mt-0.5 truncate">{s.value}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Behavior ─────────────────────────────────────────────────────── */}
      {tab === 'Behavior' && (
        loadingBehavior ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin text-accent" size={24} />
          </div>
        ) : behaviorError ? (
          <div className="card flex flex-col items-center gap-3 py-12 text-center">
            <AlertTriangle size={28} className="text-yellow-400" />
            <p className="text-sm text-text-secondary">{behaviorError}</p>
            <button onClick={() => loadBehavior(company.id)} className="btn-ghost text-xs">Retry</button>
          </div>
        ) : behavior ? (
          <BehaviorPanel b={behavior} />
        ) : null
      )}

      {/* ── Correlation ───────────────────────────────────────────────────── */}
      {tab === 'Correlation' && (
        loadingCorr ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin text-accent" size={24} />
          </div>
        ) : corrError ? (
          <div className="card flex flex-col items-center gap-3 py-12 text-center">
            <AlertTriangle size={28} className="text-yellow-400" />
            <p className="text-sm text-text-secondary">{corrError}</p>
            <button onClick={() => loadCorrelation(company.id)} className="btn-ghost text-xs">Retry</button>
          </div>
        ) : correlation ? (
          <CorrelationPanel c={correlation} />
        ) : null
      )}

      {/* ── News ─────────────────────────────────────────────────────────── */}
      {tab === 'News' && (
        <div className="space-y-3">
          {relatedNews.length === 0 ? (
            <EmptyState title="No news found" description="No articles categorized for this company yet." />
          ) : (
            relatedNews.map(article => (
              <div key={article.id} className="card hover:border-accent/30 transition-all cursor-pointer group">
                <p className="text-sm font-medium text-text-primary group-hover:text-accent-light line-clamp-2">{article.headline}</p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <SentimentBadge label={article.sentiment_label} />
                  {article.company_tags.map(tag => (
                    <Badge key={tag.id} variant="purple" size="xs">
                      {tag.company_symbol ?? tag.company_name} {Math.round(tag.confidence * 100)}%
                    </Badge>
                  ))}
                  <span className="text-xs text-text-muted ml-auto">
                    {article.published_at ? formatDistanceToNow(new Date(article.published_at), { addSuffix: true }) : '—'}
                    {' · '}{article.source}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Floorsheet ────────────────────────────────────────────────────── */}
      {tab === 'Floorsheet' && (
        <div className="space-y-4">
          {floorDate && (
            <p className="text-xs text-text-muted">
              Latest available floorsheet date: <span className="font-medium text-text-secondary">{floorDate}</span>
            </p>
          )}
          {floorsheet.length === 0 ? (
            <EmptyState title="No floorsheet data" description="No transaction data collected for this company yet." />
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <BrokerTable rows={buyers} title="Top Buyers" color="text-up" />
                <BrokerTable rows={sellers} title="Top Sellers" color="text-down" />
              </div>
              <div className="card overflow-x-auto">
                <h3 className="text-sm font-semibold text-text-primary mb-3">All Transactions</h3>
                <table className="w-full text-xs min-w-[560px]">
                  <thead>
                    <tr className="text-text-muted border-b border-bg-border">
                      <th className="text-left py-1.5 font-medium">Buyer</th>
                      <th className="text-left py-1.5 font-medium">Seller</th>
                      <th className="text-right py-1.5 font-medium">Qty</th>
                      <th className="text-right py-1.5 font-medium">Rate</th>
                      <th className="text-right py-1.5 font-medium">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {floorsheet.map(f => (
                      <tr key={f.id} className="table-row">
                        <td className="py-1.5 text-text-secondary">{f.buyer_broker}</td>
                        <td className="py-1.5 text-text-secondary">{f.seller_broker}</td>
                        <td className="py-1.5 text-right font-mono">{f.quantity.toLocaleString()}</td>
                        <td className="py-1.5 text-right font-mono">{Number(f.rate).toFixed(2)}</td>
                        <td className="py-1.5 text-right font-mono text-text-primary">
                          Rs.&nbsp;{Number(f.amount).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
