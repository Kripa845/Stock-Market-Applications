import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TopBroker } from '../../../api/brokerAccumulation';
import { formatCount } from '../../market/format';

// Top-5 accumulators (right, green) against top-5 distributors (left, red) by net quantity.

const BUY = '#10b981';
const SELL = '#f43f5e';
const GRID = 'var(--trading-grid)';
const MUTED = 'var(--trading-muted)';

interface Row { label: string; name: string; net: number }

const compact = (value: number) => {
  const abs = Math.abs(value);
  const [div, suffix] = abs >= 1e6 ? [1e6, 'M'] : abs >= 1e3 ? [1e3, 'K'] : [1, ''];
  return `${(value / div).toFixed(div === 1 ? 0 : 1).replace(/\.0$/, '')}${suffix}`;
};

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-text-primary">{row.name}</p>
      <p className="font-mono" style={{ color: row.net >= 0 ? BUY : SELL }}>Net {row.net > 0 ? '+' : ''}{formatCount(row.net)}</p>
    </div>
  );
}

export default function TopBrokersChart({ accumulators, distributors }: { accumulators: TopBroker[]; distributors: TopBroker[] }) {
  const rows: Row[] = [...accumulators, ...[...distributors].reverse()].map((broker) => ({
    label: `#${broker.broker}`,
    name: broker.name,
    net: broker.net_qty,
  }));
  if (!rows.length) return <p className="py-10 text-center text-xs text-text-muted">No net buying or selling in this range.</p>;

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 30 + 30)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid horizontal={false} stroke={GRID} strokeDasharray="3 3" />
        <XAxis type="number" tickFormatter={compact} tick={{ fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="label" width={44} tick={{ fontSize: 11, fill: MUTED }} axisLine={false} tickLine={false} />
        <ReferenceLine x={0} stroke={MUTED} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(59,130,246,0.08)' }} />
        <Bar dataKey="net" radius={3} maxBarSize={18}>
          {rows.map((row) => <Cell key={row.label} fill={row.net >= 0 ? BUY : SELL} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
