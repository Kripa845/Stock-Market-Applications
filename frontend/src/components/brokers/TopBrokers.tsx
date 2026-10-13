import { useState } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import BrokerBadge from './BrokerBadge';
import type { BrokerActivity, BrokerAnalysisResponse } from '../../api/analysis';

type TabKey = 'buyers' | 'sellers' | 'net_buyers' | 'net_sellers';

interface TabConfig {
  label: string;
  rows: (data: BrokerAnalysisResponse) => BrokerActivity[];
  quantity: (row: BrokerActivity) => number;
  value: (row: BrokerActivity) => number;
  // Share of the market-wide total for this side; net tabs have no meaningful total.
  share?: (row: BrokerActivity, data: BrokerAnalysisResponse) => number;
  tone: 'up' | 'down';
}

const TABS: Record<TabKey, TabConfig> = {
  buyers: {
    label: 'Top Buyers',
    rows: d => d.most_active_buyers,
    quantity: r => r.buy_quantity,
    value: r => Number(r.buy_value),
    share: (r, d) => (d.summary.total_buy_quantity ? r.buy_quantity / d.summary.total_buy_quantity : 0),
    tone: 'up',
  },
  sellers: {
    label: 'Top Sellers',
    rows: d => d.most_active_sellers,
    quantity: r => r.sell_quantity,
    value: r => Number(r.sell_value),
    share: (r, d) => (d.summary.total_sell_quantity ? r.sell_quantity / d.summary.total_sell_quantity : 0),
    tone: 'down',
  },
  net_buyers: {
    label: 'Net Buyers',
    rows: d => d.top_net_buyers,
    quantity: r => r.net_quantity,
    value: r => Number(r.net_value),
    tone: 'up',
  },
  net_sellers: {
    label: 'Net Sellers',
    rows: d => d.top_net_sellers,
    quantity: r => r.net_quantity,
    value: r => Number(r.net_value),
    tone: 'down',
  },
};

// Gold / silver / bronze accents for the podium ranks; ranks 4–5 stay neutral.
export const MEDALS = ['#f5b301', '#a8b3c2', '#cd7f32'];

const compact = (value: number) =>
  new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 }).format(value);
const signed = (value: number, text: string) => (value > 0 ? `+${text}` : text);

export function RankBadge({ rank }: { rank: number }) {
  const medal = MEDALS[rank - 1];
  return (
    <span
      className={clsx(
        'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 font-mono text-xs font-bold',
        !medal && 'border-bg-border text-text-muted',
      )}
      style={medal ? { borderColor: medal, color: medal, backgroundColor: `${medal}1f` } : undefined}
    >
      {rank}
    </span>
  );
}

function BrokerCard({ row, rank, tab, data }: { row: BrokerActivity; rank: number; tab: TabConfig; data: BrokerAnalysisResponse }) {
  const medal = MEDALS[rank - 1];
  const quantity = tab.quantity(row);
  const value = tab.value(row);
  const isNet = !tab.share;
  const toneText = tab.tone === 'up' ? 'text-up' : 'text-down';
  const buyPct = row.total_quantity ? (row.buy_quantity / row.total_quantity) * 100 : 0;
  const sharePct = tab.share ? tab.share(row, data) * 100 : 0;

  return (
    <Link
      to={`/broker-analysis/${encodeURIComponent(row.broker)}`}
      className="group flex snap-start flex-col gap-3 rounded-lg border border-bg-border bg-bg-elevated p-3 transition-colors hover:border-accent/60"
      style={medal ? { borderTopColor: medal, borderTopWidth: 2 } : undefined}
    >
      <div className="flex items-center justify-between gap-2">
        <RankBadge rank={rank} />
        <span className="text-[10px] text-text-muted">{row.trades.toLocaleString()} trades</span>
      </div>

      <BrokerBadge brokerCode={row.broker_code} name={row.broker_name || row.name} shortName={row.short_name} logoUrl={row.logo_url} className="text-xs" />

      <div>
        <p className={clsx('font-mono text-lg font-bold tabular-nums', toneText)}>
          {isNet ? signed(quantity, compact(quantity)) : compact(quantity)}
          <span className="ml-1 text-[10px] font-normal text-text-muted">shares</span>
        </p>
        <p className="font-mono text-[11px] text-text-secondary tabular-nums">
          Rs {isNet ? signed(value, compact(value)) : compact(value)}
        </p>
      </div>

      {isNet ? (
        <div>
          <div className="flex h-1.5 overflow-hidden rounded-full bg-bg-border">
            <div className="bg-up" style={{ width: `${buyPct}%` }} />
            <div className="bg-down flex-1" />
          </div>
          <p className="mt-1 flex justify-between text-[10px] text-text-muted">
            <span>Buy {buyPct.toFixed(0)}%</span>
            <span>Sell {(100 - buyPct).toFixed(0)}%</span>
          </p>
        </div>
      ) : (
        <div>
          <div className="h-1.5 overflow-hidden rounded-full bg-bg-border">
            <div className={tab.tone === 'up' ? 'h-full bg-up' : 'h-full bg-down'} style={{ width: `${Math.min(sharePct, 100)}%` }} />
          </div>
          <p className="mt-1 text-[10px] text-text-muted">{sharePct.toFixed(1)}% of all {tab.tone === 'up' ? 'bought' : 'sold'} shares</p>
        </div>
      )}
    </Link>
  );
}

export default function TopBrokers({ data }: { data: BrokerAnalysisResponse }) {
  const [active, setActive] = useState<TabKey>('buyers');
  const tab = TABS[active];
  const rows = tab.rows(data);

  return (
    <section className="card space-y-4" aria-label="Top brokers">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-text-primary">Top Brokers</h2>
        <div className="flex gap-1 rounded-lg bg-bg-elevated p-0.5 text-xs" role="tablist">
          {(Object.keys(TABS) as TabKey[]).map(key => (
            <button
              key={key}
              role="tab"
              aria-selected={key === active}
              onClick={() => setActive(key)}
              className={clsx(
                'rounded-md px-2.5 py-1',
                key === active ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary',
              )}
            >
              {TABS[key].label}
            </button>
          ))}
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-text-muted">No broker activity in this selection.</p>
      ) : (
        <div className="grid snap-x auto-cols-[minmax(190px,1fr)] grid-flow-col gap-3 overflow-x-auto pb-1 xl:grid-flow-row xl:grid-cols-5 xl:overflow-visible">
          {rows.map((row, index) => (
            <BrokerCard key={row.broker} row={row} rank={index + 1} tab={tab} data={data} />
          ))}
        </div>
      )}
    </section>
  );
}
