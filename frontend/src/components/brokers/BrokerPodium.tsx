import { useState } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import type { TopBrokerRow } from '../../api/analysis';
import { formatNprArab } from '../market/format';
import { BuySellBar } from './BrokerTurnoverTable';
import { MEDALS, RankBadge } from './TopBrokers';

function BrokerLogo({ row, large }: { row: TopBrokerRow; large: boolean }) {
  const [broken, setBroken] = useState(false);
  const size = large ? 'h-16 w-16 text-base' : 'h-12 w-12 text-sm';
  const label = (row.short_name || row.name || row.broker).slice(0, 3).toUpperCase();
  return row.logo_url && !broken ? (
    <img src={row.logo_url} alt="" onError={() => setBroken(true)} className={clsx(size, 'rounded-full bg-white object-contain p-1')} />
  ) : (
    <span className={clsx(size, 'flex items-center justify-center rounded-full bg-bg-border font-bold text-text-primary')}>{label}</span>
  );
}

function PodiumSpot({ row, rank }: { row: TopBrokerRow; rank: number }) {
  const medal = MEDALS[rank - 1];
  const first = rank === 1;
  return (
    <Link
      to={`/broker-analysis/${encodeURIComponent(row.broker)}`}
      className={clsx(
        'flex flex-col items-center gap-2 rounded-xl border border-bg-border bg-bg-elevated px-3 text-center transition-colors hover:border-accent/60',
        first ? 'pb-6 pt-5 sm:-mt-4' : 'pb-4 pt-4',
      )}
      style={{ borderTopColor: medal, borderTopWidth: 3, background: `linear-gradient(180deg, ${medal}14, transparent 60%)` }}
    >
      <RankBadge rank={rank} />
      <span className="rounded-full p-0.5" style={{ boxShadow: `0 0 0 2px ${medal}` }}>
        <BrokerLogo row={row} large={first} />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-text-primary" title={row.name}>{row.name || `Broker ${row.broker}`}</p>
        <p className="text-[10px] text-text-muted">#{row.broker_code}</p>
      </div>
      <p className={clsx('font-mono font-bold tabular-nums', first ? 'text-xl' : 'text-lg')} style={{ color: medal }}>
        Rs {formatNprArab(row.total_value)}
      </p>
      <div className="w-full max-w-[200px]">
        <BuySellBar buy={Number(row.buy_value)} sell={Number(row.sell_value)} />
      </div>
    </Link>
  );
}

/** Top 3 brokers by turnover, laid out 2 · 1 · 3 with the leader raised. */
export default function BrokerPodium({ rows }: { rows: TopBrokerRow[] }) {
  if (rows.length === 0) return null;
  // Visual order 2-1-3 on wide screens; plain 1-2-3 when stacked on mobile.
  const order = ['sm:order-2', 'sm:order-1', 'sm:order-3'];
  return (
    <div className="grid gap-3 pt-4 sm:grid-cols-3 sm:items-end">
      {rows.slice(0, 3).map((row, index) => (
        <div key={row.broker} className={order[index]}>
          <PodiumSpot row={row} rank={index + 1} />
        </div>
      ))}
    </div>
  );
}
