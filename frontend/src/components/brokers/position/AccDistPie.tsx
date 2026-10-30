// Share of the broker's buying (accumulation) or selling (distribution) across the selected stocks:
// a donut plus a ranked list with shares and percentages, so no value relies on colour alone.
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { formatCount } from '../../market/format';
import { seriesColor } from './format';

export interface PieSlice {
  symbol: string;
  slot: number;
  value: number;
}

export default function AccDistPie({ slices, side }: { slices: PieSlice[]; side: 'bought' | 'sold' }) {
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  if (!total) {
    return <p className="py-16 text-center text-sm text-text-muted">The broker {side === 'bought' ? 'bought' : 'sold'} nothing in the shown stocks in this range.</p>;
  }
  const ranked = [...slices].sort((a, b) => b.value - a.value);
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6 py-4">
      <div className="relative h-[280px] w-[280px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={slices.filter((s) => s.value > 0)} dataKey="value" nameKey="symbol" innerRadius={78} outerRadius={128}
              stroke="var(--trading-panel)" strokeWidth={2} isAnimationActive={false}>
              {slices.filter((s) => s.value > 0).map((s) => <Cell key={s.symbol} fill={seriesColor(s.slot)} />)}
            </Pie>
            <Tooltip formatter={(value, name) => [`${formatCount(Number(value))} (${((Number(value) / total) * 100).toFixed(1)}%)`, String(name)]}
              contentStyle={{ background: 'var(--trading-panel)', border: '1px solid var(--trading-grid)', borderRadius: 8, fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[11px] text-text-muted">{side === 'bought' ? 'Total bought' : 'Total sold'}</span>
          <span className="font-mono text-lg font-semibold text-text-primary">{formatCount(total)}</span>
        </div>
      </div>
      <div className="w-full max-w-md">
        {ranked.map((s) => (
          <div key={s.symbol} className="grid grid-cols-[14px_1fr_auto_auto] items-center gap-3 border-b border-bg-border px-1 py-2 text-sm">
            <span className="h-3 w-3 rounded-full" style={{ background: seriesColor(s.slot) }} />
            <span className="font-semibold text-text-primary">{s.symbol}</span>
            <span className="font-mono text-text-secondary">{formatCount(s.value)}</span>
            <span className="w-14 text-right font-mono text-text-muted">{((s.value / total) * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
