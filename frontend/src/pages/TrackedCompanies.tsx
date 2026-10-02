import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Info, Minus, RefreshCw, Star } from 'lucide-react';
import { format } from 'date-fns';
import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';
import Sparkline from '../components/common/Sparkline';
import CompanyLogo from '../components/companies/CompanyLogo';
import BrokerBadge from '../components/brokers/BrokerBadge';
import BasketChart from '../components/market/BasketChart';
import {
  changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate,
} from '../components/market/format';
import {
  marketApi,
  type BasketIndex, type BrokerWindow, type DividendRow, type Signals, type TopMetric,
  type TrackedRow, type TrackedSummary, type WatchlistRow,
} from '../api/market';
import type { NewsArticle } from '../types';
import { useAuth } from '../contexts/AuthContext';

// Dashboard for the TRACKED COMPANIES only (/api/market/). Never labelled as the NEPSE market.

const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-muted' };
const ToneIcon = { up: ArrowUpRight, down: ArrowDownRight, flat: Minus };

function Change({ pct }: { pct: number | null }) {
  const tone = changeTone(pct);
  const Icon = ToneIcon[tone];
  return (
    <span className={`inline-flex items-center gap-0.5 font-mono ${toneText[tone]}`}>
      <Icon size={12} />{formatPct(pct)}
    </span>
  );
}

function Tile({ label, value, tone, hint }: { label: string; value: React.ReactNode; tone?: string; hint?: string }) {
  return (
    <div className="card p-4" title={hint}>
      <div className="truncate text-xs text-text-muted">{label}</div>
      <div className={`mt-1 whitespace-nowrap font-mono text-lg font-semibold ${tone ?? 'text-text-primary'}`}>{value}</div>
    </div>
  );
}

function SummaryTiles({ summary }: { summary: TrackedSummary }) {
  const transactions = summary.transactions_reported
    ? `${formatCount(summary.total_transactions)}${summary.transactions_reported < summary.tracked_count ? '*' : ''}`
    : '—';
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
      <Tile label="Tracked traded" value={summary.tracked_count} />
      <Tile label="Advanced" value={summary.advanced} tone="text-up" />
      <Tile label="Declined" value={summary.declined} tone="text-down" />
      <Tile label="Unchanged" value={summary.unchanged} hint={`${summary.no_prev_close} without a previous close`} />
      <Tile label="Circuit ↑ / ↓" value={`${summary.positive_circuit} / ${summary.negative_circuit}`} hint="|change %| ≥ 9.9" />
      <Tile label="Turnover" value={`Rs ${formatNprCompact(summary.total_turnover)}`} />
      <Tile label="Shares traded" value={formatCount(summary.total_traded_shares)} />
      <Tile
        label="Transactions"
        value={transactions}
        hint={`From the floorsheet; known for ${summary.transactions_reported ?? 0} of ${summary.tracked_count} companies`}
      />
    </div>
  );
}

function MoversTable({ rows, selected, onSelect, watched, onToggleWatch }: {
  rows: TrackedRow[];
  selected: string | null;
  onSelect: (symbol: string) => void;
  watched: Set<string> | null;
  onToggleWatch: (symbol: string) => void;
}) {
  return (
    <div className="card overflow-x-auto">
      <h2 className="mb-3 text-sm font-semibold text-text-primary">All tracked companies by change</h2>
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-bg-border text-text-secondary">
            {watched && <th className="w-8" />}
            <th className="py-2 text-left font-medium">Company</th>
            <th className="py-2 text-center font-medium">Last 7 closes</th>
            <th className="py-2 text-right font-medium">LTP</th>
            <th className="py-2 text-right font-medium">Prev close</th>
            <th className="py-2 text-right font-medium">Change</th>
            <th className="py-2 text-right font-medium">Volume</th>
            <th className="py-2 text-right font-medium">Turnover</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const tone = changeTone(row.change_pct);
            const isWatched = watched?.has(row.symbol) ?? false;
            return (
              <tr
                key={row.symbol}
                onClick={() => onSelect(row.symbol)}
                className={`table-row cursor-pointer ${selected === row.symbol ? 'bg-accent/5' : ''}`}
              >
                {watched && (
                  <td className="py-2" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => onToggleWatch(row.symbol)}
                      title={isWatched ? 'Remove from my watchlist' : 'Add to my watchlist'}
                      aria-pressed={isWatched}
                      className="rounded p-1 text-text-muted hover:text-yellow-400"
                    >
                      <Star size={14} className={isWatched ? 'fill-yellow-400 text-yellow-400' : ''} />
                    </button>
                  </td>
                )}
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <CompanyLogo symbol={row.symbol} name={row.name} size="sm" />
                    <span>
                      <span className="block font-mono font-semibold text-accent-light">{row.symbol}</span>
                      <span className="block text-xs text-text-muted">{row.sector}</span>
                    </span>
                    {row.book_closure_in_window && (
                      <span
                        className="rounded bg-yellow-500/10 px-1.5 py-0.5 text-[10px] text-yellow-400"
                        title="A recorded book closure falls in this session; the change may be a price adjustment, not trading."
                      >
                        Book closure
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-2">
                  <div className="flex justify-center">
                    <Sparkline data={(row.sparkline ?? []).map((p) => Number(p.close))} width={90} height={26} positive={tone !== 'down'} />
                  </div>
                </td>
                <td className="py-2 text-right font-mono font-semibold text-text-primary">{formatPrice(row.ltp)}</td>
                <td className="py-2 text-right font-mono text-text-secondary">{formatPrice(row.prev_close)}</td>
                <td className="py-2 text-right"><Change pct={row.change_pct} /></td>
                <td className="py-2 text-right font-mono">{formatCount(row.volume)}</td>
                <td className="py-2 text-right font-mono">{formatNprCompact(row.turnover)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const TOP_TABS: { metric: TopMetric; label: string; value: (row: TrackedRow) => string }[] = [
  { metric: 'turnover', label: 'Turnover', value: (row) => `Rs ${formatNprCompact(row.turnover)}` },
  { metric: 'volume', label: 'Volume', value: (row) => formatCount(row.volume) },
  { metric: 'transactions', label: 'Transactions', value: (row) => (row.transactions === null ? 'Not crawled' : formatCount(row.transactions)) },
];

function TopLists() {
  const [metric, setMetric] = useState<TopMetric>('turnover');
  const [rows, setRows] = useState<TrackedRow[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    marketApi.top(metric, 5).then((data) => { if (!cancelled) setRows(data.rows); }).catch(() => { if (!cancelled) setRows([]); });
    return () => { cancelled = true; };
  }, [metric]);

  const tab = TOP_TABS.find((t) => t.metric === metric)!;
  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-text-primary">Top 5 by</h2>
        <div className="flex gap-1 rounded-lg bg-bg-elevated p-0.5 text-xs">
          {TOP_TABS.map((t) => (
            <button
              key={t.metric}
              onClick={() => setMetric(t.metric)}
              className={`rounded-md px-2.5 py-1 ${metric === t.metric ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      {rows === null ? <p className="py-6 text-center text-xs text-text-muted">Loading…</p> : (
        <ol className="space-y-2">
          {rows.map((row, i) => (
            <li key={row.symbol} className="flex items-center gap-3 text-sm">
              <span className="w-4 text-xs text-text-muted">{i + 1}</span>
              <span className="w-16 font-mono font-semibold text-accent-light">{row.symbol}</span>
              <span className="flex-1 text-right font-mono text-text-primary">{tab.value(row)}</span>
              <span className="w-20 text-right text-xs"><Change pct={row.change_pct} /></span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function SignalsCard({ signals }: { signals: Signals }) {
  const ma = signals.moving_averages;
  const range = signals.range_52w;
  const vol = signals.volume_vs_20d_avg;
  const needs = (sessions: number, required: number) => `Needs ${required} sessions (${sessions} stored)`;
  const items = [
    {
      label: 'Volume vs 20-day avg',
      value: vol.ratio === null ? '—' : `${Number(vol.ratio).toFixed(2)}×`,
      note: vol.ratio === null ? needs(vol.sessions, vol.required_sessions) : `avg ${formatCount(vol.average_volume)}`,
    },
    {
      label: '5-day MA',
      value: formatPrice(ma.ma5.value),
      note: ma.ma5.value === null ? needs(ma.ma5.sessions, 5) : `LTP ${formatPct(ma.ltp_vs_ma5_pct)}`,
    },
    {
      label: '20-day MA',
      value: formatPrice(ma.ma20.value),
      note: ma.ma20.value === null ? needs(ma.ma20.sessions, 20) : `LTP ${formatPct(ma.ltp_vs_ma20_pct)}`,
    },
    {
      label: '52-week high',
      value: formatPrice(range.high),
      note: `${formatPct(range.distance_from_high_pct)} from high`,
    },
    {
      label: '52-week low',
      value: formatPrice(range.low),
      note: `${formatPct(range.distance_from_low_pct)} from low`,
    },
  ];
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-text-primary">Signals · {formatTradeDate(signals.trade_date)}</h3>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {items.map((item) => (
          <div key={item.label}>
            <div className="text-[11px] text-text-muted">{item.label}</div>
            <div className="font-mono text-base font-semibold text-text-primary">{item.value}</div>
            <div className="text-[11px] text-text-secondary">{item.note}</div>
          </div>
        ))}
      </div>
      {range.sessions < 200 && (
        <p className="mt-3 flex items-center gap-1 text-[11px] text-text-muted">
          <Info size={11} /> The 52-week range covers only the {range.sessions} sessions stored since {formatTradeDate(range.first_date)}.
        </p>
      )}
    </div>
  );
}

function BrokerSide({ title, rows, side }: { title: string; rows: BrokerWindow['top_buyers']; side: 'buy' | 'sell' }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium text-text-secondary">{title}</h4>
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li key={row.broker} className="flex items-center justify-between gap-2 text-xs">
            <BrokerBadge brokerCode={row.broker} name={row.broker_name} />
            <span className={`font-mono ${side === 'buy' ? 'text-up' : 'text-down'}`}>
              {formatCount(side === 'buy' ? row.buy_quantity : row.sell_quantity)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BrokersCard({ windows, denominator }: { windows: BrokerWindow[]; denominator: string }) {
  const [index, setIndex] = useState(0);
  const window = windows[index];
  if (!window) return null;
  return (
    <div className="card">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-text-primary">Broker activity</h3>
        <div className="flex gap-1 rounded-lg bg-bg-elevated p-0.5 text-xs">
          {windows.map((w, i) => (
            <button
              key={w.sessions}
              onClick={() => setIndex(i)}
              className={`rounded-md px-2.5 py-1 ${i === index ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'}`}
            >
              {w.sessions} sessions
            </button>
          ))}
        </div>
      </div>
      {window.total_trades === 0 ? (
        <p className="py-6 text-center text-xs text-text-muted">No floorsheet trades collected for this company yet.</p>
      ) : (
        <>
          <p className="text-[11px] text-text-muted">
            {window.sessions_available < window.sessions && `Only ${window.sessions_available} floorsheet sessions available. `}
            {formatTradeDate(window.start_date)} – {formatTradeDate(window.end_date)} · {formatCount(window.total_trades)} trades ·
            Rs {formatNprCompact(window.total_amount)}
          </p>
          {window.concentration && (
            <p className="mt-2 text-xs text-text-secondary">
              Top {window.concentration.top_n} brokers handled{' '}
              <span className="font-mono font-semibold text-text-primary">{Number(window.concentration.volume_share_pct).toFixed(1)}%</span>{' '}
              of the traded volume.
            </p>
          )}
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <BrokerSide title="Top buyers (shares)" rows={window.top_buyers} side="buy" />
            <BrokerSide title="Top sellers (shares)" rows={window.top_sellers} side="sell" />
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[520px] text-xs">
              <thead>
                <tr className="border-b border-bg-border text-text-secondary">
                  <th className="py-2 text-left font-medium">Broker</th>
                  <th className="py-2 text-right font-medium">Net shares</th>
                  <th className="py-2 text-right font-medium">Net amount</th>
                  <th className="py-2 text-right font-medium">Share of turnover</th>
                </tr>
              </thead>
              <tbody>
                {window.brokers.slice(0, 10).map((row) => (
                  <tr key={row.broker} className="table-row">
                    <td className="py-1.5"><BrokerBadge brokerCode={row.broker} name={row.broker_name} /></td>
                    <td className={`py-1.5 text-right font-mono ${toneText[changeTone(row.net_quantity)]}`}>{formatCount(row.net_quantity)}</td>
                    <td className={`py-1.5 text-right font-mono ${toneText[changeTone(row.net_amount)]}`}>{formatNprCompact(row.net_amount)}</td>
                    <td className="py-1.5 text-right font-mono text-text-primary">{row.share_pct === null ? '—' : `${Number(row.share_pct).toFixed(2)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[10px] text-text-muted" title={denominator}>
            Share of turnover = (buy + sell amount) ÷ (2 × company turnover in the window), so all brokers add up to 100%.
          </p>
        </>
      )}
    </div>
  );
}

function CompanyDetail({ symbol }: { symbol: string }) {
  const { hasPermission } = useAuth();
  const canAnalyse = hasPermission('view_analysis');
  const canNews = hasPermission('view_news');
  const [signals, setSignals] = useState<Signals | null | undefined>(undefined);
  const [brokers, setBrokers] = useState<{ windows: BrokerWindow[]; share_denominator: string } | null>(null);
  const [news, setNews] = useState<NewsArticle[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSignals(undefined); setBrokers(null); setNews(null);
    if (canAnalyse) {
      marketApi.signals(symbol).then((d) => { if (!cancelled) setSignals(d.signals); }).catch(() => { if (!cancelled) setSignals(null); });
      marketApi.brokers(symbol).then((d) => { if (!cancelled) setBrokers(d); }).catch(() => undefined);
    }
    if (canNews) {
      marketApi.companyNews(symbol).then((d) => { if (!cancelled) setNews(d.results.slice(0, 5)); }).catch(() => { if (!cancelled) setNews([]); });
    }
    return () => { cancelled = true; };
  }, [symbol, canAnalyse, canNews]);

  if (!canAnalyse && !canNews) return null;
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-text-primary">
        <span className="font-mono text-accent-light">{symbol}</span> in detail
      </h2>
      {canAnalyse && signals && <SignalsCard signals={signals} />}
      <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
        {canAnalyse && brokers && <BrokersCard key={symbol} windows={brokers.windows} denominator={brokers.share_denominator} />}
        {canNews && (
          <div className="card">
            <h3 className="mb-3 text-sm font-semibold text-text-primary">Latest news about {symbol}</h3>
            {news === null ? <p className="text-xs text-text-muted">Loading…</p> : news.length === 0 ? (
              <p className="text-xs text-text-muted">No categorised news for this company yet.</p>
            ) : (
              <ul className="space-y-3">
                {news.map((article) => (
                  <li key={article.id}>
                    <Link to={`/news/${article.id}`} className="text-sm leading-snug text-text-primary hover:text-accent-light">{article.headline}</Link>
                    <div className="text-[11px] text-text-muted">
                      {article.source}{article.published_at ? ` · ${format(new Date(article.published_at), 'MMM d, yyyy')}` : ''}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function DividendsCard({ rows }: { rows: DividendRow[] }) {
  return (
    <div className="card overflow-x-auto">
      <h2 className="mb-3 text-sm font-semibold text-text-primary">Proposed dividends</h2>
      {rows.length === 0 ? (
        <p className="py-4 text-center text-xs text-text-muted">No dividend announcements recorded yet. Admins can add them in Django admin.</p>
      ) : (
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-bg-border text-text-secondary">
              <th className="py-2 text-left font-medium">Company</th>
              <th className="py-2 text-left font-medium">Fiscal year</th>
              <th className="py-2 text-right font-medium">Bonus</th>
              <th className="py-2 text-right font-medium">Cash</th>
              <th className="py-2 text-right font-medium">Total</th>
              <th className="py-2 text-right font-medium">Book closure</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="table-row">
                <td className="py-2 font-mono font-semibold text-accent-light">{row.symbol}</td>
                <td className="py-2 text-text-secondary">{row.fiscal_year}</td>
                <td className="py-2 text-right font-mono">{Number(row.bonus_pct).toFixed(2)}%</td>
                <td className="py-2 text-right font-mono">{Number(row.cash_pct).toFixed(2)}%</td>
                <td className="py-2 text-right font-mono font-semibold text-text-primary">{Number(row.total_pct).toFixed(2)}%</td>
                <td className="py-2 text-right text-text-secondary">{formatTradeDate(row.book_closure_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function WatchlistCard({ rows, canRemove, onRemove }: { rows: WatchlistRow[]; canRemove: boolean; onRemove: (symbol: string) => void }) {
  return (
    <div className="card">
      <h2 className="mb-3 text-sm font-semibold text-text-primary">My watchlist</h2>
      {rows.length === 0 ? (
        <p className="py-4 text-center text-xs text-text-muted">Star a company in the table to follow it here.</p>
      ) : (
        <ul className="divide-y divide-bg-border">
          {rows.map((row) => (
            <li key={row.symbol} className="flex items-center gap-3 py-2 text-sm">
              <span className="w-16 font-mono font-semibold text-accent-light">{row.symbol}</span>
              <span className="flex-1 text-right font-mono text-text-primary">{formatPrice(row.ltp)}</span>
              <span className="w-20 text-right text-xs"><Change pct={row.change_pct} /></span>
              {canRemove && (
                <button onClick={() => onRemove(row.symbol)} title="Remove" className="text-text-muted hover:text-down">
                  <Star size={13} className="fill-yellow-400 text-yellow-400" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function TrackedCompaniesPage() {
  const { hasPermission } = useAuth();
  const canViewWatchlist = hasPermission('view_watchlist');
  const canAdd = hasPermission('add_watchlist');
  const canRemove = hasPermission('remove_watchlist');

  const [summary, setSummary] = useState<TrackedSummary | null>(null);
  const [movers, setMovers] = useState<TrackedRow[]>([]);
  const [basket, setBasket] = useState<BasketIndex | null>(null);
  const [dividends, setDividends] = useState<DividendRow[] | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistRow[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWatchlist = useCallback(() => {
    if (!canViewWatchlist) return;
    marketApi.watchlist().then((d) => setWatchlist(d.rows)).catch(() => setWatchlist(null));
  }, [canViewWatchlist]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [summaryRes, moversRes, basketRes, dividendsRes] = await Promise.allSettled([
      marketApi.summary(), marketApi.movers(), marketApi.basket(60), marketApi.dividends(),
    ]);
    if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value.summary);
    if (moversRes.status === 'fulfilled') {
      setMovers(moversRes.value.rows);
      setSelected((current) => current ?? moversRes.value.rows[0]?.symbol ?? null);
    }
    if (basketRes.status === 'fulfilled') setBasket(basketRes.value);
    if (dividendsRes.status === 'fulfilled') setDividends(dividendsRes.value.rows);
    if (summaryRes.status === 'rejected' && moversRes.status === 'rejected') setError('Unable to load tracked company data.');
    loadWatchlist();
    setLoading(false);
  }, [loadWatchlist]);

  useEffect(() => { load(); }, [load]);

  const watched = canViewWatchlist && watchlist ? new Set(watchlist.map((row) => row.symbol)) : null;

  const toggleWatch = async (symbol: string) => {
    try {
      if (watched?.has(symbol)) {
        if (!canRemove) return;
        await marketApi.removeFromWatchlist(symbol);
      } else {
        if (!canAdd) return;
        await marketApi.addToWatchlist(symbol);
      }
      loadWatchlist();
    } catch {
      setError('Could not update your watchlist.');
    }
  };

  const tradeDate = summary?.trade_date ?? null;
  return (
    <div className="space-y-6">
      <PageHeader
        title="Tracked Companies"
        subtitle={`Closing data for the companies StockScope tracks — not the whole NEPSE market.${tradeDate ? ` As of ${formatTradeDate(tradeDate)}.` : ''}`}
        actions={
          <button onClick={load} className="btn-ghost flex items-center gap-2" disabled={loading}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh
          </button>
        }
      />
      {error && <div className="flex items-center gap-2 text-sm text-down"><AlertTriangle size={14} />{error}</div>}
      {loading && !summary && <p className="text-text-secondary">Loading tracked companies…</p>}
      {!loading && !error && movers.length === 0 && (
        <EmptyState title="No tracked prices yet" description="Run the price crawler to populate the tracked companies." />
      )}

      {summary && summary.trade_date && <SummaryTiles summary={summary} />}

      {movers.length > 0 && (
        <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
          <MoversTable
            rows={movers}
            selected={selected}
            onSelect={setSelected}
            watched={canAdd || canRemove ? watched : null}
            onToggleWatch={toggleWatch}
          />
          <div className="space-y-4">
            {basket && (
              <div className="card">
                <h2 className="text-sm font-semibold text-text-primary">{basket.label}</h2>
                <p className="mb-3 text-[11px] text-text-muted">Index of the tracked companies, base 1000. Not the NEPSE index.</p>
                <BasketChart rows={basket.rows} height={130} />
              </div>
            )}
            <TopLists />
            {canViewWatchlist && watchlist && <WatchlistCard rows={watchlist} canRemove={canRemove} onRemove={toggleWatch} />}
          </div>
        </div>
      )}

      {selected && <CompanyDetail symbol={selected} />}

      {dividends && <DividendsCard rows={dividends} />}
    </div>
  );
}
