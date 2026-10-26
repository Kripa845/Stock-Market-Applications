import { Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { FlowPoint } from '../../../api/brokerAccumulation';
import { formatCount, formatPrice } from '../../market/format';

// Close price (line, right axis) over each session's net top-5 broker flow (bars, left axis).

const BUY = '#10b981';
const SELL = '#f43f5e';
const PRICE = '#3b82f6';
const GRID = 'var(--trading-grid)';
const MUTED = 'var(--trading-muted)';

const compact = (value: number) => {
  const abs = Math.abs(value);
  const [div, suffix] = abs >= 1e6 ? [1e6, 'M'] : abs >= 1e3 ? [1e3, 'K'] : [1, ''];
  return `${(value / div).toFixed(div === 1 ? 0 : 1).replace(/\.0$/, '')}${suffix}`;
};
const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: FlowPoint }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-text-muted">{dayLabel(row.date)}</p>
      <p className="font-mono" style={{ color: PRICE }}>Close {formatPrice(row.close)}</p>
      <p className="font-mono" style={{ color: row.net_flow >= 0 ? BUY : SELL }}>Net flow {row.net_flow > 0 ? '+' : ''}{formatCount(row.net_flow)}</p>
      <p className="font-mono text-text-secondary">Top-5 buy +{formatCount(row.top5_buy_net)} · sell {formatCount(row.top5_sell_net)}</p>
      <p className="font-mono text-text-secondary">Ratio {row.ratio === null ? '—' : `${row.ratio.toFixed(2)}×`}</p>
    </div>
  );
}

export default function FlowOverlayChart({ points }: { points: FlowPoint[] }) {
  if (!points.length) return <p className="py-10 text-center text-xs text-text-muted">No sessions in this range.</p>;

  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={points} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={36} tick={{ fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="flow" tickFormatter={compact} width={44} tick={{ fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="price" orientation="right" domain={['auto', 'auto']} width={52} tick={{ fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
        <ReferenceLine yAxisId="flow" y={0} stroke={MUTED} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(59,130,246,0.08)' }} />
        <Bar yAxisId="flow" dataKey="net_flow" maxBarSize={14} radius={2}>
          {points.map((point) => <Cell key={point.date} fill={point.net_flow >= 0 ? BUY : SELL} fillOpacity={0.75} />)}
        </Bar>
        <Line yAxisId="price" dataKey="close" stroke={PRICE} strokeWidth={2} dot={points.length <= 5} connectNulls />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
