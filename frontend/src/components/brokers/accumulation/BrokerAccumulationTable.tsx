import { useMemo, useState } from 'react';
import { ChevronDown, ChevronsUpDown, ChevronUp } from 'lucide-react';
import type { BrokerRow } from '../../../api/brokerAccumulation';
import { formatCount, formatPct, formatPrice } from '../../market/format';
import BrokerBadge from '../BrokerBadge';

// Every broker in the window: buy / sell / net quantity, average prices and net share of volume.
// Sorting only reorders what the API computed.

type SortKey = 'broker' | 'buy_qty' | 'sell_qty' | 'net_qty' | 'avg_buy' | 'avg_sell' | 'net_pct_of_volume';

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'buy_qty', label: 'Buy qty' }, { key: 'sell_qty', label: 'Sell qty' }, { key: 'net_qty', label: 'Net qty' },
  { key: 'avg_buy', label: 'Avg buy' }, { key: 'avg_sell', label: 'Avg sell' }, { key: 'net_pct_of_volume', label: 'Net % vol' },
];

const tone = (value: number | null) => (value === null || value === 0 ? 'text-text-muted' : value > 0 ? 'text-up' : 'text-down');

export default function BrokerAccumulationTable({ rows }: { rows: BrokerRow[] }) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'net_qty', desc: true });

  const sorted = useMemo(() => {
    const factor = sort.desc ? -1 : 1;
    return [...rows].sort((a, b) => {
      if (sort.key === 'broker') return a.broker.localeCompare(b.broker, undefined, { numeric: true }) * factor;
      const left = a[sort.key];
      const right = b[sort.key];
      if (left === null) return 1;
      if (right === null) return -1;
      return (left - right) * factor;
    });
  }, [rows, sort]);

  const toggle = (key: SortKey) =>
    setSort((current) => (current.key === key ? { key, desc: !current.desc } : { key, desc: key !== 'broker' }));

  const header = (key: SortKey, label: string, align: 'left' | 'right') => {
    const active = sort.key === key;
    const Icon = !active ? ChevronsUpDown : sort.desc ? ChevronDown : ChevronUp;
    return (
      <th key={key} className={`whitespace-nowrap px-3 py-2.5 font-medium ${align === 'left' ? 'text-left' : 'text-right'}`}>
        <button type="button" onClick={() => toggle(key)} className={`inline-flex items-center gap-0.5 hover:text-text-primary ${active ? 'text-accent-light' : ''}`}>
          {label}<Icon size={11} className={active ? '' : 'opacity-40'} />
        </button>
      </th>
    );
  };

  if (!rows.length) return <p className="py-8 text-center text-sm text-text-muted">No broker trades in this range.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-[13px]">
        <thead>
          <tr className="border-b border-bg-border text-[11px] text-text-secondary">
            {header('broker', 'Broker', 'left')}
            {COLUMNS.map((column) => header(column.key, column.label, 'right'))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.broker} className="table-row">
              <td className="px-3 py-2">
                <BrokerBadge brokerCode={row.broker} name={row.name} shortName={row.short_name} logoUrl={row.logo_url} />
              </td>
              <td className="px-3 py-2 text-right font-mono tabular-nums text-text-secondary">{formatCount(row.buy_qty)}</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums text-text-secondary">{formatCount(row.sell_qty)}</td>
              <td className={`px-3 py-2 text-right font-mono font-semibold tabular-nums ${tone(row.net_qty)}`}>
                {row.net_qty > 0 ? '+' : ''}{formatCount(row.net_qty)}
              </td>
              <td className="px-3 py-2 text-right font-mono tabular-nums text-text-secondary">{formatPrice(row.avg_buy)}</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums text-text-secondary">{formatPrice(row.avg_sell)}</td>
              <td className={`px-3 py-2 text-right font-mono tabular-nums ${tone(row.net_pct_of_volume)}`}>{formatPct(row.net_pct_of_volume)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
