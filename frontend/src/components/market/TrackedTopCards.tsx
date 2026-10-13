import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowUpRight, BarChart3, Coins, Layers, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react';
import { marketApi, type TopMetric, type TrackedRow, type TrackedSummary } from '../../api/market';
import { formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from './format';

// Top Gainers / Losers / Turnover / Volume / Transactions + summary for the TRACKED companies
// (latest crawled session). Ranking is done by the backend (services/movers.py); this only formats.

const ROWS = 8;
const BREAKDOWN_LINK = '/tracked';

const ltp = (value: number | string | null) =>
  value === null ? '—' : Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });

interface CardSpec {
  title: string;
  icon: LucideIcon;
  border: string;   // coloured top edge
  tint: string;     // icon colour
  valueLabel: string;
  value: (row: TrackedRow) => React.ReactNode;
}

const CARDS: Record<'gainers' | 'losers' | TopMetric, CardSpec> = {
  gainers: {
    title: 'Top Gainers', icon: TrendingUp, border: 'border-t-up', tint: 'text-up', valueLabel: '% Change',
    value: (row) => <span className="text-up">{formatPct(row.change_pct)}</span>,
  },
  losers: {
    title: 'Top Losers', icon: TrendingDown, border: 'border-t-down', tint: 'text-down', valueLabel: '% Change',
    value: (row) => <span className="text-down">{formatPct(row.change_pct)}</span>,
  },
  turnover: {
    title: 'Top Turnover', icon: Coins, border: 'border-t-amber-400', tint: 'text-amber-400', valueLabel: 'Turnover',
    value: (row) => formatNprCompact(row.turnover),
  },
  volume: {
    title: 'Top Volume', icon: Layers, border: 'border-t-sky-400', tint: 'text-sky-400', valueLabel: 'Volume',
    value: (row) => formatNprCompact(row.volume),
  },
  transactions: {
    title: 'Top Transactions', icon: BarChart3, border: 'border-t-violet-400', tint: 'text-violet-400', valueLabel: 'Trades',
    value: (row) => (row.transactions === null ? <span className="text-text-muted">—</span> : formatCount(row.transactions)),
  },
};

function RankCard({ spec, rows, emptyText }: { spec: CardSpec; rows: TrackedRow[]; emptyText: string }) {
  const navigate = useNavigate();
  const Icon = spec.icon;
  return (
    <div className={`card flex h-full flex-col border-t-2 !p-0 ${spec.border}`}>
      <h3 className="flex items-center gap-2 border-b border-bg-border px-4 py-3 text-sm font-semibold text-text-primary">
        <Icon size={15} className={spec.tint} /> {spec.title}
      </h3>
      {rows.length === 0 ? (
        <p className="px-4 py-8 text-center text-xs text-text-muted">{emptyText}</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-bg-border text-[10px] uppercase tracking-wide text-text-muted">
              <th className="px-4 py-2 text-left font-medium">Symbol</th>
              <th className="py-2 text-right font-medium">LTP</th>
              <th className="px-4 py-2 text-right font-medium">{spec.valueLabel}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} onClick={() => navigate(`/companies/${row.symbol}`)}
                className="cursor-pointer border-b border-bg-border last:border-0 hover:bg-bg-elevated/50">
                <td className="px-4 py-2.5 font-semibold text-text-primary">{row.symbol}</td>
                <td className="py-2.5 text-right font-mono text-text-secondary">{ltp(row.close)}</td>
                <td className="px-4 py-2.5 text-right font-mono font-semibold text-text-primary">{spec.value(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SummaryCard({ summary }: { summary: TrackedSummary | null }) {
  const traded = summary
    ? summary.tracked_count - summary.excluded_counts.missing_price - summary.excluded_counts.not_traded
    : null;
  const trades = summary?.total_transactions;
  const partial = summary && summary.transactions_reported !== undefined && traded !== null
    && summary.transactions_reported < traded;
  const items = [
    { label: 'Total turnover Rs', value: summary?.total_turnover == null ? '—' : formatPrice(summary.total_turnover) },
    { label: 'Total traded shares', value: formatCount(summary?.total_traded_shares) },
    {
      label: 'Total transactions',
      value: trades == null ? '—' : formatCount(trades),
      note: partial ? `${summary!.transactions_reported} of ${traded} companies reported` : undefined,
    },
    { label: 'Total scrips traded', value: traded === null ? '—' : `${traded} of ${summary!.tracked_count}` },
  ];
  return (
    <div className="card flex h-full flex-col border-t-2 border-t-accent !p-0">
      <h3 className="flex items-center gap-2 border-b border-bg-border px-4 py-3 text-sm font-semibold text-text-primary">
        <ArrowUpRight size={15} className="text-accent-light" /> Market Summary
      </h3>
      <dl className="flex-1">
        {items.map((item) => (
          <div key={item.label} className="border-b border-bg-border px-4 py-3">
            <dt className="text-[10px] uppercase tracking-wide text-text-muted">{item.label}</dt>
            <dd className="mt-1 font-mono text-base font-semibold text-text-primary">{item.value}</dd>
            {item.note && <dd className="text-[10px] text-amber-400">{item.note}</dd>}
          </div>
        ))}
      </dl>
      <Link to={BREAKDOWN_LINK} className="flex items-center justify-center gap-1 px-4 py-3 text-xs text-accent-light hover:underline">
        See full breakdown →
      </Link>
    </div>
  );
}

interface Data {
  gainers: TrackedRow[];
  losers: TrackedRow[];
  top: Record<TopMetric, TrackedRow[]>;
  summary: TrackedSummary | null;
  asOf: string | null;
  reason?: string;
}

export default function TrackedTopCards() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      marketApi.movers('1D', ROWS),
      marketApi.top('turnover', ROWS),
      marketApi.top('volume', ROWS),
      marketApi.top('transactions', ROWS),
      marketApi.summary(),
    ])
      .then(([movers, turnover, volume, transactions, summary]) => {
        if (cancelled) return;
        setData({
          gainers: movers.gainers,
          losers: movers.losers,
          // A NULL trade count means "not filled yet", not zero: keep those rows out of the ranking.
          top: { turnover: turnover.rows, volume: volume.rows, transactions: transactions.rows.filter((r) => r.transactions !== null) },
          summary: summary.summary,
          asOf: movers.as_of ?? turnover.trade_date,
          reason: movers.reason ?? turnover.reason,
        });
      })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <div className="card flex items-center justify-center gap-2 py-8 text-sm text-down">
        <AlertTriangle size={14} /> Could not load the tracked-company rankings.
      </div>
    );
  }
  if (!data) return <div className="card py-8 text-center text-sm text-text-muted">Loading rankings…</div>;

  const empty = data.reason ?? 'No rows for this session.';
  return (
    <section className="space-y-2">
      {data.asOf && <p className="text-xs text-text-muted">Session {formatTradeDate(data.asOf)} · not live</p>}
      <div className="grid items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        <RankCard spec={CARDS.gainers} rows={data.gainers} emptyText={empty} />
        <RankCard spec={CARDS.losers} rows={data.losers} emptyText={empty} />
        <RankCard spec={CARDS.turnover} rows={data.top.turnover} emptyText={empty} />
        <RankCard spec={CARDS.volume} rows={data.top.volume} emptyText={empty} />
        <RankCard spec={CARDS.transactions} rows={data.top.transactions}
          emptyText={data.reason ?? 'Trade counts are not filled for this session yet.'} />
        <SummaryCard summary={data.summary} />
      </div>
    </section>
  );
}
