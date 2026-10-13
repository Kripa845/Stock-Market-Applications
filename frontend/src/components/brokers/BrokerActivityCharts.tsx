import { useMemo, useState } from 'react';
import { LineChart as LineChartIcon } from 'lucide-react';
import {
  Area, Bar, CartesianGrid, ComposedChart, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { BrokerDetailResponse } from '../../api/analysis';

// Broker profile charts: turnover line over total-volume bars, and buy (up) / sell (down) quantity bars.

const TURNOVER = '#3b82f6';
const BUY = '#10b981';
const SELL = '#f43f5e';
const GRID = 'var(--trading-grid)';
const MUTED = 'var(--trading-muted)';
const RANGES = ['1M', '3M', '6M', '1Y', 'ALL'] as const;
const RANGE_DAYS: Record<string, number> = { '1M': 31, '3M': 92, '6M': 183, '1Y': 366 };

type Range = typeof RANGES[number];
interface Row { date: string; turnover: number; volume: number; buy: number; sell: number }

const compact = (value: number) => {
  const abs = Math.abs(value);
  const [div, suffix] = abs >= 1e9 ? [1e9, 'B'] : abs >= 1e6 ? [1e6, 'M'] : abs >= 1e3 ? [1e3, 'K'] : [1, ''];
  return `${(value / div).toFixed(div === 1 ? 0 : 1).replace(/\.0$/, '')}${suffix}`;
};
const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
const fullDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

function ChartTooltip({ active, payload, kind }: { active?: boolean; payload?: { payload: Row }[]; kind: 'turnover' | 'quantity' }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return <div className="rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
    <p className="mb-1 text-text-muted">{fullDate(row.date)}</p>
    {kind === 'turnover' ? <>
      <p className="font-mono" style={{ color: TURNOVER }}>Turnover Rs {row.turnover.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
      <p className="font-mono text-text-secondary">Volume {row.volume.toLocaleString()}</p>
    </> : <>
      <p className="font-mono" style={{ color: BUY }}>Bought {row.buy.toLocaleString()}</p>
      <p className="font-mono" style={{ color: SELL }}>Sold {Math.abs(row.sell).toLocaleString()}</p>
      <p className="font-mono text-text-secondary">Net {(row.buy + row.sell).toLocaleString()}</p>
    </>}
  </div>;
}

const Title = ({ children }: { children: string }) =>
  <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary"><LineChartIcon size={14} className="text-text-muted" />{children}</h2>;

const xAxis = <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={48} tick={{ fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />;

export default function BrokerActivityCharts({ daily, sessions }: { daily: BrokerDetailResponse['daily_activity']; sessions: string[] }) {
  const [range, setRange] = useState<Range>('3M');
  const rows = useMemo<Row[]>(() => {
    // Walk every market session so days this broker sat out show as zero instead of disappearing.
    const byDate = new Map(daily.map(row => [row.date, row]));
    const timeline = [...new Set([...sessions, ...byDate.keys()])].sort();
    const days = RANGE_DAYS[range];
    const last = timeline.length ? new Date(`${timeline[timeline.length - 1]}T00:00:00`).getTime() : 0;
    return timeline
      .filter(date => !days || new Date(`${date}T00:00:00`).getTime() >= last - days * 86400000)
      .map(date => {
        const row = byDate.get(date);
        return {
          date,
          turnover: row ? Number(row.buy_value) + Number(row.sell_value) : 0,
          volume: row ? row.buy_quantity + row.sell_quantity : 0,
          buy: row?.buy_quantity ?? 0,
          sell: -(row?.sell_quantity ?? 0),
        };
      });
  }, [daily, sessions, range]);
  const idle = rows.filter(row => row.volume === 0).length;
  const maxVolume = Math.max(0, ...rows.map(row => row.volume));
  const maxSide = Math.max(1, ...rows.map(row => Math.max(row.buy, -row.sell)));
  const empty = <p className="py-10 text-center text-xs text-text-muted">No captured sessions in this period.</p>;

  return <div className="space-y-4">
    <div className="card">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <Title>Broker Turnover &amp; Volume</Title>
          {rows.length > 0 && <p className="mt-0.5 text-[10px] text-text-muted">
            {fullDate(rows[0].date)} – {fullDate(rows[rows.length - 1].date)} · {rows.length} sessions{idle > 0 && ` · ${idle} with no trades by this broker`}
          </p>}
        </div>
        <div className="flex gap-1 rounded-md border border-bg-border p-0.5">
          {RANGES.map(item => <button key={item} onClick={() => setRange(item)}
            className={`rounded px-2.5 py-1 text-[11px] font-semibold ${range === item ? 'bg-bg-elevated text-text-primary' : 'text-text-muted hover:text-text-primary'}`}>{item}</button>)}
        </div>
      </div>
      {rows.length ? <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={rows} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="broker-turnover" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={TURNOVER} stopOpacity={0.25} />
              <stop offset="100%" stopColor={TURNOVER} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          {xAxis}
          <YAxis yAxisId="turnover" orientation="right" width={64} domain={['auto', 'auto']} tickFormatter={(v: number) => `Rs ${compact(v)}`} tick={{ fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
          {/* Volume bars use the bottom fifth of the chart. */}
          <YAxis yAxisId="volume" hide domain={[0, maxVolume * 5 || 1]} />
          <Legend verticalAlign="top" align="left" height={24} iconSize={8} wrapperStyle={{ fontSize: 11, color: MUTED }} />
          <Bar yAxisId="volume" dataKey="volume" name="Total volume" fill={TURNOVER} fillOpacity={0.35} legendType="circle" isAnimationActive={false} />
          <Area yAxisId="turnover" type="linear" dataKey="turnover" name="Turnover" stroke={TURNOVER} strokeWidth={1.5} fill="url(#broker-turnover)" dot={false} legendType="plainline" isAnimationActive={false} />
          <Tooltip content={<ChartTooltip kind="turnover" />} cursor={{ stroke: MUTED, strokeDasharray: '3 3' }} />
        </ComposedChart>
      </ResponsiveContainer> : empty}
    </div>

    <div className="card">
      <div className="mb-2"><Title>Buy / Sell Quantity Trend</Title></div>
      {rows.length ? <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={rows} stackOffset="sign" margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          {xAxis}
          <YAxis orientation="right" width={64} domain={[-maxSide, maxSide]} tickFormatter={compact} tick={{ fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
          <ReferenceLine y={0} stroke={MUTED} strokeOpacity={0.5} />
          <Bar dataKey="buy" name="Bought" stackId="side" fill={BUY} isAnimationActive={false} />
          <Bar dataKey="sell" name="Sold" stackId="side" fill={SELL} isAnimationActive={false} />
          <Tooltip content={<ChartTooltip kind="quantity" />} cursor={{ fill: 'rgba(120,123,134,0.12)' }} />
        </ComposedChart>
      </ResponsiveContainer> : empty}
    </div>
  </div>;
}
