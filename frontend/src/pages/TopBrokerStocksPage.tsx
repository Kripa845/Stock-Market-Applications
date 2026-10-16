// One broker's top stocks for one trading day (from the Top Brokers ranking).
// Data: GET /api/analysis/brokers/top/?date= — the broker's row carries top_stocks
// (up to 10, highest buy + sell turnover first) and stock_count.
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle, ArrowDownRight, ArrowLeft, ArrowUpRight, BarChart3, ExternalLink, Minus, Table2,
} from 'lucide-react';

import { analysisApi, type TopBrokerRankedStock, type TopBrokerResponse, type TopBrokerRow } from '../api/analysis';
import { BrokerLogo } from '../components/brokers/BrokerBadge';
import { RankBadge } from '../components/brokers/TopBrokers';
import CompanyLogo from '../components/companies/CompanyLogo';
import { formatCount, formatNprArab } from '../components/market/format';

const dayLabel = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

const num = (value: string | number | null | undefined) => (value == null ? 0 : Number(value));
const pct = (value: number) => `${value.toFixed(1)}%`;

// ─── Small pieces ────────────────────────────────────────────────────────────

function Kpi({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: React.ReactNode; tone?: string }) {
  return (
    <div className="card flex flex-col gap-1">
      <p className="text-[11px] font-medium uppercase tracking-wide text-text-secondary">{label}</p>
      <p className={`font-mono text-xl font-semibold tabular-nums ${tone ?? 'text-text-primary'}`}>{value}</p>
      {hint && <p className="text-[11px] text-text-muted">{hint}</p>}
    </div>
  );
}

function NetChip({ buy, sell }: { buy: number; sell: number }) {
  const net = buy - sell;
  const total = buy + sell;
  // Within 2% of balanced counts as two-way; otherwise say which side dominated.
  if (total === 0 || Math.abs(net) / total < 0.02) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] font-medium text-text-secondary">
        <Minus size={10} /> Two-way
      </span>
    );
  }
  const buyer = net > 0;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-medium ${buyer ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`}>
      {buyer ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
      Net {buyer ? 'buyer' : 'seller'} {formatNprArab(Math.abs(net))}
    </span>
  );
}

/** Buy (left, green) and sell (right, red) as one bar scaled to the largest turnover in the list. */
function SplitBar({ stock, max }: { stock: TopBrokerRankedStock; max: number }) {
  const buy = num(stock.buy_amount);
  const sell = num(stock.sell_amount);
  const scale = max > 0 ? 100 / max : 0;
  return (
    <div className="flex h-3 w-full items-center" aria-hidden="true">
      <div className="flex h-full items-stretch gap-[2px]" style={{ width: `${(buy + sell) * scale}%` }}>
        {buy > 0 && <div className="rounded-l-[4px] bg-up last:rounded-r-[4px]" style={{ flexGrow: buy }} />}
        {sell > 0 && <div className="rounded-r-[4px] bg-down first:rounded-l-[4px]" style={{ flexGrow: sell }} />}
      </div>
    </div>
  );
}

function HoverCard({ stock }: { stock: TopBrokerRankedStock }) {
  return (
    <div role="tooltip" className="pointer-events-none absolute right-0 top-full z-20 mt-1 w-60 rounded-md border border-bg-border bg-bg-card p-3 text-xs shadow-xl">
      <p className="mb-2 font-semibold text-text-primary">{stock.symbol} <span className="font-normal text-text-muted">· {stock.name}</span></p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono tabular-nums">
        <dt className="font-sans text-text-muted"><span className="mr-1.5 inline-block h-2 w-2 rounded-sm bg-up" />Bought</dt>
        <dd className="text-right text-text-primary">Rs {formatNprArab(stock.buy_amount)} · {formatCount(stock.buy_quantity)} sh</dd>
        <dt className="font-sans text-text-muted"><span className="mr-1.5 inline-block h-2 w-2 rounded-sm bg-down" />Sold</dt>
        <dd className="text-right text-text-primary">Rs {formatNprArab(stock.sell_amount)} · {formatCount(stock.sell_quantity)} sh</dd>
        <dt className="font-sans text-text-muted">Turnover</dt>
        <dd className="text-right font-semibold text-text-primary">Rs {formatNprArab(stock.turnover)}</dd>
        <dt className="font-sans text-text-muted">Share</dt>
        <dd className="text-right text-text-primary">{stock.share_pct === null ? '—' : `${Number(stock.share_pct).toFixed(2)}%`}</dd>
      </dl>
    </div>
  );
}

function StockBars({ stocks }: { stocks: TopBrokerRankedStock[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(0, ...stocks.map((s) => num(s.turnover)));
  return (
    <ol className="divide-y divide-bg-border">
      {stocks.map((stock, i) => (
        <li
          key={stock.symbol}
          className="relative grid grid-cols-[28px_minmax(140px,1.1fr)_minmax(160px,2fr)_auto] items-center gap-3 px-1 py-2.5 transition-colors hover:bg-blue-500/5 sm:grid-cols-[28px_minmax(170px,1fr)_minmax(200px,2fr)_110px_150px]"
          onMouseEnter={() => setHover(stock.symbol)}
          onMouseLeave={() => setHover(null)}
          onFocus={() => setHover(stock.symbol)}
          onBlur={() => setHover(null)}
        >
          <span className="text-center font-mono text-xs text-text-muted">{i + 1}</span>
          <Link to={`/companies/${stock.symbol}`} className="flex min-w-0 items-center gap-2.5 hover:text-accent-light">
            <CompanyLogo symbol={stock.symbol} name={stock.name} logoUrl={stock.logo_url} size="md" />
            <span className="min-w-0">
              <span className="block font-mono text-sm font-semibold text-text-primary">{stock.symbol}</span>
              <span className="block truncate text-[11px] text-text-muted" title={stock.name}>{stock.name}</span>
            </span>
          </Link>
          <div className="min-w-0" tabIndex={0} aria-label={`${stock.symbol}: bought Rs ${formatNprArab(stock.buy_amount)}, sold Rs ${formatNprArab(stock.sell_amount)}`}>
            <SplitBar stock={stock} max={max} />
            <p className="mt-1 hidden font-mono text-[10px] tabular-nums text-text-muted sm:block">
              B {formatNprArab(stock.buy_amount)} · S {formatNprArab(stock.sell_amount)}
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono text-sm font-semibold tabular-nums text-text-primary">{formatNprArab(stock.turnover)}</p>
            <p className="font-mono text-[11px] tabular-nums text-text-secondary">
              {stock.share_pct === null ? '—' : pct(Number(stock.share_pct))}
            </p>
          </div>
          <div className="hidden justify-end sm:flex">
            <NetChip buy={num(stock.buy_amount)} sell={num(stock.sell_amount)} />
          </div>
          {hover === stock.symbol && <HoverCard stock={stock} />}
        </li>
      ))}
    </ol>
  );
}

function StockTable({ stocks }: { stocks: TopBrokerRankedStock[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-xs">
        <thead className="border-b border-bg-border text-text-muted">
          <tr>
            <th className="px-2 py-2 text-left font-medium">#</th>
            <th className="px-2 py-2 text-left font-medium">Stock</th>
            <th className="px-2 py-2 text-right font-medium text-up">Bought (Rs)</th>
            <th className="px-2 py-2 text-right font-medium text-up">Shares</th>
            <th className="px-2 py-2 text-right font-medium text-down">Sold (Rs)</th>
            <th className="px-2 py-2 text-right font-medium text-down">Shares</th>
            <th className="px-2 py-2 text-right font-medium">Turnover (Rs)</th>
            <th className="px-2 py-2 text-right font-medium">Share</th>
            <th className="px-2 py-2 text-right font-medium">Net (Rs)</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock, i) => {
            const net = num(stock.buy_amount) - num(stock.sell_amount);
            return (
              <tr key={stock.symbol} className="table-row">
                <td className="px-2 py-2 font-mono text-text-muted">{i + 1}</td>
                <td className="px-2 py-2">
                  <Link to={`/companies/${stock.symbol}`} className="font-mono font-semibold text-accent-light hover:underline">{stock.symbol}</Link>
                </td>
                <td className="px-2 py-2 text-right font-mono tabular-nums">{num(stock.buy_amount).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                <td className="px-2 py-2 text-right font-mono tabular-nums">{formatCount(stock.buy_quantity)}</td>
                <td className="px-2 py-2 text-right font-mono tabular-nums">{num(stock.sell_amount).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                <td className="px-2 py-2 text-right font-mono tabular-nums">{formatCount(stock.sell_quantity)}</td>
                <td className="px-2 py-2 text-right font-mono font-semibold tabular-nums">{num(stock.turnover).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                <td className="px-2 py-2 text-right font-mono tabular-nums">{stock.share_pct === null ? '—' : `${Number(stock.share_pct).toFixed(2)}%`}</td>
                <td className={`px-2 py-2 text-right font-mono tabular-nums ${net > 0 ? 'text-up' : net < 0 ? 'text-down' : 'text-text-secondary'}`}>
                  {net > 0 ? '+' : ''}{net.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function TopBrokerStocksPage() {
  const { broker = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const requestedDate = searchParams.get('date') ?? '';

  const [data, setData] = useState<TopBrokerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState<'chart' | 'table'>('chart');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    analysisApi.getTopBrokers(requestedDate || undefined)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setError('Unable to load broker activity. Check your access and try again.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [requestedDate]);

  const rank = useMemo(() => (data ? data.results.findIndex((r) => r.broker === broker) + 1 : 0), [data, broker]);
  const row: TopBrokerRow | undefined = rank > 0 ? data!.results[rank - 1] : undefined;
  const day = data?.date ?? requestedDate;
  const backLink = `/top-brokers${day ? `?date=${day}` : ''}`;
  const explorerLink = `/broker-analysis/${encodeURIComponent(broker)}${day ? `?start_date=${day}&end_date=${day}` : ''}`;

  const buy = num(row?.buy_value);
  const sell = num(row?.sell_value);
  const total = num(row?.total_value);
  const net = buy - sell;
  // Every trade has a buying and a selling broker, so all brokers' buy + sell is twice the day's turnover.
  const marketTotal = num(data?.summary.total_amount) * 2;
  const marketShare = marketTotal > 0 ? (total / marketTotal) * 100 : null;
  const stocks = row?.top_stocks ?? [];
  const topShare = stocks.reduce((sum, s) => sum + num(s.share_pct), 0);
  const name = row?.name || `Broker ${broker}`;

  return (
    <div className="space-y-5">
      <button type="button" onClick={() => navigate(backLink)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-text-secondary hover:text-text-primary">
        <ArrowLeft size={14} /> Top Brokers{day ? ` · ${dayLabel(day)}` : ''}
      </button>

      {error && (
        <div role="alert" className="card flex items-center gap-2 text-sm text-down"><AlertTriangle size={15} /> {error}</div>
      )}

      {/* Hero */}
      <section className="card relative overflow-hidden">
        <div className="pointer-events-none absolute inset-y-0 right-0 w-1/2 bg-gradient-to-l from-accent/10 to-transparent" aria-hidden="true" />
        <div className="relative flex flex-col gap-5 md:flex-row md:items-center">
          <div className="flex min-w-0 items-center gap-4">
            {loading && !row ? <div className="skeleton h-16 w-16 rounded-full" /> : (
              <BrokerLogo brokerCode={broker} name={name} shortName={row?.short_name} logoUrl={row?.logo_url} size={64} />
            )}
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-wider text-accent-light">Broker #{broker}</p>
              <h1 className="truncate text-xl font-semibold text-text-primary sm:text-2xl">{loading && !row ? 'Loading…' : name}</h1>
              {row && (
                <p className="mt-1 flex items-center gap-2 text-xs text-text-secondary">
                  <RankBadge rank={rank} />
                  <span>of {formatCount(data!.results.length)} brokers by turnover</span>
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 md:ml-auto">
            {data && data.available_dates.length > 0 && (
              <label className="flex items-center gap-2 text-xs text-text-muted">
                Trading day
                <select className="input py-1.5 text-xs" value={day} disabled={loading}
                  onChange={(e) => setSearchParams({ date: e.target.value }, { replace: true })}>
                  {data.available_dates.map((d) => (
                    <option key={d.date} value={d.date}>{dayLabel(d.date)}{d.is_complete ? '' : ` · partial (${d.companies} co.)`}</option>
                  ))}
                </select>
              </label>
            )}
            <Link to={explorerLink} className="btn-ghost flex items-center gap-1.5 border border-bg-border text-xs">
              <ExternalLink size={13} /> Broker Explorer
            </Link>
          </div>
        </div>
        {data && !data.is_complete && data.date && (
          <p className="relative mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-400">
            Partial day: trades exist for only {data.companies} of {data.expected_companies} tracked companies, so these figures are incomplete.
          </p>
        )}
      </section>

      {!loading && data && !row && (
        <div className="card py-12 text-center">
          <p className="text-sm text-text-primary">Broker #{broker} has no trades on {day ? dayLabel(day) : 'this day'}.</p>
          <p className="mt-1 text-xs text-text-muted">Pick another trading day above, or go back to the ranking.</p>
          <Link to={backLink} className="btn-primary mt-4 inline-block text-xs">Back to Top Brokers</Link>
        </div>
      )}

      {row && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Kpi label="Turnover" value={`Rs ${formatNprArab(total)}`}
              hint={marketShare !== null ? `${pct(marketShare)} of all broker turnover` : undefined} />
            <Kpi label="Bought" tone="text-up" value={`Rs ${formatNprArab(buy)}`} hint={`${formatCount(row.buy_quantity)} shares`} />
            <Kpi label="Sold" tone="text-down" value={`Rs ${formatNprArab(sell)}`} hint={`${formatCount(row.sell_quantity)} shares`} />
            <Kpi label="Net position" tone={net > 0 ? 'text-up' : net < 0 ? 'text-down' : undefined}
              value={`${net > 0 ? '+' : net < 0 ? '−' : ''}Rs ${formatNprArab(Math.abs(net))}`}
              hint={net > 0 ? 'Net buyer for the day' : net < 0 ? 'Net seller for the day' : 'Balanced'} />
            <Kpi label="Stocks traded" value={formatCount(row.stock_count)}
              hint={stocks.length ? `Top ${stocks.length} = ${pct(topShare)} of its turnover` : undefined} />
          </div>

          {/* Buy / sell balance */}
          <section className="card">
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="font-medium text-up">Buy {total ? pct((buy / total) * 100) : '—'}</span>
              <span className="text-text-muted">Buy vs sell, by value</span>
              <span className="font-medium text-down">Sell {total ? pct((sell / total) * 100) : '—'}</span>
            </div>
            <div className="flex h-2.5 gap-[2px]" role="img" aria-label={`Buy ${total ? pct((buy / total) * 100) : '0%'}, sell ${total ? pct((sell / total) * 100) : '0%'}`}>
              {buy > 0 && <div className="rounded-l-[4px] bg-up last:rounded-r-[4px]" style={{ flexGrow: buy }} />}
              {sell > 0 && <div className="rounded-r-[4px] bg-down first:rounded-l-[4px]" style={{ flexGrow: sell }} />}
            </div>
          </section>

          {/* Top stocks */}
          <section className="card">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-text-primary">
                  Top {stocks.length} {stocks.length === 1 ? 'stock' : 'stocks'}
                </h2>
                <p className="text-[11px] text-text-muted">
                  Ranked by buy + sell turnover
                  {row.stock_count > stocks.length ? ` · ${stocks.length} of ${row.stock_count} stocks traded` : ' · every stock traded'}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {view === 'chart' && (
                  <span className="flex items-center gap-3 text-[11px] text-text-secondary" aria-label="Legend">
                    <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-up" /> Bought</span>
                    <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-down" /> Sold</span>
                  </span>
                )}
                <div role="radiogroup" aria-label="View" className="inline-flex rounded-md border border-bg-border bg-bg-elevated p-0.5">
                  {([['chart', BarChart3, 'Chart'], ['table', Table2, 'Table']] as const).map(([id, Icon, label]) => (
                    <button key={id} type="button" role="radio" aria-checked={view === id} onClick={() => setView(id)}
                      className={`flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium ${view === id ? 'bg-accent/20 text-accent-light' : 'text-text-secondary hover:text-text-primary'}`}>
                      <Icon size={12} /> {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {stocks.length === 0
              ? <p className="py-8 text-center text-xs text-text-muted">No stock breakdown for this day.</p>
              : view === 'chart' ? <StockBars stocks={stocks} /> : <StockTable stocks={stocks} />}

            {row.stock_count > stocks.length && (
              <p className="mt-3 border-t border-bg-border pt-3 text-[11px] text-text-muted">
                {row.stock_count - stocks.length} more {row.stock_count - stocks.length === 1 ? 'stock' : 'stocks'} not shown ·{' '}
                <Link to={explorerLink} className="text-accent-light hover:underline">see every stock in Broker Explorer →</Link>
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
